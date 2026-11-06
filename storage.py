"""Зберігання фільмів у базі даних SQLite (файл data.db).

У лабораторній 6 фільми лежали в текстовому файлі data.txt.
Тепер вони в таблиці movies бази SQLite. logic.py від цього не змінився:
він, як і раніше, отримує список словників.

ВАЖЛИВО: значення в SQL-запити підставляються ТІЛЬКИ через знак ?,
ніколи через f-рядок. Інакше можлива SQL-ін'єкція.
"""

import sqlite3

DB = "data.db"  # тести підмінюють це значення на тимчасову базу


def connect():
    """Відкриває з'єднання з базою."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  # рядки можна перетворити на словники
    return conn


def init():
    """Створює таблицю, якщо її ще немає."""
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status TEXT NOT NULL,
            rating INTEGER NOT NULL,
            date TEXT NOT NULL)""")
    conn.close()


def load(status=None):
    """Повертає список словників-фільмів. Якщо задано status, лише з цим статусом."""
    with connect() as conn:
        if status is None:
            rows = conn.execute("SELECT * FROM movies ORDER BY date, id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM movies WHERE status = ? ORDER BY date, id",
                                (status,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def add(movie):
    """Додає фільм (словник з logic.make_record) і повертає його id."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO movies (title, year, status, rating, date) VALUES (?, ?, ?, ?, ?)",
            (movie["title"], movie["year"], movie["status"], movie["rating"], movie["date"]))
        new_id = cur.lastrowid
    conn.close()
    return new_id


def delete(movie_id):
    """Видаляє фільм за id. Повертає True, якщо такий був."""
    with connect() as conn:
        cur = conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted
