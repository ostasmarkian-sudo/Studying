import httpx
from bs4 import BeautifulSoup
import asyncio
import json
import re

LIMIT = 500
URL = "https://auto.ria.com/uk/search/"
TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
LIMITS = httpx.Limits(max_connections=7, max_keepalive_connections=7)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en-US;q=0.7,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Referer": "https://auto.ria.com/uk/",
}


async def get_catalog():
    async with (
        httpx.AsyncClient(headers=headers, timeout=TIMEOUT, limits=LIMITS) as client,
    ):
        with open("cars.jsonl", "a", encoding="utf-8") as f:
            params = {
                "category": 0,
                "abroad": 0,
                "customs_cleared": 1,
                "limit": LIMIT,
                "page": 0,
            }
            response = await client.get(URL, params=params)
            html = response.text
            urls = await parser(html)
            print(response.status_code)

            for car_data in urls:
                f.write(json.dumps(car_data, ensure_ascii=False) + "\n")


async def parser(html):
    urls = []
    soup = BeautifulSoup(html, "lxml")
    cars = soup.find_all("a", class_="link product-card horizontal")
    for card in cars:
        car_id = card.get("data-car-id")
        url = "https://auto.ria.com" + card.get("href")

        title = card.select_one(".product-card-content .titleS")
        title = title.get_text(strip=True) if title else None
        cars_count = soup.find("span", class_="common-text ws-pre-wrap body")
        cars_count = cars_count.get_text() if cars_count else None
        match = re.findall(r"\d", cars_count)
        print(match)

        car_data = {
            "car_id": car_id,
            "url": url,
            "title": title,
        }
        urls.append(car_data)
    return urls


asyncio.run(get_catalog())
