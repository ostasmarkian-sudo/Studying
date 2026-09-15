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


class Search(StatesGroup):
    menu = State()
    manual = State()


# The draft lives in the FSM data until "Почати моніторинг":
#   filters - {column: value}, exactly what goes into search_subscriptions;
#   labels  - {column: text}, what the user sees for each chosen value;
#   manual, prompt_id - which parameter is being typed, and the prompt message.

# A parameter whose options depend on another one. Without the parent there is
# nothing to list, and a new parent makes the old child meaningless.
PARENTS = {"model_id": "brand_id", "city_id": "state_id"}
NEED_PARENT = {
    "model_id": "Спочатку оберіть марку",
    "city_id": "Спочатку оберіть область",
}

# Brand ids are shared across categories (Volkswagen 84 sells cars, trucks and
# buses), so a brand and its model survive a category change. Bodies do not,
# every category has its own.
DEPENDENT = {
    "category_id": ("body_id",),
    "brand_id": ("model_id",),
    "state_id": ("city_id",),
}

# column -> (number type, lowest, highest). Bounds only catch nonsense, the
# real range of the data is narrower.
RANGES = {
    "year": (int, 1900, 2100),
    "price_usd": (int, 0, 100_000_000),
    "mileage_km": (int, 0, 10_000_000),
    "engine_liters": (float, 0, 99.99),
}

PROMPTS = {
    "brand_id": "Напишіть назву марки так, як на auto.ria, наприклад: Lexus",
    "model_id": "Напишіть назву моделі так, як на auto.ria, наприклад: Golf",
    "city_id": "Напишіть назву міста, наприклад: Бровари",
    "year": "Напишіть роки: 2012-2018, від 2015, до 2010 або один рік",
    "price_usd": "Напишіть ціну в доларах: 5000-12000, від 8000 або до 15000",
    "mileage_km": "Напишіть пробіг у км: 50000-150000, від 100000 або до 200000",
    "engine_liters": "Напишіть об'єм у літрах: 1.6-2.0, від 2.5 або до 1.8",
}

_RANGE = re.compile(r"(\d+(?:\.\d+)?)?(-)?(\d+(?:\.\d+)?)?")


def parse_range(column, text):
    """[min, max] from "2010-2018", "2010-", "-2018", "від 2010 до 2018" or a
    single "2015". Both ends included, None is an open end. None on nonsense.

    Buttons send their ranges through here too: callback_data is not checked
    by Telegram, a modified client can put anything into it.
    """
    kind, lowest, highest = RANGES[column]
    text = text.lower()
    only_from = "від" in text and "до" not in text
    text = text.replace("від", "").replace("до", "-").replace(",", ".")
    text = re.sub(r"\s+", "", text.replace("–", "-").replace("—", "-"))
    if only_from and "-" not in text:
        text += "-"
    match = _RANGE.fullmatch(text)
    if not match or not (match[1] or match[3]):
        return None
    try:
        low = kind(match[1]) if match[1] else None
        high = kind(match[3]) if match[3] else None
    except ValueError:  # "1.5" where a whole number is expected
        return None
    if not match[2]:
        high = low
    if low is not None and high is not None and low > high:
        low, high = high, low
    for bound in (low, high):
        if bound is not None and not lowest <= bound <= highest:
            return None
    if kind is float:
        low, high = (None if b is None else round(b, 2) for b in (low, high))
    return [low, high]


def _bound(column, number):
    if column == "year":
        return str(number)
    if column == "engine_liters":
        return f"{number:.1f} л" if round(number, 1) == number else f"{number:.2f} л"
    grouped = f"{number:,}".replace(",", " ")
    return f"${grouped}" if column == "price_usd" else f"{grouped} км"


def _range_label(column, low, high):
    if low == high:
        return _bound(column, low)
    if high is None:
        return f"від {_bound(column, low)}"
    if low is None:
        return f"до {_bound(column, high)}"
    return f"{_bound(column, low)} – {_bound(column, high)}"


def _callback_value(value):
    """A stored value back in the form its button sends, to tick that button."""
    if value is None:
        return None
    if isinstance(value, list):
        return "-".join(
            "" if v is None else f"{v:g}" if isinstance(v, float) else str(v)
            for v in value
        )
    return str(value)


