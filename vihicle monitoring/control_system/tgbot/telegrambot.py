import asyncio
import os
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
import logging
from aiogram.enums import ParseMode
from handler import router
from dotenv import load_dotenv

dp = Dispatcher()
load_dotenv(Path(__file__).parent / ".env")
TOKEN = os.environ["TOKEN"]
logging.basicConfig(level=logging.INFO)  # .


async def main():
    dp.include_router(router)
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(
        bot,
    )


asyncio.run(main())
