from playwright_ import open_w, get_url
from filter import filter_data
from db import data_recording
import asyncio
from patchright.async_api import async_playwright
from pathlib import Path

profile_path = Path(__file__).parent / "browser_profile_digikey"
queue = asyncio.Queue()
db_queue = asyncio.Queue()
urlqueus = asyncio.Queue()


async def open_s(urlqueus, queue, page):
    urls = await urlqueus.get()
    await open_w(urls, queue, page)


async def process_data(queue, db_queue):
    while True:
        data = await queue.get()

        if data is None:
            await db_queue.put(None)
            break

        filtered_data = filter_data(data)
        await db_queue.put(filtered_data)


async def record_data(db_queue):
    while True:
        data = await db_queue.get()

        if data is None:
            break
        await data_recording(data)


async def main():
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=False
        )
        page = await context.new_page()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(get_url(urlqueus, page))
            tg.create_task(open_s(urlqueus, queue, page))
            tg.create_task(process_data(queue, db_queue))
            tg.create_task(record_data(db_queue))
        await context.close()


asyncio.run(main())
