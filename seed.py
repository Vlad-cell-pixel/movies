"""Заповнює базу прикладами фільмів з example.txt.

Запуск: python3 seed.py ЛОГІН   (фільми додаються цьому користувачу)
Формат example.txt той самий, що в лабораторній 6: назва;рік;статус;оцінка;дата
Кожен рядок проходить ту саму перевірку logic.make_record, що й POST /movies.
"""

import sys

import logic
import storage


def main():
    if len(sys.argv) < 2:
        print("використання: python3 seed.py ЛОГІН")
        return
    storage.init()
    user = storage.get_user_by_login(sys.argv[1])
    if user is None:
        print("немає користувача з логіном", repr(sys.argv[1]))
        return
    if len(storage.load(user["id"])) > 0:
        print("у цього користувача вже є фільми, нічого не додаю")
        return
    added = 0
    with open("example.txt", encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            parts = line.strip().split(";")
            if len(parts) != 5:
                continue
            try:
                movie = logic.make_record(*parts)
            except ValueError as error:
                print(f"рядок {number} пропущено: {error}")
                continue
            storage.add(movie, user["id"])
            added += 1
    print(f"додано фільмів: {added}")


if __name__ == "__main__":
    main()
