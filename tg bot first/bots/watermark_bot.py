import os

import telebot
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("TELEGRAM_WATERMARK_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Set TELEGRAM_WATERMARK_BOT_TOKEN before running the bot.")
bot = telebot.TeleBot(TOKEN)


def watermark(image, name):
    img = Image.open(image).convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)
    font = ImageFont.truetype("arial.ttf", 40)
    for x in range(0, img.width, 250):
        for y in range(0, img.height, 150):
            if (x // 250 + y // 150) % 2 == 0:
                draw.text((x, y), name, fill=(255, 255, 255, 80), font=font)
    txt_layer = txt_layer.rotate(
        -45,
    )
    result = Image.alpha_composite(img, txt_layer)
    result = result.convert("RGB")
    result.save(f"{name}+watermark.jpg")


@bot.message_handler(content_types=["photo"])
def water(message):
    try:
        caption = message.caption
        if not caption:
            bot.send_message(message.chat.id, "/watermark текст")
            return
        if caption and caption.startswith("/watermark"):
            tex = caption.split()
            name = " ".join(tex[1:])
            file_id = message.photo[-1].file_id
            imp = bot.get_file(file_id)
            downloaded = bot.download_file(imp.file_path)
            with open("input.jpg", "wb") as f:
                f.write(downloaded)
            watermark("input.jpg", name)
            bot.send_photo(message.chat.id, open(f"{name}+watermark.jpg", "rb"))
        else:
            bot.send_message(message.chat.id, "")
    except:
        bot.send_message(message.chat.id, f" Error:{Exception}")


bot.polling()
