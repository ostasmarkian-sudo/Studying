from patchright.async_api import async_playwright
from pathlib import Path
import asyncio
import random
import re
from lzstring import LZString
import json
import math
from urllib.parse import unquote

queue = asyncio.Queue()
statequeue = asyncio.Queue()
urlqueus = asyncio.Queue()
lz = LZString()
profile_path = Path(__file__).parent / "browser_profile"


async def get_url(urlqueus):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=False
        )
        page = await browser.new_page()
        await page.goto(
            "https://www.digikey.co.uk/en/products?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY+TLkYADN7UA",
            wait_until="load",
        )
        catalog = page.locator('//ul[@ref_page_event="Select Family"]')
        for _ in range(25):
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(random.randint(1, 100))
        catalog_button = page.locator(
            'a[class="tss-css-gqjq9w-root-NthLevelCategory-categoryAnchor"]'
        )
        urls = []
        for i in range(await catalog_button.count()):
            href = await catalog_button.nth(i).get_attribute("href")
            urls.append(href)
        await urlqueus.put(urls)
        await browser.close()


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
    fetch_url_i = response.url
    ma = re.search(
        r"(^(?P<endpoint>https:\/\/www.digikey.com\/products\/api\/v5\/filter-page\/\d+\?)s=(?P<page_state>.+))$",
        fetch_url_i,
    )
    fetch_url_o = ma.group("page_state")
    endpoint = ma.group("endpoint")
    product_count = data["data"]["commonFilters"][0]["options"][0]["productCount"]
    product_count = int(product_count.replace(",", ""))
    request_headers = await response.request.all_headers()

    locale_headers = {
        name: value
        for name, value in request_headers.items()
        if name.lower() in {"site", "lang", "x-currency"}
    }
    await queue.put(data)
    await statequeue.put((fetch_url_o, product_count, endpoint, locale_headers))


async def handle_r(response):
    await handle_response(response, queue)


async def open_w(urlqueus, queue):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=False,
        )
        page = await context.new_page()
        for url in urlqueus:
            url_d = "https://www.digikey.com/" + url
            page.on("response", handle_r)
            await page.goto(
                url_d,
                wait_until="domcontentloaded",
            )
            reg_fetch = page.get_by_role("button", name="Apply All")
            cords_reg = await reg_fetch.bounding_box()
            x_R = cords_reg["x"] + cords_reg["width"] / 2
            y_R = cords_reg["y"] + cords_reg["height"] / 2
            await page.mouse.move(
                x_R,
                y_R,
                steps=random.randint(15, 40),
            )
            await reg_fetch.click()
            await page.wait_for_timeout(random.randint(100, 400))
            state, product_count, endpoint, locale_headers = await statequeue.get()
            page.remove_listener("response", handle_r)
            print(product_count)
            page_count = math.ceil(product_count / 100)
            dstate = unquote(state)
            decode_state = lz.decompressFromEncodedURIComponent(dstate)
            decode_j = json.loads(decode_state)
            for i in range(2, page_count + 1):
                decode_j["5"]["p"] = i
                decode_j["5"]["pp"] = 100
                compact_json = json.dumps(
                    decode_j,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                fetch_key = lz.compressToEncodedURIComponent(compact_json)
                print(fetch_key)
                print(lz.decompressFromEncodedURIComponent(fetch_key))
                fetch_url = f"{endpoint}s={fetch_key}"
                result = await page.evaluate(
                    """
                    async ({url, localeHeaders}) => {
                        const response = await fetch(url, {
                            method: "GET",
                            credentials: "include",
                            headers: {
                                "Accept": "application/json, text/plain, */*",
                                ...localeHeaders
                            },
                            referrer: window.location.href
                        });

                        const body = await response.text();

                        if (!response.ok) {
                            throw new Error(
                                `DigiKey returned ${response.status}: ${body.slice(0, 500)}`
                            );
                        }

                        return JSON.parse(body);
                    }
                    """,
                    {
                        "url": fetch_url,
                        "localeHeaders": locale_headers,
                    },
                )
                print(i)
                await queue.put(result)

        await context.close()
        await queue.put(None)
