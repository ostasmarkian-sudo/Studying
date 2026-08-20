import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

DATABASE_CONNECTION = {
    "dbname": "product_avnet",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
}

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

COLUMNS = (
    "article_id",
    "sku",
    "variant",
    "name",
    "brand",
    "price",
    "rrp",
    "discount",
    "currency",
    "category",
    "category_id",
    "stock_state",
    "dispatch_days",
    "availability",
    "rating",
    "reviews",
    "url",
    "image",
    "description",
    "data_hash",
)

UPSERT_SQL = """
    INSERT INTO automation24_products ({columns})
    VALUES ({placeholders})
    ON CONFLICT (article_id) DO UPDATE SET
        {assignments},
        updated_at = CASE
            WHEN automation24_products.data_hash IS DISTINCT FROM EXCLUDED.data_hash
            THEN now() ELSE automation24_products.updated_at
        END,
        last_seen_at = now()
""".format(
    columns=", ".join(COLUMNS),
    placeholders=", ".join(["%s"] * len(COLUMNS)),
    assignments=",\n        ".join(
        f"{column} = EXCLUDED.{column}" for column in COLUMNS if column != "article_id"
    ),
)

STOCK_STATES = (
    ("few in stock", "few"),
    ("in stock", "in_stock"),
    ("currently out of stock", "reserve"),
    ("order item", "order_item"),
    ("not available", "unavailable"),
)

DISPATCH_NEXT_DAY = re.compile(r"dispatch next working day")
DISPATCH_IN_DAYS = re.compile(r"dispatch expected in (\d+) working day")


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
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_availability(text):
    """('in stock Dispatch next working day') -> ('in_stock', 1)."""
    if not text:
        return None, None
    lowered = text.lower()
    state = next(
        (name for prefix, name in STOCK_STATES if lowered.startswith(prefix)), None
    )
    if DISPATCH_NEXT_DAY.search(lowered):
        days = 1
    else:
        match = DISPATCH_IN_DAYS.search(lowered)
        days = int(match.group(1)) if match else None
    return state, days


def _hash(values):
    payload = {
        column: value
        for column, value in values.items()
        if column not in ("data_hash", "availability")
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).digest()


def build_row(product):
    """Розкладає один розпарсений товар по COLUMNS, у їх порядку."""
    state, days = parse_availability(product.get("availability"))
    values = {
        "article_id": _int(product.get("article_id")),
        "sku": _text(product.get("sku")),
        "variant": _int(product.get("variant")),
        "name": _text(product.get("name")),
        "brand": _text(product.get("brand")),
        "price": _num(product.get("price")),
        "rrp": _num(product.get("rrp")),
        "discount": _num(product.get("discount")),
        "currency": _text(product.get("currency")),
        "category": _text(product.get("category")),
        "category_id": _int(product.get("category_id")),
        "stock_state": state,
        "dispatch_days": days,
        "availability": _text(product.get("availability")),
        "rating": _num(product.get("rating")),
        "reviews": _int(product.get("reviews")),
        "url": _text(product.get("url")),
        "image": _text(product.get("image")),
        "description": _text(product.get("description")),
    }
    values["data_hash"] = _hash(values)
    return tuple(values[column] for column in COLUMNS)


def init_db():
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def save_products(products):
    if not products:
        return 0, 0
    rows, skipped = [], 0
    for product in products:
        row = build_row(product)
        if row[0] is None or not row[1] or not row[3] or not row[16]:
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


def run_stats(since):
    """(усього рядків, нових за прогін, змінених за прогін, побачених за прогін)."""
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        return connection.execute(
            """
            SELECT (SELECT count(*) FROM automation24_products),
                   (SELECT count(*) FROM automation24_products WHERE first_seen_at >= %s),
                   (SELECT count(*) FROM automation24_products
                     WHERE updated_at >= %s AND first_seen_at < %s),
                   (SELECT count(*) FROM automation24_products WHERE last_seen_at >= %s)
            """,
            (since, since, since, since),
        ).fetchone()
