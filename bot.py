import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from openai import OpenAI

# Логирование
logging.basicConfig(level=logging.INFO)

# Токены из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Логика арбитра
def arbitrate_conflict(text):
    prompt = f"""
Ты — строгий арбитр в споре.  
Разбери ситуацию пошагово:
1. Определи позиции обеих сторон.
2. Выяви манипуляции, передёргивания или некорректные приёмы.
3. Дай прямой вердикт: кто победитель (без ничьих).
4. Кратко обоснуй выбор.
5. Предложи план примирения.
Текст спора: {text}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне текст спора, и я вынесу вердикт.")

# Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    verdict = arbitrate_conflict(user_text)
    await update.message.reply_text(verdict)

# Запуск бота
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


