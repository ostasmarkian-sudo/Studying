import time
import psycopg
import requests
import re
from config import DATABASE_CONFIG


def add_new_website(url_clean):
    match = re.search(
        r"^(?P<url>https?://(?:www\.)?(?:[a-z0-9-]+\.)*(?P<name>[a-z0-9-]+)\.[a-z]{2,63}(?::\d{1,5})?(?:[/?#][^\s]*)?)$",
        url_clean,
        re.IGNORECASE,
    )
    if match is None:
        print("Некоректне посилання")
        return
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                           SELECT id,name FROM websites
                           WHERE url = %s OR name = %s;
                           """,
                (
                    match.group("url"),
                    match.group("name"),
                ),
            )
            if cursor.fetchone():
                print("Цей сайт уже існує")
                return

    url1c = match.group("url")
    start = time.perf_counter()
    status_code = None
    response_time = None
    is_available = False
    error_message = None
    try:
        check = requests.get(url1c, timeout=5)
        check.raise_for_status()

        status_code = check.status_code
        response_time = time.perf_counter() - start
        urlfc = url1c
        is_available = True
        error_message = None

        print(f"Сайт працює. Статус: {status_code}")

    except requests.HTTPError as error:
        response_time = time.perf_counter() - start
        error_message = f"Сайт відповів, але повернув помилку: {error}"
        urlfc = url1c
        is_available = False

    except requests.RequestException as error:
        error_message = f"Не вдалося підключитися до сайту: {error}"[:64]
        is_available = False
        urlfc = url1c
    name = match.group("name")
    url = urlfc
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO websites (name,url) 
                VALUES (%s, %s)
                RETURNING id;
                """,
                (name, url),
            )

            result = cursor.fetchone()
            response_time = round(response_time, 3)

            if result is None:
                raise RuntimeError("INSERT не повернув ID")

            website_id = result["id"]
            cursor.execute(
                """
                INSERT INTO checks (website_id,status_code,response_time,is_available,error_message)
                VALUES(%s,%s,%s,%s,%s)
                """,
                (website_id, status_code, response_time, is_available, error_message),
            )


def find_website_history(name_or_url):
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                           SELECT websites.*, checks.* from checks
                           JOIN websites
                           ON checks.website_id = websites.id
                           WHERE websites.name ILIKE  %s or websites.url = %s;
                           """,
                (name_or_url, name_or_url),
            )
            results = cursor.fetchall()
            if not results:
                print("Цього сайту немає в бд")
                return
            for row in results:
                print(row)
