from dataclasses import dataclass
import re
import asyncio
from decimal import Decimal

queue = asyncio.Queue()


@dataclass
class Product:
    product_id: str
    name: str
    price: Decimal
    company: str
    product_count: int
    series: str
    package: str


async def filter_data(data):
    filtered_products = []
    products = data["data"]["products"]
    for product in products:
        name = str(product[0]["value"]["manufacturerPartNumber"])
        try:
            price = Decimal(str(product[0]["value"]["price"]))
        except KeyError:
            try:
                price = Decimal(str(round(product[3]["value"][0]["unitPrice"], 2)))
            except:
                price = None
        try:
            company = str(product[0]["value"]["manufacturer"]["name"])
        except KeyError:
            try:
                company = str(product[1]["value"]["manufacturer"]["value"]["label"])
            except:
                company = None
        product_id = str(product[0]["value"]["productId"])
        product_count = product[2]["value"][0]["quantity"]
        product_count = int(product_count.replace(",", ""))
        try:
            series = str(product[5]["value"]["label"])
        except:
            series = None
        try:
            package = str(product[6]["value"][0]["value"])
        except:
            package = None
        filtered_product = Product(
            product_id=product_id,
            name=name,
            price=price,
            company=company,
            product_count=product_count,
            series=series,
            package=package,
        )
        filtered_products.append(filtered_product)
    await queue.put(filtered_products)
