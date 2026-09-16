import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import DATABASE_CONNECTION

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Every active row is one more query for whoever sends the notifications.
MAX_SUBSCRIPTIONS = 10
MAX_WATCHES = 30

# Enough for the popular options without a keyboard taller than the screen;
# the rest is reachable by typing the name.
CHOICES_LIMIT = 40

# How far back a check reaches beyond last_checked_at.
#
# cars.first_seen_at is the start time of the scraper transaction, and a batch
# of a thousand cars becomes visible only when that transaction commits, whole
# seconds later. A check that runs in between would see nothing, move the
# beacon past those cars and lose them for good. So the window is deliberately
# too wide and sent_cars throws away what was sent before.
CHECK_OVERLAP = timedelta(minutes=15)

# The columns a filter is allowed to name, the same list as SEARCH_PARAMS in
# keyboard.py. Kept here as well so that no key out of the jsonb can reach the
# query, whatever ends up in the table.
MATCH_COLUMNS = (
    "category_id",
    "brand_id",
    "model_id",
    "body_id",
    "year",
    "price_usd",
    "mileage_km",
    "fuel_id",
    "gearbox",
    "engine_liters",
    "state_id",
    "city_id",
    "country_import",
    "is_dealer",
)

# What a notification shows on top of the columns above.
CARD_COLUMNS = ("car_id", "title", "url", "city", "currency", "price_main", "first_seen_at")

UPSERT_USER_SQL = """
    INSERT INTO bot_users (tg_user_id, username, first_name, language)
    VALUES (%(id)s, %(username)s, %(first_name)s, %(language)s)
    ON CONFLICT (tg_user_id) DO UPDATE SET
        username = EXCLUDED.username,
        first_name = EXCLUDED.first_name,
        language = EXCLUDED.language,
        is_blocked = false,
        last_active_at = now()
"""

# Options for the keyboards, most frequent first. parent is the category for
# brands and bodies, the brand for models, the state for cities.
CHOICES_SQL = {
    "brand_id": """
        SELECT brand_id, min(brand) FROM cars
        WHERE category_id = %(parent)s AND status = 'ACTIVE' AND brand_id IS NOT NULL
        GROUP BY brand_id ORDER BY count(*) DESC LIMIT %(limit)s
    """,
    "model_id": """
        SELECT model_id, min(model) FROM cars
        WHERE brand_id = %(parent)s AND status = 'ACTIVE' AND model_id IS NOT NULL
        GROUP BY model_id ORDER BY count(*) DESC LIMIT %(limit)s
    """,
    "city_id": """
        SELECT city_id, min(city) FROM cars
        WHERE state_id = %(parent)s AND status = 'ACTIVE' AND city_id IS NOT NULL
        GROUP BY city_id ORDER BY count(*) DESC LIMIT %(limit)s
    """,
    "body_id": """
        SELECT c.body_id, b.name FROM cars c
        JOIN body_types b ON b.body_id = c.body_id
        WHERE c.category_id = %(parent)s AND c.status = 'ACTIVE'
        GROUP BY c.body_id, b.name ORDER BY count(*) DESC LIMIT %(limit)s
    """,
}

# The name behind an id, which is also the check that the id is real. Each one
# goes through an index: the lists above take ~0.5 s, too slow for every press.
NAME_SQL = {
    "brand_id": "SELECT brand FROM cars WHERE brand_id = %(value)s LIMIT 1",
    "model_id": """SELECT model FROM cars
                   WHERE brand_id = %(parent)s AND model_id = %(value)s LIMIT 1""",
    "city_id": """SELECT city FROM cars
                  WHERE state_id = %(parent)s AND city_id = %(value)s LIMIT 1""",
    "body_id": "SELECT name FROM body_types WHERE body_id = %(value)s",
}

# Typed names. Case-insensitive but otherwise exact, so "golf" finds Golf and
# "gol" finds nothing instead of a guess.
BY_NAME_SQL = {
    "brand_id": """
        SELECT brand_id, min(brand) FROM cars
        WHERE lower(brand) = lower(%(name)s) AND brand_id IS NOT NULL
        GROUP BY brand_id ORDER BY count(*) DESC LIMIT 1
    """,
    "model_id": """
        SELECT model_id, min(model) FROM cars
        WHERE brand_id = %(parent)s AND lower(model) = lower(%(name)s) AND model_id IS NOT NULL
        GROUP BY model_id ORDER BY count(*) DESC LIMIT 1
    """,
    "city_id": """
        SELECT city_id, min(city) FROM cars
        WHERE state_id = %(parent)s AND lower(city) = lower(%(name)s) AND city_id IS NOT NULL
        GROUP BY city_id ORDER BY count(*) DESC LIMIT 1
    """,
}

