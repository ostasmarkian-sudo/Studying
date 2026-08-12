from playwright_ import open_w
from filter import filter_data
import os
import asyncio

urls = [
    "https://www.digikey.com/en/products/filter/controllers/cable-assemblies/823?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/controller-accessories/816?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUY%2BTLkYADN7UA",
    "https://www.digikey.com/en/products/filter/controllers/liquid-level/806?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
    "https://www.digikey.com/en/products/filter/controllers/plc-modules/821?s=N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL61A",
]


async def process_data(queue):
    while True:
        data = await queue.get()

        if data is None:
            break

        await filter_data(data)


async def main():
    queue = asyncio.Queue()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(open_w(urls, queue))
        tg.create_task(process_data(queue))


asyncio.run(main())
