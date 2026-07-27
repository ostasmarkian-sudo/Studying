import argparse
from database import add_new_website, find_website_history, delete_website
from monitoring import update
import telebot
from apscheduler.schedulers.blocking import BlockingScheduler
from config import TG_BOT_TOKEN

BOT = telebot.TeleBot(TG_BOT_TOKEN)
parse = argparse.ArgumentParser
parse.add_argument(
    "-a",
    "--add",
    type=str,
)
