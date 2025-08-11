# database.py
import sqlite3
import logging
from contextlib import contextmanager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_NAME = "ebites.db"

@contextmanager
def get_db_connection():
    """Контекстный менеджер для безопасного подключения к БД."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка базы данных: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Создаёт таблицы при первом запуске."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                city TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle'  -- idle, searching, chatting
            )
        """)
        # Таблица фильтров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                user_id INTEGER PRIMARY KEY,
                preferred_gender TEXT NOT NULL DEFAULT 'any',
                min_age INTEGER NOT NULL DEFAULT 18,
                max_age INTEGER NOT NULL DEFAULT 35,
                city TEXT NOT NULL DEFAULT 'any',
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)
        # Активные чаты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_chats (
                user1_id INTEGER,
                user2_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user1_id, user2_id)
            )
        """)
        conn.commit()
        logger.info("✅ База данных инициализирована: ebites.db")

def add_user(user_id: int):
    """Добавляет пользователя с пустыми данными (для /start)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, name, age, gender, city, status)
            VALUES (?, '', 0, '', '', 'idle')
        """, (user_id,))
        cursor.execute("""
            INSERT OR IGNORE INTO filters (user_id)
            VALUES (?)
        """, (user_id,))
        conn.commit()

def get_user(user_id: int) -> dict:
    """Возвращает данные пользователя и фильтры."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.name, u.age, u.gender, u.city, u.status,
                   f.preferred_gender, f.min_age, f.max_age, f.city AS filter_city
            FROM users u
            LEFT JOIN filters f ON u.user_id = f.user_id
            WHERE u.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            # Если нет — создаём
            add_user(user_id)
            return get_user(user_id)

        return {
            "profile": {
                "name": row[0],
                "age": int(row[1]) if row[1] else 0,
                "gender": row[2],
                "city": row[3]
            },
            "status": row[4],
            "preferences": {
                "gender": row[5],
                "age_min": int(row[6]),
                "age_max": int(row[7]),
                "city": row[8]
            }
        }

def update_user(user_id: int, name: str, age: int, gender: str, city: str):
    """Обновляет профиль пользователя."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET name = ?, age = ?, gender = ?, city = ?
            WHERE user_id = ?
        """, (name, age, gender, city, user_id))
        conn.commit()

def update_filters(user_id: int, preferred_gender=None, min_age=None, max_age=None, city=None):
    """Обновляет только указанные фильтры."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if preferred_gender is not None:
            cursor.execute("UPDATE filters SET preferred_gender = ? WHERE user_id = ?", (preferred_gender, user_id))
        if min_age is not None:
            cursor.execute("UPDATE filters SET min_age = ? WHERE user_id = ?", (min_age, user_id))
        if max_age is not None:
            cursor.execute("UPDATE filters SET max_age = ? WHERE user_id = ?", (max_age, user_id))
        if city is not None:
            cursor.execute("UPDATE filters SET city = ? WHERE user_id = ?", (city, user_id))
        conn.commit()

def set_status(user_id: int, status: str):
    """Обновляет статус пользователя."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        conn.commit()

def find_compatible(user_id: int) -> list:
    """Возвращает список совместимых пользователей (взаимные фильтры)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.name, u.age, u.gender, u.city,
                   f.preferred_gender, f.min_age, f.max_age, f.city AS filter_city
            FROM users u
            JOIN filters f ON u.user_id = f.user_id
            WHERE u.user_id != ? AND u.status = 'searching'
        """, (user_id,))
        candidates = cursor.fetchall()
        current_user = get_user(user_id)
        if not current_user:
            return []
        compatible = []
        for row in candidates:
            cand_id, name, age, gender, city, pref_gender, min_age, max_age, filter_city = row

            # 1. Проверяем: кандидат подходит под фильтры текущего
            if current_user["preferences"]["gender"] != "any" and current_user["preferences"]["gender"] != gender:
                continue
            if not (current_user["preferences"]["age_min"] <= age <= current_user["preferences"]["age_max"]):
                continue
            if current_user["preferences"]["city"] != "any" and current_user["preferences"]["city"].lower() != city.lower():
                continue

            # 2. Проверяем: текущий подходит под фильтры кандидата
            if pref_gender != "any" and current_user["profile"]["gender"] != pref_gender:
                continue
            if not (min_age <= current_user["profile"]["age"] <= max_age):
                continue
            if filter_city != "any" and current_user["profile"]["city"].lower() != filter_city.lower():
                continue

            compatible.append({"user_id": cand_id})
        return compatible

def create_chat(user1_id: int, user2_id: int):
    """Создаёт двусторонний чат."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO active_chats (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id))
        cursor.execute("INSERT OR REPLACE INTO active_chats (user1_id, user2_id) VALUES (?, ?)", (user2_id, user1_id))
        conn.commit()

def get_companion(user_id: int) -> int | None:
    """Возвращает ID собеседника."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user2_id FROM active_chats WHERE user1_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def delete_chat(user_id: int):
    """Удаляет все чаты, связанные с user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_chats WHERE user1_id = ?", (user_id,))
        # Второе направление удаляется по ON DELETE CASCADE, если бы было, но удалим явно
        conn.commit()