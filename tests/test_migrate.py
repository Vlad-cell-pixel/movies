"""Тести міграції: старі бази переносяться без втрат, усі фільми отримують власника."""

import sqlite3

import pytest
from werkzeug.security import check_password_hash

import migrate
import storage


def make_lab10_db(path):
    """База як у лабораторній 10: статус текстом, користувачів немає."""
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE movies (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
        year INTEGER NOT NULL, status TEXT NOT NULL, rating INTEGER NOT NULL, date TEXT NOT NULL)""")
    conn.executemany("INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?)", [
        (1, "Матриця", 1999, "переглянуто", 10, "2026-09-03"),
        (5, "Дюна", 2021, "заплановано", 0, "2026-09-05"),       # id з «дірками» зберігаються
        (9, "Оппенгеймер", 2023, "дивлюсь", 0, "2026-09-23")])
    conn.commit()
    conn.close()


def make_lab11_db(path):
    """База як у лабораторній 11: статуси окремою таблицею, журнал без user_id."""
    make_lab10_db(path)
    conn = sqlite3.connect(path)
    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    migrate.migrate_statuses(conn)
    conn.execute("INSERT INTO audit_log (ts, action, movie_id, details) "
                 "VALUES ('2026-11-01T10:00:00', 'add', 9, 'Оппенгеймер')")
    conn.close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setenv("DB_PATH", str(path))
    return path


def test_migrate_from_lab11(db_path, monkeypatch):
    make_lab11_db(db_path)
    migrate.main("vlad", "dovhyi-parol-123")
    user = storage.get_user_by_login("vlad")
    movies = {m.id: m for m in storage.load(user["id"])}
    assert set(movies) == {1, 5, 9}                                 # нічого не загубилося
    assert (movies[5].title, movies[5].status) == ("Дюна", "заплановано")
    assert check_password_hash(user["password_hash"], "dovhyi-parol-123")
    assert user["password_hash"] != "dovhyi-parol-123"              # у базі хеш, а не пароль
    assert user["is_admin"] == 0                                    # адміна скрипт не призначає
    assert storage.read_log()[0]["user_id"] is None                 # старий запис журналу цілий


def test_migrate_from_lab10_does_both_steps(db_path):
    make_lab10_db(db_path)
    migrate.main("vlad", "dovhyi-parol-123")
    user = storage.get_user_by_login("vlad")
    assert len(storage.load(user["id"])) == 3
    new_id = storage.add(storage.load(user["id"])[0], user["id"])  # після міграції все працює
    assert new_id == 10 and storage.read_log()[0]["user_id"] == user["id"]


def test_migrate_twice_is_safe(db_path, capsys):
    make_lab10_db(db_path)
    migrate.main("vlad", "dovhyi-parol-123")
    migrate.main("vlad", "dovhyi-parol-123")
    assert "вже в новому форматі" in capsys.readouterr().out
    assert len(storage.list_users()) == 1
    assert len(storage.load_all()) == 3


def test_migrate_rejects_short_password(db_path):
    make_lab10_db(db_path)
    with pytest.raises(SystemExit):
        migrate.main("vlad", "123")
    conn = sqlite3.connect(db_path)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(movies)")]
    conn.close()
    assert "status" in columns and "user_id" not in columns         # база не чіпана
