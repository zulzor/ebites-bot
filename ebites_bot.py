# ebites_bot.py

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
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv("ebites.env")

# Получение токена
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === Импорт после инициализации бота ===
from database import init_db, add_user, get_user, update_user, update_filters, set_status, \
    find_compatible, create_chat, get_companion, delete_chat

# --- Состояния ---
class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    waiting_for_city = State()
    waiting_for_city_manual = State()

class FilterStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_age_min = State()
    waiting_for_age_max = State()
    waiting_for_city = State()

# --- Инлайн-кнопки ---
# Пол
gender_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
     InlineKeyboardButton(text="👩 Женский", callback_data="gender_female")]
])

# Возраст (кнопки)
age_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="18-25", callback_data="age_18_25"),
     InlineKeyboardButton(text="26-35", callback_data="age_26_35")],
    [InlineKeyboardButton(text="36-50", callback_data="age_36_50"),
     InlineKeyboardButton(text="51-100", callback_data="age_51_100")]
])

# Город
city_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Москва", callback_data="city_Москва")],
    [InlineKeyboardButton(text="Санкт-Петербург", callback_data="city_Санкт-Петербург")],
    [InlineKeyboardButton(text="Новосибирск", callback_data="city_Новосибирск")],
    [InlineKeyboardButton(text="Другой", callback_data="city_other")]
])

# Фильтры: пол
filter_gender_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Любой", callback_data="filter_gender_any"),
     InlineKeyboardButton(text="Мужской", callback_data="filter_gender_Мужской"),
     InlineKeyboardButton(text="Женский", callback_data="filter_gender_Женский")]
])

# --- Меню ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль")],
            [KeyboardButton(text="⚙️ Изменить фильтры")],
            [KeyboardButton(text="🔍 Найти собеседника")]
        ],
        resize_keyboard=True
    )

def get_in_chat_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚪 Выйти из чата")]],
        resize_keyboard=True
    )

def get_searching_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔍 Отменить поиск")]],
        resize_keyboard=True
    )

def get_back_button():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True
    )

# --- /start ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    add_user(user_id)
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я — анонимный бот для знакомств.\n"
        "Заполни профиль и начни общение!",
        reply_markup=get_main_menu()
    )

# --- Профиль ---
@dp.message(F.text == "👤 Мой профиль")
async def profile_handler(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user["profile"]["name"]:
        await message.answer("📝 Введите имя:")
        await state.set_state(ProfileStates.waiting_for_name)
        return

    p = user["profile"]
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"• Имя: {p['name']}\n"
        f"• Возраст: {p['age']}\n"
        f"• Пол: {p['gender']}\n"
        f"• Город: {p['city']}\n\n"
        f"🔧 Что хотите изменить?"
    )
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Изменить имя")],
            [KeyboardButton(text="📅 Изменить возраст")],
            [KeyboardButton(text="⚧ Изменить пол")],
            [KeyboardButton(text="🏙 Изменить город")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "🔙 Назад")
async def go_back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы в главном меню.", reply_markup=get_main_menu())

# --- Редактирование имени ---
@dp.message(F.text == "✏️ Изменить имя")
async def edit_name(message: types.Message, state: FSMContext):
    await message.answer("📝 Введите новое имя:", reply_markup=get_back_button())
    await state.set_state(ProfileStates.waiting_for_name)

