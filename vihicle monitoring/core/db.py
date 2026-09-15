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
    "source",
    "fingerprint",
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
    "power_hp",
    "power_kw",
    "price_main",
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

# Only what the SELLER changes. price_uah/price_eur/price_usd are left out:
# the server recalculates them at the current rate on every request, so between
# two neighbouring runs they differ in 96-98% of rows. With them in, each run
# wrote ~340k history rows of which about 1% carried meaning. expires_at and
# promo_level drift on their own the same way and say nothing about the ad.
# Traits of the CAR itself, the ones that hold while it is still the same car.
# Price, mileage and status are deliberately absent: they move, the print must
# not.
IDENTITY_FIELDS = (
    "vin_masked",
    "brand_id",
    "model_id",
    "year",
)

HASHED_FIELDS = (
    "price_main",
    "currency",
    "status",
    "mileage_km",
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
    "source",
    "vin_masked",
    "price_main",
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


# Nothing on auto.ria makes this, ships included. Above it the number is not
# power at all: an electric scooter listed as "2720" is watts, and the rest is
# simply mistyped. Measured on 1000 live ads, it drops 2 of 344 filled values.
POWER_CEILING = 2000


def _power(value):
    """Engine power, or None where the number cannot be power.

    The API reports the unknown as a 0 rather than a null (checked on live
    ads), and a zero would quietly pass every "from X hp" filter and pull the
    averages down.
    """
    number = _int(value)
    if not number or number < 0 or number > POWER_CEILING:
        return None
    return number


def _sane_power(hp, kw, liters):
    """Drop the pair where the seller typed the displacement into power.

    A "Lada 2108" with 1.5 l and 1500 hp, an Opel Kadett with 1.3 l and 1300.
    The value matches the displacement in cc exactly, which is what makes it
    safe to catch: no 1.5 litre car makes 1500 hp. kW goes out together with
    it, the site computes that one from hp and so repeats the same mistake.
    About 1.5% of the ads that have power at all.
    """
    if hp and liters and hp == round(float(liters) * 1000):
        return None, None
    return hp, kw


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


def _fingerprint(row):
    if not row.get("vin_masked"):
        return None
    payload = "|".join(str(row.get(f)) for f in IDENTITY_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _hash(row):
    payload = json.dumps(
        [str(row.get(field)) for field in HASHED_FIELDS],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def build_row(car, source="auto.ria"):
    """Flatten one GraphQL car into a dict shaped like the cars columns.

    Takes the raw advertisements(...) object exactly as it arrived. Returns
    None for a record with no car_id or no title: the first is the upsert key,
    the second comes back empty for ids that do not exist, which leave behind
    an object of nothing but None.
    """
    car_id = _int(car.get("id"))
    title = _text(car.get("title"))
    if car_id is None or title is None:
        return None

    # The API gives mileage in thousands of km (169 = 169k), the db in km.
    mileage = _int(car.get("race"))
    uri = _text(car.get("uri"))
    company = _text(_dig(car, "owner", "company", "name"))

    liters = _num(_dig(car, "engine", "volume", "liters"))
    power_hp, power_kw = _sane_power(
        _power(_dig(car, "engine", "power", "hp")),
        _power(_dig(car, "engine", "power", "kW")),
        liters,
    )

    row = {
        "car_id": car_id,
        "source": source,
        "fingerprint": None,
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
        "engine_liters": liters,
        "power_hp": power_hp,
        "power_kw": power_kw,
        "price_main": _int(_dig(car, "price", "main", "value")),
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
    row["fingerprint"] = _fingerprint(row)
    row["data_hash"] = _hash(row)
    return row


def _car_tuple(row):
    return tuple(
        Jsonb(row[column]) if column == "photos" else row[column]
        for column in CAR_COLUMNS
    )


def _history_tuple(row):
    snapshot = {}
    for key, value in row.items():
        if key in ("data_hash", "fingerprint"):
            continue
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        snapshot[key] = value
    return (
        row["car_id"],
        row["source"],
        row["vin_masked"],
        row["price_main"],
        row["price_usd"],
        row["price_uah"],
        row["status"],
        row["promo_level"],
        Jsonb(snapshot),
        row["data_hash"],
    )


def _prepare(cars, source):
    rows, skipped = [], 0
    for car in cars:
        row = build_row(car, source) if isinstance(car, dict) else None
        if row is None:
            skipped += 1
            continue
        rows.append(row)
    rows = list({row["car_id"]: row for row in rows}.values())
    return (
        [_car_tuple(row) for row in rows],
        [_history_tuple(row) for row in rows],
        skipped,
    )


async def data_recording(cars, source="auto.ria"):
    if not cars:
        return 0, 0, 0

    car_rows, history_rows, skipped = await asyncio.to_thread(_prepare, cars, source)
    if not car_rows:
        return 0, skipped, 0

    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONNECTION
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.executemany(UPSERT_CARS_SQL, car_rows)
            written = cursor.rowcount
            await cursor.executemany(INSERT_HISTORY_SQL, history_rows)
            historied = cursor.rowcount
    return written, skipped, historied


async def init_db():
    """Create the tables if they are missing. Idempotent, safe on every run."""
    # execute() without parameters goes over the simple protocol (PQsendQuery),
    # and that one accepts the whole schema.sql in a single piece. Otherwise
    # the file would have to be cut into separate statements.
    schema = await asyncio.to_thread(SCHEMA_PATH.read_text, encoding="utf-8")
    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONNECTION
    ) as connection:
        await connection.execute(schema)


SCAN_STATE_SQL = """
    INSERT INTO scan_state (source, category_id, boundary_at)
    VALUES (%s, %s, %s)
    ON CONFLICT (source, category_id) DO UPDATE SET
        boundary_at = EXCLUDED.boundary_at,
        finished_at = now()
"""


async def read_boundary(connection, source, category_id):
    """Head time of the feed as of the last completed run, or None."""
    cursor = await connection.execute(
        "SELECT boundary_at FROM scan_state WHERE source = %s AND category_id = %s",
        (source, category_id),
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def write_boundary(connection, source, category_id, boundary_at):
    await connection.execute(SCAN_STATE_SQL, (source, category_id, boundary_at))


async def touch_seen(connection, ids):
    """Mark that these ids are still present in the feed.

    Kept deliberately apart from writing the data: if GraphQL fails on a batch,
    the cars still stay marked as alive and the weekly pass will not bury them
    by mistake.
    """
    await connection.execute(
        "UPDATE cars SET last_seen_at = now() WHERE car_id = ANY(%s)",
        ([int(i) for i in ids],),
    )


async def stale_active(started_at, source="auto.ria", categories=None):
    """Rows still active in the db that a full crawl never met in the feed."""
    sql = """SELECT car_id FROM cars
             WHERE source = %s AND status = 'ACTIVE' AND last_seen_at < %s"""
    params = [source, started_at]
    if categories is not None:
        sql += " AND category_id = ANY(%s)"
        params.append([int(c) for c in categories])
    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONNECTION
    ) as connection:
        cursor = await connection.execute(sql, params)
        return [row[0] for row in await cursor.fetchall()]


async def mark_gone(ids, source="auto.ria"):
    """Last resort for the ids GraphQL answered nothing at all about.

    The GONE status says only "vanished from the feed and cannot be checked".
    When the API does answer, no reason has to be written by hand: it reports
    ARCHIVED, REMOVED_BY_CRON or SOLD itself, and that beats any guess.
    """
    if not ids:
        return 0
    async with await psycopg.AsyncConnection.connect(
        **DATABASE_CONNECTION
    ) as connection:
        cursor = await connection.execute(
            """UPDATE cars SET status = 'GONE', updated_at = now()
               WHERE source = %s AND car_id = ANY(%s) AND status = 'ACTIVE'""",
            (source, [int(i) for i in ids]),
        )
        return cursor.rowcount
