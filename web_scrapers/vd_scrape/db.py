import psycopg
import asyncio
from psycopg.rows import dict_row
import os

PASSWORD = os.environ["PASSWORD"]
db_queue = asyncio.Queue()
DATABASE_CONECTION = {
    "dbname": PASSWORD,
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
    "row_factory": dict_row,
}


async def data_recording():
    filtered_products = await db_queue.get()
    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONECTION
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                                 
                                 """)
