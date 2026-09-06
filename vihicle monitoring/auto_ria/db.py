import asyncio
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

DATABASE_CONNECTION = {
    "dbname": "vihicle",
    "user": "postgres",
    "password": "spectr",
    "host": "localhost",
    "port": 5432,
}

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

CAR_COLUMNS = (
    "car_id",
    "vin_masked",
    "title",
    "brand_id",
    "brand",
    "model_id",
    "model",
    "category_id",
    "body_id",
    "year",
    "mileage_km",
    "fuel_id",
    "fuel",
    "gearbox",
    "engine_liters",
    "price_usd",
    "price_uah",
    "price_eur",
    "currency",
    "city_id",
    "city",
    "state_id",
    "state",
    "seller_id",
    "seller_name",
    "seller_rating",
    "seller_reviews",
    "seller_company",
    "is_dealer",
    "photo_main",
    "photos",
    "customs_code",
    "abroad",
    "country_import",
    "promo_level",
    "status",
    "url",
    "listed_at",
    "published_at",
    "expires_at",
    "data_hash",
)

HASHED_FIELDS = (
    "price_usd",
    "price_uah",
    "price_eur",
    "status",
    "mileage_km",
    "promo_level",
    "expires_at",
)

_UPDATABLE = tuple(c for c in CAR_COLUMNS if c != "car_id")

UPSERT_CARS_SQL = """
    INSERT INTO cars ({columns})
    VALUES ({placeholders})
    ON CONFLICT (car_id) DO UPDATE SET
        {assignments},
        updated_at = CASE
            WHEN cars.data_hash IS DISTINCT FROM EXCLUDED.data_hash THEN now()
            ELSE cars.updated_at
        END,
        last_seen_at = now()
""".format(
    columns=", ".join(CAR_COLUMNS),
    placeholders=", ".join(["%s"] * len(CAR_COLUMNS)),
    assignments=",\n        ".join(f"{c} = EXCLUDED.{c}" for c in _UPDATABLE),
)

HISTORY_COLUMNS = (
    "car_id",
    "vin_masked",
    "price_usd",
    "price_uah",
    "status",
    "promo_level",
    "snapshot",
    "data_hash",
)

