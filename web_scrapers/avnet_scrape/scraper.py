import asyncio
import base64
import json
import sys
import urllib.parse
from datetime import datetime, timezone
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

# What the site itself sends: Sboat is the sales-org scope, without it the same
# query returns a different (partly non-Abacus) catalog.
CATALOG_FILTER = "Sboat eq 'T'"

# Availability. This is exactly the site's "In Stock (N)" badge - the number
# discover_categories records - and it is the difference between 30 880 parts
# catalog-wide and the 1 182 330 that CATALOG_FILTER alone returns.
# `Stock gt 0` selects the identical set; Instock is an Edm.String, so `eq true`
# is a server error and `eq 'Y'` silently matches nothing.
IN_STOCK_FILTER = "Instock eq 'Yes'"

# Live availability, straight from SAP - the same call the product page makes.
# The search index's Stock is only a snapshot taken when the index was built.
INVENTORY_URL = (
    "https://apigw.avnet.com/external/fspmicro-inventory/api/inventory/getinventory"
)
# The endpoint runs at ~23 parts/sec whatever the batch size (measured at 100,
# 500, 1000 and 2000 per call), so keep requests short rather than sending
# 2000-part monsters that hold a connection open for 84 seconds.
STOCK_CHUNK = 100

# Flip to True once fetch_price_chunk() below is implemented, so `price` stops
# short instead of launching a browser and opening a session for nothing.
PRICE_SOURCE_READY = False


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


def category_filter(name, in_stock=True):
    literal = odata_str(name)
    parts = [
        f"(Level_2_Name eq {literal}",
        f" or Level_3_Name eq {literal}",
        f" or Level_4_Name eq {literal})",
        CATALOG_FILTER,
    ]
    if in_stock:
        parts.append(IN_STOCK_FILTER)
    return " and ".join(parts)


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
    return await post_json(session, headers_holder, API_URL, body, attempts)


async def post_json(session, headers_holder, url, body, attempts=4):
    for attempt in range(attempts):
        current = headers_holder["headers"]
        try:
            async with session.post(url, headers=current, json=body) as resp:
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


async def page_filter(session, headers_holder, base, semaphore, on_batch):
    """Keyset-page every product matching `base` and hand each batch to on_batch.

    ItemNumber is a fixed-width 'Abacus-NNNNNNNNN' string, so `gt` on it is a
    stable total order and paging on it needs no `skip` - which matters, because
    the API rejects skip > 100 000 and a big category has more rows than that.

    Returns (fetched, cursor, error). `cursor` is the last ItemNumber that was
    stored, so a failed sweep says where it stopped instead of just how far.
    """
    fetched, cursor, top = 0, None, BATCH_SIZE
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
            "top": top,
            "isProductImageInclude": False,
            "isSkipFacets": True,
        }
        async with semaphore:
            data = await post_search(session, headers_holder, body)

        if not data or not data.get("IsSuccessFull"):
            # A 2000-product response is megabytes; when one keeps timing out,
            # ask for a smaller slice of the same cursor rather than abandoning
            # the sweep here - that is what silently truncated Surface Mount
            # Resistors at exactly 100 000 of its 123 118 rows.
            if top > BATCH_SIZE // 8:
                top //= 2
                continue
            error = data.get("ErrorMessage") if data else "request failed"
            return fetched, cursor, error

        batch = (data.get("Data") or {}).get("Products") or []
        # Stopping on a short batch would trust the API to always fill `top`;
        # one more request that comes back empty is cheap and cannot truncate.
        if not batch:
            return fetched, cursor, None
        await on_batch(batch)
        fetched += len(batch)
        nxt = batch[-1].get("ItemNumber")
        if not nxt:
            return fetched, cursor, "no ItemNumber to page on"
        cursor = nxt


async def sweep(session, headers_holder, base, semaphore, category, label, failures):
    """Run one page_filter sweep into the database and report what it did."""
    written = skipped = 0

    async def on_batch(batch):
        nonlocal written, skipped
        batch_written, batch_skipped = await db.save_products(category, batch)
        written += batch_written
        skipped += batch_skipped

    try:
        fetched, cursor, error = await page_filter(
            session, headers_holder, base, semaphore, on_batch
        )
    except Exception as exception:  # noqa: BLE001 - one category must not kill the run
        fetched, cursor, error = 0, None, repr(exception)

    if error:
        print(f"error fetching {label} after {fetched}: {error}")
        failures.append((label, fetched, cursor))

    # `written` counts rows the upsert actually touched. Everything else was
    # already in the table byte for byte, which is why a second run of an
    # unchanged catalog legitimately reports 0 written - see the run summary.
    print(
        f"{label}: {fetched} fetched, {written} written, "
        f"{fetched - written - skipped} unchanged"
        + (f", {skipped} skipped" if skipped else "")
    )


async def fetch_category(session, headers_holder, entry, semaphore, failures):
    await sweep(
        session,
        headers_holder,
        category_filter(entry["name"]),
        semaphore,
        entry["name"],
        f"{entry['name']} (badge {entry['count']})",
        failures,
    )


async def report(started_at, failures):
    total, new, changed, seen = await db.run_stats(started_at)
    print()
    print(
        f"run summary: {seen} parts seen, {new} new, {changed} changed, "
        f"{seen - new - changed} unchanged; products now holds {total} rows"
    )
    if failures:
        print()
        print(f"{len(failures)} sweeps failed:")
        for label, fetched, cursor in failures:
            print(f"   {label} stopped after {fetched} at {cursor}")


