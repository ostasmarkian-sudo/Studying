import asyncio
import pandas as pd
from sqlalchemy import create_engine
import psycopg2
import matplotlib.pyplot as plt

engine_1 = create_engine(
    "postgresql+psycopg2://postgres:spectr@localhost:5432/product_avnet"
)
engine_2 = create_engine(
    "postgresql+psycopg2://postgres:spectr@localhost:5432/product_dk"
)
digikey_db = pd.read_sql(
    "SELECT product_id,name,company,series,price,product_count,package FROM product_unique",
    engine_2,
)
print(digikey_db)
