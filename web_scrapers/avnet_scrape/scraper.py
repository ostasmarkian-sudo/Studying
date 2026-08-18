import asyncio
import base64
import json
import sys
import urllib.parse
from pathlib import Path

import aiohttp
import db
from patchright.async_api import async_playwright

profile_path = Path(__file__).parent / "browser_profile_avnet"
categories_path = Path(__file__).parent / "categories.json"

API_URL = "https://apigw.avnet.com/external/fspmicro-application/api/application/product/search"
BATCH_SIZE = 2000  # sweet spot found by benchmarking API's own "top" param: ~500-600 items/s
                    # plateau between 2k-10k; below 2k per-request overhead dominates, above
                    # ~20k response time balloons non-linearly and requests start timing out.


async def creating_links(page):
    await page.goto(
        "https://my.avnet.com/abacus/products/c/see-all-products/",
        wait_until="load",
    )
    catalog = page.locator("ul[class='sublevel2']").locator("li").locator("a")
    entries = []
    for i in range(1, await catalog.count()):
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
    compact_json = json.dumps(decode, separators=(",", ":"), ensure_ascii=False).encode()
    encode = base64.b64encode(compact_json).decode()
    go = urllib.parse.quote(encode, safe="")
    return f"https://my.avnet.com/{href.lstrip('/')}?go={go}&page=1&limit=1&orderby=&orderbydirection=asc"


def category_filter(name):
    escaped = name.replace("'", "''")
    return f"(Level_2_Name eq '{escaped}') and Sboat eq 'T'"


async def get_api_headers():
    """Trigger one real category search in the browser and sniff the auth headers
    (bearer token + subscription key) it sends, so the rest of the run can hit the
    XHR endpoint directly via aiohttp instead of loading pages."""
    captured = {}

    async def on_request(request):
        if "product/search" in request.url and request.method == "POST":
            captured["headers"] = dict(request.headers)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=True
        )
        page = await browser.new_page()
        page.on("request", lambda r: asyncio.create_task(on_request(r)))

        await page.goto(
            "https://my.avnet.com/abacus/products/c/see-all-products/",
            wait_until="load",
        )
        catalog = page.locator("ul[class='sublevel2']").locator("li").locator("a")
        href = await catalog.nth(1).get_attribute("href")
        name = await catalog.nth(1).inner_text()
        await page.goto(category_page_url(href, name), wait_until="load")
        await page.wait_for_timeout(2000)

        await page.close()
        await browser.close()

    headers = captured["headers"]
    for key in ("content-length", "host", "connection"):
        headers.pop(key, None)
    return headers


async def post_search(session, headers_holder, body):
    for attempt in range(2):
        async with session.post(
            API_URL, headers=headers_holder["headers"], json=body
        ) as resp:
            if resp.status == 401 and attempt == 0:
                headers_holder["headers"] = await get_api_headers()
                continue
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)
    return None


async def count_worker(session, headers_holder, queue, results, semaphore):
    while True:
        entry = await queue.get()
        try:
            body = {
                "filter": category_filter(entry["name"]),
                "isIncludeCount": True,
                "search": "",
                "skip": 0,
                "top": 1,
                "isProductImageInclude": False,
                "isSkipFacets": True,
            }
            async with semaphore:
                data = await post_search(session, headers_holder, body)
            count = data["Data"]["Count"] if data and data.get("IsSuccessFull") else 0
            results.append({**entry, "count": count})
            print(f"{count:>6}  {entry['name']}")
        except Exception as e:
            print(f"error on {entry['name']}: {e}")
        finally:
            queue.task_done()


async def discover_categories(concurrency=8):
    """Enumerate every category and record its real product count via a direct
    count-only API call (top=1, isIncludeCount=true) instead of scraping the page's
    filter-count badge, which was found to show a stale/unrelated number. Run this
    manually (`python scraper.py discover`) whenever the catalog needs re-indexing;
    fetch_products reads the resulting categories.json rather than re-walking the
    site on every run."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path), headless=True
        )
        page = await browser.new_page()
        entries = await creating_links(page)
        await page.close()
        await browser.close()

    headers_holder = {"headers": await get_api_headers()}
    queue = asyncio.Queue()
    for entry in entries:
        queue.put_nowait(entry)

    results = []
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        workers = [
            asyncio.create_task(
                count_worker(session, headers_holder, queue, results, semaphore)
            )
            for _ in range(concurrency)
        ]
        await queue.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    non_empty = [r for r in results if r["count"] > 0]
    categories_path.write_text(
        json.dumps(non_empty, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"saved {len(non_empty)} categories to {categories_path} ({len(results) - len(non_empty)} empty skipped)")


async def fetch_category(session, headers_holder, entry, semaphore):
    count = entry["count"]
    if count <= 0:
        return

    filt = category_filter(entry["name"])
    saved = 0
    for skip in range(0, count, BATCH_SIZE):
        top = min(BATCH_SIZE, count - skip)
        body = {
            "filter": filt,
            "isIncludeCount": False,
            "search": "",
            "skip": skip,
            "top": top,
            "isProductImageInclude": False,
            "isSkipFacets": True,
        }
        async with semaphore:
            data = await post_search(session, headers_holder, body)
        if not data or not data.get("IsSuccessFull"):
            error = data.get("ErrorMessage") if data else "request failed"
            print(f"error fetching {entry['name']} skip={skip}: {error}")
            continue
        batch = data["Data"]["Products"]
        await db.save_products(entry["name"], batch)
        saved += len(batch)

    print(f"{entry['name']}: upserted {saved} products")


async def fetch_products(concurrency=4):
    """Read categories.json (built by discover_categories) and pull full product
    data straight from the XHR endpoint in BATCH_SIZE-sized pages, upserting each
    batch into Postgres (current state in `products`, superseded versions archived
    into `products_history` by a trigger). Splits any category whose count exceeds
    BATCH_SIZE across multiple requests."""
    if not categories_path.exists():
        print(f"{categories_path} not found, run `python scraper.py discover` first")
        return

    await db.init_db()
    entries = json.loads(categories_path.read_text(encoding="utf-8"))
    headers_holder = {"headers": await get_api_headers()}
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *(
                fetch_category(session, headers_holder, entry, semaphore)
                for entry in entries
            )
        )


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "discover":
        await discover_categories()
    elif mode == "fetch":
        await fetch_products()
    else:
        print("usage: python scraper.py [discover|fetch]")


asyncio.run(main())
