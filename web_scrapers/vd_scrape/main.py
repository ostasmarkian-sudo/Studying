from playwright_ import open_w, get_url
from filter import filter_data
from db import data_recording
import asyncio

queue = asyncio.Queue()
db_queue = asyncio.Queue()
urlqueus = asyncio.Queue()


async def open_s(urlqueus, queue):
    urls = await urlqueus.get()
    await open_w(urls, queue)


async def process_data(queue, db_queue):
    while True:
        data = await queue.get()

        if data is None:
            await db_queue.put(None)
            break

        clear_data = await filter_data(data)
        await db_queue.put(clear_data)


async def record_data(db_queue):
    while True:
        data = await db_queue.get()

        if data is None:
            break
        await data_recording(data)


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(get_url(urlqueus))
        tg.create_task(open_s(urlqueus, queue))
        tg.create_task(process_data(queue, db_queue))
        tg.create_task(record_data(db_queue))


asyncio.run(main())
