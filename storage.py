"""Зберігання фільмів у базі SQLite.

Таблиці:
    statuses   — довідник статусів (переглянуто, дивлюсь, заплановано)
    movies     — фільми; статус зберігається як status_id, посилання на statuses
    audit_log  — журнал дій: кожне додавання і видалення з часом

Шлях до бази береться з оточення DB_PATH у момент підключення
(за замовчуванням data.db). Тести підставляють туди тимчасову базу.

ВАЖЛИВО: значення в SQL-запити підставляються ТІЛЬКИ через знак ?,
ніколи через f-рядок. Інакше можлива SQL-ін'єкція.
"""

import os
import sqlite3
from datetime import datetime

import logic
from models import Movie

# Фільми разом з назвою статусу: JOIN двох таблиць
SELECT_MOVIES = """
    SELECT m.id, m.title, m.year, s.name AS status, m.rating, m.date
    FROM movies m
    JOIN statuses s ON s.id = m.status_id
"""


def connect():
    """Відкриває з'єднання з базою і вмикає перевірку зв'язків між таблицями."""
    conn = sqlite3.connect(os.environ.get("DB_PATH", "data.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # без цього SQLite не перевіряє REFERENCES
    return conn


def init():
    """Створює таблиці (якщо їх ще немає) і заповнює довідник статусів."""
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status_id INTEGER NOT NULL REFERENCES statuses(id),
            rating INTEGER NOT NULL,
            date TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            movie_id INTEGER,
            details TEXT)""")
        for name in logic.STATUSES:
            conn.execute("INSERT OR IGNORE INTO statuses (name) VALUES (?)", (name,))
    conn.close()


def log_action(conn, action, movie_id, details):
    """Додає запис у журнал дій (у тому самому з'єднанні, що й основна дія)."""
    conn.execute(
        "INSERT INTO audit_log (ts, action, movie_id, details) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), action, movie_id, details))


def load(status=None):
    """Повертає список об'єктів Movie. Якщо задано status, лише з цим статусом."""
    with connect() as conn:
        if status is None:
            rows = conn.execute(SELECT_MOVIES + " ORDER BY m.date, m.id").fetchall()
        else:
            rows = conn.execute(SELECT_MOVIES + " WHERE s.name = ? ORDER BY m.date, m.id",
                                (status,)).fetchall()
    conn.close()
    return [Movie.from_row(row) for row in rows]


def add(movie):
    """Додає фільм (об'єкт Movie), записує дію в журнал і повертає новий id."""
    with connect() as conn:
        row = conn.execute("SELECT id FROM statuses WHERE name = ?", (movie.status,)).fetchone()
        if row is None:
            raise ValueError(f"невідомий статус: {movie.status}")
        cur = conn.execute(
            "INSERT INTO movies (title, year, status_id, rating, date) VALUES (?, ?, ?, ?, ?)",
            (movie.title, movie.year, row["id"], movie.rating, movie.date))
        new_id = cur.lastrowid
        log_action(conn, "add", new_id, movie.title)
    conn.close()
    return new_id


def delete(movie_id):
    """Видаляє фільм за id і записує це в журнал. Повертає True, якщо такий був."""
    with connect() as conn:
        row = conn.execute("SELECT title FROM movies WHERE id = ?", (movie_id,)).fetchone()
        if row is None:
            deleted = False
        else:
            conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            log_action(conn, "delete", movie_id, row["title"])
            deleted = True
    conn.close()
    return deleted


def status_report():
    """Звіт через JOIN: для кожного статусу кількість фільмів і середня оцінка."""
    with connect() as conn:
        rows = conn.execute("""
            SELECT s.name AS status,
                   COUNT(m.id) AS count,
                   ROUND(AVG(CASE WHEN m.rating > 0 THEN m.rating END), 2) AS average_rating
            FROM statuses s
            LEFT JOIN movies m ON m.status_id = s.id
            GROUP BY s.id
            ORDER BY count DESC, s.name""").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def read_log(limit=50):
    """Останні записи журналу дій, найновіші першими."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                            (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]
