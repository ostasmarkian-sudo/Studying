from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message


async def edit(call: CallbackQuery, text=None, markup=None):
    """Put new content on the message the pressed button sits on.

    text=None changes only the keyboard. Telegram refuses to edit a message
    older than 48 hours (aiogram hands it over as InaccessibleMessage), so that
    one gets a fresh message instead. It also refuses an edit that changes
    nothing, which is exactly what pressing an already chosen option does, and
    that refusal is not an error here.
    """
    if not isinstance(call.message, Message):
        if text is not None:
            await call.bot.send_message(call.from_user.id, text, reply_markup=markup)
        return
    try:
        if text is None:
            await call.message.edit_reply_markup(reply_markup=markup)
        else:
            await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in error.message:
            raise


async def drop_markup(message: Message, message_id):
    """Take the buttons off an earlier bot message so they cannot be pressed."""
    if message_id is None:
        return
    try:
        await message.bot.edit_message_reply_markup(
            chat_id=message.chat.id, message_id=message_id, reply_markup=None
        )
    except TelegramBadRequest:
        pass  # deleted by the user or too old, nothing left to clean up
