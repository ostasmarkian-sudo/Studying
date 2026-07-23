import time
from config import DATABASE_CONFIG
import psycopg
import requests
import telebot
from config import TG_BOT_TOKEN, CHAT_ID

bot = telebot.TeleBot(TG_BOT_TOKEN)
headers = {"User-Agent": "MyWebsiteMonitoring"}


def update():
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                            SELECT DISTINCT ON (websites.id)
                                websites.url,
                                checks.status_code,
                                websites.id
                            FROM websites
                            JOIN checks
                                ON checks.website_id = websites.id
                            ORDER BY
                                websites.id,
                                checks.checked_at DESC,
                                checks.id DESC;
                           """)
            result = cursor.fetchall()
            for row in result:
                status = row["status_code"]
                url = row["url"]
                website_id = row["id"]
                status_code = None
                response_time = None
                is_available = False
                error_message = None
                start = time.perf_counter()
                try:
                    check = requests.get(url, timeout=5, headers=headers)
                    status_code = check.status_code
                    check.raise_for_status()
                    response_time = time.perf_counter() - start
                    is_available = True
                    error_message = None
                except requests.HTTPError as error:
                    response_time = time.perf_counter() - start
                    error_message = str(error)[:64]
                    is_available = False

                except requests.RequestException as error:
                    response_time = time.perf_counter() - start
                    is_available = False
                    error_message = str(error)[:64]
                response_time = round(response_time, 3)
                cursor.execute(
                    """
                            INSERT INTO checks(website_id,status_code,response_time,is_available,error_message)
                            VALUES(%s,%s,%s,%s,%s)
                            """,
                    (
                        website_id,
                        status_code,
                        response_time,
                        is_available,
                        error_message,
                    ),
                )
                if status != status_code:
                    bot.send_message(CHAT_ID, f"{url} change status to {status_code}")
