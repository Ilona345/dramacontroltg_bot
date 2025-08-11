import os
import logging
import telebot
from openai import OpenAI

# Настройка логирования — максимум подробностей
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.DEBUG
)

telebot.logger.setLevel(logging.DEBUG)  # Логируем телеграм-бот полностью

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    logging.error("BOT_TOKEN или OPENAI_API_KEY не заданы в переменных окружения")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {"step": 0, "side1": None, "side2": None}
    bot.send_message(chat_id,
                     "Бот поможет объективно решить любой конфликт.\n"
                     "По очереди опишите, что случилось по мнению каждого участника конфликта.\n"
                     "Затем напишите /solve, чтобы получить вердикт.\n\n"
                     "Сначала — сторона 1:\nЧто случилось по Вашему мнению?")
    user_data[chat_id]["step"] = 1
    logging.debug(f"User {chat_id} started interaction.")

@bot.message_handler(func=lambda m: True)
def get_response(message):
