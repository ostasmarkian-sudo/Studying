import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
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

UUID_RE = re.compile(r"^[0-9a-f]{32}$")


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _num(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _hash(values):
    """Fingerprint of the stored fields, so updated_at only moves on a real change."""
    payload = {
        column: value
        for column, value in values.items()
        if column not in ("data_hash", "availability", "price_display")
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def init_db():
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


# --- catalogue ---------------------------------------------------------------

COLUMNS = (
    "uuid",
    "sku",
    "name",
    "brand",
    "mpn",
    "gtin",
    "price",
    "price_min",
    "price_is_from",
    "currency",
    "price_display",
    "stock_state",
    "availability",
    "variants",
    "categories",
    "url",
    "image",
    "description",
    "price_tiers",
    "parent_uuid",
    "data_hash",
)

UPSERT_SQL = """
    INSERT INTO stex24_products ({columns})
    VALUES ({placeholders})
    ON CONFLICT (uuid) DO UPDATE SET
        {assignments},
        updated_at = CASE
            WHEN stex24_products.data_hash IS DISTINCT FROM EXCLUDED.data_hash
            THEN now() ELSE stex24_products.updated_at
        END,
        last_seen_at = now()
""".format(
    columns=", ".join(COLUMNS),
    placeholders=", ".join(["%s"] * len(COLUMNS)),
    assignments=",\n        ".join(
        # categories belong to discover_catalog; the API pass never sees them
        f"{column} = EXCLUDED.{column}"
        for column in COLUMNS
        if column not in ("uuid", "categories")
    ),
)

# Deliberately narrow upsert for discover: it only knows a uuid and the branch
# the product turned up in, so it has no business touching any other column.
# Categories are merged into what is already there rather than overwritten,
# because the same product sits in several branches.
UUID_UPSERT_SQL = """
    INSERT INTO stex24_products (uuid, categories, data_hash)
    VALUES (%s, %s, %s)
    ON CONFLICT (uuid) DO UPDATE SET
        categories = (
            SELECT array_agg(DISTINCT c ORDER BY c)
            FROM unnest(stex24_products.categories || EXCLUDED.categories) AS c
        ),
        last_seen_at = now()
"""


def build_row(product):
    """Lay one API product out along COLUMNS, in their order.

    Volume pricing arrives as a list of tiers, dearest first. The single-unit
    price is the first tier, price_min the last.
    """
    tiers = product.get("price_tiers") or []
    price = _num(product.get("price"))
    if price is None and tiers:
        price = _num(tiers[0].get("price"))

    values = {
        "uuid": _text(product.get("uuid")),
        "sku": _text(product.get("sku")),
        "name": _text(product.get("name")),
        "brand": _text(product.get("brand")),
        "mpn": _text(product.get("mpn")),
        "gtin": _text(product.get("gtin")),
        "price": price,
        "price_min": _num(tiers[-1].get("price")) if tiers else price,
        "price_is_from": len(tiers) > 1,
        "currency": _text(product.get("currency")),
        "price_display": None,  # legacy: markup string, superseded by price_tiers
        "stock_state": "in_stock" if product.get("available") else "out_of_stock",
        "availability": None,  # legacy: schema.org value from the JSON-LD block
        "variants": _int(product.get("variants")),
        "categories": sorted({c for c in (product.get("categories") or []) if c}),
        "url": _text(product.get("url")),
        "image": _text(product.get("image")),
        "description": _text(product.get("description")),
        "price_tiers": Jsonb(tiers) if tiers else None,
        "parent_uuid": _text(product.get("parent_uuid")),
    }
    values["data_hash"] = _hash(values)
    return tuple(values[column] for column in COLUMNS)


def save_uuids(rows):
    """Write from discover: a uuid and the branch it turned up in, nothing else."""
    prepared = []
    for uuid, categories in rows:
        uuid = _text(uuid)
        if not uuid or not UUID_RE.match(uuid):
            continue
        prepared.append((uuid, sorted({c for c in categories if c}), _hash({"uuid": uuid})))
    if not prepared:
        return 0

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(UUID_UPSERT_SQL, prepared)
    return len(prepared)


def save_products(products):
    if not products:
        return 0, 0
    rows, skipped = [], 0
    for product in products:
        row = build_row(product)
        if not row[0] or not UUID_RE.match(row[0]):
            skipped += 1
            continue
        rows.append(row)
    rows = list({row[0]: row for row in rows}.values())
    if not rows:
        return 0, skipped

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_SQL, rows)
    return len(rows), skipped


def fetch_uuids(limit=None):
    """[(uuid, sku, name)] - the input the API pass works from."""
    sql = "SELECT uuid, sku, name FROM stex24_products ORDER BY uuid"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        return connection.execute(sql).fetchall()


def run_stats(since):
    """(rows in total, new this run, changed this run, seen this run)."""
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        return connection.execute(
            """
            SELECT (SELECT count(*) FROM stex24_products),
                   (SELECT count(*) FROM stex24_products WHERE first_seen_at >= %s),
                   (SELECT count(*) FROM stex24_products
                     WHERE updated_at >= %s AND first_seen_at < %s),
                   (SELECT count(*) FROM stex24_products WHERE last_seen_at >= %s)
            """,
            (since, since, since, since),
        ).fetchone()


# --- stock -------------------------------------------------------------------

STOCK_COLUMNS = (
    "uuid",
    "sku",
    "express_qty",
    "external_qty",
    "total_qty",
    "ordered_qty",
    "available",
    "delivery_time",
    "delivery_min",
    "delivery_max",
    "restock_time",
    "data_hash",
)

STOCK_UPSERT_SQL = """
    INSERT INTO stex24_stock ({columns})
    VALUES ({placeholders})
    ON CONFLICT (uuid) DO UPDATE SET
        {assignments},
        updated_at = CASE
            WHEN stex24_stock.data_hash IS DISTINCT FROM EXCLUDED.data_hash
            THEN now() ELSE stex24_stock.updated_at
        END,
        last_seen_at = now()
""".format(
    columns=", ".join(STOCK_COLUMNS),
    placeholders=", ".join(["%s"] * len(STOCK_COLUMNS)),
    assignments=",\n        ".join(
        f"{column} = EXCLUDED.{column}" for column in STOCK_COLUMNS if column != "uuid"
    ),
)


def build_stock_row(record):
    """Lay one stock record out along STOCK_COLUMNS, in their order."""
    express = _int(record.get("express_qty"))
    external = _int(record.get("external_qty"))
    total = (
        None
        if express is None and external is None
        else (express or 0) + (external or 0)
    )

    values = {
        "uuid": _text(record.get("uuid")),
        "sku": _text(record.get("sku")),
        "express_qty": express,
        "external_qty": external,
        "total_qty": total,
        "ordered_qty": _int(record.get("ordered_qty")),
        "available": record.get("available"),
        "delivery_time": _text(record.get("delivery_time")),
        "delivery_min": _int(record.get("delivery_min")),
        "delivery_max": _int(record.get("delivery_max")),
        "restock_time": _int(record.get("restock_time")),
    }
    values["data_hash"] = _hash(values)
    return tuple(values[column] for column in STOCK_COLUMNS)


def save_stock(records):
    if not records:
        return 0, 0
    rows, skipped = [], 0
    for record in records:
        row = build_stock_row(record)
        if not row[0] or not UUID_RE.match(row[0]):
            skipped += 1
            continue
        rows.append(row)
    rows = list({row[0]: row for row in rows}.values())
    if not rows:
        return 0, skipped

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(STOCK_UPSERT_SQL, rows)
    return len(rows), skipped


def stock_stats(since):
    """(rows in total, new this run, changed this run, seen this run)."""
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        return connection.execute(
            """
            SELECT (SELECT count(*) FROM stex24_stock),
                   (SELECT count(*) FROM stex24_stock WHERE first_seen_at >= %s),
                   (SELECT count(*) FROM stex24_stock
                     WHERE updated_at >= %s AND first_seen_at < %s),
                   (SELECT count(*) FROM stex24_stock WHERE last_seen_at >= %s)
            """,
            (since, since, since, since),
        ).fetchone()
