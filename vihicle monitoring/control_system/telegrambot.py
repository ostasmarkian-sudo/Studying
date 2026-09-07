import asyncio
import os
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv

dp = Dispatcher()
load_dotenv(Path(__file__).parents[1] / ".env")
TOKEN = os.environ["TOKEN"]


@dp.message(CommandStart())
async def start(msg: types.Message):
    await msg.answer(text="Hello world")


async def main():
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


asyncio.run(main())
