from patchright.async_api import async_playwright
from pathlib import Path
import asyncio
import random
import base64
import json
import urllib.parse

profile_path = Path(__file__).parent / "browser_profile_avnet"


async def creating_links():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=False
        )
        page = await browser.new_page()
        await page.goto(
            "https://my.avnet.com/abacus/products/c/see-all-products/",
            wait_until="load",
        )
        catalog = page.locator("ul[class='sublevel2']").locator("li").locator("a")
        urls = []
        for i in range(1, await catalog.count()):
            href = await catalog.nth(i).get_attribute("href")
            name = await catalog.nth(i).inner_text()
            decode = {
                "Categories": {
                    "selection": [
                        {
                            "value": name,
                            "hidden_payload": {"Level": 3},
                        }
                    ],
                    "main_label": "Category",
                }
            }
            compact_json = json.dumps(
                decode,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            encode = base64.b64encode(compact_json).decode()
            go = urllib.parse.quote(encode, safe="")
            url = f"https://my.avnet.com/{href}?go={go}&page=1&limit=1&orderby=&orderbydirection=asc"
            urls.append(url)
        print(urls)
        await browser.close()
async def first_request():
    

asyncio.run(creating_links())
