import psycopg
import asyncio
from psycopg.rows import dict_row
import os

# PASSWORD = os.environ["PASSWORD"]
DATABASE_CONECTION = {
    "dbname": "product_dk",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
    "row_factory": dict_row,
}


async def data_recording(filtered_products):
    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONECTION
    ) as connection:
        async with await connection.cursor() as cursor:
            await cursor.executemany(
                """
                INSERT INTO product_unique(product_id,name,company,series,price,product_count,package)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (product_id)
                DO UPDATE SET
                price = EXCLUDED.price,
                product_count = EXCLUDED.product_count,
                updated_at = NOW()
                """,
                filtered_products,
            )
