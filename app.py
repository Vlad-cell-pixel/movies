"""Вебсервіс списку фільмів на Flask.

Запуск:  python3 app.py   →   http://127.0.0.1:5000/movies

Маршрути:
    GET    /movies                 усі фільми (JSON)
    GET    /movies?status=...      фільтр за статусом (також title, year, rating)
    POST   /movies                 додати фільм (JSON у тілі запиту)
    GET    /report                 звіт

Адміністративні маршрути (потрібен заголовок X-Admin-Token, доступ лише через VPN):
    DELETE /admin/movies/<id>      видалити фільм за id
    GET    /admin/export           усі фільми одним списком (резервна копія)
    POST   /admin/import           додати багато фільмів зі списку JSON
"""

import os
import secrets

from flask import Flask, request, jsonify, abort
from flask_cors import CORS

import logic
import storage

app = Flask(__name__)
CORS(app, origins=["https://vhritsun.pp.ua"])
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
                   "GET /report"],
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


def movie_from_json(data):
    """Перевіряє один фільм з JSON і повертає словник. Помилка -> ValueError."""
    if not isinstance(data, dict):
        raise ValueError("очікується JSON-об'єкт")
    for field in ("title", "year", "status"):
        if field not in data:
            raise ValueError(f"немає поля {field}")
    for field, value in data.items():
        # null, true/false, списки і вкладені об'єкти не приймаємо
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"поле {field} має бути текстом або числом")
    return logic.make_record(
        str(data["title"]), str(data["year"]), str(data["status"]),
        str(data.get("rating", 0)), str(data.get("date", "")))


@app.post("/movies")
def add_movie():
    """Додає фільм. Очікує JSON: {"title", "year", "status", "rating"?, "date"?}."""
    data = request.get_json(silent=True)  # silent=True: None замість падіння
    if not isinstance(data, dict):
        return jsonify({"error": "очікується JSON-об'єкт у тілі запиту"}), 400
    try:
        movie = movie_from_json(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    movie["id"] = storage.add(movie)
    return jsonify(movie), 201


# ---------- Адміністративні маршрути ----------

def require_admin():
    """Пускає далі лише запит з правильним заголовком X-Admin-Token.

    Токен береться з оточення (файл .env на сервері), а не з коду.
    Якщо токен на сервері не налаштований, адмінка закрита для всіх.
    """
    expected = os.environ.get("ADMIN_TOKEN")
    given = request.headers.get("X-Admin-Token", "")
    if not expected or not secrets.compare_digest(given, expected):
        abort(403)


@app.delete("/admin/movies/<int:movie_id>")
def delete_movie(movie_id):
    """Видаляє фільм за id."""
    require_admin()
    if storage.delete(movie_id):
        return jsonify({"deleted": movie_id})
    return jsonify({"error": f"фільм з id {movie_id} не знайдено"}), 404


@app.get("/admin/export")
def export_movies():
    """Віддає всі фільми одним списком."""
    require_admin()
    return jsonify(storage.load())


@app.post("/admin/import")
def import_movies():
    """Додає список фільмів. Спершу перевіряє всі, і лише потім додає (все або нічого)."""
    require_admin()
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "очікується JSON-список фільмів"}), 400
    movies = []
    for number, item in enumerate(data, start=1):
        try:
            movies.append(movie_from_json(item))
        except ValueError as error:
            return jsonify({"error": f"фільм №{number}: {error}"}), 400
    for movie in movies:
        storage.add(movie)
    return jsonify({"imported": len(movies)}), 201


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


# Невідома адреса, заборонено або неправильний метод: теж JSON, а не HTML-сторінка.
@app.errorhandler(403)
def forbidden(error):
    return jsonify({"error": "доступ заборонено"}), 403


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "такої адреси немає"}), 404


@app.errorhandler(405)
def wrong_method(error):
    return jsonify({"error": "цей метод тут не підтримується"}), 405


if __name__ == "__main__":
    app.run(debug=True)