INSERT_HISTORY_SQL = """
    INSERT INTO car_history ({columns})
    VALUES ({placeholders})
    ON CONFLICT (car_id, data_hash) DO NOTHING
""".format(
    columns=", ".join(HISTORY_COLUMNS),
    placeholders=", ".join(["%s"] * len(HISTORY_COLUMNS)),
)


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _num(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _ts(value):
    ms = _int(value)
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _dig(source, *path):
    current = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _hash(row):
    payload = json.dumps(
        [str(row.get(field)) for field in HASHED_FIELDS],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def build_row(car):
    """Розкласти одну машину з GraphQL у плаский словник під колонки cars.

    На вхід іде сирий обʼєкт advertisements(...) як він прийшов. Повертає None
    для запису без car_id або без title: перше - ключ апсерта, друге приходить
    порожнім у неіснуючих id, які лишають по собі обʼєкт із самих None.
    """
    car_id = _int(car.get("id"))
    title = _text(car.get("title"))
    if car_id is None or title is None:
        return None

    # У API пробіг у тисячах км (169 = 169 тис.), у базі - в км.
    mileage = _int(car.get("race"))
    uri = _text(car.get("uri"))
    company = _text(_dig(car, "owner", "company", "name"))

    row = {
        "car_id": car_id,
        "vin_masked": _text(car.get("VIN")),
        "title": title,
        "brand_id": _int(_dig(car, "brand", "id")),
        "brand": _text(_dig(car, "brand", "name")),
        "model_id": _int(_dig(car, "model", "id")),
        "model": _text(_dig(car, "model", "name")),
        "category_id": _int(_dig(car, "category", "id")),
        "body_id": _int(_dig(car, "body", "id")),
        "year": _int(car.get("year")),
        "mileage_km": mileage * 1000 if mileage is not None else None,
        "fuel_id": _int(_dig(car, "fuel", "id")),
        "fuel": _text(_dig(car, "fuel", "name")),
        "gearbox": _text(_dig(car, "gearbox", "name")),
        "engine_liters": _num(_dig(car, "engine", "volume", "liters")),
        "price_usd": _int(_dig(car, "price", "all", "USD", "value")),
        "price_uah": _int(_dig(car, "price", "all", "UAH", "value")),
        "price_eur": _int(_dig(car, "price", "all", "EUR", "value")),
        "currency": _text(_dig(car, "price", "main", "currency", "sign")),
        "city_id": _int(_dig(car, "location", "city", "id")),
        "city": _text(_dig(car, "location", "city", "name")),
        "state_id": _int(_dig(car, "location", "state", "id")),
        "state": _text(_dig(car, "location", "state", "name")),
        "seller_id": _int(_dig(car, "owner", "id")),
        "seller_name": _text(_dig(car, "owner", "name")),
        "seller_rating": _num(_dig(car, "owner", "rating", "average")),
        "seller_reviews": _int(_dig(car, "owner", "rating", "count")),
        "seller_company": company,
        # Компанія в owner є лише в автосалонів, приватники її не мають -
        # це найнадійніша ознака дилера з того, що віддає API.
        "is_dealer": bool(company),
        "photo_main": _text(_dig(car, "photos", "main", "url")),
        "photos": [
            p["url"] for p in (_dig(car, "photos", "all") or []) if p and p.get("url")
        ],
        "customs_code": _int(car.get("custom")),
        "abroad": car.get("abroad"),
        "country_import": _int(_dig(car, "country", "id")),
        "promo_level": _int(_dig(car, "levels", "active", "value")),
        "status": _text(car.get("status")) or "UNKNOWN",
        "url": f"https://auto.ria.com{uri}" if uri else None,
        "listed_at": _ts(car.get("createdAt")),
        "published_at": _ts(_dig(car, "publication", "createdAt")),
        "expires_at": _ts(_dig(car, "publication", "expiredAt")),
    }
    row["data_hash"] = _hash(row)
    return row


def _car_tuple(row):
    return tuple(
        Jsonb(row[column]) if column == "photos" else row[column]
        for column in CAR_COLUMNS
    )


def _history_tuple(row):
    # Знімок кладеться без bytea і без datetime/Decimal - jsonb їх не приймає,
    # а відбиток і так лежить окремою колонкою.
    snapshot = {}
    for key, value in row.items():
        if key == "data_hash":
            continue
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        snapshot[key] = value
    return (
        row["car_id"],
        row["vin_masked"],
        row["price_usd"],
        row["price_uah"],
        row["status"],
        row["promo_level"],
        Jsonb(snapshot),
        row["data_hash"],
    )


def _data_recording_sync(cars):
    rows, skipped = [], 0
    for car in cars:
        row = build_row(car) if isinstance(car, dict) else None
        if row is None:
            skipped += 1
            continue
        rows.append(row)

    # Один car_id може прийти двічі в межах пачки: сторінки видачі дрейфують,
    # і сусідні сторінки подекуди повертають те саме оголошення. Лишаємо
    # останній стан - писати той самий ключ двічі в одному executemany не можна.
    rows = list({row["car_id"]: row for row in rows}.values())
    if not rows:
        return 0, skipped, 0

    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(UPSERT_CARS_SQL, [_car_tuple(r) for r in rows])
            written = cursor.rowcount
            cursor.executemany(INSERT_HISTORY_SQL, [_history_tuple(r) for r in rows])
            historied = cursor.rowcount
    return written, skipped, historied


async def data_recording(cars):
    if not cars:
        return 0, 0, 0
    return await asyncio.to_thread(_data_recording_sync, cars)


def _init_db_sync():
    with psycopg.connect(**DATABASE_CONNECTION) as connection:
        connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


async def init_db():
    """Створити таблиці, якщо їх ще немає. Ідемпотентно, можна щозапуску."""
    await asyncio.to_thread(_init_db_sync)