@dp.message(ProfileStates.waiting_for_name)
async def get_new_name(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await go_back_to_main(message, state)
        return
    if not message.text.isalpha() or len(message.text) > 50:
        await message.answer("Только буквы, до 50 символов:")
        return
    await state.update_data(name=message.text)
    await message.answer("📅 Выберите возраст:", reply_markup=age_inline_kb)
    await state.set_state(ProfileStates.waiting_for_age)

# --- Редактирование возраста ---
@dp.message(F.text == "📅 Изменить возраст")
async def edit_age(message: types.Message):
    await message.answer("Выберите возраст:", reply_markup=age_inline_kb)

@dp.callback_query(F.data.startswith("age_"))
async def handle_age_choice(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    age_min = int(data[1])
    age_max = int(data[2])
    age_display = f"{age_min}–{age_max}"
    await state.update_data(age=age_max)  # Сохраняем максимальный как основной
    await callback.message.edit_text(f"✅ Возраст: {age_display}")
    await callback.message.answer("⚧ Выберите пол:", reply_markup=gender_inline_kb)
    await state.set_state(ProfileStates.waiting_for_gender)
    await callback.answer()

# --- Редактирование пола ---
@dp.message(F.text == "⚧ Изменить пол")
async def edit_gender(message: types.Message):
    await message.answer("Выберите пол:", reply_markup=gender_inline_kb)

@dp.callback_query(F.data.in_(["gender_male", "gender_female"]))
async def handle_gender_choice(callback: types.CallbackQuery, state: FSMContext):
    gender = "Мужской" if callback.data == "gender_male" else "Женский"
    await state.update_data(gender=gender)
    await callback.message.edit_text(f"✅ Пол: {gender}")
    await callback.message.answer("🏙 Выберите город:", reply_markup=city_inline_kb)
    await state.set_state(ProfileStates.waiting_for_city)
    await callback.answer()

# --- Редактирование города ---
@dp.message(F.text == "🏙 Изменить город")
async def edit_city(message: types.Message):
    await message.answer("Выберите город:", reply_markup=city_inline_kb)

@dp.callback_query(F.data.startswith("city_"))
async def handle_city_choice(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split("_", 1)[1]
    if city == "other":
        await callback.message.answer("Введите город вручную:", reply_markup=get_back_button())
        await state.set_state(ProfileStates.waiting_for_city_manual)
        await callback.answer()
        return

    data = await state.get_data()
    user_id = callback.from_user.id
    name = data.get("name", get_user(user_id)["profile"]["name"])
    age = data.get("age", get_user(user_id)["profile"]["age"])
    gender = data.get("gender", get_user(user_id)["profile"]["gender"])

    update_user(user_id, name, age, gender, city)
    set_status(user_id, "idle")
    await callback.message.edit_text(f"✅ Город: {city}")
    await callback.message.answer("✅ Профиль обновлён!", reply_markup=get_main_menu())
    await state.clear()
    await callback.answer()

@dp.message(ProfileStates.waiting_for_city_manual)
async def enter_city_manual(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await go_back_to_main(message, state)
        return
    if not message.text.replace(" ", "").isalpha() or len(message.text) > 30:
        await message.answer("Введите корректное название города:")
        return
    data = await state.get_data()
    user_id = message.from_user.id
    name = data.get("name", get_user(user_id)["profile"]["name"])
    age = data.get("age", get_user(user_id)["profile"]["age"])
    gender = data.get("gender", get_user(user_id)["profile"]["gender"])
    update_user(user_id, name, age, gender, message.text)
    await message.answer("✅ Город обновлён!", reply_markup=get_main_menu())
    await state.clear()

# --- Фильтры ---
@dp.message(F.text == "⚙️ Изменить фильтры")
async def filters_menu(message: types.Message):
    kb = [
        [KeyboardButton(text="Пол")],
        [KeyboardButton(text="Возраст")],
        [KeyboardButton(text="Город")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("🔧 Выберите фильтр:", reply_markup=markup)

@dp.message(F.text == "Пол")
async def ask_gender_filter(message: types.Message):
    await message.answer("⚧ Кого искать?", reply_markup=filter_gender_kb)

@dp.callback_query(F.data.startswith("filter_gender_"))
async def set_gender_filter(callback: types.CallbackQuery):
    gender = callback.data.split("_", 2)[2]
    gender_display = "any" if gender == "Любой" else gender
    update_filters(callback.from_user.id, preferred_gender=gender_display)
    await callback.message.edit_text(f"✅ Пол фильтра: {gender}")
    await callback.message.answer("Фильтры обновлены", reply_markup=get_main_menu())
    await callback.answer()

@dp.message(F.text == "Возраст")
async def ask_age_min_filter(message: types.Message, state: FSMContext):
    await message.answer("Мин. возраст (18-100):", reply_markup=get_back_button())
    await state.set_state(FilterStates.waiting_for_age_min)

@dp.message(FilterStates.waiting_for_age_min)
async def set_min_age_filter(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await go_back_to_main(message, state)
        return
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    age_min = int(message.text)
    if not (18 <= age_min <= 100):
        await message.answer("От 18 до 100.")
        return
    await state.update_data(age_min=age_min)
    await message.answer("Макс. возраст (18-100):")
    await state.set_state(FilterStates.waiting_for_age_max)

@dp.message(FilterStates.waiting_for_age_max)
async def set_max_age_filter(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await go_back_to_main(message, state)
        return
    data = await state.get_data()
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    age_max = int(message.text)
    if not (18 <= age_max <= 100):
        await message.answer("От 18 до 100.")
        return
    if age_max < data["age_min"]:
        await message.answer("❌ Макс. < мин.")
        return
    update_filters(message.from_user.id, min_age=data["age_min"], max_age=age_max)
    await message.answer("✅ Возраст фильтра обновлён!", reply_markup=get_main_menu())
    await state.clear()

@dp.message(F.text == "Город")
async def ask_city_filter(message: types.Message, state: FSMContext):
    await message.answer("Город (или 'любой'):", reply_markup=get_back_button())
    await state.set_state(FilterStates.waiting_for_city)

@dp.message(FilterStates.waiting_for_city)
async def set_city_filter(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await go_back_to_main(message, state)
        return
    city = "any" if message.text.lower() == "любой" else message.text
    update_filters(message.from_user.id, city=city)
    await message.answer(f"✅ Город фильтра: {city}", reply_markup=get_main_menu())
    await state.clear()

# --- Поиск ---
@dp.message(F.text == "🔍 Найти собеседника")
async def start_search(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["status"] == "chatting":
        await message.answer("Вы в чате!", reply_markup=get_in_chat_menu())
        return
    if user["status"] == "searching":
        await message.answer("Вы уже ищете!", reply_markup=get_searching_menu())
        return
    if not all([user["profile"]["name"], user["profile"]["age"], user["profile"]["gender"], user["profile"]["city"]]):
        await message.answer("❌ Заполните профиль!")
        return

    set_status(user_id, "searching")
    await message.answer("🔎 Ищем...", reply_markup=get_searching_menu())
    asyncio.create_task(find_partner_with_timeout(user_id))

async def find_partner_with_timeout(user_id: int):
    try:
        # --- Этап 1: Основной поиск (15 секунд) ---
        for _ in range(3):  # 3 попытки × 5 сек = 15 сек
            await asyncio.sleep(5)
            if get_user(user_id)["status"] != "searching":  # Пользователь мог выйти
                return
            candidates = find_compatible(user_id)
            for cand in candidates:
                companion_id = cand["user_id"]
                if get_user(companion_id)["status"] == "searching":
                    create_chat(user_id, companion_id)
                    set_status(user_id, "chatting")
                    set_status(companion_id, "chatting")
                    await bot.send_message(user_id, "🎉 Нашли! Пишите:", reply_markup=get_in_chat_menu())
                    await bot.send_message(companion_id, "🎉 Нашли! Ждём:", reply_markup=get_in_chat_menu())
                    return

        # --- Этап 2: Проверяем, всё ещё ищем? ---
        if get_user(user_id)["status"] != "searching":
            return

        # --- Этап 3: Расширяем фильтры ---
        user = get_user(user_id)
        new_max_age = min(user["preferences"]["age_max"] + 10, 99)
        new_gender = "any"
        new_city = "any"

        update_filters(user_id, preferred_gender=new_gender, max_age=new_max_age, city=new_city)
        set_status(user_id, "searching")  # Перестраховка

        await bot.send_message(
    user_id,
    f"🔍 Нет совпадений. Расширяем поиск:\n"
    f"• Пол: любой\n"
    f"• Возраст: до {new_max_age}\n"
    f"• Город: любой\n"
    f"Продолжаем искать…"
)

        # --- Этап 4: Бесконечный поиск с расширенными фильтрами ---
        while True:
            if get_user(user_id)["status"] != "searching":
                return
            candidates = find_compatible(user_id)
            for cand in candidates:
                companion_id = cand["user_id"]
                if get_user(companion_id)["status"] == "searching":
                    create_chat(user_id, companion_id)
                    set_status(user_id, "chatting")
                    set_status(companion_id, "chatting")
                    await bot.send_message(user_id, "🎉 Нашли! Пишите:", reply_markup=get_in_chat_menu())
                    await bot.send_message(companion_id, "🎉 Нашли! Ждём:", reply_markup=get_in_chat_menu())
                    return
            await asyncio.sleep(3)

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await bot.send_message(user_id, "❌ Ошибка поиска. Попробуйте снова.", reply_markup=get_main_menu())
        set_status(user_id, "idle")

# --- Отмена поиска ---
@dp.message(F.text == "🔍 Отменить поиск")
async def cancel_search(message: types.Message):
    user_id = message.from_user.id
    if get_user(user_id)["status"] == "searching":
        set_status(user_id, "idle")
    await message.answer("Поиск остановлен.", reply_markup=get_main_menu())

# --- Чат ---
@dp.message(F.text == "🚪 Выйти из чата")
async def exit_chat(message: types.Message):
    user_id = message.from_user.id
    comp_id = get_companion(user_id)
    if not comp_id:
        await message.answer("Вы не в чате.", reply_markup=get_main_menu())
        return
    delete_chat(user_id)
    set_status(user_id, "idle")
    set_status(comp_id, "idle")
    await bot.send_message(comp_id, "Собеседник вышел.", reply_markup=get_main_menu())
    await message.answer("Вы вышли из чата.", reply_markup=get_main_menu())

@dp.message(F.text, F.text != "🚪 Выйти из чата")
async def chat_message(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user["status"] != "chatting":
        return
    comp_id = get_companion(user_id)
    if not comp_id:
        await message.answer("Вы не в чате.", reply_markup=get_main_menu())
        return
    try:
        await bot.send_message(comp_id, message.text)
    except Exception:
        await message.answer("❌ Собеседник отключился.")
        await exit_chat(message)

# --- Запуск ---
if __name__ == "__main__":
    init_db()
    print("🟢 Бот @anon_ebites_bot запущен!")
    dp.run_polling(bot)