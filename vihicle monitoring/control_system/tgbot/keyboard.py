from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

WATCH_BUTTON = "Моніторинг уже виставленого автомобіля"
SEARCH_BUTTON = "Пошук автомобіля по критеріях"

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=WATCH_BUTTON)],
        [KeyboardButton(text=SEARCH_BUTTON)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Виберіть пункт в меню",
)

# callback_data everywhere is "<key>:<value>". In the search keyboards <key> is
# the cars column itself, so a chosen value lands in the filter under the name
# of the column it filters.
#   <value> "any"    - the user does not care about this parameter;
#   <value> "manual" - the user wants to type the value as a message.
# Ranges are "min-max" with both ends included; an empty side is open:
# "price_usd:-3000" is up to 3000, "year:2023-" is 2023 and newer.
#
# Left out on purpose, judging by the data in cars:
#   customs_code, abroad - one value across all rows (0 and false);
#   status, source       - 99.99% ACTIVE and only auto.ria, filtered in SQL;
#   power_hp             - filled in 1.6% of the cars, the filter drops the rest;
#   seller_rating        - filled in 8% of the rows.

# Event names mirror what car_history records: price_main, status and mileage
# move the data_hash; relisting is found through fingerprint.
WATCH_EVENTS = {
    "price": "Зміна ціни",
    "price_down": "Лише зниження ціни",
    "status": "Продано / знято з продажу",
    "mileage": "Зміна пробігу",
    "relist": "Перевиставлено під новим оголошенням",
}

SEARCH_PARAMS = {
    "category_id": "Тип транспорту",
    "brand_id": "Марка",
    "model_id": "Модель",
    "body_id": "Кузов",
    "year": "Рік випуску",
    "price_usd": "Ціна",
    "mileage_km": "Пробіг",
    "fuel_id": "Паливо",
    "gearbox": "Коробка передач",
    "engine_liters": "Об'єм двигуна",
    "state_id": "Область",
    "city_id": "Місто",
    "country_import": "Пригнана з",
    "is_dealer": "Продавець",
}

# Ordered by the number of ads.
CATEGORIES = {
    1: "Легкові",
    2: "Мото",
    6: "Вантажівки",
    5: "Причепи",
    7: "Автобуси",
    4: "Спецтехніка",
    3: "Водний транспорт",
    8: "Автобудинки",
    9: "Повітряний транспорт",
}

# Top 20 of the passenger cars. Brands of the other categories come from the
# database, the rest of the list through manual input.
BRANDS = {
    84: "Volkswagen",
    6: "Audi",
    9: "BMW",
    24: "Ford",
    48: "Mercedes-Benz",
    88: "ВАЗ / Lada",
    62: "Renault",
    55: "Nissan",
    70: "Skoda",
    56: "Opel",
    79: "Toyota",
    29: "Hyundai",
    47: "Mazda",
    33: "Kia",
    58: "Peugeot",
    13: "Chevrolet",
    52: "Mitsubishi",
    18: "Daewoo",
    2233: "Tesla",
    32: "Jeep",
}

# Passenger cars only. Other categories have bodies of their own (Спортбайк,
# Тягач, Катер...), those come from body_types.
BODY_TYPES = {
    5: "Позашляховик / Кросовер",
    3: "Седан",
    2: "Універсал",
    4: "Хетчбек",
    8: "Мінівен",
    307: "Ліфтбек",
    6: "Купе",
    449: "Мікровен",
    9: "Пікап",
    7: "Кабріолет",
    448: "Фастбек",
    315: "Родстер",
    252: "Лімузин",
}

YEARS = {
    "-1999": "до 1999",
    "2000-2005": "2000–2005",
    "2006-2010": "2006–2010",
    "2011-2015": "2011–2015",
    "2016-2019": "2016–2019",
    "2020-2022": "2020–2022",
    "2023-": "2023 і новіші",
}

# Against price_usd: price_main is in whatever currency the seller chose.
PRICES = {
    "-3000": "до $3 000",
    "3000-5000": "$3 000 – 5 000",
    "5000-8000": "$5 000 – 8 000",
    "8000-12000": "$8 000 – 12 000",
    "12000-20000": "$12 000 – 20 000",
    "20000-35000": "$20 000 – 35 000",
    "35000-60000": "$35 000 – 60 000",
    "60000-": "від $60 000",
}

MILEAGES = {
    "-50000": "до 50 тис. км",
    "50000-100000": "50 – 100 тис. км",
    "100000-150000": "100 – 150 тис. км",
    "150000-200000": "150 – 200 тис. км",
    "200000-250000": "200 – 250 тис. км",
    "250000-300000": "250 – 300 тис. км",
    "300000-": "від 300 тис. км",
}

FUELS = {
    1: "Бензин",
    2: "Дизель",
    4: "Газ пропан-бутан / Бензин",
    8: "Газ метан / Бензин",
    3: "Газ",
    6: "Електро",
    5: "Гібрид (HEV)",
    10: "Гібрид (PHEV)",
    11: "Гібрид (MHEV)",
    12: "Гібрид (REEV)",
}

