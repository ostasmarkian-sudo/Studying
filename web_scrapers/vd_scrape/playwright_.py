from patchright.async_api import async_playwright, expect
from pathlib import Path
import asyncio
import random
import re
from filter import filter_data

urls = [
    "https://www.digikey.com/en/products/filter/controllers/cable-assemblies/823?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/controller-accessories/816?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/liquid-level/806?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
    "https://www.digikey.com/en/products/filter/controllers/plc-modules/821?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
]


async def handle_response(response):
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
    filter_data(data)


profile_path = Path(__file__).parent / "browser_profile"


async def open_w(swap_pages):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
        )
        page = await context.new_page()
        page.on("response", handle_response)
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
            c = page.locator(
                '[data-testid="per-page-selector-container"]:visible'
            ).first
            text = await c.inner_text()
            number = re.search(r"of\s+([\d,]+)", text)
            total = int(number.group(1).replace(",", ""))
            pages = (total + 99) // 100
            clicks = max(0, pages - 1)
            print(clicks)
            first_p = page.locator('//tr[@class="tss-css-hi2p03-tr"]')
            for i in range(2, clicks):
                old_href = await first_p.first.get_attribute("href")
                cords_npb = await next_page_button.bounding_box()
                x_N = cords_npb["x"] + cords_npb["width"] / 2
                y_N = cords_npb["y"] + cords_npb["height"] / 2
                await page.mouse.move(x_N, y_N, steps=random.randint(15, 40))
                async with page.expect_response(
                    lambda response: "/products/api/v5/filter-page" in response.url
                ) as response_info:
                    await next_page_button.click()
                response = await response_info.value
                await response.finished()
        await page.wait_for_timeout(10000)
        await context.close()


async def main():
    await asyncio.gather(
        open_w(urls),
    )


asyncio.run(main())
