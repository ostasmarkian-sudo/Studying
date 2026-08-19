import asyncio
import hashlib
import json
from datetime import date
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

DATABASE_CONNECTION = {
    "dbname": "product_avnet",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
}

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DROP_ALWAYS = frozenset(
    {
        "Type",
        "Sboat",
        "ERPSystemName",
        "DivisionCodeName",
        "DeleteFlag",
        "Published",
        "WebCode",
        "PIMBlock",
        "DesignIds",
        "AllocationFlag",
        "FactoryLeadTime",
        "NPIFlag",
        "SoftwareFlag",
        "ITARFlag",
        "MilitaryProductFlag",
        "PackageSizeMandatoryFlag",
        "IsDesignsAvailable",
        "@search.score",
        "sys_update_dt",
        "sys_delta_dt",
        "ItemRowNumber",
        "ERPPartCreateDate",  # == ActiveDate
        "Structuregroupidentifier",  # == deepest Level_N_ID
        "ImagePath",
        "ThumbnailPath",
        "AssetPath",
        "AssetURL",
        # presentation-only and not returned consistently: the same part
        # arrives with them from one category and without from another,
        # which used to flip data_hash and fabricate empty history versions
        "Level_1_URL",
        "Level_2_URL",
        "Level_3_URL",
        "Level_4_URL",
        "ManufacturerURL",
        "ManufacturerLogo",
        "TopProducts",
    }
)

PROMOTED = frozenset(
    {
        "ItemNumber",
        "ERPPartNumber",
        "WCSPartNumber",
        "VariantNumber",
        "ManufacturerCode",
        "ManufacturerName",
        "ERPManufacturerCode",
        "ERPSupplierCode",
        "ManufacturerPartNumber",
        "ERPMFRPartNumber",
        "VendorPartNumber",
        "Level_1_Name",
        "Level_2_Name",
        "Level_3_Name",
        "Level_4_Name",
        "SAPMatgroup",
        "Instock",
        "Stock",
        "QtyMin",
        "QtyMult",
        "Werks",
        "PackagingTypeCode",
        "ERPProductStatus",
        "ActiveDate",
        "ObsoleteFlag",
        "EndofLifeFlag",
        "LifeCycleRisk",
        "SupplyChainRisk",
        "EnvironmentalRisk",
        "ROHSCompliantCode",
        "ReachCompliantFlag",
        "HTSCode",
        "ECCNCode",
        "ShortDescription",
        "LongDescription",
        "ManufacturerDatasheetURL",
        "IHSManufacturerDatasheetURL",
        "Attributes",
    }
)

COLUMNS = (
    "item_number",
    "erp_part_number",
    "wcs_part_number",
    "variant_number",
    "mfr_code",
    "mfr_name",
    "erp_mfr_code",
    "erp_supplier_code",
    "mpn",
    "erp_mfr_part",
    "vendor_part",
    "cat_l1",
    "cat_l2",
    "cat_l3",
    "cat_l4",
    "sap_matgroup",
    "in_stock",
    "stock",
    "qty_min",
    "qty_mult",
    "warehouse",
    "packaging",
    "erp_status",
    "price",
    "active_date",
    "obsolete",
    "eol",
    "lifecycle_risk",
    "supply_risk",
    "env_risk",
    "rohs_code",
    "reach_compliant",
    "hts_code",
    "eccn_code",
    "short_description",
    "long_description",
    "datasheet_url",
    "ihs_datasheet_url",
    "attrs",
    "attr_ranges",
    "raw",
    "data_hash",
)

# Columns the schema declares NOT NULL. One offending product would abort the
# whole executemany (and with it the batch), so they are checked per row and
# the bad row is skipped and reported instead.
REQUIRED_COLUMNS = tuple(
    (column, COLUMNS.index(column))
    for column in (
        "item_number",
        "erp_part_number",
        "mfr_code",
        "mfr_name",
        "mpn",
        "cat_l1",
    )
)


def _assignment(column):
    # price does not come from the search API, so an upsert must never blank out
    # a price that some other job has already filled in.
    if column == "price":
        return "price = COALESCE(EXCLUDED.price, products.price)"
    return f"{column} = EXCLUDED.{column}"


# item_number is the conflict key and first_seen_at must survive updates, so
# neither is reassigned here.
UPSERT_SQL = """
    INSERT INTO products ({columns})
    VALUES ({placeholders})
    ON CONFLICT (item_number) DO UPDATE SET
        {assignments},
        updated_at = now()
    WHERE products.data_hash IS DISTINCT FROM EXCLUDED.data_hash
""".format(
    columns=", ".join(COLUMNS),
    placeholders=", ".join(["%s"] * len(COLUMNS)),
    assignments=",\n        ".join(
        _assignment(column) for column in COLUMNS if column != "item_number"
    ),
)

