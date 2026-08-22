import asyncio
from pathlib import Path

from patchright.async_api import async_playwright

from db import data_recording
from filter import filter_data
from playwright_ import get_url, open_w

profile_path = Path(__file__).parent / "browser_profile_digikey"


async def scrape(urlqueue, queue, page):
    """Collect the family links, then walk them.

    get_url and open_w drive the same page, so they have to run one after the
    other rather than as two tasks racing inside the group.
    """
    await get_url(urlqueue, page)
    urls = await urlqueue.get()
    await open_w(urls, queue, page)


async def process_data(queue, db_queue):
    while True:
        data = await queue.get()

        if data is None:
            await db_queue.put(None)
            break

        try:
            filtered_data = filter_data(data)
        except (KeyError, IndexError, TypeError) as error:
            # a filter-page response that is not a product listing, e.g. the
            # one the facet panel fires - not worth taking the run down for
            print(f"response did not parse, skipped: {error!r}")
            continue
        await db_queue.put(filtered_data)


async def record_data(db_queue):
    written = skipped = 0
    while True:
        data = await db_queue.get()

        if data is None:
            break
        batch_written, batch_skipped = await data_recording(data)
        written += batch_written
        skipped += batch_skipped
        print(f"db: +{batch_written} rows (total {written}, skipped {skipped})")
    return written, skipped


async def main():
    queue = asyncio.Queue()
    db_queue = asyncio.Queue()
    urlqueue = asyncio.Queue()

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
            no_viewport=True,
        )
        try:
            page = await context.new_page()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(scrape(urlqueue, queue, page))
                tg.create_task(process_data(queue, db_queue))
                tg.create_task(record_data(db_queue))
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
