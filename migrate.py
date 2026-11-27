"""Перенесення бази на нову схему (лабораторні 11 і 12).

Крок лабораторної 11 (якщо ще не зроблено):
    movies.status TEXT  →  movies.status_id → statuses.id, + таблиця audit_log
Крок лабораторної 12:
    + таблиця users (логін, ХЕШ пароля, is_admin)
    + movies.user_id → users.id: усі наявні фільми приписуються ОДНОМУ користувачу (вам)
    + audit_log.user_id (хто виконав дію)

Перед запуском обов'язково копія бази:
    sqlite3 data.db ".backup data-before-lab12.db"
Запуск (логін — ваш, пароль скрипт спитає двічі, на екрані він не видно):
    python3 migrate.py ваш_логін
Повторний запуск безпечний: якщо база вже нова, скрипт нічого не змінить.

Адміністратора скрипт НЕ призначає. Це робиться вручну на сервері:
    sqlite3 data.db "UPDATE users SET is_admin = 1 WHERE login = 'ваш_логін';"
"""

import getpass
import os
import sqlite3
import sys

from werkzeug.security import generate_password_hash

import storage


def columns_of(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def migrate_statuses(conn):
    """Крок лабораторної 11: статус текстом → status_id."""
    before = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    print(f"лаб. 11: фільмів у старій базі: {before}")
    conn.execute("PRAGMA foreign_keys = OFF")  # під час перебудови таблиці так радить документація SQLite
    try:
        conn.execute("BEGIN")
        conn.execute("""CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            movie_id INTEGER,
            details TEXT)""")
        for name in storage.logic.STATUSES:
            conn.execute("INSERT OR IGNORE INTO statuses (name) VALUES (?)", (name,))
        conn.execute("INSERT OR IGNORE INTO statuses (name) SELECT DISTINCT status FROM movies")
        conn.execute("""CREATE TABLE movies_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status_id INTEGER NOT NULL REFERENCES statuses(id),
            rating INTEGER NOT NULL,
            date TEXT NOT NULL)""")
        conn.execute("""INSERT INTO movies_new (id, title, year, status_id, rating, date)
            SELECT m.id, m.title, m.year, s.id, m.rating, m.date
            FROM movies m JOIN statuses s ON s.name = m.status""")
        after = conn.execute("SELECT COUNT(*) FROM movies_new").fetchone()[0]
        if after != before:
            raise RuntimeError(f"було {before} фільмів, а перенеслося {after}")
        conn.execute("DROP TABLE movies")
        conn.execute("ALTER TABLE movies_new RENAME TO movies")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        print("ПОМИЛКА: базу не змінено")
        raise
    conn.execute("PRAGMA foreign_keys = ON")
    print(f"лаб. 11: перенесено фільмів: {after}")


def migrate_users(conn, login, password_hash):
    """Крок лабораторної 12: таблиця users, власник у кожного фільму, user_id у журналі."""
    before = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    print(f"лаб. 12: фільмів у базі: {before}")
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL)""")
        row = conn.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
        if row is None:
            user_id = conn.execute(
                "INSERT INTO users (login, password_hash, created) VALUES (?, ?, ?)",
                (login, password_hash, storage.now())).lastrowid
        else:
            user_id = row["id"]

        if "user_id" not in columns_of(conn, "audit_log"):
            conn.execute("ALTER TABLE audit_log ADD COLUMN user_id INTEGER REFERENCES users(id)")

        conn.execute("""CREATE TABLE movies_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status_id INTEGER NOT NULL REFERENCES statuses(id),
            rating INTEGER NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id))""")
        conn.execute("""INSERT INTO movies_new (id, title, year, status_id, rating, date, user_id)
            SELECT id, title, year, status_id, rating, date, ? FROM movies""", (user_id,))
        after = conn.execute("SELECT COUNT(*) FROM movies_new").fetchone()[0]
        if after != before:
            raise RuntimeError(f"було {before} фільмів, а перенеслося {after}")
        conn.execute("DROP TABLE movies")
        conn.execute("ALTER TABLE movies_new RENAME TO movies")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        print("ПОМИЛКА: базу не змінено")
        raise
    conn.execute("PRAGMA foreign_keys = ON")
    print(f"лаб. 12: користувач {login!r} (id {user_id}), йому приписано фільмів: {after}")


def ask_login_and_password():
    """Логін з командного рядка, пароль вводиться двічі і не показується на екрані."""
    if len(sys.argv) < 2:
        print("вкажіть свій логін: python3 migrate.py ваш_логін")
        sys.exit(1)
    login = sys.argv[1].strip()
    password = getpass.getpass("придумайте пароль (від 8 символів): ")
    if getpass.getpass("повторіть пароль: ") != password:
        print("паролі не збігаються, нічого не змінено")
        sys.exit(1)
    return login, password


def main(login=None, password=None):
    path = os.environ.get("DB_PATH", "data.db")
    conn = sqlite3.connect(path)
    conn.isolation_level = None  # транзакцію відкриваємо і закриваємо самі: BEGIN ... COMMIT
    conn.row_factory = sqlite3.Row

    columns = columns_of(conn, "movies")
    if not columns:
        conn.close()
        print("таблиці movies немає: старої бази нема, переносити нічого")
        storage.init()
        return
    if "user_id" in columns:
        conn.close()
        print("база вже в новому форматі, нічого не роблю")
        storage.init()
        return

    if login is None:
        login, password = ask_login_and_password()
    if len(login) < 3 or len(password) < 8:
        conn.close()
        print("логін від 3 символів, пароль від 8; нічого не змінено")
        sys.exit(1)

    if "status_id" not in columns:
        migrate_statuses(conn)
    migrate_users(conn, login, generate_password_hash(password))

    problems = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    storage.init()
    print(f"готово, порушених зв'язків: {len(problems)}")


if __name__ == "__main__":
    main()