def _lines(labels):
    return [(kb.SEARCH_PARAMS[c], labels[c]) for c in kb.SEARCH_PARAMS if c in labels]


def _menu_text(labels):
    lines = _lines(labels)
    if not lines:
        return (
            "<b>Новий моніторинг</b>\n"
            "Оберіть параметри, і я повідомлятиму про нові оголошення за ними."
        )
    body = "\n".join(f"{name}: <b>{escape(label)}</b>" for name, label in lines)
    return f"<b>Новий моніторинг</b>\n{body}"


def _context(column, value):
    # With no category chosen the keyboards show passenger cars, so for what
    # depends on the category "not chosen" and "Легкові" are the same thing.
    return 1 if column == "category_id" and value is None else value


def _apply(filters, labels, column, value=None, label=None):
    """Set a parameter, or drop it when value is None. Whatever depended on
    its old value goes as well."""
    if _context(column, filters.get(column)) != _context(column, value):
        for child in DEPENDENT.get(column, ()):
            filters.pop(child, None)
            labels.pop(child, None)
    if value is None:
        filters.pop(column, None)
        labels.pop(column, None)
    else:
        filters[column] = value
        labels[column] = label


async def _from_button(column, raw, filters):
    """(value, label) for a pressed option, or None if the value is not real."""
    if column in RANGES:
        bounds = parse_range(column, raw)
        if bounds is None:
            return None
        return bounds, kb.STATIC_OPTIONS[column].get(raw) or _range_label(column, *bounds)

    # Outside passenger cars brands and bodies come from the database, and
    # models and cities always do, so the database is what checks them.
    if column in ("brand_id", "body_id", "model_id", "city_id"):
        parent = filters.get(PARENTS.get(column))
        if column in PARENTS and parent is None:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        name = await db.choice_name(column, value, parent)
        return (value, name) if name else None

    for value, label in kb.STATIC_OPTIONS[column].items():
        if str(value) == raw:
            return value, label
    return None


async def _from_text(column, text, filters):
    """(value, label) for a typed value, or None if nothing matches."""
    if column in RANGES:
        bounds = parse_range(column, text)
        return (bounds, _range_label(column, *bounds)) if bounds else None
    row = await db.choice_by_name(column, text, filters.get(PARENTS.get(column)))
    return tuple(row) if row else None


async def _keyboard(column, filters):
    selected = _callback_value(filters.get(column))
    if column in PARENTS:
        rows = await db.choices(column, filters[PARENTS[column]])
        return kb.from_rows(column, rows, selected)
    category = filters.get("category_id")
    if column in ("brand_id", "body_id") and category not in (None, 1):
        rows = await db.choices(column, category)
        return kb.from_rows(column, rows, selected)
    return kb.param_keyboard(column, selected)


async def start(msg: Message, state: FSMContext):
    """Entry from the reply keyboard. A draft in progress is kept."""
    if await state.get_state() not in Search.__all_states_names__:
        await state.set_data({})
    await state.set_state(Search.menu)
    data = await state.get_data()
    await msg.answer(
        _menu_text(data.get("labels", {})),
        reply_markup=kb.search_menu(data.get("filters", {})),
    )


def _is_param_value(call: CallbackQuery):
    return (call.data or "").partition(":")[0] in kb.SEARCH_PARAMS


