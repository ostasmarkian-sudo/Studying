import requests
from bs4 import BeautifulSoup
import re
import psycopg
from config import DATABASE_CONFIG, HEADERS


def book_list_sql():
    with psycopg.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                        SELECT book_name FROM books;
                        """,
            )
            books = cursor.fetchall()
            return books


book = book_list_sql()
