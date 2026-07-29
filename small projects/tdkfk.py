import requests
from bs4 import BeautifulSoup
import re

x = 1
while x < 51:
    url = f"https://books.toscrape.com/catalogue/page-{x}.html"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for match in soup.find_all("li", class_="col-xs-6 col-sm-4 col-md-3 col-lg-3"):
        product_pod = match.find("article", class_="product_pod")
        print(product_pod.h3.a.text)
        product_prise = product_pod.find("div", class_="product_price")
        filt = re.search(r"(\d+)", product_prise.p.text)
        print(filt.group(1) + "£")
        instock_availability = product_prise.find(
            "p", class_="instock availability"
        ).text.strip()
        print(instock_availability)
    x += 1
