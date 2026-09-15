import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold

import database as db
import keyboard as kb
import search
import watch

router = Router()
logging.basicConfig(level=logging.INFO)  # .


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    await db.upsert_user(msg.from_user)
    referense = f"Hello {hbold(msg.from_user.first_name)}"
    await msg.answer(text=referense, reply_markup=kb.main)


@router.message(Command("help"))
async def help(msg: Message):
    await msg.answer(text="ddss")


# The reply buttons live here and not in their own routers: this router is
# checked before its sub-routers, so the buttons work even while a flow is
# waiting for typed text and would otherwise take the button text as input.
@router.message(F.text == kb.SEARCH_BUTTON)
async def open_search(msg: Message, state: FSMContext):
    await search.start(msg, state)


@router.message(F.text == kb.WATCH_BUTTON)
async def open_watch(msg: Message, state: FSMContext):
    await watch.start(msg, state)


# Checked last. A button from a finished flow, or one left over from before a
# restart (MemoryStorage forgets every draft), gets an answer instead of a
# spinner that never stops.
stale = Router()


@stale.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer(
        "Це меню вже неактуальне, відкрийте його заново кнопками внизу.",
        show_alert=True,
    )


router.include_routers(search.router, watch.router, stale)
