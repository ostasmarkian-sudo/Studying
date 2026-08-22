import asyncio
from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation

import psycopg

# PASSWORD = os.environ["PASSWORD"]
DATABASE_CONNECTION = {
    "dbname": "product_dk",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
}

# The column order of the INSERT, and the only place it is written down.
# Product's own field order is a different one - price and company sit where
# company and series sit here - so a row must never be built by unpacking the
# dataclass. That mismatch is what pushed price into the company column and
# made the whole batch fail on the first insert.
COLUMNS = (
    "product_id",
    "name",
    "company",
    "series",
    "price",
    "product_count",
    "package",
)

# Only the moving fields are refreshed on conflict: product_unique holds one
# row per part, and the card (name, company, series, package) does not change
# between runs the way price and stock do.
UPSERT_SQL = """
    INSERT INTO product_unique ({columns})
    VALUES ({placeholders})
    ON CONFLICT (product_id) DO UPDATE SET
        price = EXCLUDED.price,
        product_count = EXCLUDED.product_count,
        updated_at = now()
""".format(
    columns=", ".join(COLUMNS),
    placeholders=", ".join(["%s"] * len(COLUMNS)),
)


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _int(value):
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _num(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def build_row(product):
    """Lay one product out along COLUMNS, in their order.

    Takes the Product dataclass filter_data yields, a plain dict, or anything
    else with those attributes. Returns None for a product with no usable
    product_id - that is the key the upsert conflicts on, so a row without it
    has nowhere to go.
    """
    if is_dataclass(product) and not isinstance(product, type):
        values = {field.name: getattr(product, field.name) for field in fields(product)}
    else:
        values = dict(product)

    # product_id is a bigint in the table while filter_data hands over a string
    product_id = _int(values.get("product_id"))
    if product_id is None:
        return None

    row = {
        "product_id": product_id,
        "name": _text(values.get("name")),
        "company": _text(values.get("company")),
        "series": _text(values.get("series")),
        "price": _num(values.get("price")),
        # product_count is NOT NULL DEFAULT 0, and a default only applies to a
        # column left out of the INSERT - an explicit None still breaks it.
        # filter_data yields None whenever the quantity cell is missing, so
        # read that as the column's own default rather than losing the row.
        "product_count": _int(values.get("product_count")) or 0,
        "package": _text(values.get("package")),
    }
    return tuple(row[column] for column in COLUMNS)


def _data_recording_sync(filtered_products):
    rows, skipped = [], 0
    for product in filtered_products:
        row = build_row(product)
        if row is None:
            skipped += 1
            continue
        rows.append(row)

    # Keep the last row per product_id: the same part turns up on more than one
    # page of a family, and there is no point writing the same key twice.
    rows = list({row[0]: row for row in rows}.values())
    if not rows:
        return 0, skipped

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_SQL, rows)
            written = cursor.rowcount
    return written, skipped


async def data_recording(filtered_products):
    """Write one batch, returns (written, skipped).

    psycopg's async mode needs a SelectorEventLoop, but patchright needs a
    ProactorEventLoop on Windows to spawn the browser subprocess, and one loop
    cannot be both. Sync psycopg in a worker thread sidesteps that fight and
    still keeps the browser responsive while the batch is being written.
    """
    if not filtered_products:
        return 0, 0
    return await asyncio.to_thread(_data_recording_sync, filtered_products)