async def fetch_products(concurrency=4):
    """Sweep in-stock parts category by category, from categories.json."""
    if not categories_path.exists():
        print(f"{categories_path} not found, run `python scraper.py discover` first")
        return

    await db.init_db()
    entries = json.loads(categories_path.read_text(encoding="utf-8"))
    started_at = datetime.now(timezone.utc)
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

    await report(started_at, failures)


async def fetch_all():
    """Sweep the whole in-stock catalog with one filter and no category walk.

    30 880 parts in ~16 requests, against 315 category sweeps that pull the same
    part once per category it is filed under. Level_2_Name is missing on 1 462
    of those parts, so cat_l2 stays NULL here instead of borrowing the requested
    category name the way fetch_products does.
    """
    await db.init_db()
    started_at = datetime.now(timezone.utc)
    headers_holder = {"headers": await get_api_headers(), "lock": asyncio.Lock()}
    failures = []

    timeout = aiohttp.ClientTimeout(total=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        await sweep(
            session,
            headers_holder,
            f"{CATALOG_FILTER} and {IN_STOCK_FILTER}",
            asyncio.Semaphore(1),
            None,
            "in-stock catalog",
            failures,
        )

    await report(started_at, failures)


async def fetch_stock_chunk(session, headers_holder, parts, semaphore):
    """Live quantity for up to STOCK_CHUNK parts, keyed the way SAP keys them.

    `matnr` is the ERPPartNumber and `mfr` the ERPManufacturerCode; the response
    carries `qas` (available quantity), `plifz` (lead time) and `meins` (unit),
    stamped with today's date because it is computed per request rather than
    served from a cache.
    """
    body = {
        "iT_INVENTORY": [
            {"sboat": "T", "matnr": erp, "mfr": mfr, "reQ_DATE": ""}
            for _, erp, mfr in parts
        ]
    }
    async with semaphore:
        data = await post_json(session, headers_holder, INVENTORY_URL, body)
    if not data or not data.get("isSuccessFull"):
        return None

    entries = (data.get("data") or {}).get("eT_INVENTORY") or []
    by_part = {entry.get("matnr"): entry for entry in entries}
    records = []
    for item_number, erp, _ in parts:
        entry = by_part.get(erp)
        if entry is None:
            continue
        quantity = entry.get("qas")
        records.append(
            (
                item_number,
                int(quantity) if quantity is not None else None,
                (entry.get("plifz") or "").strip() or None,
                (entry.get("meins") or "").strip() or None,
            )
        )
    return records


async def fetch_price_chunk(session, headers_holder, parts, semaphore):
    """Current price for up to STOCK_CHUNK parts - not implemented yet.

    Prices are gated behind a signed-in Abacus account. With the anonymous
    profile the scraper uses, the product page shows "SIGN IN TO SEE YOUR ABACUS
    PRICE" and fires no pricing call at all, so the endpoint and its payload are
    still unknown - there is nothing to guess at here.

    To finish it: sign into a real account once inside browser_profile_avnet
    (headless=False), reload a product page with the network log open, find the
    call that returns the price, and return records shaped like
    (item_number, price, currency, Jsonb(breaks) or None). Everything
    downstream - products_price, save_prices, the `price` mode - already works.
    """
    raise NotImplementedError(
        "no pricing source yet: sign browser_profile_avnet into an Abacus "
        "account and fill in fetch_price_chunk()"
    )


async def sync_live(label, fetch_chunk, save, concurrency=4):
    """Drive one live-data sweep: read the parts, fetch in chunks, store."""
    await db.init_db()
    parts = await db.parts_for_sync()
    if not parts:
        print("nothing to check - run `python scraper.py fetch-all` first")
        return
    print(f"{label}: checking {len(parts)} parts")

    headers_holder = {"headers": await get_api_headers(), "lock": asyncio.Lock()}
    semaphore = asyncio.Semaphore(concurrency)
    chunks = [parts[i : i + STOCK_CHUNK] for i in range(0, len(parts), STOCK_CHUNK)]
    written = new = changed = zeroed = missing = 0

    timeout = aiohttp.ClientTimeout(total=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def run(chunk):
            nonlocal written, new, changed, zeroed, missing
            records = await fetch_chunk(session, headers_holder, chunk, semaphore)
            if records is None:
                missing += len(chunk)
                return
            missing += len(chunk) - len(records)
            counts = await save(records)
            written += counts[0]
            new += counts[1]
            changed += counts[2]
            zeroed += counts[3]

        await asyncio.gather(*(run(chunk) for chunk in chunks))

    print()
    print(
        f"{label}: {written} stored, {new} new, {changed} changed, "
        f"{zeroed} dropped to zero"
        + (f", {missing} without a live record" if missing else "")
    )


async def fetch_stock():
    await sync_live("live stock", fetch_stock_chunk, db.save_stock)
    rows, available, ghosts, buyable = await db.stock_stats()
    print(
        f"of {rows} parts checked, {available} can really be shipped and "
        f"{buyable} clear their minimum order quantity; "
        f"{ghosts} are listed in stock but are really at zero"
    )


async def fetch_prices():
    if not PRICE_SOURCE_READY:
        print(
            "price sync is not wired up yet - prices need a signed-in "
            "Abacus account. See fetch_price_chunk() for what to fill in; "
            "the table, the upsert and this mode are already in place."
        )
        return
    await sync_live("price", fetch_price_chunk, db.save_prices)


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "discover":
        await discover_categories()
    elif mode == "fetch":
        await fetch_products()
    elif mode == "fetch-all":
        await fetch_all()
    elif mode == "stock":
        await fetch_stock()
    elif mode == "price":
        await fetch_prices()
    else:
        print("usage: python scraper.py [discover|fetch|fetch-all|stock|price]")


if __name__ == "__main__":
    asyncio.run(main())
