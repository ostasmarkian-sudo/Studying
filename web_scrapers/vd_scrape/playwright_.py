from patchright.async_api import async_playwright, expect
from pathlib import Path
import asyncio
import random
import re
from filter import filter_data

queue = asyncio.Queue()


async def handle_response(response, queue):
    resource_type = response.request.resource_type

    if resource_type not in {
        "fetch",
    }:
        return
    if not re.search(
        r"https://www.digikey.com/products/api/v5/filter-page",
        response.url,
    ):
        return
    print("URL:", response.url)
    data = await response.json()
    await queue.put(data)


profile_path = Path(__file__).parent / "browser_profile"


async def open_w(swap_pages, queue):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
        )
        page = await context.new_page()
        page.on("response", lambda response: handle_response(response, queue))
        for swap_page in swap_pages:
            await page.goto(
                swap_page,
                wait_until="load",
            )
            reg_fetch = page.get_by_role("button", name="Apply All")
            cords_reg = await reg_fetch.bounding_box()
            x_R = cords_reg["x"] + cords_reg["width"] / 2
            y_R = cords_reg["y"] + cords_reg["height"] / 2
            await page.mouse.move(x_R, y_R, steps=random.randint(15, 40))
            await reg_fetch.click()
            await page.wait_for_timeout(random.randint(100, 400))
            next_page_button = page.get_by_role("button", name="Next Page")
            last_page_button = page.get_by_role("button", name="Last Page")
            cords_lpb = await last_page_button.bounding_box()
            x_L = cords_lpb["x"] + cords_lpb["width"] / 2
            y_L = cords_lpb["y"] + cords_lpb["height"] / 2
            await page.mouse.move(x_L, y_L, steps=random.randint(15, 40))
            await last_page_button.click()
            currently_page = page.locator('button[tabindex="-1"]')
            max_page = int(await currently_page.inner_text())
            all_page_buttons = page.locator('button[data-testid^="btn-page-"]')
            for i in range(max_page - 1, 1, -1):
                print(i)
            await page.wait_for_timeout(10000)
        await context.close()
        await queue.put(None)
