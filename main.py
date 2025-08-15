import asyncio
from aiogram import Bot, Dispatcher
import logging
import sys
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

async def main():
    from ebites_bot import dp, bot
    
    # Удаляем все предыдущие webhook-и (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    # Запускаем поллинг с обработкой ошибок
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logging.error(f"Polling error: {e}, restarting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке для UptimeRobot
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем бота с обработкой KeyboardInterrupt
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
        sys.exit(1)
