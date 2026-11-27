"""Одноразове перенесення бази на нову схему (лабораторна 11).

Було:  movies(id, title, year, status TEXT, rating, date)
Стало: statuses(id, name)  +  movies(id, title, year, status_id → statuses.id, rating, date)
       + audit_log (журнал дій)

Що робить:
  1. створює таблиці statuses і audit_log;
  2. додає в statuses усі статуси, що трапляються в старих фільмах;
  3. переписує movies: замість тексту статусу — його id; id фільмів не змінюються;
  4. перевіряє, що кількість фільмів до і після однакова, інакше нічого не зберігає.

Запускається ОДИН раз, перед запуском зробіть копію бази:
    sqlite3 data.db ".backup data-before-migrate.db"
    python3 migrate.py
Повторний запуск безпечний: якщо база вже нова, скрипт нічого не змінить.
Файл лишається в репозиторії як документ того, що сталося з базою.
"""

import os
import sqlite3

import storage


def main():
    path = os.environ.get("DB_PATH", "data.db")
    conn = sqlite3.connect(path)
    conn.isolation_level = None  # транзакцію відкриваємо і закриваємо самі: BEGIN ... COMMIT
    conn.row_factory = sqlite3.Row

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(movies)")]
    if not columns:
        conn.close()
        print("таблиці movies немає: старої бази нема, переносити нічого")
        storage.init()
        return
    if "status_id" in columns:
        conn.close()
        print("база вже в новому форматі, нічого не роблю")
        storage.init()  # на випадок, якщо бракує audit_log
        return

    before = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    print(f"фільмів у старій базі: {before}")

    # Під час перебудови таблиці перевірку зв'язків вимикають (так радить документація SQLite)
    conn.execute("PRAGMA foreign_keys = OFF")
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
        # статуси: спершу стандартні, потім усі, що є в старих записах
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
        conn.close()
        print("ПОМИЛКА: базу не змінено")
        raise
    conn.execute("PRAGMA foreign_keys = ON")
    problems = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    print(f"перенесено фільмів: {after}, порушених зв'язків: {len(problems)}")


if __name__ == "__main__":
    main()
