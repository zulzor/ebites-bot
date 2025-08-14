from flask import Flask
import threading
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# === Flask веб-сервер ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает! 🚀"

@app.route('/health')
def health():
    return {"status": "ok"}, 200

# Запуск Flask в фоне
def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# === Telegram бот ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.startup()
async def startup():
    print("✅ Бот запущен")

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Бот работает.")

# === Запуск ===
async def start_bot():
    # Запускаем Flask в отдельном потоке
    thread = threading.Thread(target=run_web, daemon=True)
    thread.start()

    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(start_bot())
