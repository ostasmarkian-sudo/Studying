from psycopg.rows import dict_row

DATABASE_CONFIG = {
    "dbname": "test",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
    "row_factory": dict_row,
}
