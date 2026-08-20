import json
import sys
import time
from datetime import datetime, timezone

import certifi
import httpx
from bs4 import BeautifulSoup

import db
from urllib3.util.ssl_ import create_urllib3_context

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIST_URL = "https://www.automation24.com/en/article/list"
ITEMS = 250
DELAY = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.automation24.com/",
}

SSL_CONTEXT = create_urllib3_context()
SSL_CONTEXT.load_verify_locations(cafile=certifi.where())

CATEGORIES = {
    4: "Sensor systems",
    489: "Process instrumentation",
    39: "Connection technology",
    37: "Industrial enclosures",
    31: "Control & signalling devices",
    544: "Safety technology",
    33: "Industrial controls",
    32: "Measuring & regulation technology",
    35: "Protection equipment",
    29: "Control systems",
    36: "Drive technology",
    41: "Work tools",
    775: "Industrial valves",
    38: "Industrial luminaires",
    30: "Industrial communication technology",
    43: "SALE",
    40: "Power supply",
}


def text(node, default=None):
    return node.get_text(" ", strip=True).replace("\xa0", " ") if node else default


def parse_items(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select(".article-listitem"):
        track = item.select_one("[data-type='ArticleTracking']")
        if not track:
            continue
        link = item.select_one(".title a")
        rrp = item.select_one(".priceUVP [itemprop='price']")
        rating = item.select_one("[itemprop='ratingValue']")
        image = item.select_one("a img")
        sku, _, variant = track.get("data-sku", "").partition(";")
        rows.append(
            {
                "article_id": track.get("data-article-id"),
                "sku": sku,
                "variant": variant,
                "name": track.get("data-name"),
                "brand": track.get("data-brand"),
                "price": track.get("data-price"),
                "discount": track.get("data-discount"),
                "rrp": rrp.get("content") if rrp else None,
                "currency": track.get("data-currency-code"),
                "category": track.get("data-category"),
                "category_id": track.get("data-category-id"),
                "availability": text(
                    item.select_one("[data-id='availability-container']")
                ),
                "rating": rating.get("content") if rating else None,
                "reviews": text(item.select_one("[itemprop='reviewCount']")),
                "url": "https://www.automation24.com" + link["href"] if link else None,
                "image": image.get("src") if image else None,
                "description": text(item.select_one(".shopdesc")),
            }
        )
    return rows


def scrape_category(client, category_id):
    page = 1
    while True:
        response = client.get(
            LIST_URL,
            params={
                "Page": page,
                "Items": ITEMS,
                "Filter": json.dumps(
                    {"category": [category_id]}, separators=(",", ":")
                ),
                "s": "",
                "Sort": 1,
                "view": "",
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows = parse_items(payload["RenderedView"])
        yield page, rows, payload["TotalResultsCount"]
        if len(rows) < ITEMS:
            return
        page += 1
        time.sleep(DELAY)


def main(category_ids):
    db.init_db()
    started_at = datetime.now(timezone.utc)
    fetched = skipped_total = 0

    with httpx.Client(
        verify=SSL_CONTEXT, headers=HEADERS, follow_redirects=True, timeout=120
    ) as client:
        for category_id in category_ids:
            print()
            print(f"[{category_id}] {CATEGORIES.get(category_id, '?')}")
            for page, rows, total in scrape_category(client, category_id):
                written, skipped = db.save_products(rows)
                fetched += len(rows)
                skipped_total += skipped
                print(
                    f"  page {page}: {len(rows):>4} products in {total:>5} "
                    f"-> в базу {written}" + (f", skip {skipped}" if skipped else "")
                )
            time.sleep(DELAY)

    rows_total, new, changed, seen = db.run_stats(started_at)
    print()
    print(
        f"collected rows: {fetched}"
        + (f", skip: {skipped_total}" if skipped_total else "")
    )
    print(
        f"in automation24_products: {rows_total} products "
        f"(new {new}, changed {changed}, products_seen {seen})"
    )


if __name__ == "__main__":
    # python scraper.py            - усі категорії
    # python scraper.py 40 36      - лише вказані id
    main([int(arg) for arg in sys.argv[1:]] or list(CATEGORIES))
