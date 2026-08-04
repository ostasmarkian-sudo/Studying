import time
import asyncio
import aiohttp
import psycopg
import selectors
from config import DATABASE_CONFIG

semaphore = asyncio.Semaphore(50)
timeout = aiohttp.ClientTimeout(connect=5, total=10)
HEADERS = {"User-Agent": "MyWebsiteMonitoring"}


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
            async for data in cursor:
                yield data


async def get_request(data):
    status = data["status_code"]
    url = data["url"]
    website_id = data["id"]
    status_code = None
    response_time = None
    is_available = False
    error_message = None
    start = time.perf_counter()
    try:
        async with semaphore, aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=timeout) as response:
                status_code = response.status
                response.raise_for_status()
                response_time = time.perf_counter() - start
                is_available = True
                error_message = ""
    except asyncio.TimeoutError as error:
        is_available = False
        response_time = time.perf_counter() - start
        error_message = str(error)[:64]
    except aiohttp.ClientConnectionError as error:
        is_available = False
        response_time = time.perf_counter() - start
        error_message = str(error)[:64]
    except aiohttp.ClientResponseError as error:
        response_time = time.perf_counter() - start
        error_message = str(error)[:64]
        is_available = False
    except aiohttp.ClientError as error:
        response_time = time.perf_counter() - start
        is_available = False
        error_message = str(error)[:64]
    response_time = round(response_time, 3)
    return is_available, error_message, status_code, website_id, response_time


async def post_data(
    website_id, status_code, response_time, is_available, error_message
):
    async with await psycopg.AsyncConnection.connect(**DATABASE_CONFIG) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                            INSERT INTO checks(website_id,status_code,response_time,is_available,error_message)
                            VALUES(%s,%s,%s,%s,%s)
                            """,
                (
                    website_id,
                    status_code,
                    response_time,
                    is_available,
                    error_message,
                ),
            )


async def main():
    dds = []
    async with asyncio.TaskGroup() as tg:
        async for data in get_data():
            dds.append(tg.create_task(get_request(data)))
    data_r = [task.result() for task in dds]
    for data_i in data_r:
        await post_data(data_i[3], data_i[2], data_i[4], data_i[0], data_i[1])
        print(f"checked{data_i[3]}")


loop_factory = lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
asyncio.run(main(), loop_factory=loop_factory)
