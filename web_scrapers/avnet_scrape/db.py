import asyncio
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


def _init_db_sync():
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


async def init_db():
    # psycopg's async mode needs a SelectorEventLoop, but patchright needs a
    # ProactorEventLoop on Windows for subprocess support - run sync psycopg
    # in a worker thread instead of fighting over the loop implementation.
    await asyncio.to_thread(_init_db_sync)


def _save_products_sync(category, products):
    rows = [
        (
            product["ItemNumber"],
            product.get("ManufacturerPartNumber"),
            product.get("ManufacturerName"),
            category,
            Jsonb(product),
        )
        for product in products
    ]
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO products (item_number, manufacturer_part_number, manufacturer_name, category, data)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (item_number) DO UPDATE SET
                    manufacturer_part_number = EXCLUDED.manufacturer_part_number,
                    manufacturer_name = EXCLUDED.manufacturer_name,
                    category = EXCLUDED.category,
                    data = EXCLUDED.data,
                    updated_at = now()
                WHERE products.data IS DISTINCT FROM EXCLUDED.data
                """,
                rows,
            )


async def save_products(category, products):
    if not products:
        return
    await asyncio.to_thread(_save_products_sync, category, products)
