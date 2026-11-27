"""Тест міграції: стара база (статус текстом) переноситься без втрат."""

import sqlite3

import migrate
import storage


def make_old_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE movies (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
        year INTEGER NOT NULL, status TEXT NOT NULL, rating INTEGER NOT NULL, date TEXT NOT NULL)""")
    conn.executemany("INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?)", [
        (1, "Матриця", 1999, "переглянуто", 10, "2026-09-03"),
        (5, "Дюна", 2021, "заплановано", 0, "2026-09-05"),       # id з «дірками» зберігаються
        (9, "Оппенгеймер", 2023, "дивлюсь", 0, "2026-09-23")])
    conn.commit()
    conn.close()


def test_migrate_keeps_all_movies(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    make_old_db(path)
    monkeypatch.setenv("DB_PATH", str(path))
    migrate.main()
    movies = {m.id: m for m in storage.load()}
    assert set(movies) == {1, 5, 9}
    assert (movies[5].title, movies[5].status) == ("Дюна", "заплановано")
    assert movies[1].rating == 10
    # після міграції можна додавати нові фільми, і вони пишуться в журнал
    new_id = storage.add(movies[1])
    assert new_id == 10 and storage.read_log()[0]["action"] == "add"


def test_migrate_twice_is_safe(tmp_path, monkeypatch, capsys):
    path = tmp_path / "old.db"
    make_old_db(path)
    monkeypatch.setenv("DB_PATH", str(path))
    migrate.main()
    migrate.main()
    assert "вже в новому форматі" in capsys.readouterr().out
    assert len(storage.load()) == 3
