import psycopg
import asyncio


async def data_recording():
    with psycopg.AsyncConnection.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                           
                        """,
            )
