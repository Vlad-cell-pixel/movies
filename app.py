"""Вебсервіс списку фільмів на Flask (з лабораторної 12 — з користувачами).

Запуск:  SECRET_KEY=будь-що python3 app.py   →   http://127.0.0.1:5000/

Перевірка для монітора:
    GET    /health                 {"status": "ok"} або 503, якщо база не відповідає

Вхід:
    POST   /register               {"login", "password"} → створити акаунт і увійти
    POST   /login                  {"login", "password"} → увійти (сервер ставить cookie сесії)
    POST   /logout                 вийти
    GET    /me                     хто я

Свої фільми (без входу → 401):
    GET    /movies                 свої фільми (JSON), фільтри ?status= ?title= ?year= ?rating=
    POST   /movies                 додати фільм
    DELETE /movies/<id>            видалити свій фільм (чужий → 404)
    GET    /report                 звіт
    GET    /report/statuses        звіт за статусами (JOIN)

Адміністратор (is_admin = 1 у базі, доступ лише через VPN):
    DELETE /admin/movies/<id>      видалити будь-який фільм
    GET    /admin/export           усі фільми всіх користувачів
    POST   /admin/import           додати багато фільмів собі
    GET    /admin/users            користувачі (без паролів)
    GET    /admin/log?limit=50     журнал дій
"""

import os
import sqlite3

from flask import Flask, request, jsonify, abort, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

import logic
import storage

app = Flask(__name__)
# supports_credentials=True: браузеру дозволено надсилати cookie сесії з сайту на API
CORS(app, origins=["https://vhritsun.pp.ua"], supports_credentials=True)
app.json.ensure_ascii = False  # щоб кирилиця в JSON була читабельною, а не \u0444...
app.json.mimetype = "application/json; charset=utf-8"

# Ключ, яким сервер підписує cookie сесії. Лежить у .env, НЕ в коді.
# Якщо його не задано, сервер навмисно не запуститься (KeyError) — це краще, ніж працювати без захисту.
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SESSION_COOKIE_SECURE"] = True        # cookie лише через https
app.config["SESSION_COOKIE_HTTPONLY"] = True      # JavaScript на сторінці не може прочитати cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"     # чужі сайти не можуть надсилати запити з вашим cookie
app.config["SESSION_COOKIE_DOMAIN"] = ".vhritsun.pp.ua"  # спільний для сайту і api.

storage.init()

# Хеш-«пустушка»: перевіряється, коли логіна не існує, щоб відповідь тривала стільки ж,
# скільки й для справжнього логіна (інакше за часом можна вгадати, які логіни є).
DUMMY_HASH = generate_password_hash("dummy-password")


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
        "routes": ["GET /health", "POST /register", "POST /login", "POST /logout", "GET /me",
                   "GET /movies", "POST /movies", "DELETE /movies/<id>",
                   "GET /report", "GET /report/statuses"],
    })


@app.get("/health")
def health():
    """Чи живий сервіс і чи відповідає база. Без входу і без даних: це опитує монітор."""
    try:
        conn = storage.connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "db_error"}), 503


# ---------- Користувачі і сесії ----------

def read_credentials():
    """Логін і пароль з JSON. Не рядки (null, числа) → порожні, далі їх відкине перевірка."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    login, password = data.get("login"), data.get("password")
    login = login.strip() if isinstance(login, str) else ""
    password = password if isinstance(password, str) else ""
    return login, password


@app.post("/register")
def register():
    """Реєстрація: {"login", "password"}. Пароль зберігається лише як хеш."""
    login, password = read_credentials()
    if len(login) < 3 or len(login) > 50 or len(password) < 8:
        return jsonify({"error": "логін від 3 до 50 символів, пароль від 8"}), 400
    try:
        user_id = storage.add_user(login, generate_password_hash(password))
    except sqlite3.IntegrityError:
        return jsonify({"error": "логін зайнятий"}), 409
    session.clear()
    session["user_id"] = user_id
    return jsonify({"id": user_id, "login": login}), 201


@app.post("/login")
def login():
    """Вхід: {"login", "password"}. Після успіху сервер «пам'ятає» користувача через cookie."""
    login, password = read_credentials()
    user = storage.get_user_by_login(login)
    if user is None:
        check_password_hash(DUMMY_HASH, password)  # та сама робота, що й для справжнього логіна
        return jsonify({"error": "неправильний логін або пароль"}), 401
    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "неправильний логін або пароль"}), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"id": user["id"], "login": user["login"]})


@app.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


