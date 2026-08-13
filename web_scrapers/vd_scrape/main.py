from playwright_ import open_w
from filter import filter_data
from db import data_recording
import asyncio

queue = asyncio.Queue()
db_queue = asyncio.Queue()
urls = [
    "https://www.digikey.com/en/products/filter/controllers/cable-assemblies/823?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/controller-accessories/816?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/liquid-level/806?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
    "https://www.digikey.com/en/products/filter/controllers/plc-modules/821?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
]


async def process_data(queue, db_queue):
    while True:
        data = await queue.get()

        if data is None:
            await db_queue.put(None)
            break

        clear_data = await filter_data(data)
        await db_queue.put(clear_data)


async def record_data(db_queue):
    while True:
        data = await db_queue.get()

        if data is None:
            break
        await data_recording(data)


async def main():

    async with asyncio.TaskGroup() as tg:
        tg.create_task(open_w(urls, queue))
        tg.create_task(process_data(queue, db_queue))
        tg.create_task(record_data(db_queue))


asyncio.run(main())