FIND_CAR_SQL = """
    SELECT c.car_id, c.title, c.price_usd, c.city, c.status, c.url,
           c.fingerprint IS NOT NULL AS can_relist,
           w.events AS watched
    FROM cars c
    LEFT JOIN car_watches w
           ON w.car_id = c.car_id AND w.tg_user_id = %(user)s AND w.is_active
    WHERE c.car_id = %(car)s
"""

FIND_SUBSCRIPTION_SQL = """
    SELECT is_active FROM search_subscriptions WHERE tg_user_id = %s AND filters = %s
"""

COUNT_SUBSCRIPTIONS_SQL = """
    SELECT count(*) FROM search_subscriptions WHERE tg_user_id = %s AND is_active
"""

# Reached only for a new row or an inactive one, so the reset of
# last_checked_at never skips changes of a running subscription.
UPSERT_SUBSCRIPTION_SQL = """
    INSERT INTO search_subscriptions (tg_user_id, filters, summary)
    VALUES (%s, %s, %s)
    ON CONFLICT (tg_user_id, filters) DO UPDATE SET
        summary = EXCLUDED.summary,
        is_active = true,
        last_checked_at = now()
"""

FIND_WATCH_SQL = """
    SELECT is_active FROM car_watches WHERE tg_user_id = %s AND car_id = %s
"""

COUNT_WATCHES_SQL = """
    SELECT count(*) FROM car_watches WHERE tg_user_id = %s AND is_active
"""

# SET reads the old row, so the CASE sees is_active as it was before this
# statement. A running watch keeps its place, a revived one starts from now.
UPSERT_WATCH_SQL = """
    INSERT INTO car_watches (tg_user_id, car_id, events)
    VALUES (%s, %s, %s)
    ON CONFLICT (tg_user_id, car_id) DO UPDATE SET
        events = EXCLUDED.events,
        last_checked_at = CASE WHEN car_watches.is_active
                               THEN car_watches.last_checked_at
                               ELSE now() END,
        is_active = true
"""


# Blocked users are left out: their subscriptions keep their old beacon and
# come back to life on the next /start, which clears is_blocked.
ACTIVE_SUBSCRIPTIONS_SQL = """
    SELECT s.subscription_id, s.tg_user_id, s.filters, s.summary, s.last_checked_at
    FROM search_subscriptions s
    JOIN bot_users u USING (tg_user_id)
    WHERE s.is_active AND NOT u.is_blocked
    ORDER BY s.last_checked_at
"""

NEW_CARS_SQL = """
    SELECT {columns}
    FROM cars
    WHERE status = 'ACTIVE' AND first_seen_at > %s
    ORDER BY first_seen_at
""".format(columns=", ".join(CARD_COLUMNS + MATCH_COLUMNS))

# One round trip for the whole batch: what comes back from RETURNING is what
# this subscription has not been sent yet.
MARK_SENT_SQL = """
    INSERT INTO sent_cars (subscription_id, car_id)
    SELECT %s, unnest(%s::bigint[])
    ON CONFLICT DO NOTHING
    RETURNING car_id
"""

UNMARK_SENT_SQL = """
    DELETE FROM sent_cars WHERE subscription_id = %s AND car_id = ANY(%s)
"""

TOUCH_SUBSCRIPTIONS_SQL = """
    UPDATE search_subscriptions SET last_checked_at = %s WHERE subscription_id = ANY(%s)
"""

BLOCK_USER_SQL = "UPDATE bot_users SET is_blocked = true WHERE tg_user_id = %s"

CLEANUP_SENT_SQL = "DELETE FROM sent_cars WHERE sent_at < now() - interval '2 days'"


def connect(**kwargs):
    """A connection of its own. notifier.py keeps one for a whole check, the
    handlers take one per query: a bot that waits on Telegram most of the time
    has no use for a pool."""
    return psycopg.AsyncConnection.connect(**DATABASE_CONNECTION, **kwargs)


def _user_params(user):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "language": user.language_code,
    }


async def _fetchall(query, params):
    async with await connect() as connection:
        cursor = await connection.execute(query, params)
        return await cursor.fetchall()


