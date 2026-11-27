"""Тести логіки: клас Movie і функції з logic.py. База і Flask тут не потрібні."""

import pytest

import logic
from models import Movie

MOVIES = [
    Movie("Інтерстеллар", 2014, "переглянуто", 9, "2026-10-01", 1),
    Movie("Матриця", 1999, "переглянуто", 10, "2026-10-02", 2),
    Movie("Дюна: Частина друга", 2024, "заплановано", 0, "2026-10-03", 3),
    Movie("Дюна", 2021, "переглянуто", 7, "2026-10-04", 4),
    Movie("Шоу Трумана", 1998, "дивлюсь", 0, "2026-10-05", 5),
]


def test_movie_converts_text_to_numbers():
    m = Movie("Матриця", "1999", "переглянуто", "10")
    assert m.year == 1999 and m.rating == 10      # рядки стали числами в одному місці


def test_movie_to_dict_and_is_rated():
    m = Movie("Дюна", 2021, "заплановано", 0, "2026-10-04", 7)
    assert m.to_dict() == {"id": 7, "title": "Дюна", "year": 2021,
                           "status": "заплановано", "rating": 0, "date": "2026-10-04"}
    assert not m.is_rated()
    assert Movie("Дюна", 2021, "переглянуто", 8).is_rated()


def test_make_record_returns_movie():
    m = logic.make_record("  Матриця ", "1999", "Переглянуто", "10", "2026-10-02")
    assert isinstance(m, Movie)
    assert (m.title, m.year, m.status, m.rating) == ("Матриця", 1999, "переглянуто", 10)


@pytest.mark.parametrize("args", [
    ("", "2000", "переглянуто"),                   # порожня назва
    ("А;Б", "2000", "переглянуто"),                # ; у назві
    ("Фільм", "абв", "переглянуто"),               # рік не число
    ("Фільм", "1500", "переглянуто"),              # рік занадто ранній
    ("Фільм", "2000", "колись"),                   # невідомий статус
    ("Фільм", "2000", "переглянуто", "11"),        # оцінка > 10
    ("Фільм", "2000", "переглянуто", "5", "03.10.2026"),  # дата не в тому форматі
])
def test_make_record_rejects_bad_input(args):
    with pytest.raises(ValueError):
        logic.make_record(*args)


def test_find():
    assert len(logic.find(MOVIES, "title", "дюна")) == 2
    assert len(logic.find(MOVIES, "status", "переглянуто")) == 3
    assert logic.find(MOVIES, "year", "1999")[0].title == "Матриця"
    assert len(logic.find(MOVIES, "rating", "9")) == 2
    with pytest.raises(ValueError):
        logic.find(MOVIES, "genre", "драма")


def test_count_by_status():
    assert logic.count_by_status(MOVIES) == {"переглянуто": 3, "заплановано": 1, "дивлюсь": 1}
    assert logic.count_by_status([]) == {}


def test_average_rating():
    assert logic.average_rating(MOVIES) == 8.67    # нулі не враховуються
    assert logic.average_rating([]) is None
    assert logic.average_rating([MOVIES[2]]) is None


def test_top_rated():
    assert [m.title for m in logic.top_rated(MOVIES, 2)] == ["Матриця", "Інтерстеллар"]
    assert len(logic.top_rated(MOVIES, 10)) == 3
