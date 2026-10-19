"""Зберігання фільмів у текстовому файлі.

Формат файла: один фільм на рядок, поля через крапку з комою:
    назва;рік;статус;оцінка;дата
Приклад:
    Інтерстеллар;2014;переглянуто;9;2026-10-03

У лабораторній 7 цей файл буде замінено на SQLite, а logic.py і cli.py
майже не зміняться.
"""

import sys

import logic


def parse_line(line):
    """Перетворює рядок файла на словник. Якщо рядок пошкоджений, кидає ValueError."""
    parts = line.split(";")
    if len(parts) != 5:
        raise ValueError(f"очікувалось 5 полів, а знайдено {len(parts)}")
    # Ті самі перевірки, що й для команди add: рік, статус, оцінка, дата.
    return logic.make_record(parts[0], parts[1], parts[2], parts[3], parts[4])


def load(filename):
    """Повертає список словників з файла. Пошкоджені рядки пропускає."""
    records = []
    try:
        f = open(filename, "r", encoding="utf-8")
    except FileNotFoundError:
        return records  # файла ще немає: це нормально, просто порожній список

    with f:
        for number, line in enumerate(f, start=1):
            line = line.strip()
            if line == "":
                continue
            try:
                records.append(parse_line(line))
            except ValueError as error:
                # Пишемо у stderr (потік помилок), щоб не змішувати з корисним виводом.
                print(f"увага: рядок {number} пошкоджений і пропущений ({error}): {line}",
                      file=sys.stderr)
    return records


def save(filename, records):
    """Записує всі фільми у файл (повністю перезаписує його)."""
    with open(filename, "w", encoding="utf-8") as f:
        for r in records:
            f.write(f"{r['title']};{r['year']};{r['status']};{r['rating']};{r['date']}\n")
