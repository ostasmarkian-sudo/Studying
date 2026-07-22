import time
from config import DATABASE_CONFIG
import psycopg
import requests


def update():
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT websites.url,checks.status_code,website.id FROM checks
                           JOIN websites
                           ON checks.website_id = websites.id
                           """)
            result = cursor.fetchall()
            for row in result:
                status = row["status_code"]
                url = row["url"]
                start = time.perf_counter()
                rest = requests.get(url, timeout=5)
                status_n = rest.status_code()
                website_id = row["id"]
                response_time = time.perf_counter() - start
                if status != status_n:
                    print("Сайт змінив статус")
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                        INSERT INTO checks(website_id,status_code,response_time,is_available,error_message)
                        VALUES(%s,%s,%s,%s,%s)
                           """,
                (
                    website_id,
                    status_n,
                    response_time,
                ),
            )
