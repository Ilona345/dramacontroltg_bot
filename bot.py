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
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Напишите /start, чтобы начать.")
        logging.debug(f"User {chat_id} sent message without starting: {message.text}")
        return

    step = user_data[chat_id]["step"]

    if step == 1:
        user_data[chat_id]["side1"] = message.text
        bot.send_message(chat_id, "Теперь — сторона 2:\nЧто произошло с Вашей точки зрения?")
        user_data[chat_id]["step"] = 2
        logging.debug(f"User {chat_id} provided side1: {message.text}")

    elif step == 2:
        user_data[chat_id]["side2"] = message.text
        bot.send_message(chat_id, "Отлично! Напишите /solve, чтобы вынести вердикт.")
        user_data[chat_id]["step"] = 3
        logging.debug(f"User {chat_id} provided side2: {message.text}")

@bot.message_handler(commands=["solve"])
def solve_conflict(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)

    if not data or not data["side1"] or not data["side2"]:
        bot.send_message(chat_id, "Сначала введите версии обеих сторон.")
        logging.debug(f"User {chat_id} tried to solve without both sides.")
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
    logging.debug(f"User {chat_id} prompt for OpenAI:\n{prompt}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты опытный арбитр по конфликтам, принимающий жёсткие решения."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        verdict = response.choices[0].message["content"]
        logging.debug(f"User {chat_id} received verdict:\n{verdict}")
        bot.send_message(chat_id, verdict)
    except Exception as e:
        logging.error(f"OpenAI request failed for user {chat_id}: {e}")
        bot.send_message(chat_id, "Произошла ошибка при обработке запроса. Попробуйте позже.")

if __name__ == "__main__":
    bot.remove_webhook()
    logging.info("Запуск бота...")
    bot.polling(none_stop=True)
