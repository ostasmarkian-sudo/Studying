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
import keyboard as kb

router = Router()
logging.basicConfig(level=logging.INFO)  # .


@router.message(CommandStart())
async def start(msg: Message):
    referense = f"Hello {(hbold(msg.from_user.first_name),)}"
    await msg.answer(text=referense, reply_markup=kb.main)


@router.message(Command("help"))
async def help(msg: Message):
    await msg.answer(text="ddss")
