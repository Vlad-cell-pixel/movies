"""Логіка: перевірка, пошук і звіти по фільмах.

Тут немає ні print, ні input: функції лише обчислюють і ПОВЕРТАЮТЬ результат.
Друкує той, хто їх викликав (cli.py зараз, app.py у лабораторній 7).
"""

from datetime import date

STATUSES = ["переглянуто", "дивлюсь", "заплановано"]
MIN_YEAR = 1888  # рік першого фільму в історії


def make_record(title, year, status, rating="0", date_str=""):
    """Перевіряє введені дані й повертає словник-фільм.

    Усі аргументи можуть бути рядками (так вони приходять з терміналу).
    Якщо щось не так, кидає ValueError із зрозумілим повідомленням.
    Оцінка 0 означає «ще не оцінено».
    """
    title = title.strip()
    if title == "":
        raise ValueError("назва не може бути порожньою")
    if ";" in title:
        raise ValueError("у назві не можна використовувати символ ';'")

    try:
        year = int(year)
    except ValueError:
        raise ValueError(f"рік має бути цілим числом, а не '{year}'")
    this_year = date.today().year
    if year < MIN_YEAR or year > this_year + 5:
        raise ValueError(f"рік має бути від {MIN_YEAR} до {this_year + 5}")

    status = status.strip().lower()
    if status not in STATUSES:
        raise ValueError("статус має бути одним із: " + ", ".join(STATUSES))

    try:
        rating = int(rating)
    except ValueError:
        raise ValueError(f"оцінка має бути цілим числом від 0 до 10, а не '{rating}'")
    if rating < 0 or rating > 10:
        raise ValueError("оцінка має бути від 0 до 10 (0 = ще не оцінено)")

    if date_str == "":
        date_str = date.today().isoformat()
    else:
        try:
            date.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"дата має бути у форматі РРРР-ММ-ДД, а не '{date_str}'")

    return {"title": title, "year": year, "status": status,
            "rating": rating, "date": date_str}


def find(records, field, value):
    """Шукає фільми за полем.

    title  - частина назви, без урахування великих/малих літер
    status - точний статус
    year   - точний рік
    rating - оцінка не нижча за вказану
    Невідоме поле або неправильне значення -> ValueError.
    """
    if field == "title":
        needle = value.lower()
        return [r for r in records if needle in r["title"].lower()]
    if field == "status":
        return [r for r in records if r["status"] == value.lower()]
    if field == "year":
        try:
            year = int(value)
        except ValueError:
            raise ValueError(f"рік має бути числом, а не '{value}'")
        return [r for r in records if r["year"] == year]
    if field == "rating":
        try:
            minimum = int(value)
        except ValueError:
            raise ValueError(f"оцінка має бути числом, а не '{value}'")
        return [r for r in records if r["rating"] >= minimum]
    raise ValueError(f"невідоме поле '{field}'. Можна: title, status, year, rating")


def count_by_status(records):
    """Повертає словник {статус: кількість фільмів}."""
    counts = {}
    for r in records:
        status = r["status"]
        if status not in counts:
            counts[status] = 0
        counts[status] = counts[status] + 1
    return counts


def average_rating(records):
    """Середня оцінка серед оцінених фільмів (оцінка > 0).

    Якщо оцінених фільмів немає, повертає None (а не ділить на нуль).
    """
    rated = [r["rating"] for r in records if r["rating"] > 0]
    if len(rated) == 0:
        return None
    return round(sum(rated) / len(rated), 2)


def top_rated(records, n=3):
    """Повертає n фільмів з найвищою оцінкою (неоцінені не враховуються)."""
    rated = [r for r in records if r["rating"] > 0]
    rated.sort(key=lambda r: r["rating"], reverse=True)
    return rated[:n]
