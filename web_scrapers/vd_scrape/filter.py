from dataclasses import dataclass
import re
from decimal import Decimal


@dataclass
class Product:
    product_id: str
    name: str
    prise: Decimal
    company: str
    product_count: int


async def filter_data(data):
    products = data["data"]["products"]
    for product in products:
        name = str(product[0]["value"]["manufacturerPartNumber"])
        prise = Decimal(product[0]["value"]["price"])
        company = str(product[0]["value"]["manufacturer"]["name"])
        product_id = str(product[0]["value"]["productId"])
        product_count = int(product[2]["value"][0]["quantity"])
