"""Вебсервіс списку фільмів на Flask.

Запуск:  python3 app.py   →   http://127.0.0.1:5000/movies

Маршрути:
    GET    /movies                 усі фільми (JSON)
    GET    /movies?status=...      фільтр за статусом (також title, year, rating)
    POST   /movies                 додати фільм (JSON у тілі запиту)
    DELETE /movies/<id>            видалити фільм за id
    GET    /report                 звіт
"""

from flask import Flask, request, jsonify

import logic
import storage

app = Flask(__name__)
app.json.ensure_ascii = False  # щоб кирилиця в JSON була читабельною, а не ф...
app.json.mimetype = "application/json; charset=utf-8"
storage.init()


def get_arg(name):
    """Читає параметр з адреси (?name=...).

    Якщо кирилицю в адресі не закодували (curl "...?status=дивлюсь"),
    тестовий сервер Flask отримує її «кракозябрами». Тут ми це виправляємо.
    Браузер і curl з --data-urlencode кодують адресу самі, тоді нічого не міняється.
    """
    value = request.args.get(name)
    if value is None:
        return None
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


@app.get("/")
def index():
    """Головна сторінка: коротка підказка, які є маршрути."""
    return jsonify({
        "service": "Фільми",
        "routes": ["GET /movies", "GET /movies?status=...", "POST /movies",
                   "DELETE /movies/<id>", "GET /report"],
    })


@app.get("/movies")
def list_movies():
    """Усі фільми або відфільтровані через ?status= / ?title= / ?year= / ?rating=."""
    status = get_arg("status")  # None, якщо в адресі немає ?status=
    if status is not None and status.lower() not in logic.STATUSES:
        return jsonify({"error": "статус має бути одним із: " + ", ".join(logic.STATUSES)}), 400
    movies = storage.load(status.lower() if status else None)

    # Інші фільтри робить logic.find, той самий, що й у лабораторній 6.
    for field in ("title", "year", "rating"):
        value = get_arg(field)
        if value is not None:
            try:
                movies = logic.find(movies, field, value)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
    return jsonify(movies)


@app.post("/movies")
def add_movie():
    """Додає фільм. Очікує JSON: {"title", "year", "status", "rating"?, "date"?}."""
    data = request.get_json(silent=True)  # silent=True: None замість падіння
    if not isinstance(data, dict):
        return jsonify({"error": "очікується JSON-об'єкт у тілі запиту"}), 400
    for field in ("title", "year", "status"):
        if field not in data:
            return jsonify({"error": f"немає поля {field}"}), 400
    for field, value in data.items():
        # null, true/false, списки і вкладені об'єкти не приймаємо
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return jsonify({"error": f"поле {field} має бути текстом або числом"}), 400
    try:
        movie = logic.make_record(
            str(data["title"]), str(data["year"]), str(data["status"]),
            str(data.get("rating", 0)), str(data.get("date", "")))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    movie["id"] = storage.add(movie)
    return jsonify(movie), 201


@app.delete("/movies/<int:movie_id>")
def delete_movie(movie_id):
    """Видаляє фільм за id."""
    if storage.delete(movie_id):
        return jsonify({"deleted": movie_id})
    return jsonify({"error": f"фільм з id {movie_id} не знайдено"}), 404


@app.get("/report")
def report():
    """Звіт: кількість, статуси, середня оцінка, топ-3."""
    movies = storage.load()
    return jsonify({
        "total": len(movies),
        "by_status": logic.count_by_status(movies),
        "average_rating": logic.average_rating(movies),
        "top_rated": logic.top_rated(movies, 3),
    })


# Невідома адреса або неправильний метод: теж JSON, а не HTML-сторінка.
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "такої адреси немає"}), 404


@app.errorhandler(405)
def wrong_method(error):
    return jsonify({"error": "цей метод тут не підтримується"}), 405


if __name__ == "__main__":
    app.run(debug=True)
