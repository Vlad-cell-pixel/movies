"""Перевірки logic.py, storage.py (SQLite) і app.py (Flask). Запуск: python3 tests.py"""

import os

import logic
import storage

MOVIES = [
    {"title": "Інтерстеллар", "year": 2014, "status": "переглянуто", "rating": 9, "date": "2026-10-01"},
    {"title": "Матриця", "year": 1999, "status": "переглянуто", "rating": 10, "date": "2026-10-02"},
    {"title": "Дюна: Частина друга", "year": 2024, "status": "заплановано", "rating": 0, "date": "2026-10-03"},
    {"title": "Дюна", "year": 2021, "status": "переглянуто", "rating": 7, "date": "2026-10-04"},
    {"title": "Шоу Трумана", "year": 1998, "status": "дивлюсь", "rating": 0, "date": "2026-10-05"},
]


def expect_error(func, *args):
    """Перевіряє, що виклик func(*args) кидає ValueError."""
    try:
        func(*args)
    except ValueError:
        return
    raise AssertionError(f"очікувалась ValueError для {func.__name__}{args}")


def test_make_record():
    r = logic.make_record("Матриця", "1999", "переглянуто", "10", "2026-10-02")
    assert r == {"title": "Матриця", "year": 1999, "status": "переглянуто",
                 "rating": 10, "date": "2026-10-02"}
    # статус великими літерами і пробіли навколо назви теж приймаються
    r = logic.make_record("  Дюна ", "2021", "Заплановано")
    assert r["title"] == "Дюна" and r["status"] == "заплановано" and r["rating"] == 0
    assert r["date"] != ""  # дата за замовчуванням = сьогодні
    # неправильні дані
    expect_error(logic.make_record, "", "2000", "переглянуто")            # порожня назва
    expect_error(logic.make_record, "А;Б", "2000", "переглянуто")         # ; у назві
    expect_error(logic.make_record, "Фільм", "абв", "переглянуто")        # рік не число
    expect_error(logic.make_record, "Фільм", "1500", "переглянуто")       # рік занадто ранній
    expect_error(logic.make_record, "Фільм", "2000", "колись")            # невідомий статус
    expect_error(logic.make_record, "Фільм", "2000", "переглянуто", "11")  # оцінка > 10
    expect_error(logic.make_record, "Фільм", "2000", "переглянуто", "-1")  # оцінка < 0
    expect_error(logic.make_record, "Фільм", "2000", "переглянуто", "5", "03.10.2026")  # дата


def test_find():
    assert len(logic.find(MOVIES, "title", "дюна")) == 2          # без урахування регістру
    assert logic.find(MOVIES, "title", "немає такого") == []
    assert len(logic.find(MOVIES, "status", "переглянуто")) == 3
    assert logic.find(MOVIES, "year", "1999")[0]["title"] == "Матриця"
    assert len(logic.find(MOVIES, "rating", "9")) == 2           # оцінка 9 і вище
    assert logic.find([], "status", "переглянуто") == []
    expect_error(logic.find, MOVIES, "year", "давно")
    expect_error(logic.find, MOVIES, "genre", "драма")


def test_count_by_status():
    assert logic.count_by_status(MOVIES) == {"переглянуто": 3, "заплановано": 1, "дивлюсь": 1}
    assert logic.count_by_status([]) == {}


def test_average_rating():
    assert logic.average_rating(MOVIES) == 8.67  # (9 + 10 + 7) / 3, нулі не рахуються
    assert logic.average_rating([]) is None       # немає ділення на нуль
    assert logic.average_rating([MOVIES[2]]) is None  # лише неоцінений фільм


def test_top_rated():
    top = logic.top_rated(MOVIES, 2)
    assert [r["title"] for r in top] == ["Матриця", "Інтерстеллар"]
    assert len(logic.top_rated(MOVIES, 10)) == 3  # неоцінені не потрапляють
    assert logic.top_rated([], 3) == []


