from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Моніторинг")],
        [KeyboardButton(text="Пошук автомобіля по критеріях")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Виберіть пункт в меню",
)