# gearbox has no id in the db, only the text, so the text itself is the value.
GEARBOXES = {
    name: name
    for name in (
        "Автомат",
        "Ручна / Механіка",
        "Варіатор",
        "Робот",
        "Типтронік",
        "Редуктор",
    )
}

# A third of the values carry two decimals (1.97, 2.49), hence the .99 ends:
# with 1.9 the 1.97 would fall between two buttons. 12% of the cars have 0,
# electric and unknown alike, so the lowest range starts above it.
ENGINES = {
    "0.01-1.49": "до 1.5 л",
    "1.5-1.99": "1.5 – 1.9 л",
    "2-2.49": "2.0 – 2.4 л",
    "2.5-2.99": "2.5 – 2.9 л",
    "3-": "від 3.0 л",
}

STATES = {
    1: "Вінницька",
    18: "Волинська",
    11: "Дніпропетровська",
    13: "Донецька",
    2: "Житомирська",
    22: "Закарпатська",
    14: "Запорізька",
    15: "Івано-Франківська",
    10: "Київська",
    16: "Кіровоградська",
    5: "Львівська",
    19: "Миколаївська",
    12: "Одеська",
    20: "Полтавська",
    9: "Рівненська",
    8: "Сумська",
    3: "Тернопільська",
    7: "Харківська",
    23: "Херсонська",
    4: "Хмельницька",
    24: "Черкаська",
    25: "Чернівецька",
    6: "Чернігівська",
}

# ISO 3166 numeric codes. Empty in 57% of the cars.
COUNTRIES = {
    840: "США",
    276: "Німеччина",
    528: "Нідерланди",
    250: "Франція",
    756: "Швейцарія",
    616: "Польща",
    408: "Південна Корея",
    124: "Канада",
    56: "Бельгія",
    578: "Норвегія",
    203: "Чехія",
    380: "Італія",
    752: "Швеція",
    440: "Литва",
}

SELLERS = {
    False: "Приватна особа",
    True: "Автосалон",
}

# Parameters whose options are known without the database.
STATIC_OPTIONS = {
    "category_id": CATEGORIES,
    "brand_id": BRANDS,
    "body_id": BODY_TYPES,
    "year": YEARS,
    "price_usd": PRICES,
    "mileage_km": MILEAGES,
    "fuel_id": FUELS,
    "gearbox": GEARBOXES,
    "engine_liters": ENGINES,
    "state_id": STATES,
    "country_import": COUNTRIES,
    "is_dealer": SELLERS,
}

# Parameters that can also be typed as a message.
MANUAL = {
    "brand_id",
    "model_id",
    "city_id",
    "year",
    "price_usd",
    "mileage_km",
    "engine_liters",
}

# Short labels fit three to a row.
_WIDE = {"state_id", "country_import"}

cancel_input = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Скасувати", callback_data="search:menu")]
    ]
)

watch_cancel = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Скасувати", callback_data="watch:cancel")]
    ]
)


def _options(prefix, options, selected=None, width=2, manual=False):
    builder = InlineKeyboardBuilder()
    for value, text in options.items():
        if str(value) == selected:
            text = f"✅ {text}"
        builder.button(text=text, callback_data=f"{prefix}:{value}")
    builder.adjust(width)
    if manual:
        builder.row(
            InlineKeyboardButton(
                text="✏️ Ввести вручну", callback_data=f"{prefix}:manual"
            )
        )
    builder.row(
        InlineKeyboardButton(text="Не важливо", callback_data=f"{prefix}:any"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="search:menu"),
    )
    return builder.as_markup()


def param_keyboard(column, selected=None):
    """Keyboard of a parameter from STATIC_OPTIONS.

    selected is the chosen value in its callback form ("84", "2016-2019"),
    that button gets a tick.
    """
    width = 3 if column in _WIDE else 2
    return _options(column, STATIC_OPTIONS[column], selected, width, column in MANUAL)


def from_rows(column, rows, selected=None):
    """Keyboard for the options only the database knows: models of a brand,
    cities of a state, brands and bodies outside passenger cars.

    rows are (id, name) pairs straight from fetchall().
    """
    return _options(column, dict(rows), selected, manual=column in MANUAL)


def search_menu(filters):
    builder = InlineKeyboardBuilder()
    for column, text in SEARCH_PARAMS.items():
        if column in filters:
            text = f"✅ {text}"
        builder.button(text=text, callback_data=f"param:{column}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="🔔 Почати моніторинг", callback_data="search:save")
    )
    builder.row(
        InlineKeyboardButton(text="🔎 Шукати", callback_data="search:run"),
        InlineKeyboardButton(text="Скинути все", callback_data="search:reset"),
    )
    return builder.as_markup()


def vihicle_monitoring(selected=(), relist=True):
    """Events to watch on one car. relist=False hides the event for an ad
    without a VIN: no fingerprint, nothing to find the relisting by."""
    rows = []
    for event, text in WATCH_EVENTS.items():
        if event == "relist" and not relist:
            continue
        mark = "✅" if event in selected else "▫️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {text}", callback_data=f"watch:{event}"
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔔 Почати моніторинг", callback_data="watch:start"
            ),
            InlineKeyboardButton(text="Скасувати", callback_data="watch:cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
