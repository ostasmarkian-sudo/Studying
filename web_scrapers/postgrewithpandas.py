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
automation24 = pd.read_sql(
    "SELECT article_id,name,brand,price FROM automation24_products", engine_1
)
avnet = pd.read_sql(
    """
    SELECT
    p.item_number,
    p.mpn,
    p.mpn_norm,
    p.mfr_name,
    p.packaging,
    p.in_stock,
    pr.price,
    pr.currency,
    ps.qty AS stock_qty,
    ps.lead_time_weeks
FROM products p
LEFT JOIN products_price pr ON pr.item_number = p.item_number
LEFT JOIN products_stock ps ON ps.item_number = p.item_number;""",
    engine_1,
)

stex24 = pd.read_sql("SELECT * FROM stex24_products", engine_1)
df = pd.read_sql("SELECT * FROM product_unique", engine_2)
import pandas as pd
import matplotlib.pyplot as plt

df.columns = [
    "id",
    "code",
    "sku",
    "manufacturer",
    "model",
    "price",
    "quantity",
    "unit",
    "timestamp",
]
top_by_sku = df.groupby("manufacturer").size().sort_values(ascending=False).head(10)
top_by_qty = (
    df.groupby("manufacturer")["quantity"].sum().sort_values(ascending=False).head(10)
)
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].barh(top_by_sku.index[::-1], top_by_sku.values[::-1])
axes[0].set_title("Manufactures Manufactures (SKU)")
axes[0].set_xlabel("number unique products")

axes[1].barh(top_by_qty.index[::-1], top_by_qty.values[::-1])
axes[1].set_title("Top-10 Manufactures (quantity)")
axes[1].set_xlabel("Total number")

plt.tight_layout()
plt.show()
