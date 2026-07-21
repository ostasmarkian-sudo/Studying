import time
import psycopg
import requests
import re
from config import DATABASE_CONFIG


def add_new_website(url_clean):
    match = re.search(
        r"^(?P<url>https?://(?:www\.)?(?:[a-z0-9-]+\.)*(?P<name>[a-z0-9-]+)\.[a-z]{2,63}(?::\d{1,5})?(?:[/?#][^\s]*)?$)",
        url_clean,
        re.IGNORECASE,
    )
    if match is None:
        print("Некоректне посилання")
        return
    url1c = match.group("url")
    try:
        check = requests.get(url1c, timeout=5)
        check.raise_for_status()

        status = check.status_code
        urlfc = url1c

        print(f"Сайт працює. Статус: {status}")

    except requests.HTTPError as error:
        print(f"Сайт відповів, але повернув помилку: {error}")

    except requests.RequestException as error:
        print(f"Не вдалося підключитися до сайту: {error}")
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

            website_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO checks (website_id,status_code,response_time,is_available,error_message)
                VALUES(%s,%s,%s,%s,%s)
                """,
                (website_id, status_code, response_time, is_available, error_message),
            )
