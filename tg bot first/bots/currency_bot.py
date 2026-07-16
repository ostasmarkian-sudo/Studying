import os

import requests
import telebot

TOKEN = os.environ.get("TELEGRAM_CURRENCY_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Set TELEGRAM_CURRENCY_BOT_TOKEN before running the bot.")
bot = telebot.TeleBot(TOKEN)

def get_rate(base, target):
    url = f"https://api.frankfurter.app/latest?from={base}&to={target}"
    data = requests.get(url).json()
    return data["rates"][target]
    
def get_quote():
    url = "https://api.frankfurter.dev/v2/currencies"
    data = requests.get(url).json()
    name_result = {}
    for item in data:
        name_result[item["name"]] = item["iso_code"]
    return name_result

@bot.message_handler(commands=['convert'])
def convert(message):
    try:
        part = message.text.split()

        if len(part)== 4:
        
            amount = float(part[1])
            base = part[2].upper()
            target = part[3].upper()
        
            rate = get_rate(base,target)
            result = rate * amount
            bot.send_message(
            message.chat.id,
            f"{amount} {base} = {result:.2f} {target}"
            )
        elif len(part) == 3:
            amount = 1
            base = part[1].upper()
            target = part[2].upper()
        
            rate = get_rate(base,target)
            result = rate * amount
            bot.send_message(
            message.chat.id,
            f"{amount} {base} = {result:.2f} {target}"
            )
        else:
            bot.send_message(
            message.chat.id,
            "У вас некоректний формат повідомленя,ось зразок /convert amound base target"
            )
            return
    except Exception as e:
        bot.send_message(message.chat.id, f" Error: {e}")

@bot.message_handler(commands=['all_currency'])
def all_currency(message):
    registr = message.text.split().lower()
    
    curen = get_quote()
    text = ""
    for code, name in curen.items():
        text += f"{code} - {name}\n"

    bot.send_message(message.chat.id, text)    