def current_user():
    """Повертає користувача поточної сесії або зупиняє запит з 401."""
    user_id = session.get("user_id")
    if user_id is None:
        abort(401)
    user = storage.get_user(user_id)
    if user is None:          # користувача видалили, а cookie лишився
        session.clear()
        abort(401)
    return user


def require_admin():
    """Пускає далі лише користувача з is_admin = 1."""
    user = current_user()
    if not user["is_admin"]:
        abort(403)
    return user


@app.get("/me")
def me():
    """Хто я? Сторінка викликає це при відкритті, щоб знати, чи показувати форму входу."""
    user = current_user()
    return jsonify({"id": user["id"], "login": user["login"], "is_admin": bool(user["is_admin"])})


# ---------- Фільми поточного користувача ----------

@app.get("/movies")
def list_movies():
    """Свої фільми або відфільтровані через ?status= / ?title= / ?year= / ?rating=."""
    user = current_user()
    status = get_arg("status")  # None, якщо в адресі немає ?status=
    if status is not None and status.lower() not in logic.STATUSES:
        return jsonify({"error": "статус має бути одним із: " + ", ".join(logic.STATUSES)}), 400
    movies = storage.load(user["id"], status.lower() if status else None)

    for field in ("title", "year", "rating"):
        value = get_arg(field)
        if value is not None:
            try:
                movies = logic.find(movies, field, value)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
    return jsonify([m.to_dict() for m in movies])


def movie_from_json(data):
    """Перевіряє один фільм з JSON і повертає об'єкт Movie. Помилка -> ValueError."""
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
    """Додає фільм поточному користувачу. JSON: {"title", "year", "status", "rating"?, "date"?}."""
    user = current_user()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "очікується JSON-об'єкт у тілі запиту"}), 400
    try:
        movie = movie_from_json(data)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    movie.id = storage.add(movie, user["id"])
    return jsonify(movie.to_dict()), 201


@app.delete("/movies/<int:movie_id>")
def delete_own_movie(movie_id):
    """Видаляє СВІЙ фільм. Чужий або неіснуючий → 404 (не підтверджуємо, що він є)."""
    user = current_user()
    if storage.delete(movie_id, user["id"]):
        return jsonify({"deleted": movie_id})
    return jsonify({"error": f"фільм з id {movie_id} не знайдено"}), 404


@app.get("/report")
def report():
    """Звіт по своїх фільмах: кількість, статуси, середня оцінка, топ-3."""
    user = current_user()
    movies = storage.load(user["id"])
    return jsonify({
        "total": len(movies),
        "by_status": logic.count_by_status(movies),
        "average_rating": logic.average_rating(movies),
        "top_rated": [m.to_dict() for m in logic.top_rated(movies, 3)],
    })


@app.get("/report/statuses")
def report_statuses():
    """Звіт через JOIN: кількість своїх фільмів і середня оцінка для кожного статусу."""
    user = current_user()
    return jsonify(storage.status_report(user["id"]))


# ---------- Адміністративні маршрути (лише is_admin = 1, і ще nginx пускає лише з VPN) ----------

@app.delete("/admin/movies/<int:movie_id>")
def admin_delete_movie(movie_id):
    """Видаляє будь-який фільм за id."""
    admin = require_admin()
    if storage.admin_delete(movie_id, admin["id"]):
        return jsonify({"deleted": movie_id})
    return jsonify({"error": f"фільм з id {movie_id} не знайдено"}), 404


@app.get("/admin/export")
def export_movies():
    """Усі фільми всіх користувачів одним списком (з user_id власника)."""
    require_admin()
    return jsonify([{**m.to_dict(), "user_id": m.user_id} for m in storage.load_all()])


@app.post("/admin/import")
def import_movies():
    """Додає список фільмів адміністратору. Спершу перевіряє всі (все або нічого)."""
    admin = require_admin()
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
        storage.add(movie, admin["id"])
    return jsonify({"imported": len(movies)}), 201


@app.get("/admin/users")
def admin_users():
    """Список користувачів (без хешів паролів) і скільки в кого фільмів."""
    require_admin()
    return jsonify(storage.list_users())


@app.get("/admin/log")
def show_log():
    """Останні записи журналу дій. ?limit= від 1 до 500, за замовчуванням 50."""
    require_admin()
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({"error": "limit має бути числом"}), 400
    if limit < 1 or limit > 500:
        return jsonify({"error": "limit має бути від 1 до 500"}), 400
    return jsonify(storage.read_log(limit))


# Помилки теж JSON, а не HTML-сторінка.
@app.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "потрібно увійти"}), 401


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
