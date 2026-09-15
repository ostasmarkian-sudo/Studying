import re
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import common
import database as db
import keyboard as kb

router = Router()


class Watch(StatesGroup):
    car = State()
    events = State()


# The draft lives in the FSM data until "Почати моніторинг":
#   car_id, title, relist - the ad and whether it has a fingerprint;
#   events                - the ticked events.

DEFAULT_EVENTS = ["price", "status"]

# Every price change already includes the drops, ticking both would only
# send the same notification twice.
EXCLUSIVE = {"price": "price_down", "price_down": "price"}

# https://auto.ria.com/uk/auto_volkswagen_golf_38118461.html: the slug does
# not matter, the id is the number right before .html.
_AD_URL = re.compile(r"_(\d{1,18})\.html")


def _car_id(text):
    match = _AD_URL.search(text)
    if match:
        return int(match[1])
    text = text.strip()
    return int(text) if text.isdigit() and len(text) <= 18 else None


def _car_text(car):
    title = escape(car["title"])
    if car["url"]:
        title = f'<a href="{escape(car["url"])}">{title}</a>'
    details = []
    if car["price_usd"]:
        details.append(f"${car['price_usd']:,}".replace(",", " "))
    if car["city"]:
        details.append(escape(car["city"]))
    question = (
        "Ви вже стежите за цим авто, події можна змінити:"
        if car["watched"]
        else "Про що повідомляти?"
    )
    return f"<b>{title}</b>\n{', '.join(details)}\n\n{question}"


async def start(msg: Message, state: FSMContext):
    """Entry from the reply keyboard."""
    await state.set_data({})
    await state.set_state(Watch.car)
    await msg.answer(
        "Надішліть посилання на оголошення auto.ria або його номер.",
        reply_markup=kb.watch_cancel,
    )


def _is_event(call: CallbackQuery):
    data = call.data or ""
    return data.startswith("watch:") and data.removeprefix("watch:") in kb.WATCH_EVENTS


@router.message(Watch.car, F.text)
async def car_link(msg: Message, state: FSMContext):
    car_id = _car_id(msg.text)
    if car_id is None:
        await msg.answer(
            "Не бачу номера оголошення. Надішліть посилання на кшталт "
            "https://auto.ria.com/auto_volkswagen_golf_38118461.html або сам номер."
        )
        return

    car = await db.find_car(car_id, msg.from_user.id)
    if car is None:
        await msg.answer("Цього оголошення немає в базі. Перевірте посилання.")
        return
    if car["status"] != "ACTIVE":
        await msg.answer("Це оголошення вже не активне, стежити за ним немає сенсу.")
        return

    events = [e for e in (car["watched"] or DEFAULT_EVENTS) if car["can_relist"] or e != "relist"]
    await state.update_data(
        car_id=car_id, title=car["title"], relist=car["can_relist"], events=events
    )
    await state.set_state(Watch.events)
    await msg.answer(
        _car_text(car), reply_markup=kb.vihicle_monitoring(events, car["can_relist"])
    )


@router.message(Watch.car)
async def car_not_text(msg: Message):
    await msg.answer("Надішліть посилання текстом.")


@router.message(Watch.events)
async def events_text_input(msg: Message):
    await msg.answer("Оберіть події кнопками вище або натисніть «Скасувати».")


@router.callback_query(Watch.events, _is_event)
async def toggle_event(call: CallbackQuery, state: FSMContext):
    event = call.data.removeprefix("watch:")
    data = await state.get_data()
    if event == "relist" and not data.get("relist"):
        await call.answer(
            "В оголошенні немає VIN, перевиставлення не відстежити", show_alert=True
        )
        return

    chosen = set(data.get("events", []))
    if event in chosen:
        chosen.discard(event)
    else:
        chosen.discard(EXCLUSIVE.get(event))
        chosen.add(event)
    events = [e for e in kb.WATCH_EVENTS if e in chosen]

    await state.update_data(events=events)
    await common.edit(call, markup=kb.vihicle_monitoring(events, data.get("relist")))
    await call.answer()


@router.callback_query(Watch.events, F.data == "watch:start")
async def start_watch(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    events = data.get("events", [])
    if not events:
        await call.answer("Оберіть хоча б одну подію", show_alert=True)
        return

    result = await db.save_watch(call.from_user, data["car_id"], events)
    if result == "limit":
        await call.answer(
            f"Можна стежити не більше ніж за {db.MAX_WATCHES} авто", show_alert=True
        )
        return

    await state.clear()
    header = "Моніторинг оновлено" if result == "updated" else "Моніторинг запущено"
    lines = "\n".join(f"• {kb.WATCH_EVENTS[e]}" for e in events)
    await common.edit(
        call, f"🔔 <b>{header}</b>\n{escape(data.get('title', ''))}\n\n{lines}"
    )
    await call.answer()


@router.callback_query(StateFilter(Watch), F.data == "watch:cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    # Only the draft is dropped: a watch saved earlier keeps running.
    await common.edit(call, "Скасовано, нічого не змінено.")
    await call.answer()
