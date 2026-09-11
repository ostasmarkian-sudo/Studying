import asyncio
import random
import sys
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import DATABASE_CONNECTION, data_recording, init_db


SOURCE = "auto.ria"

A = "https://auto.ria.com/api/search/auto"
U = "https://auto.ria.com/graphql/"
H = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://auto.ria.com/uk/search/",
    "Origin": "https://auto.ria.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}
Q = """query($ids:[ID],$lang:ID){ advertisements(ids:$ids, langId:$lang){
  id createdAt year race VIN uri title custom abroad status
  brand{id name} model{id name} body{id} category{id name}
  fuel{id name} gearbox{name}
  engine{volume{liters}}
  price{main{value currency{sign}} all{USD{value} UAH{value} EUR{value}}}
  location{city{id name} state{id name}}
  photos{main{url} all{url}}
  owner{id name rating{average count} company{id name}}
  publication{createdAt expiredAt}
  levels{active{value}} country{id}
}}"""

LIMIT = 500
URL = "https://auto.ria.com/uk/search/"
TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=60.0)
LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=8)
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

QUEUE_MAXSIZE = 8
GQL_BATCH = 500
CONSUMERS = 3

queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)


async def request(client, method, url, retries=5, **kwargs):
    last = None
    for attempt in range(retries):
        try:
            r = await client.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                last = httpx.HTTPStatusError(
                    f"HTTP {r.status_code}", request=r.request, response=r
                )
            else:
                r.raise_for_status()
                return r
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
        delay = 2**attempt + random.uniform(0, 1)
        print(
            f"    retry {attempt + 1}/{retries} за {delay:.1f}s ({type(last).__name__})"
        )
        await asyncio.sleep(delay)
    raise last


async def fetch_ids(
    client,
    queue,
    categories=range(1, 11),
    full=False,
):
    total = 0
    with psycopg.connect(**DATABASE_CONNECTION) as conn:
        for category_id in categories:
            row = conn.execute(
                """select car_id from cars
                   where category_id = %s and listed_at is not null
                   order by listed_at desc limit 1""",
                (category_id,),
            ).fetchone()
            stop_at = None if full else (str(row[0]) if row else None)
            page = 0
            while True:
                r = await request(
                    client,
                    "GET",
                    A,
                    params={
                        "category_id": category_id,
                        "page": page,
                        "countpage": 100,
                        "order_by": 7,
                    },
                )
                batch = r.json()["result"]["search_result"]["ids"]

                if not batch:
                    break
                if stop_at in batch:
                    batch = batch[: batch.index(stop_at)]
                    if batch:
                        await queue.put(batch)
                        total += len(batch)
                        print(f"cat {category_id} page {page}: +{len(batch)}")
                    break
                await queue.put(batch)
                total += len(batch)
                page += 1
                print(
                    f"cat {category_id} page {page}: +{len(batch)} (queue {queue.qsize()})"
                )
        print(f"finished: {total} id")


async def drain(queue, limit=GQL_BATCH):
    batch = await queue.get()
    if batch is None:
        return None
    ids = list(batch)
    while len(ids) < limit:
        try:
            nxt = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if nxt is None:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            break
        ids += nxt
    return ids


async def consume(client, queue):
    while True:
        ids = await drain(queue)
        if ids is None:
            break
        try:
            await fetch_cars(client, ids)
        except Exception as e:
            print(f"  consume skiped {len(ids)} id: {type(e).__name__}: {str(e)[:70]}")


async def produce(
    client, queue, categories=range(1, 11), consumers=CONSUMERS, full=False
):
    try:
        await fetch_ids(client, queue, categories, full=full)
    finally:
        for _ in range(consumers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                break


async def fetch_cars(client, ids):
    r = await request(
        client, "POST", U, json={"query": Q, "variables": {"ids": ids[:500], "lang": 4}}
    )
    d = r.json()
    if "errors" in d:
        print("errors:", len(d["errors"]), d["errors"][0]["message"])
    cars = [
        car
        for car in (d.get("data") or {}).get("advertisements") or []
        if car and car.get("status") == "ACTIVE" and car.get("brand")
    ]
    written, skipped, historied = await data_recording(cars, source=SOURCE)
    print(f"  db:recorded {written}, skipped {skipped}, histored +{historied}")


async def main():
    async with httpx.AsyncClient(
        headers=headers, limits=LIMITS, timeout=TIMEOUT
    ) as client:
        await init_db()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(produce(client, queue))
            for _ in range(CONSUMERS):
                tg.create_task(consume(client, queue))


asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
