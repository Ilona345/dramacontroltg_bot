# main.py
import os
import json
import asyncio
from datetime import datetime
import openai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI   # <-- импорт OpenAI тут


# --- Настройки (из env) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DAILY_QUOTA = int(os.environ.get('DAILY_QUOTA', '3'))
client = OpenAI(api_key=OPENAI_API_KEY)  
openai.api_key = OPENAI_API_KEY

# --- Внутренняя память сессий (demo). Для продакшна: БД. ---
sessions = {}  # chat_id -> {'state': 'idle'|'asking1'|'asking2'|'ready', 'answers': {'A':..., 'B':...}}

QUOTA_FILE = "quota.json"

def load_quota():
    try:
        with open(QUOTA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"date": today_str(), "count": 0}
    # reset if date changed
    if data.get("date") != today_str():
        data = {"date": today_str(), "count": 0}
    return data

def save_quota(q):
    with open(QUOTA_FILE, 'w', encoding='utf-8') as f:
        json.dump(q, f)

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

def increment_quota():
    q = load_quota()
    q['count'] += 1
    save_quota(q)
    return q['count']

def quota_remaining():
    q = load_quota()
    return max(0, DAILY_QUOTA - q['count'])

# --- Промпт (жёсткий арбитр) ---
SYSTEM_PROMPT = (
    "Ты — очень жёсткий, безэмоциональный арбитр. Твоя задача — вынести однозначный и категоричный вердикт: "
    "ПРАВА ЛИБО СТОРОНА A, ЛИБО СТОРОНА B. Не оставляй неопределённостей в вердикте — выбери одну сторону даже при недостатке данных; "
    "при этом обязательно перечисли ключевые допущения, из-за которых вынесен вердикт. Строго отделяй факты от интерпретаций, "
    "выявляй и отмечай манипуляции и передёргивания. Пиши коротко, нумерованными пунктами. Не давай юридических консультаций. "
    "Если в тексте есть угрозы насилия, признания в тяжёлом преступлении или явная срочная опасность — НЕ выносить категоричный вердикт, "
    "а рекомендовать обратиться в экстренные службы / правоохранительные органы."
)

USER_TEMPLATE = (
    "Участник A:\n{a}\n\nУчастник B:\n{b}\n\n"
    "Выполни строго по пунктам:\n"
    "1) Подтверждаемые факты (максимум 6 пунктов) — каждая строка: [A:] или [B:] + факт.\n"
    "2) Явные противоречия между описаниями.\n"
    "3) Манипуляции / передёргивания — укажи точные фразы и почему.\n"
    "4) ВЕРДИКТ (caps): ПРАВА СТОРОНА A  — или — ПРАВА СТОРОНА B.\n"
    "5) Краткое обоснование (2-3 предложения).\n"
    "6) Рекомендация: один оптимальный вариант разрешения конфликта и пошаговый план примирения (не более 3 шага).\n"
    "Ограничение: итог не более 400 слов."
)

# --- UI ---
WELCOME = (
    "Бот поможет объективно решить любой конфликт. По очереди опишите, что случилось по мнению каждого участника. "
    "Затем нажмите кнопку «Решить конфликт»."
)

def kb_button(text, cb):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=cb)]])

# --- Handlers ---
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessions[chat_id] = {'state': 'idle', 'answers': {'A': None, 'B': None}}
    await update.effective_chat.send_message(WELCOME, reply_markup=kb_button("Начать", "begin"))

async def cb_begin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    sessions.setdefault(chat_id, {'state': 'idle', 'answers': {'A': None, 'B': None}})
    sessions[chat_id]['state'] = 'asking1'
    sessions[chat_id]['answers'] = {'A': None, 'B': None}
    await q.message.reply_text("Начинаем. Участник 1: Опишите, пожалуйста, что случилось.")

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    sess = sessions.get(chat_id)
    if not sess:
        await update.message.reply_text("Нажмите /start, чтобы начать сессию.")
        return

    state = sess['state']

    if state == 'asking1':
        sess['answers']['A'] = text
        sess['state'] = 'asking2'
        await update.message.reply_text("Теперь Участник 2: Опишите, что произошло с Вашей точки зрения.")
        return

    if state == 'asking2':
        sess['answers']['B'] = text
        sess['state'] = 'ready'
        await update.message.reply_text(
            "Оба ответа получены. Нажмите «Решить конфликт» для получения анализа.",
            reply_markup=kb_button("Решить конфликт", "resolve")
        )
        return

    if state == 'ready':
        await update.message.reply_text("Ответы уже получены. Нажмите «Решить конфликт», чтобы получить анализ или /start для новой сессии.")
        return

    await update.message.reply_text("Нажмите 'Решить конфликт' для начала.")

async def cb_resolve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    sess = sessions.get(chat_id)
    if not sess or sess.get('state') != 'ready':
        await q.message.reply_text("Сессия не готова к разрешению. Нажмите «Решить конфликт», чтобы начать.")
        return

    # quota check
    rem = quota_remaining()
    if rem <= 0:
        await q.message.reply_text("Достигнут дневной лимит запросов к ИИ. Попробуйте завтра или измените DAILY_QUOTA.")
        return

    a = sess['answers']['A'] or ""
    b = sess['answers']['B'] or ""
    user_text = USER_TEMPLATE.format(a=a, b=b)

    await q.message.reply_text(f"Отправляю запрос на решение конфликта. Осталось запросов сегодня: {rem-1}")

    def call_openai(messages):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # поменяли модель
            messages=messages,
            temperature=0.0,
            max_tokens=800
        )
        return resp.choices[0].message.content

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text}
    ]

    # sync call in thread
    try:
        result = await asyncio.to_thread(call_openai, messages)
        increment_quota()
    except Exception as e:
        result = f"Ошибка при вызове LLM: {e}"

    # отправляем результат; кнопка остается для повторных итераций
    await q.message.reply_text(result, reply_markup=kb_button("Старт", "begin"))

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(cb_begin, pattern="^begin$"))
    app.add_handler(CallbackQueryHandler(cb_resolve, pattern="^resolve$"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    print("Bot started (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()

