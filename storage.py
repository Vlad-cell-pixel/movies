"""Зберігання даних у базі SQLite.

Таблиці:
    users      — користувачі: логін, ХЕШ пароля (не сам пароль!), чи адміністратор
    statuses   — довідник статусів (переглянуто, дивлюсь, заплановано)
    movies     — фільми; status_id → statuses, user_id → users (чий це фільм)
    audit_log  — журнал дій: хто (user_id), що зробив і коли

Шлях до бази береться з оточення DB_PATH у момент підключення
(за замовчуванням data.db). Тести підставляють туди тимчасову базу.

ВАЖЛИВО:
  * значення в SQL підставляються ТІЛЬКИ через знак ?, ніколи через f-рядок;
  * кожна функція з фільмами користувача отримує user_id і має в SQL
    "WHERE ... user_id = ?" — так ніхто не бачить і не змінює чужого.
"""

import os
import sqlite3
from datetime import datetime

import logic
from models import Movie

# Фільми разом з назвою статусу: JOIN двох таблиць
SELECT_MOVIES = """
    SELECT m.id, m.title, m.year, s.name AS status, m.rating, m.date, m.user_id
    FROM movies m
    JOIN statuses s ON s.id = m.status_id
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    """Відкриває з'єднання з базою і вмикає перевірку зв'язків між таблицями."""
    conn = sqlite3.connect(os.environ.get("DB_PATH", "data.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # без цього SQLite не перевіряє REFERENCES
    return conn


def init():
    """Створює таблиці (якщо їх ще немає) і заповнює довідник статусів."""
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status_id INTEGER NOT NULL REFERENCES statuses(id),
            rating INTEGER NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            movie_id INTEGER,
            details TEXT,
            user_id INTEGER REFERENCES users(id))""")
        for name in logic.STATUSES:
            conn.execute("INSERT OR IGNORE INTO statuses (name) VALUES (?)", (name,))
    conn.close()


# ---------- Користувачі ----------

def add_user(login, password_hash):
    """Створює користувача і повертає його id.

    Якщо такий логін уже є, SQLite кидає sqlite3.IntegrityError (через UNIQUE).
    Сюди передається вже ХЕШ пароля, сам пароль storage ніколи не бачить.
    """
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (login, password_hash, created) VALUES (?, ?, ?)",
            (login, password_hash, now()))
        new_id = cur.lastrowid
        log_action(conn, "register", None, login, new_id)
    conn.close()
    return new_id


def get_user(user_id):
    """Користувач за id (словник) або None."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_login(login):
    """Користувач за логіном (словник) або None."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users():
    """Усі користувачі для адміністратора: БЕЗ хешів паролів, з кількістю фільмів."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT u.id, u.login, u.is_admin, u.created, COUNT(m.id) AS movies
            FROM users u LEFT JOIN movies m ON m.user_id = u.id
            GROUP BY u.id ORDER BY u.id""").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------- Журнал ----------

def log_action(conn, action, movie_id, details, user_id):
    """Додає запис у журнал дій (у тому самому з'єднанні, що й основна дія)."""
    conn.execute(
        "INSERT INTO audit_log (ts, action, movie_id, details, user_id) VALUES (?, ?, ?, ?, ?)",
        (now(), action, movie_id, details, user_id))


def read_log(limit=50):
    """Останні записи журналу дій, найновіші першими."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                            (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------- Фільми ----------

def load(user_id, status=None):
    """Фільми ОДНОГО користувача (список Movie). Якщо задано status, лише з цим статусом."""
    with connect() as conn:
        if status is None:
            rows = conn.execute(SELECT_MOVIES + " WHERE m.user_id = ? ORDER BY m.date, m.id",
                                (user_id,)).fetchall()
        else:
            rows = conn.execute(
                SELECT_MOVIES + " WHERE m.user_id = ? AND s.name = ? ORDER BY m.date, m.id",
                (user_id, status)).fetchall()
    conn.close()
    return [Movie.from_row(row) for row in rows]


def load_all():
    """Фільми ВСІХ користувачів. Лише для адміністратора (експорт)."""
    with connect() as conn:
        rows = conn.execute(SELECT_MOVIES + " ORDER BY m.id").fetchall()
    conn.close()
    return [Movie.from_row(row) for row in rows]


def add(movie, user_id):
    """Додає фільм користувачу user_id, записує дію в журнал і повертає новий id."""
    with connect() as conn:
        row = conn.execute("SELECT id FROM statuses WHERE name = ?", (movie.status,)).fetchone()
        if row is None:
            raise ValueError(f"невідомий статус: {movie.status}")
        cur = conn.execute(
            "INSERT INTO movies (title, year, status_id, rating, date, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (movie.title, movie.year, row["id"], movie.rating, movie.date, user_id))
        new_id = cur.lastrowid
        log_action(conn, "add", new_id, movie.title, user_id)
    conn.close()
    movie.user_id = user_id
    return new_id


def delete(movie_id, user_id):
    """Видаляє фільм, ТІЛЬКИ якщо він належить user_id. Повертає True, якщо видалено.

    Чужий і неіснуючий фільм дають однаковий результат (False → 404),
    щоб не підказувати, що під цим id щось є.
    """
    with connect() as conn:
        row = conn.execute("SELECT title FROM movies WHERE id = ? AND user_id = ?",
                           (movie_id, user_id)).fetchone()
        deleted = row is not None
        if deleted:
            conn.execute("DELETE FROM movies WHERE id = ? AND user_id = ?", (movie_id, user_id))
            log_action(conn, "delete", movie_id, row["title"], user_id)
    conn.close()
    return deleted


def admin_delete(movie_id, admin_id):
    """Адміністратор видаляє будь-який фільм. У журнал пишеться id адміністратора."""
    with connect() as conn:
        row = conn.execute("SELECT title, user_id FROM movies WHERE id = ?",
                           (movie_id,)).fetchone()
        deleted = row is not None
        if deleted:
            conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            log_action(conn, "admin_delete", movie_id,
                       f"{row['title']} (власник user_id={row['user_id']})", admin_id)
    conn.close()
    return deleted


def status_report(user_id):
    """Звіт через JOIN для одного користувача: кількість фільмів і середня оцінка за статусами."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT s.name AS status,
                   COUNT(m.id) AS count,
                   ROUND(AVG(CASE WHEN m.rating > 0 THEN m.rating END), 2) AS average_rating
            FROM statuses s
            LEFT JOIN movies m ON m.status_id = s.id AND m.user_id = ?
            GROUP BY s.id
            ORDER BY count DESC, s.name""", (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]
