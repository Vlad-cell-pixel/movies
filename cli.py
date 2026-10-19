"""Консольний інтерфейс списку фільмів.

Приклади:
    python3 cli.py add "Інтерстеллар" 2014 переглянуто 9
    python3 cli.py list
    python3 cli.py find status заплановано
    python3 cli.py report
"""

import sys

import logic
import storage

FILE = "data.txt"

USAGE = """використання:
  python3 cli.py add НАЗВА РІК СТАТУС [ОЦІНКА] [ДАТА]
  python3 cli.py list
  python3 cli.py find title|status|year|rating ЗНАЧЕННЯ
  python3 cli.py report

статуси: """ + ", ".join(logic.STATUSES) + """
оцінка: 0-10 (0 або нічого = ще не оцінено); дата: РРРР-ММ-ДД (нічого = сьогодні)
назву з пробілами беріть у лапки: "Втеча з Шоушенка\""""


def format_movie(r):
    """Один фільм у вигляді рядка таблиці."""
    rating = "-" if r["rating"] == 0 else f"{r['rating']}/10"
    return f"{r['title'][:30]:<30} {r['year']:>4}  {r['status']:<12} {rating:>5}  {r['date']}"


def print_table(records):
    if len(records) == 0:
        print("нічого не знайдено")
        return
    print(f"{'Назва':<30} {'Рік':>4}  {'Статус':<12} {'Оцінка':>5}  Дата")
    print("-" * 70)
    for r in records:
        print(format_movie(r))
    print(f"\nвсього: {len(records)}")


def cmd_add(args, records):
    if len(args) < 3:
        print("для add потрібні щонайменше НАЗВА, РІК і СТАТУС")
        print(USAGE)
        return
    title, year, status = args[0], args[1], args[2]
    rating = args[3] if len(args) > 3 else "0"
    date_str = args[4] if len(args) > 4 else ""
    try:
        movie = logic.make_record(title, year, status, rating, date_str)
    except ValueError as error:
        print("помилка:", error)
        return
    records.append(movie)
    storage.save(FILE, records)
    print("додано:", format_movie(movie))


def cmd_find(args, records):
    if len(args) < 2:
        print("для find потрібні ПОЛЕ і ЗНАЧЕННЯ, наприклад: find status переглянуто")
        return
    try:
        found = logic.find(records, args[0], args[1])
    except ValueError as error:
        print("помилка:", error)
        return
    print_table(found)


def cmd_report(records):
    if len(records) == 0:
        print("список порожній, додайте фільм командою add")
        return
    print(f"Усього фільмів: {len(records)}\n")

    print("За статусом:")
    for status, count in logic.count_by_status(records).items():
        print(f"  {status:<12} {count}")

    avg = logic.average_rating(records)
    print("\nСередня оцінка:", "ще немає оцінених фільмів" if avg is None else f"{avg}/10")

    top = logic.top_rated(records, 3)
    if top:
        print("\nНайкращі фільми:")
        for i, r in enumerate(top, start=1):
            print(f"  {i}. {r['title']} ({r['year']}) - {r['rating']}/10")


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return
    command = sys.argv[1]
    args = sys.argv[2:]
    records = storage.load(FILE)

    if command == "add":
        cmd_add(args, records)
    elif command == "list":
        print_table(records)
    elif command == "find":
        cmd_find(args, records)
    elif command == "report":
        cmd_report(records)
    else:
        print("невідома команда:", command)
        print(USAGE)


if __name__ == "__main__":
    main()
