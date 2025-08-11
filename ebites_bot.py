import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramNetworkError
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv("ebites.env")

# Конфигурация
CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск",
    "Екатеринбург", "Казань", "Нижний Новгород",
    "Челябинск", "Самара", "Другой город"
]

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher()

# Хранилище данных
users_db = {}
active_chats = {}
searching_users = set()

class User:
    def __init__(self):
        self.name = ""
        self.age = 0
        self.gender = ""
        self.city = ""
        self.preferences = {
            "gender": "any",
            "age_min": 18,
            "age_max": 30,
            "city": "any"
        }
        self.status = "idle"  # idle/searching/chatting

class Form(StatesGroup):
    name = State()
    age = State()
    gender = State()
    city_confirm = State()
    city_manual = State()

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = User()
        await message.answer("👋 Добро пожаловать! Введите ваше имя:")
        await state.set_state(Form.name)
    else:
        await show_main_menu(user_id)

async def show_main_menu(user_id: int):
    user = users_db[user_id]
    kb = []
    
    if user.status == "idle":
        kb = [
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🔍 Найти собеседника")],
            [KeyboardButton(text="⚙️ Настройки")]
        ]
    elif user.status == "searching":
        kb = [
            [KeyboardButton(text="⏹ Остановить поиск")],
            [KeyboardButton(text="⚙️ Настройки")]
        ]
    elif user.status == "chatting":
        kb = [
            [KeyboardButton(text="🚪 Выйти из чата")],
            [KeyboardButton(text="⚠️ Пожаловаться")]
        ]

    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await bot.send_message(user_id, "Главное меню:", reply_markup=keyboard)

# ========== РЕГИСТРАЦИЯ ==========
@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    users_db[message.from_user.id].name = message.text
    await message.answer("Сколько вам лет?")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число!")
        return
    
    age = int(message.text)
    if age < 5 or age > 100:
        await message.answer("Введите реальный возраст (5-100 лет)")
        return
    
    users_db[message.from_user.id].age = age
    kb = [
        [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="gender_female")]
    ]
    await message.answer("Ваш пол:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(Form.gender)

@dp.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    users_db[callback.from_user.id].gender = gender
    
    # Создаем клавиатуру с городами (2 кнопки в ряд)
    kb = []
    for i in range(0, len(CITIES), 2):
        row = CITIES[i:i+2]
        kb.append([KeyboardButton(text=city) for city in row])
    
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await callback.message.answer("Из какого вы города? Выберите:", reply_markup=keyboard)
    await state.set_state(Form.city_confirm)
    await callback.answer()

@dp.message(Form.city_confirm)
async def confirm_city(message: types.Message, state: FSMContext):
    if message.text not in CITIES:
        await message.answer("Пожалуйста, выберите город из списка!")
        return
    
    if message.text == "Другой город":
        await message.answer("Введите название вашего города:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Form.city_manual)
    else:
        users_db[message.from_user.id].city = message.text
        await complete_registration(message.from_user.id)

@dp.message(Form.city_manual)
async def process_custom_city(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Название города слишком короткое. Введите еще раз:")
        return
    
    users_db[message.from_user.id].city = message.text
    await complete_registration(message.from_user.id)

async def complete_registration(user_id: int):
    await bot.send_message(user_id, "✅ Регистрация завершена!")
    await show_main_menu(user_id)

# ========== ПОИСК СОБЕСЕДНИКА ==========
@dp.message(F.text == "🔍 Найти собеседника")
async def start_search(message: types.Message):
    user_id = message.from_user.id
    user = users_db[user_id]
    
    if user.status != "idle":
        return
    
    user.status = "searching"
    searching_users.add(user_id)
    await message.answer("🔎 Ищем подходящего собеседника...")
    await show_main_menu(user_id)
    await find_companion(user_id)

async def find_companion(user_id: int):
    if user_id not in searching_users:
        return
    
    user = users_db[user_id]
    
    for candidate_id in searching_users:
        if candidate_id == user_id:
            continue
            
        candidate = users_db[candidate_id]
        
        # Упрощенная проверка совместимости
        if (user.preferences["gender"] in ["any", candidate.gender] and
            candidate.preferences["gender"] in ["any", user.gender] and
            user.preferences["age_min"] <= candidate.age <= user.preferences["age_max"] and
            candidate.preferences["age_min"] <= user.age <= candidate.preferences["age_max"] and
            (user.preferences["city"] == "any" or user.preferences["city"] == candidate.city) and
            (candidate.preferences["city"] == "any" or candidate.preferences["city"] == user.city)):
            
            # Соединяем пользователей
            active_chats[user_id] = candidate_id
            active_chats[candidate_id] = user_id
            
            searching_users.discard(user_id)
            searching_users.discard(candidate_id)
            
            user.status = "chatting"
            candidate.status = "chatting"
            
            await bot.send_message(user_id, "💬 Собеседник найден! Начинайте общение")
            await bot.send_message(candidate_id, "💬 Собеседник найден! Начинайте общение")
            await show_main_menu(user_id)
            await show_main_menu(candidate_id)
            return
    
    # Если собеседник не найден
    await asyncio.sleep(5)
    await find_companion(user_id)

@dp.message(F.text == "⏹ Остановить поиск")
async def stop_search(message: types.Message):
    user_id = message.from_user.id
    user = users_db[user_id]
    
    if user.status == "searching":
        user.status = "idle"
        searching_users.discard(user_id)
        await message.answer("🔍 Поиск остановлен")
        await show_main_menu(user_id)

# ========== ЧАТ ==========
@dp.message(lambda m: m.from_user.id in active_chats)
async def chat_message(message: types.Message):
    companion_id = active_chats[message.from_user.id]
    await bot.send_message(companion_id, message.text)

@dp.message(F.text == "🚪 Выйти из чата")
async def leave_chat(message: types.Message):
    user_id = message.from_user.id
    user = users_db[user_id]
    
    if user.status == "chatting" and user_id in active_chats:
        companion_id = active_chats[user_id]
        companion = users_db[companion_id]
        
        del active_chats[user_id]
        del active_chats[companion_id]
        
        user.status = "idle"
        companion.status = "idle"
        
        await message.answer("Вы вышли из чата")
        await bot.send_message(companion_id, "❌ Собеседник покинул чат")
        await show_main_menu(user_id)
        await show_main_menu(companion_id)

# ========== ЗАПУСК ==========
@dp.errors(TelegramNetworkError)
async def handle_network_error(event, bot):
    logger.error(f"Сетевая ошибка: {event.exception}")
    await asyncio.sleep(5)

if __name__ == "__main__":
    logger.info("🟢 Бот запущен!")
    dp.run_polling(bot)