async def init_bot_db():
    """Create the bot tables if they are missing. Idempotent, safe on every start."""
    schema = await asyncio.to_thread(SCHEMA_PATH.read_text, encoding="utf-8")
    async with await connect() as connection:
        await connection.execute(schema)


async def upsert_user(user):
    async with await connect() as connection:
        await connection.execute(UPSERT_USER_SQL, _user_params(user))


async def choices(column, parent):
    """[(id, name), ...] for a keyboard of brands, bodies, models or cities."""
    return await _fetchall(CHOICES_SQL[column], {"parent": parent, "limit": CHOICES_LIMIT})


async def choice_name(column, value, parent=None):
    """Name for an id taken from a button, or None when there is no such id."""
    rows = await _fetchall(NAME_SQL[column], {"value": value, "parent": parent})
    return rows[0][0] if rows else None


async def choice_by_name(column, name, parent=None):
    """(id, name) for a name the user typed, or None."""
    rows = await _fetchall(BY_NAME_SQL[column], {"name": name, "parent": parent})
    return rows[0] if rows else None


async def find_car(car_id, tg_user_id):
    """The ad plus the events this user already watches on it, or None."""
    async with await connect(row_factory=dict_row) as connection:
        cursor = await connection.execute(FIND_CAR_SQL, {"car": car_id, "user": tg_user_id})
        return await cursor.fetchone()


async def save_subscription(user, filters, summary):
    """Returns "created", "exists" (already running) or "limit"."""
    filters = Jsonb(filters)
    async with await connect() as connection:
        await connection.execute(UPSERT_USER_SQL, _user_params(user))

        cursor = await connection.execute(FIND_SUBSCRIPTION_SQL, (user.id, filters))
        row = await cursor.fetchone()
        if row and row[0]:
            return "exists"

        cursor = await connection.execute(COUNT_SUBSCRIPTIONS_SQL, (user.id,))
        (active,) = await cursor.fetchone()
        if active >= MAX_SUBSCRIPTIONS:
            return "limit"

        await connection.execute(UPSERT_SUBSCRIPTION_SQL, (user.id, filters, summary))
        return "created"


async def db_now(connection):
    """The database clock. The notifier's beacon has to come from the same
    clock as first_seen_at, not from the machine the bot happens to run on."""
    cursor = await connection.execute("SELECT now()")
    return (await cursor.fetchone())[0]


async def active_subscriptions(connection):
    cursor = connection.cursor(row_factory=dict_row)
    await cursor.execute(ACTIVE_SUBSCRIPTIONS_SQL)
    return await cursor.fetchall()


async def new_cars(connection, since):
    """Every active car first seen after `since`, as dicts."""
    cursor = connection.cursor(row_factory=dict_row)
    await cursor.execute(NEW_CARS_SQL, (since,))
    return await cursor.fetchall()


async def mark_sent(connection, subscription_id, car_ids):
    """Claim these cars for the subscription. Returns those that were not
    claimed before, which are exactly the ones worth sending."""
    cursor = await connection.execute(MARK_SENT_SQL, (subscription_id, list(car_ids)))
    return [row[0] for row in await cursor.fetchall()]


async def unmark_sent(connection, subscription_id, car_ids):
    """Give the claim back after a failed send, so the next check retries."""
    await connection.execute(UNMARK_SENT_SQL, (subscription_id, list(car_ids)))


async def touch_subscriptions(connection, subscription_ids, checked_at):
    """Move the beacon. Subscriptions that found nothing are moved as well,
    otherwise the oldest beacon stays put and the window grows every run."""
    await connection.execute(TOUCH_SUBSCRIPTIONS_SQL, (checked_at, list(subscription_ids)))


async def mark_blocked(connection, tg_user_id):
    await connection.execute(BLOCK_USER_SQL, (tg_user_id,))


async def cleanup_sent(connection):
    await connection.execute(CLEANUP_SENT_SQL)


async def save_watch(user, car_id, events):
    """Returns "created", "updated" (new events on a running watch) or "limit"."""
    async with await connect() as connection:
        await connection.execute(UPSERT_USER_SQL, _user_params(user))

        cursor = await connection.execute(FIND_WATCH_SQL, (user.id, car_id))
        row = await cursor.fetchone()
        running = bool(row and row[0])

        if not running:
            cursor = await connection.execute(COUNT_WATCHES_SQL, (user.id,))
            (active,) = await cursor.fetchone()
            if active >= MAX_WATCHES:
                return "limit"

        await connection.execute(UPSERT_WATCH_SQL, (user.id, car_id, list(events)))
        return "updated" if running else "created"