@router.callback_query(StateFilter(Search), F.data == "search:menu")
async def show_menu(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(Search.menu)
    await common.edit(
        call, _menu_text(data.get("labels", {})), kb.search_menu(data.get("filters", {}))
    )
    await call.answer()


@router.callback_query(StateFilter(Search), F.data == "search:reset")
async def reset(call: CallbackQuery, state: FSMContext):
    await state.set_data({})
    await state.set_state(Search.menu)
    await common.edit(call, _menu_text({}), kb.search_menu({}))
    await call.answer("Параметри скинуто")


@router.callback_query(StateFilter(Search), F.data.startswith("param:"))
async def open_param(call: CallbackQuery, state: FSMContext):
    column = call.data.removeprefix("param:")
    if column not in kb.SEARCH_PARAMS:
        await call.answer()
        return
    data = await state.get_data()
    filters, labels = data.get("filters", {}), data.get("labels", {})
    if column in PARENTS and PARENTS[column] not in filters:
        await call.answer(NEED_PARENT[column], show_alert=True)
        return

    markup = await _keyboard(column, filters)
    text = f"<b>{kb.SEARCH_PARAMS[column]}</b>"
    if column in labels:
        text += f"\nЗараз: {escape(labels[column])}"
    await state.set_state(Search.menu)
    await common.edit(call, text, markup)
    await call.answer()


@router.callback_query(StateFilter(Search), _is_param_value)
async def pick_value(call: CallbackQuery, state: FSMContext):
    column, _, raw = call.data.partition(":")
    data = await state.get_data()
    # get_data() copies only the top level, the nested dicts are the stored ones.
    filters, labels = dict(data.get("filters", {})), dict(data.get("labels", {}))

    if raw == "manual":
        if column not in kb.MANUAL:
            await call.answer()
            return
        if column in PARENTS and PARENTS[column] not in filters:
            await call.answer(NEED_PARENT[column], show_alert=True)
            return
        await state.set_state(Search.manual)
        await state.update_data(manual=column, prompt_id=call.message.message_id)
        await common.edit(call, PROMPTS[column], kb.cancel_input)
        await call.answer()
        return

    if raw == "any":
        _apply(filters, labels, column)
    else:
        picked = await _from_button(column, raw, filters)
        if picked is None:
            await call.answer("Цей варіант недоступний, оберіть інший", show_alert=True)
            return
        _apply(filters, labels, column, *picked)

    await state.update_data(filters=filters, labels=labels)
    await state.set_state(Search.menu)
    await common.edit(call, _menu_text(labels), kb.search_menu(filters))
    await call.answer()


@router.callback_query(StateFilter(Search), F.data == "search:save")
async def save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters, labels = data.get("filters", {}), data.get("labels", {})
    if not filters:
        await call.answer("Оберіть хоча б один параметр", show_alert=True)
        return

    summary = "\n".join(f"{name}: {label}" for name, label in _lines(labels))
    result = await db.save_subscription(call.from_user, filters, summary)
    if result == "limit":
        await call.answer(
            f"Можна мати не більше {db.MAX_SUBSCRIPTIONS} моніторингів", show_alert=True
        )
        return
    if result == "exists":
        await call.answer("Такий моніторинг у вас уже є", show_alert=True)
        return

    await state.clear()
    await common.edit(
        call,
        f"🔔 <b>Моніторинг запущено</b>\n{escape(summary)}\n\n"
        "Повідомлю, щойно з'являться нові оголошення.",
    )
    await call.answer()


@router.callback_query(StateFilter(Search), F.data == "search:run")
async def run_search(call: CallbackQuery, state: FSMContext):
    # The place for the search itself: (await state.get_data())["filters"]
    # holds the parameters in the same shape search_subscriptions stores them.
    await call.answer("Пошук ще в розробці", show_alert=True)


@router.message(Search.manual, F.text)
async def manual_value(msg: Message, state: FSMContext):
    data = await state.get_data()
    column = data.get("manual")
    filters, labels = dict(data.get("filters", {})), dict(data.get("labels", {}))
    if column not in kb.MANUAL:
        await state.set_state(Search.menu)
        await msg.answer(_menu_text(labels), reply_markup=kb.search_menu(filters))
        return

    text = msg.text.strip()[:100]
    picked = await _from_text(column, text, filters)
    if picked is None:
        if column in RANGES:
            reply = f"Не зрозумів значення. {PROMPTS[column]}"
        else:
            reply = (
                f"Не знайшов «{escape(text)}» серед оголошень. "
                "Перевірте написання або натисніть «Скасувати» і оберіть зі списку."
            )
        await msg.answer(reply)
        return

    _apply(filters, labels, column, *picked)
    await state.update_data(filters=filters, labels=labels, manual=None, prompt_id=None)
    await state.set_state(Search.menu)
    await common.drop_markup(msg, data.get("prompt_id"))
    await msg.answer(_menu_text(labels), reply_markup=kb.search_menu(filters))


@router.message(Search.manual)
async def manual_not_text(msg: Message):
    await msg.answer("Надішліть значення текстом.")


@router.message(Search.menu)
async def menu_text_input(msg: Message):
    await msg.answer("Оберіть параметри кнопками в меню вище.")
