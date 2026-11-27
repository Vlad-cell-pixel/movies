"""Тести бази: дві таблиці, JOIN, журнал дій, захист від SQL-ін'єкції."""

import sqlite3

import pytest

import storage
from models import Movie


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Порожня тимчасова база на кожен тест."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    storage.init()


def test_add_and_load_returns_movies(db):
    new_id = storage.add(Movie("Матриця", 1999, "переглянуто", 10, "2026-10-01"))
    movies = storage.load()
    assert len(movies) == 1 and movies[0].id == new_id
    assert isinstance(movies[0], Movie) and movies[0].status == "переглянуто"


def test_load_filters_by_status(db):
    storage.add(Movie("Матриця", 1999, "переглянуто", 10, "2026-10-01"))
    storage.add(Movie("Дюна", 2021, "заплановано", 0, "2026-10-02"))
    assert [m.title for m in storage.load("заплановано")] == ["Дюна"]
    assert storage.load("' OR '1'='1") == []           # SQL-ін'єкція у фільтрі не спрацьовує


def test_sql_injection_title_is_stored_as_text(db):
    storage.add(Movie("'; DROP TABLE movies; --", 2000, "переглянуто", 0, "2026-10-01"))
    assert storage.load()[0].title == "'; DROP TABLE movies; --"   # таблиця ціла


def test_status_must_exist(db):
    with pytest.raises(ValueError):
        storage.add(Movie("Фільм", 2000, "колись", 0, "2026-10-01"))


def test_foreign_key_is_checked(db):
    conn = storage.connect()
    with pytest.raises(sqlite3.IntegrityError):         # статусу з id 999 немає
        conn.execute("INSERT INTO movies (title, year, status_id, rating, date) "
                     "VALUES ('x', 2000, 999, 0, '2026-10-01')")
    conn.close()


def test_status_report_uses_join(db):
    storage.add(Movie("Матриця", 1999, "переглянуто", 10, "2026-10-01"))
    storage.add(Movie("Дюна", 2021, "переглянуто", 7, "2026-10-02"))
    storage.add(Movie("Олдбой", 2003, "заплановано", 0, "2026-10-03"))
    report = {r["status"]: r for r in storage.status_report()}
    assert report["переглянуто"] == {"status": "переглянуто", "count": 2, "average_rating": 8.5}
    assert report["заплановано"]["count"] == 1 and report["заплановано"]["average_rating"] is None
    assert report["дивлюсь"]["count"] == 0              # LEFT JOIN показує і порожні статуси


def test_audit_log_records_add_and_delete(db):
    new_id = storage.add(Movie("Матриця", 1999, "переглянуто", 10, "2026-10-01"))
    assert storage.delete(new_id) is True
    assert storage.delete(new_id) is False              # вдруге нічого видаляти і не логуємо
    log = storage.read_log()
    assert [(r["action"], r["movie_id"], r["details"]) for r in log] == [
        ("delete", new_id, "Матриця"), ("add", new_id, "Матриця")]
    assert log[0]["ts"] >= log[1]["ts"]                 # час записується
