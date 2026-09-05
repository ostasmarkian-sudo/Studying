import httpx
import asyncio
import json
import psycopg

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
  id year race VIN uri title status createdAt
  brand{id name} model{id name} fuel{id name} gearbox{id name}
  engine{volume{liters}}
  price{main{value currency{sign}} all{USD{value} UAH{value}}}
  location{city{id name} state{id name}}
  photos{all{url}}
}}"""

LIMIT = 500
URL = "https://auto.ria.com/uk/search/"
TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=60.0)
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

QUEUE_MAXSIZE = 8
GQL_BATCH = 500
CONSUMERS = 1

queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)


async def fetch_ids(
    client,
    queue,
    categories=range(1, 11),
):
    total = 0
    for category_id in categories:
        page = 0
        while True:
            r = await client.get(
                A, params={"category_id": category_id, "page": page, "countpage": 100}
            )
            r.raise_for_status()
            batch = r.json()["result"]["search_result"]["ids"]
            if not batch:
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
            queue.put_nowait(None)
            break
        ids += nxt
    return ids


async def consume(client, queue):
    while True:
        ids = await drain(queue)
        if ids is None:
            break
        await fetch_cars(client, ids)


async def produce(client, queue, categories=range(1, 11), consumers=CONSUMERS):
    try:
        await fetch_ids(client, queue, categories)
    finally:
        for _ in range(consumers):
            await queue.put(None)


async def fetch_cars(client, ids):
    r = await client.post(
        U, json={"query": Q, "variables": {"ids": ids[:500], "lang": 4}}
    )
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        print("errors:", len(d["errors"]), d["errors"][0]["message"])
    for car in (d.get("data") or {}).get("advertisements") or []:
        if car["status"] != "ACTIVE" or car["brand"] is None:
            continue
        print(car["id"], car["title"], car["price"]["all"]["USD"]["value"], "$")


async def main():
    async with httpx.AsyncClient(
        headers=headers, limits=LIMITS, timeout=TIMEOUT
    ) as client:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(produce(client, queue))
            for _ in range(CONSUMERS):
                tg.create_task(consume(client, queue))


asyncio.run(main())
