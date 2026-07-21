import psycopg
import argparse

parse = argparse.ArgumentError
parse.argument_name(
    "-a",
)
with psycopg.connect(
    host="localhost", port=5432, dbname="test", user="postgres", password="password"
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM person")

        for person in cursor.fetchall():
            print(person)
