import os
import threading
from flask import Flask
import telebot
from openai import OpenAI

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
        user_data[chat_id]["step"] = 3

@bot.message_handler(commands=["solve"])
def solve_conflict(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)

    if not data or not data["side1"] or not data["side2"]:
        bot.send_message(chat_id, "Сначала введите версии обеих сторон.")
        return

    prompt = f"""
Ты — жёсткий арбитр, который всегда определяет одну победившую сторону в конфликте.
Две версии конфликта:

Сторона 1: {data['side1']}
Сторона 2: {data['side2']}

Требования:
1. Определи победителя (Сторона 1 или Сторона 2) — без вариантов "оба виноваты".
2. Обоснуй решение по пунктам.
3. Обязательно укажи, где каждая сторона использует манипуляции или передёргивания фактов.
4. Сохрани нейтральный тон, но будь прямолинеен.
5. После вердикта дай конкретный план примирения для обеих сторон.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты опытный арбитр по конфликтам, принимающий жёсткие решения."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    verdict = response.choices[0].message["content"]
    bot.send_message(chat_id, verdict)

if __name__ == "__main__":
    bot.remove_webhook()
    threading.Thread(target=run_flask).start()
    bot.polling(none_stop=True)
