import requests
from bs4 import BeautifulSoup
import re
import psycopg
from config import DATABASE_CONFIG, HEADERS

book = "ui-catalog-card--variant-default mui-1i20r6w-ui-catalog-card"
page = 1
id = 1
with psycopg.connect(**DATABASE_CONFIG) as connection:
    with connection.cursor() as cursor:
        while page < 233:
            url = f"https://ksd.ua/books/special/all/page-{page}"
            req = requests.get(url, timeout=10, headers=HEADERS)
            req.raise_for_status()
            soup = BeautifulSoup(req.text, "html.parser")
            for match in soup.find_all("a", class_=book):
                id += 1
                book_name = match.find(
                    "p",
                    class_="MuiTypography-root MuiTypography-body1 ui-catalog-card__title mui-1st0ryw",
                )
                book_name = book_name.text
                book_author = match.find(
                    "p",
                    class_="MuiTypography-root MuiTypography-body2 ui-catalog-card__authors mui-y7plz2",
                )
                try:
                    book_author = book_author.text
                except AttributeError:
                    book_author = "немає"
                book_rate = match.find(
                    "div",
                    class_="ui-catalog-card__rating-wrapper",
                )
                try:
                    available = True
                    prise = match.find("div", class_="MuiBox-root mui-0")
                    book_price = prise.find(
                        "span",
                        class_="MuiTypography-root MuiTypography-h4 ui-catalog-card__price mui-1ng6fsq",
                    ).span.text
                    ds = prise.find(
                        "span",
                        class_="MuiTypography-root MuiTypography-subtitle3 ui-catalog-card__price ui-catalog-card__price--old mui-161am5x",
                    )
                    if ds == None:
                        discount = 0
                    else:
                        ds = ds.text
                        d = re.search(r"(\d+)", ds)
                        ds = d.group(1)
                        discount = int(ds) - int(book_price)
                except AttributeError:
                    book_price = 0
                    discount = 0
                    available = False
                rating_paragraphs = book_rate.select("p")
                rate = rating_paragraphs[0].get_text(strip=True)
                if rate == "":
                    rate = None
                rate_count = rating_paragraphs[1].get_text(strip=True)
                if rate_count == "":
                    rate_count = 0
                d = re.search(r"(\d+)", rate_count)
                rate_count = d.group(1)
                product_link = match.get("href")
                product_link = "ksd.ua" + product_link
                cursor.execute(
                    """
                    INSERT INTO books (
                        book_name,
                        book_author,
                        book_rate,
                        book_count_rate,
                        book_price,
                        bpwd,
                        product_link,
                        available
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s,%s)
                    ON CONFLICT (product_link)
                    DO UPDATE SET
                        book_name = EXCLUDED.book_name,
                        book_author = EXCLUDED.book_author,
                        book_rate = EXCLUDED.book_rate,
                        book_count_rate = EXCLUDED.book_count_rate,
                        book_price = EXCLUDED.book_price,
                        bpwd = EXCLUDED.bpwd,
                        available = EXCLUDED.available;
                    """,
                    (
                        book_name,
                        book_author,
                        rate,
                        rate_count,
                        book_price,
                        discount,
                        product_link,
                        available,
                    ),
                )

                print(f"Збережено: {book_name},сторінка: {page},книга: {id}")
            page += 1