# The upsert above skips rows whose payload is unchanged, so "this part was
# still in the catalog on this run" is recorded separately, in a narrow table
# where rewriting every row per run stays cheap (see schema.sql).
SEEN_SQL = """
    INSERT INTO products_seen (item_number, last_seen_at)
    SELECT unnest(%s::text[]), now()
    ON CONFLICT (item_number) DO UPDATE SET last_seen_at = now()
"""


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value):
    """Avnet spells booleans as Yes/No, Y/N or true/false depending on field."""
    if value is None or value == "":
        return None
    return str(value).strip().lower() in {"yes", "y", "true", "1"}


def _date(value):
    # "1999-09-11T00:00:00Z" -> date(1999, 9, 11)
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def clean_product(product):
    """Split one API product into (leftover raw, attrs, attr_ranges).

    Attributes arrive as a list of six-key objects where ATTCOMBO is always
    ATTRNAME|#|ATTRVAL and MINVAL == MAXVAL for 98.5% of them, so folding them
    into a flat mapping drops most of the payload without losing anything.
    """
    attrs, ranges = {}, {}
    for attribute in product.get("Attributes") or []:
        name = attribute.get("ATTRNAME")
        if not name:
            continue
        attrs[name] = attribute.get("ATTRVAL")
        if attribute.get("MINVAL") != attribute.get("MAXVAL"):
            ranges[name] = {
                "min": attribute.get("MINVAL"),
                "max": attribute.get("MAXVAL"),
            }

    raw = {
        key: value
        for key, value in product.items()
        if key not in DROP_ALWAYS
        and key not in PROMOTED
        and value is not None
        and value != ""
        and value != []
    }
    return raw, attrs, (ranges or None)


