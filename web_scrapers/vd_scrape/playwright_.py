from patchright.async_api import async_playwright, expect
from pathlib import Path
import asyncio
import random
import re
from lzstring import LZString
import json
import math

queue = asyncio.Queue()
statequeue = asyncio.Queue()
lz = LZString()


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
    product_count = int(data["data"]["commonFilters"][0]["options"][0]["productCount"])
    request_headers = await response.request.all_headers()

    locale_headers = {
        name: value
        for name, value in request_headers.items()
        if name.lower() in {"site", "lang", "x-currency"}
    }
    await queue.put(data)
    await statequeue.put((fetch_url_o, product_count, endpoint, locale_headers))


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
            state, product_count, endpoint, locale_headers = await statequeue.get()
            page_count = math.ceil(product_count / 100)
            decode_state = lz.decompressFromEncodedURIComponent(state)
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

                await queue.put(result)

            await page.wait_for_timeout(random.randint(800, 1600))
        await context.close()
        await queue.put(None)
