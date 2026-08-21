"""stex24.com - catalogue and stock.

The work splits in two, and the line between them is about WHERE data comes from:

  discover  the storefront is good for exactly one thing - telling us which
            uuids sit in which category. So the HTML is barely parsed here:
            one hidden input per card, nothing else.

  stock     everything else - names, brands, volume pricing, quantities across
            both warehouses - comes from the Store API in batches of 250 uuids.

The shop sits behind Cloudflare, so every request goes through curl_cffi with
browser impersonation: plain requests/httpx are rejected on the TLS fingerprint
before a single header is read.

Both tables live in the product_avnet database; see db.py.
"""

import asyncio
import random
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from curl_cffi import CurlError
from curl_cffi.requests import AsyncSession

import db

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://stex24.com"
LIMIT = 96  # the largest page size the storefront's own UI offers
CONCURRENCY = 2
RETRIES = 4
CURRENCY = "EUR"  # the only currency of this sales channel

CATEGORIES = [
    "harting-connectors",
    "circular-connectors",
    "cables-wires",
    "cable-conduits",
    "cable-glands",
    "switch-button",
    "control-cabinet-accessories",
    "automation-technology",
    "electrical-materials",
    "tools",
]

SEM = asyncio.Semaphore(CONCURRENCY)

# --- Store API ---------------------------------------------------------------
#
# The storefront proxies the Store API for its own widgets, and that proxy takes
# a LIST of ids - which is why the whole catalogue costs a few dozen calls rather
# than eleven thousand. Two conditions make it work, and neither follows from any
# documentation:
#   * the Sec-Fetch-* headers - without them Cloudflare serves a challenge;
#   * _csrf_token INSIDE the request body - as a header or a query argument it
#     is refused with "Your session has expired".
# The token is the csrf[frontend.store-api.proxy] cookie any plain GET hands out.
PROXY = f"{BASE}/_proxy/store-api?path=%2Fstore-api%2Fproduct"
CSRF_COOKIE = "csrf[frontend.store-api.proxy]"
BATCH = 250  # no ceiling on the length of ids; 250 keeps a reply under a megabyte
PAUSE = (0.8, 2.5)  # random gap between batches, seconds