def test_storage():
    """Перевіряє роботу з базою SQLite на тимчасовому файлі test_data.db."""
    old_db = storage.DB
    storage.DB = "test_data.db"
    try:
        if os.path.exists(storage.DB):
            os.remove(storage.DB)
        storage.init()
        assert storage.load() == []                     # порожня база
        ids = [storage.add(m) for m in MOVIES]
        assert ids == [1, 2, 3, 4, 5]                   # id видаються по порядку
        loaded = storage.load()
        assert len(loaded) == 5
        for movie in loaded:                            # без id — ті самі словники
            movie_without_id = dict(movie)
            del movie_without_id["id"]
            assert movie_without_id in MOVIES
        assert len(storage.load("переглянуто")) == 3    # фільтр за статусом
        assert storage.load("немає такого") == []
        assert storage.delete(2) is True                # видалили
        assert storage.delete(2) is False               # вдруге вже нічого видаляти
        assert len(storage.load()) == 4
        # SQL-ін'єкція: текст зберігається як звичайна назва, таблиця ціла
        evil = dict(MOVIES[0], title="'; DROP TABLE movies; --")
        storage.add(evil)
        assert storage.load("' OR '1'='1") == []
        assert any(m["title"] == evil["title"] for m in storage.load())
    finally:
        storage.DB = old_db
        if os.path.exists("test_data.db"):
            os.remove("test_data.db")


def test_app():
    """Перевіряє маршрути Flask без запуску сервера (test_client)."""
    old_db = storage.DB
    storage.DB = "test_app.db"
    try:
        if os.path.exists(storage.DB):
            os.remove(storage.DB)
        import app as webapp
        storage.init()
        client = webapp.app.test_client()

        assert client.get("/movies").get_json() == []
        r = client.post("/movies", json={"title": "Матриця", "year": 1999,
                                         "status": "переглянуто", "rating": 10})
        assert r.status_code == 201 and r.get_json()["id"] == 1
        client.post("/movies", json={"title": "Дюна", "year": 2021, "status": "заплановано"})
        assert len(client.get("/movies").get_json()) == 2
        assert len(client.get("/movies?status=заплановано").get_json()) == 1
        assert len(client.get("/movies?title=дюн").get_json()) == 1
        assert client.get("/report").get_json()["total"] == 2

        # неправильні запити: 400 / 404 / 405, але ніколи не 500
        assert client.post("/movies").status_code == 400                       # без тіла
        assert client.post("/movies", data="hello").status_code == 400         # не JSON
        assert client.post("/movies", json=[1, 2]).status_code == 400          # не об'єкт
        assert client.post("/movies", json={"title": "А"}).status_code == 400  # немає полів
        assert client.post("/movies", json={"title": "А", "year": "абв",
                                            "status": "переглянуто"}).status_code == 400
        assert client.post("/movies", json={"title": "А", "year": 2000,
                                            "status": "переглянуто", "rating": 15}).status_code == 400
        assert client.post("/movies", json={"title": None, "year": 2000,
                                            "status": "переглянуто"}).status_code == 400
        assert client.post("/movies", json={"title": "А", "year": True,
                                            "status": "переглянуто"}).status_code == 400
        assert client.get("/movies?status=колись").status_code == 400
        assert client.get("/movies?year=давно").status_code == 400
        assert client.delete("/movies/999").status_code == 404
        assert client.delete("/movies/abc").status_code == 404
        assert client.get("/nema").status_code == 404
        assert client.put("/movies").status_code == 405
        assert client.delete("/movies/1").status_code == 200
    finally:
        storage.DB = old_db
        if os.path.exists("test_app.db"):
            os.remove("test_app.db")


if __name__ == "__main__":
    test_make_record()
    test_find()
    test_count_by_status()
    test_average_rating()
    test_top_rated()
    test_storage()
    test_app()
    print("усі тести пройдено")
