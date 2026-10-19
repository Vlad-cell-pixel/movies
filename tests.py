"""Перевірки функцій з logic.py і storage.py. Запуск: python3 tests.py"""

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
    filename = "test_data.txt"
    try:
        storage.save(filename, MOVIES)
        assert storage.load(filename) == MOVIES      # що записали, те й прочитали
        # дописуємо сміття: програма має пропустити ці рядки, а не впасти
        with open(filename, "a", encoding="utf-8") as f:
            f.write("зламаний рядок\n")
            f.write("Фільм;не_рік;переглянуто;5;2026-10-01\n")
            f.write("Фільм;2000;колись;5;2026-10-01\n")
            f.write("Фільм;2000;переглянуто;99;2026-10-01\n")
            f.write("\n")
        assert storage.load(filename) == MOVIES
    finally:
        if os.path.exists(filename):
            os.remove(filename)
    assert storage.load("файла_точно_немає.txt") == []


if __name__ == "__main__":
    test_make_record()
    test_find()
    test_count_by_status()
    test_average_rating()
    test_top_rated()
    test_storage()
    print("усі тести пройдено")
