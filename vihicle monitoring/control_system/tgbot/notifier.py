import asyncio
import logging
from html import escape

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions
from aiogram.utils.text_decorations import html_decoration as fmt

import database as db

# The scraper writes in batches every few minutes, so checking more often than
# this would only mean empty runs.
INTERVAL = 300

# Per subscription per check. A user coming back after a pause, or a scraper
# catching up (18k cars landed in one day), must not turn into a wall of text.
MAX_CARS = 10

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

log = logging.getLogger(__name__)


def matches(car, filters):
    """Whether one car satisfies a saved filter.

    A scalar means the column equals it; a [min, max] pair means both ends are
    included and None is an open end. A column with no value never matches: a
    car with no gearbox written down is not an answer to "Автомат".
    """
    for column, wanted in filters.items():
        value = car.get(column)
        if value is None:
            return False
        if isinstance(wanted, list):
            low, high = wanted
            # engine_liters arrives as Decimal while the bound out of the jsonb
            # is a float, and Python compares those two exactly: without this
            # cast Decimal("1.49") <= 1.49 is False and the car falls out.
            value = float(value)
            if low is not None and value < low:
                return False
            if high is not None and value > high:
                return False
        elif value != wanted:
            return False
    return True


def _price(car):
    if car["price_main"] and car["currency"]:
        return f"{car['price_main']:,}".replace(",", " ") + f" {car['currency']}"
    if car["price_usd"]:
        return "$" + f"{car['price_usd']:,}".replace(",", " ")
    return "ціна не вказана"


def _card(car):
    # fmt.quote escapes only < > &, the three characters Telegram cares about.
    # html.escape would also turn an apostrophe into &#x27;, which Telegram
    # does not decode and shows to the user as it is.
    title = fmt.quote(car["title"])
    if car["url"]:
        title = f'<a href="{escape(car["url"])}">{title}</a>'
    details = [_price(car)]
    if car["mileage_km"]:
        details.append(f"{car['mileage_km']:,}".replace(",", " ") + " км")
    if car["city"]:
        details.append(fmt.quote(car["city"]))
    return f"{title}\n{' · '.join(details)}"


def _message(subscription, cars, total):
    head = f"🔔 <b>Нові оголошення</b>\n<i>{fmt.quote(subscription['summary'])}</i>"
    body = "\n\n".join(_card(car) for car in cars)
    tail = f"\n\n…і ще {total - len(cars)}. Звузьте параметри, щоб їх було менше." if total > len(cars) else ""
    return f"{head}\n\n{body}{tail}"


async def _send(bot, subscription, cars, total):
    """"sent", "blocked" (nothing to retry, the user has to be flagged) or
    "failed" (the cars go back so that the next check tries them again).

    Every error is caught on purpose. One unreachable user must not take down
    the whole check: the cars of everyone after them would stay claimed by
    sent_cars and never be sent by anyone.
    """
    text = _message(subscription, cars, total)
    for attempt in range(2):
        try:
            await bot.send_message(
                subscription["tg_user_id"], text, link_preview_options=NO_PREVIEW
            )
            return "sent"
        except TelegramForbiddenError:
            return "blocked"
        except TelegramRetryAfter as error:
            if attempt:
                return "failed"
            await asyncio.sleep(error.retry_after)
        except Exception:
            log.exception("send to %s failed", subscription["tg_user_id"])
            return "failed"
    return "failed"


async def check_once(bot):
    """One pass: what has appeared since the last check, and to whom it goes."""
    async with await db.connect(autocommit=True) as connection:
        subscriptions = await db.active_subscriptions(connection)
        if not subscriptions:
            return 0

        # Taken before reading, not after sending: everything the scraper
        # writes while this check runs has to stay on the next one's side.
        checked_at = await db.db_now(connection)
        oldest = min(s["last_checked_at"] for s in subscriptions)
        cars = await db.new_cars(connection, oldest - db.CHECK_OVERLAP)
        log.info("notifier: %s subscriptions, %s new cars", len(subscriptions), len(cars))

        checked, sent = [], 0
        for subscription in subscriptions:
            edge = subscription["last_checked_at"] - db.CHECK_OVERLAP
            found = [
                car
                for car in cars
                if car["first_seen_at"] > edge and matches(car, subscription["filters"])
            ]
            if not found:
                checked.append(subscription["subscription_id"])
                continue

            # Claimed before sending: two checks overlapping, or a restart in
            # the middle of one, must not send the same car twice.
            fresh_ids = set(
                await db.mark_sent(
                    connection, subscription["subscription_id"], [c["car_id"] for c in found]
                )
            )
            fresh = [car for car in found if car["car_id"] in fresh_ids]
            if not fresh:
                checked.append(subscription["subscription_id"])
                continue

            result = await _send(bot, subscription, fresh[:MAX_CARS], len(fresh))
            if result == "failed":
                await db.unmark_sent(connection, subscription["subscription_id"], fresh_ids)
                continue

            checked.append(subscription["subscription_id"])
            if result == "blocked":
                # Nothing to retry, and every later check would try again for
                # nothing: the flag takes this user out until their next /start.
                log.info("user %s blocked the bot", subscription["tg_user_id"])
                await db.mark_blocked(connection, subscription["tg_user_id"])
            else:
                sent += 1

        if checked:
            await db.touch_subscriptions(connection, checked, checked_at)
        await db.cleanup_sent(connection)
        return sent


async def run(bot):
    """Background loop. Swallows its own errors: a database hiccup must not
    kill the task quietly and leave the bot answering buttons but never
    notifying anyone again."""
    while True:
        try:
            await check_once(bot)
        except Exception:
            log.exception("notifier check failed")
        await asyncio.sleep(INTERVAL)
