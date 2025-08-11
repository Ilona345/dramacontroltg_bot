import os
import threading
import logging
from flask import Flask
import telebot
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

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
                     "Затем нажмите кнопку 'Решить конфликт'.\n\n"
                     "Сначала — сторона 1:\nЧто случилось по Вашему мнению?")
    user_data[chat_id]["step"] = 1

@bot.message_handler(func=lambda m: True)
def get_response(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Напишите /start, чтобы начать.")
        return

    step = user_data[chat_id]["step"]

    if step == 1:
        user_data[chat_id]["side1"] = message.text
        bot.send_message(chat_id, "Теперь — сторона 2:\nЧто произошло с Вашей точки зрения?")
        user_data[chat_id]["step"] = 2

    elif step == 2:
        user_data[chat_id]["side2"] = message.text
        bot.send_message(chat_id, "Отлично! Напишите /solve, чтобы вынести вердикт.")
        user_d_