def _hash(values):
    """Fingerprint of exactly the row we store, not of the payload we received.

    Hashing the payload meant a field that lands in no column could still flip
    the hash, while cat_l2's category fallback - which is not in the payload at
    all - could change without the hash noticing.
    """
    payload = {
        column: (value.obj if isinstance(value, Jsonb) else value)
        for column, value in values.items()
        if column != "data_hash"
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def build_row(product, category=None):
    """Map one API product onto COLUMNS, in order."""
    raw, attrs, ranges = clean_product(product)
    values = {
        "item_number": _text(product.get("ItemNumber")),
        "erp_part_number": _text(product.get("ERPPartNumber")),
        "wcs_part_number": _text(product.get("WCSPartNumber")),
        "variant_number": _text(product.get("VariantNumber")),
        "mfr_code": _text(product.get("ManufacturerCode")),
        "mfr_name": _text(product.get("ManufacturerName")),
        "erp_mfr_code": _text(product.get("ERPManufacturerCode")),
        "erp_supplier_code": _text(product.get("ERPSupplierCode")),
        # obsolete parts often carry no ManufacturerPartNumber and spell the
        # same number out only in the ERP/vendor fields (e.g. Molex 22012035)
        "mpn": (
            _text(product.get("ManufacturerPartNumber"))
            or _text(product.get("ERPMFRPartNumber"))
            or _text(product.get("VendorPartNumber"))
        ),
        "erp_mfr_part": _text(product.get("ERPMFRPartNumber")),
        "vendor_part": _text(product.get("VendorPartNumber")),
        "cat_l1": _text(product.get("Level_1_Name")),
        # the payload matched the requested category in all 29 444 rows, so the
        # name we asked for is only a fallback
        "cat_l2": _text(product.get("Level_2_Name")) or _text(category),
        "cat_l3": _text(product.get("Level_3_Name")),
        "cat_l4": _text(product.get("Level_4_Name")),
        "sap_matgroup": _text(product.get("SAPMatgroup")),
        "in_stock": bool(_bool(product.get("Instock"))),
        "stock": _int(product.get("Stock")),
        "qty_min": _int(product.get("QtyMin")),
        "qty_mult": _int(product.get("QtyMult")),
        "warehouse": _text(product.get("Werks")),
        "packaging": _text(product.get("PackagingTypeCode")),
        "erp_status": _text(product.get("ERPProductStatus")),
        # never present in the search API today; here for the separate price
        # source that will fill it in
        "price": _num(product.get("Price")),
        "active_date": _date(product.get("ActiveDate")),
        "obsolete": _bool(product.get("ObsoleteFlag")),
        "eol": _bool(product.get("EndofLifeFlag")),
        "lifecycle_risk": _text(product.get("LifeCycleRisk")),
        "supply_risk": _text(product.get("SupplyChainRisk")),
        "env_risk": _text(product.get("EnvironmentalRisk")),
        "rohs_code": _text(product.get("ROHSCompliantCode")),
        "reach_compliant": _bool(product.get("ReachCompliantFlag")),
        "hts_code": _text(product.get("HTSCode")),
        "eccn_code": _text(product.get("ECCNCode")),
        "short_description": _text(product.get("ShortDescription")),
        "long_description": _text(product.get("LongDescription")),
        "datasheet_url": _text(product.get("ManufacturerDatasheetURL")),
        "ihs_datasheet_url": _text(product.get("IHSManufacturerDatasheetURL")),
        "attrs": Jsonb(attrs),
        "attr_ranges": Jsonb(ranges) if ranges else None,
        "raw": Jsonb(raw),
    }
    values["data_hash"] = _hash(values)
    return tuple(values[column] for column in COLUMNS)


def _init_db_sync():
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


async def init_db():
    # psycopg's async mode needs a SelectorEventLoop, but patchright needs a
    # ProactorEventLoop on Windows for subprocess support - run sync psycopg
    # in a worker thread instead of fighting over the loop implementation.
    await asyncio.to_thread(_init_db_sync)


def _constraint(error):
    return error.diag.constraint_name or type(error).__name__


def _upsert(cursor, rows, item_numbers):
    cursor.executemany(UPSERT_SQL, rows)
    written = cursor.rowcount
    cursor.execute(SEEN_SQL, (item_numbers,))
    return written


def _save_products_sync(category, products):
    rows, item_numbers, skipped = [], [], []
    for product in products:
        row = build_row(product, category)
        missing = [column for column, index in REQUIRED_COLUMNS if row[index] is None]
        if missing:
            skipped.append(f"{product.get('ItemNumber')} [{', '.join(missing)}]")
            continue
        rows.append(row)
        item_numbers.append(row[0])
    if not rows:
        if skipped:
            print(f"  {category}: skipped {len(skipped)}, first {skipped[0]}")
        return 0, len(skipped)

    # SEEN_SQL is one INSERT ... ON CONFLICT and Postgres refuses to let a single
    # statement touch the same row twice, so a repeated ItemNumber inside one
    # response would abort the transaction and take the whole batch with it.
    item_numbers = list(dict.fromkeys(item_numbers))

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            try:
                with connection.transaction():
                    written = _upsert(cursor, rows, item_numbers)
            except psycopg.errors.IntegrityError as error:
                # erp_part_number is UNIQUE while the upsert only knows how to
                # resolve conflicts on item_number, so one part that reuses
                # another's ERPPartNumber would otherwise roll back all 2000
                # rows of the batch. Replay them one at a time (a savepoint
                # each) and lose only the offenders.
                print(
                    f"  {category}: batch rejected ({_constraint(error)}),"
                    " replaying row by row"
                )
                written = 0
                for row in rows:
                    try:
                        with connection.transaction():
                            written += _upsert(cursor, [row], [row[0]])
                    except psycopg.errors.IntegrityError as row_error:
                        skipped.append(f"{row[0]} [{_constraint(row_error)}]")
    if skipped:
        print(f"  {category}: skipped {len(skipped)}, first {skipped[0]}")
    return written, len(skipped)


async def save_products(category, products):
    """Returns (written, skipped) for one batch.

    `written` counts only rows the upsert actually touched: a product whose
    payload is byte-for-byte what the table already holds is skipped by the
    upsert's data_hash guard, so a re-run over an unchanged catalog reports 0
    written and that is correct, not a failure. products_seen.last_seen_at is
    still bumped for every one of them.
    """
    if not products:
        return 0, 0
    return await asyncio.to_thread(_save_products_sync, category, products)


def _run_stats_sync(since):
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        return connection.execute(
            """
            SELECT (SELECT count(*) FROM products),
                   (SELECT count(*) FROM products WHERE first_seen_at >= %s),
                   (SELECT count(*) FROM products WHERE updated_at >= %s
                                                    AND first_seen_at < %s),
                   (SELECT count(*) FROM products_seen WHERE last_seen_at >= %s)
            """,
            (since, since, since, since),
        ).fetchone()


async def run_stats(since):
    """(total rows, inserted this run, updated this run, seen this run)."""
    return await asyncio.to_thread(_run_stats_sync, since)
