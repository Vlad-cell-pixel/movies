"""Заповнює базу прикладами фільмів з example.txt.

Запуск: python3 seed.py
Формат example.txt той самий, що в лабораторній 6: назва;рік;статус;оцінка;дата
Кожен рядок проходить ту саму перевірку logic.make_record, що й POST /movies.
"""

import logic
import storage


def main():
    storage.init()
    if len(storage.load()) > 0:
        print("у базі вже є фільми, нічого не додаю (видаліть data.db, щоб почати з нуля)")
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
            storage.add(movie)
            added += 1
    print(f"додано фільмів: {added}")


if __name__ == "__main__":
    main()
