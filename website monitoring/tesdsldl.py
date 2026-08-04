import psycopg
from config import DATABASE_CONFIG
import asyncio
import selectors


async def get_data():
    async with await psycopg.AsyncConnection.connect(**DATABASE_CONFIG) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                            SELECT DISTINCT ON (websites.id)
                                websites.url,
                                checks.status_code,
                                websites.id
                            FROM websites
                            LEFT JOIN checks
                                ON checks.website_id = websites.id
                            ORDER BY
                                websites.id,
                                checks.checked_at DESC,
                                checks.id DESC;
                           """)
            data = await cursor.fetchall()
            print(data)


loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
asyncio.run(get_data(), loop_factory=loop_factory)