AJAX = {
    "Origin": BASE,
    "Referer": f"{BASE}/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

# Without includes every product drags 88 fields along; with them the reply
# shrinks about thirtyfold. Key is the entity name, value the fields to keep.
INCLUDES = {
    "product": [
        "id",
        "parentId",
        "productNumber",
        "name",
        "description",
        "ean",
        "manufacturerNumber",
        "manufacturer",
        "seoUrls",
        "cover",
        "calculatedPrice",
        "calculatedPrices",
        "childCount",
        "availableStock",
        "available",
        "deliveryTime",
        "restockTime",
        "customFields",
    ],
    "product_manufacturer": ["name"],
    "seo_url": ["seoPathInfo"],
    "product_media": ["media"],
    "media": ["url"],
    "calculated_price": ["unitPrice", "quantity"],
    "delivery_time": ["name", "min", "max"],
}

# Brand, link and image live in related entities, so they have to be asked for
# explicitly - otherwise those fields come back as bare identifiers.
ASSOCIATIONS = {"manufacturer": {}, "seoUrls": {}, "cover": {}}


# --- discover: uuids from the storefront -------------------------------------


async def fetch_page(session, url, page):
    """One listing page, retried - Cloudflare answers 403 when it gets grumpy."""
    for attempt in range(1, RETRIES + 1):
        async with SEM:
            try:
                r = await session.get(url, params={"p": page, "limit": LIMIT})
                if r.status_code == 200:
                    return r.text
                problem = f"HTTP {r.status_code}"
            except (CurlError, OSError) as exc:
                problem = f"{type(exc).__name__}: {exc}"
        print(f"  retry {attempt}/{RETRIES} {url} p{page}: {problem}")
        await asyncio.sleep(2**attempt)
    print(f"  ! skipped {url} p{page}")
    return None


def parse_uuids(html):
    """The one thing worth taking from the markup: the hidden id on each card."""
    soup = BeautifulSoup(html, "html.parser")
    return [
        node["value"].strip()
        for node in soup.select("input[name='product-id']")
        if node.get("value")
    ]


def page_count(html):
    """Highest number among the pager radios.

    The maximum, not #p-last: that element only exists once the pager has to
    collapse ("1 2 3 4 5 ... 18"), while a short category lists every page
    instead, leaving #p-next = 2 as the only hint - which silently truncates
    such a category to two pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    return max(
        (
            int(node["value"])
            for node in soup.select("input[name='p']")
            if node.get("value", "").isdigit()
        ),
        default=1,
    )


async def scrape_category(session, category):
    url = f"{BASE}/{category}"
    first = await fetch_page(session, url, 1)
    if first is None:
        print(f"! {category}: first page failed, skipped")
        return []

    pages = page_count(first)
    print(f"* {category}: {pages} page(s)")

    uuids = parse_uuids(first)
    rest = await asyncio.gather(
        *(fetch_page(session, url, p) for p in range(2, pages + 1))
    )
    for html in rest:
        if html:
            uuids.extend(parse_uuids(html))

    print(f"  {category}: {len(uuids)} uuids")
    return uuids


async def discover_catalog():
    """Walk the catalogue for identifiers alone. The API pass fills in the rest."""
    started = datetime.now(timezone.utc)
    db.init_db()

    rows = []
    async with AsyncSession(
        impersonate="chrome131", timeout=60, max_clients=CONCURRENCY
    ) as session:
        await session.get(BASE)  # warm up: picks up the Cloudflare clearance cookie
        for category in CATEGORIES:
            for uuid in await scrape_category(session, category):
                rows.append((uuid, [category]))

    saved = db.save_uuids(rows)
    total, new, _, seen = db.run_stats(started)
    unique = len({uuid for uuid, _ in rows})
    print(f"\n{len(rows)} sightings, {unique} unique uuids, {saved} written")
    print(f"stex24_products: {total} rows, {new} new, {seen} seen this run")
    print("next: python scraper.py stock")


# --- stock: everything else from the Store API -------------------------------


async def store_api_token(session):
    """Fetch the proxy's csrf cookie without giving up on the first try.

    A single GET will not do: if it catches a challenge or a 5xx there are no
    cookies at all, and the whole run dies for no good reason. A category page
    is tried as well - Shopware only sets the token on a response where it
    actually rendered the matching widgets.
    """
    for attempt in range(1, RETRIES + 1):
        for url in (BASE, f"{BASE}/{CATEGORIES[0]}"):
            try:
                r = await session.get(url)
            except (CurlError, OSError) as exc:
                problem = f"{type(exc).__name__}: {exc}"
            else:
                token = session.cookies.get(CSRF_COOKIE)
                if token:
                    return token
                problem = (
                    "Cloudflare challenge"
                    if "Just a moment" in r.text
                    else f"HTTP {r.status_code}, cookie absent"
                )
            print(f"  retry {attempt}/{RETRIES} token from {url}: {problem}")
        await asyncio.sleep(2**attempt * random.uniform(0.8, 1.4))
    return None


async def fetch_batch(session, uuids, token):
    """One batch of uuids through the storefront's Store API proxy."""
    payload = {
        "ids": uuids,
        "_csrf_token": token,
        "includes": INCLUDES,
        "associations": ASSOCIATIONS,
    }
    for attempt in range(1, RETRIES + 1):
        async with SEM:
            try:
                r = await session.post(PROXY, json=payload, headers=AJAX)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("errors"):
                        detail = data["errors"][0].get("detail", "")
                        print(f"  ! Store API: {detail[:100]}")
                        return []
                    return data.get("elements", [])
                problem = f"HTTP {r.status_code}"
            except (CurlError, OSError, ValueError) as exc:
                problem = f"{type(exc).__name__}: {exc}"
        print(f"  retry {attempt}/{RETRIES} batch of {len(uuids)}: {problem}")
        await asyncio.sleep(2**attempt * random.uniform(0.8, 1.4))
    print(f"  ! skipped batch of {len(uuids)}")
    return []


def price_tiers(element):
    """Volume pricing: [{"qty": 249, "price": 0.91}, ...].

    The last tier arrives with quantity 0, meaning "and beyond, no limit" - kept
    as None so the zero is never read as "zero units".
    """
    return [
        {"qty": tier.get("quantity") or None, "price": tier.get("unitPrice")}
        for tier in element.get("calculatedPrices") or []
    ]


def product_record(element):
    """One API element -> a catalogue row."""
    seo = element.get("seoUrls") or []
    cover = (element.get("cover") or {}).get("media") or {}
    return {
        "uuid": element.get("id"),
        "parent_uuid": element.get("parentId"),
        "sku": element.get("productNumber"),
        "name": element.get("name"),
        "brand": (element.get("manufacturer") or {}).get("name"),
        "mpn": element.get("manufacturerNumber"),
        "gtin": element.get("ean"),
        "price": (element.get("calculatedPrice") or {}).get("unitPrice"),
        "price_tiers": price_tiers(element),
        "currency": CURRENCY,
        "available": element.get("available"),
        "variants": element.get("childCount"),
        "url": f"{BASE}/{seo[0]['seoPathInfo']}" if seo else None,
        "image": cover.get("url"),
        "description": element.get("description"),
    }


def stock_record(element):
    """One API element -> a stock row."""
    custom = element.get("customFields") or {}
    delivery = element.get("deliveryTime") or {}
    return {
        "uuid": element.get("id"),
        "sku": element.get("productNumber"),
        # the Express warehouse - what actually ships today
        "express_qty": element.get("availableStock"),
        # the supplier's warehouse, which lives only in the shop's custom fields
        "external_qty": custom.get("mega_manufacturer_stock"),
        "ordered_qty": custom.get("stex_actual_order_stock"),
        "available": element.get("available"),
        "delivery_time": delivery.get("name"),
        "delivery_min": delivery.get("min"),
        "delivery_max": delivery.get("max"),
        "restock_time": element.get("restockTime"),
    }


async def give_stock():
    """Pull from the API everything discover left blank: cards and quantities."""
    started = datetime.now(timezone.utc)
    db.init_db()

    uuids = [row[0] for row in db.fetch_uuids()]
    if not uuids:
        print("! stex24_products is empty, run: python scraper.py discover")
        return
    # Shuffled on purpose: walking ids in alphabetical order is the most
    # conspicuous trace one could possibly leave in someone else's logs.
    random.shuffle(uuids)
    print(f"* {len(uuids)} products, in batches of {BATCH}")

    products, stock = [], []
    async with AsyncSession(
        impersonate="chrome131", timeout=120, max_clients=CONCURRENCY
    ) as session:
        token = await store_api_token(session)
        if not token:
            print(f"! the storefront never handed out {CSRF_COOKIE}, aborting")
            return

        for position in range(0, len(uuids), BATCH):
            chunk = uuids[position : position + BATCH]
            await asyncio.sleep(random.uniform(*PAUSE))
            elements = await fetch_batch(session, chunk, token)
            products.extend(product_record(e) for e in elements)
            stock.extend(stock_record(e) for e in elements)
            print(f"  {position + len(chunk)}/{len(uuids)}: +{len(elements)}")

    saved_products, skipped_products = db.save_products(products)
    saved_stock, skipped_stock = db.save_stock(stock)
    total, new, changed, seen = db.run_stats(started)
    stock_total, _, stock_changed, stock_seen = db.stock_stats(started)

    print(f"\n{len(products)} records, {len(uuids) - len(products)} never came back")
    print(
        f"stex24_products: {total} rows, {new} new, {changed} changed, "
        f"{seen} seen, {saved_products} written, {skipped_products} skipped"
    )
    print(
        f"stex24_stock:    {stock_total} rows, {stock_changed} changed, "
        f"{stock_seen} seen, {saved_stock} written, {skipped_stock} skipped"
    )


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "discover":
        await discover_catalog()
    elif mode == "stock":
        await give_stock()
    else:
        print("usage: python scraper.py [discover|stock]")


if __name__ == "__main__":
    asyncio.run(main())
