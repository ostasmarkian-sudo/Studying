import asyncio
import base64
import json
import sys
import urllib.parse
from pathlib import Path
import re
import aiohttp
import db
from patchright.async_api import async_playwright
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

profile_path = Path(__file__).parent / "browser_profile_avnet"
categories_path = Path(__file__).parent / "categories.json"

API_URL = "https://apigw.avnet.com/external/fspmicro-application/api/application/product/search"
BATCH_SIZE = 2000


async def creating_links(page):
    await page.goto(
        "https://my.avnet.com/abacus/products/c/see-all-products/",
        wait_until="load",
    )
    catalog = page.locator("ul[class='sublevel2']").locator("li").locator("a")
    entries = []
    for i in range(await catalog.count()):
        href = await catalog.nth(i).get_attribute("href")
        name = await catalog.nth(i).inner_text()
        entries.append({"name": name, "url": category_page_url(href, name)})
    return entries


def category_page_url(href, name):
    decode = {
        "Categories": {
            "selection": [{"value": name, "hidden_payload": {"Level": 3}}],
            "main_label": "Category",
        }
    }
    compact_json = json.dumps(
        decode, separators=(",", ":"), ensure_ascii=False
    ).encode()
    encode = base64.b64encode(compact_json).decode()
    go = urllib.parse.quote(encode, safe="")
    return f"https://my.avnet.com/{href.lstrip('/')}?go={go}&page=1&limit=1&orderby=&orderbydirection=asc"


def odata_str(value):
    # OData escapes a single quote by doubling it
    return "'" + value.replace("'", "''") + "'"


def category_filter(name):
    literal = odata_str(name)
    return (
        f"(Level_2_Name eq {literal}"
        f" or Level_3_Name eq {literal}"
        f" or Level_4_Name eq {literal}) and Sboat eq 'T'"
    )


async def block_assets(page):
    async def handler(route):
        if route.request.resource_type in {"image", "media", "font"}:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", handler)


async def get_api_headers():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=True
        )
        page = await browser.new_page()
        await block_assets(page)
        await page.goto(
            "https://my.avnet.com/abacus/products/c/see-all-products/",
            wait_until="load",
        )
        catalog = (
            page.locator("ul[class='sublevel2']")
            .locator("li")
            .filter(has_not=page.locator("ul"))
            .locator("a")
        )
        href = await catalog.nth(1).get_attribute("href")
        name = await catalog.nth(1).inner_text()

        try:
            async with page.expect_request(
                lambda r: "product/search" in r.url and r.method == "POST",
                timeout=30_000,
            ) as info:
                await page.goto(category_page_url(href, name), wait_until="commit")
            headers = dict((await info.value).headers)
        except PlaywrightTimeoutError:
            raise RuntimeError(
                f"no product/search POST on {page.url} - the session in "
                f"{profile_path.name} has probably expired, re-login with headless=False"
            ) from None
        finally:
            await page.close()
            await browser.close()

    for key in ("content-length", "host", "connection"):
        headers.pop(key, None)
    return headers


async def refresh_headers(headers_holder, stale):
    async with headers_holder["lock"]:
        if headers_holder["headers"] is stale:
            headers_holder["headers"] = await get_api_headers()


async def post_search(session, headers_holder, body, attempts=4):
    for attempt in range(attempts):
        current = headers_holder["headers"]
        try:
            async with session.post(API_URL, headers=current, json=body) as resp:
                if resp.status == 401:
                    await refresh_headers(headers_holder, current)
                    continue
                if resp.status in (429, 500, 502, 503, 504):
                    delay = float(resp.headers.get("Retry-After", 2**attempt))
                    await asyncio.sleep(delay)
                    continue
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(2**attempt)
    return None


async def discover_categories():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=True
        )
        page = await browser.new_page()
        await block_assets(page)
        entries = await creating_links(page)
        results = []
        for entry in entries:
            await page.goto(entry["url"], wait_until="domcontentloaded")
            if await page.locator('div[class="prod_count2"]').count() > 0:
                print("skip")
                continue
            unf_count_aviable = await page.locator(
                "span[class='filter-count']"
            ).first.inner_text()
            match = re.search(r"\(([\d,\s]+)\)", unf_count_aviable)
            if not match:
                continue
            count_aviable = int(match.group(1).replace(",", "").replace(" ", ""))
            if count_aviable == 0:
                continue
            results.append({**entry, "count": count_aviable})
        await page.close()
        await browser.close()
        categories_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"saved {len(results)} categories to {categories_path})")


async def fetch_category(session, headers_holder, entry, semaphore, failures):
    base = category_filter(entry["name"])
    fetched, written, cursor = 0, 0, None
    try:
        while True:
            filt = base
            if cursor is not None:
                filt = f"{base} and ItemNumber gt {odata_str(cursor)}"
            body = {
                "filter": filt,
                "isIncludeCount": False,
                "search": "",
                "orderby": "ItemNumber",
                "orderbydirection": "asc",
                "skip": 0,
                "top": BATCH_SIZE,
                "isProductImageInclude": False,
                "isSkipFacets": True,
            }
            async with semaphore:
                data = await post_search(session, headers_holder, body)
            if not data or not data.get("IsSuccessFull"):
                error = data.get("ErrorMessage") if data else "request failed"
                print(f"error fetching {entry['name']} after {fetched}: {error}")
                failures.append((entry["name"], fetched))
                break
            batch = (data.get("Data") or {}).get("Products") or []
            if not batch:
                break
            written += await db.save_products(entry["name"], batch)
            fetched += len(batch)
            cursor = batch[-1].get("ItemNumber")
            if not cursor:
                print(
                    f"error fetching {entry['name']} after {fetched}: no ItemNumber to page on"
                )
                failures.append((entry["name"], fetched))
                break
            if len(batch) < BATCH_SIZE:
                break
    except Exception as error:
        print(f"error fetching {entry['name']} after {fetched}: {error!r}")
        failures.append((entry["name"], fetched))
    print(
        f"{entry['name']}: {fetched} fetched, {written} written (badge {entry['count']})"
    )


async def fetch_products(concurrency=4):
    if not categories_path.exists():
        print(f"{categories_path} not found, run `python scraper.py discover` first")
        return

    await db.init_db()
    entries = json.loads(categories_path.read_text(encoding="utf-8"))
    headers_holder = {"headers": await get_api_headers(), "lock": asyncio.Lock()}
    semaphore = asyncio.Semaphore(concurrency)
    failures = []

    timeout = aiohttp.ClientTimeout(total=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        await asyncio.gather(
            *(
                fetch_category(session, headers_holder, entry, semaphore, failures)
                for entry in entries
            ),
            return_exceptions=True,
        )

    if failures:
        print()
        print(f"{len(failures)} pages failed:")
        for name, fetched in failures:
            print(f"   {name} stopped after {fetched}")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "discover":
        await discover_categories()
    elif mode == "fetch":
        await fetch_products()
    else:
        print("usage: python scraper.py [discover|fetch]")


if __name__ == "__main__":
    asyncio.run(main())
