import asyncio


async def fetch_data(id, delay):
    print(f"{id} loading information....")
    await asyncio.sleep(delay)
    return f"{id} information load"


async def main():
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for i, ts in enumerate([1, 4, 3, 2], start=1):
            task = tg.create_task(fetch_data(i, ts))
            tasks.append(task)
    results = [task.result() for task in tasks]
    for result in results:
        print(result)


asyncio.run(main())
