import pandas as pd
from sqlalchemy import create_engine
import psycopg2
def rewrite_stock(x):
    if x == ""
engine_1 = create_engine(
    "postgresql+psycopg2://postgres:spectr@localhost:5432/product_avnet"
)
engine_2 = create_engine(
    "postgresql+psycopg2://postgres:spectr@localhost:5432/product_dk"
)
automation24 = pd.read_sql(
    "SELECT article_id,name,brand,price, FROM automation24_products", engine_1
)
avnet = pd.read_sql("SELECT * FROM products", engine_1)
stex24 = pd.read_sql("SELECT * FROM stex24_products", engine_1)
digikey = pd.read_sql("SELECT * FROM product_unique", engine_2)