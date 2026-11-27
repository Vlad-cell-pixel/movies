"""Тести маршрутів Flask: без запуску сервера (test_client) і на окремій базі.

Кожен test_client має свій «браузер» зі своїми cookie, тому два клієнти —
це два різні користувачі.
"""

import pytest

import storage

PASSWORD = "dovhyi-parol-123"


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """Порожня база на кожен тест. Cookie без домену і без https, бо тест іде на localhost."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import app
    app.storage.init()
    monkeypatch.setitem(app.app.config, "TESTING", True)
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_DOMAIN", None)
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)
    return app


def new_user(app_module, login):
    """Новий «браузер», зареєстрований і вже з сесією."""
    c = app_module.app.test_client()
    r = c.post("/register", json={"login": login, "password": PASSWORD})
    assert r.status_code == 201
    return c


@pytest.fixture
def client(app_module):
    return new_user(app_module, "vlad")


@pytest.fixture
def admin(app_module):
    c = new_user(app_module, "boss")
    conn = storage.connect()           # так само, як вручну через sqlite3 на сервері
    conn.execute("UPDATE users SET is_admin = 1 WHERE login = 'boss'")
    conn.commit()
    conn.close()
    return c


def add(client, title="Матриця", year=1999, status="переглянуто", **extra):
    return client.post("/movies", json={"title": title, "year": year, "status": status, **extra})


# ---------- реєстрація, вхід, вихід ----------

def test_cookie_settings_in_production():
    import app
    # у тестах ці значення підмінені фікстурою, тут перевіряємо справжні
    assert app.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_password_is_stored_as_hash(client):
    user = storage.get_user_by_login("vlad")
    assert user["password_hash"] != PASSWORD
    assert user["password_hash"].startswith(("scrypt:", "pbkdf2:"))   # назва алгоритму на початку


def test_register_validation(app_module, client):
    c = app_module.app.test_client()
    assert c.post("/register", json={"login": "vlad", "password": PASSWORD}).status_code == 409
    assert c.post("/register", json={"login": "ab", "password": PASSWORD}).status_code == 400
    assert c.post("/register", json={"login": "anna", "password": "1234567"}).status_code == 400
    assert c.post("/register", json={"login": None, "password": 12345678}).status_code == 400
    assert c.post("/register").status_code == 400


def test_login_logout(app_module, client):
    c = app_module.app.test_client()
    assert c.get("/me").status_code == 401
    r = c.post("/login", json={"login": "vlad", "password": PASSWORD})
    assert r.status_code == 200 and r.get_json()["login"] == "vlad"
    assert c.get("/me").get_json() == {"id": 1, "login": "vlad", "is_admin": False}
    assert c.post("/logout").status_code == 200
    assert c.get("/me").status_code == 401
    assert c.get("/movies").status_code == 401


def test_wrong_password_and_unknown_login_look_the_same(app_module, client):
    c = app_module.app.test_client()
    wrong = c.post("/login", json={"login": "vlad", "password": "nepravylnyi"})
    unknown = c.post("/login", json={"login": "nikoho", "password": "nepravylnyi"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()         # не підказуємо, які логіни існують
    assert c.get("/movies").status_code == 401


def test_without_session_everything_is_401(app_module):
    c = app_module.app.test_client()
    assert c.get("/movies").status_code == 401
    assert add(c).status_code == 401
    assert c.delete("/movies/1").status_code == 401
    assert c.get("/report").status_code == 401
    assert c.get("/report/statuses").status_code == 401
    assert c.get("/admin/log").status_code == 401


def test_forged_cookie_is_rejected(app_module):
    c = app_module.app.test_client()
    c.set_cookie("session", "eyJ1c2VyX2lkIjoxfQ.fake.signature")   # {"user_id":1} без справжнього підпису
    assert c.get("/movies").status_code == 401


# ---------- свої фільми ----------

def test_add_and_list(client):
    r = add(client, rating=10)
    assert r.status_code == 201 and r.get_json()["id"] == 1
    add(client, "Дюна", 2021, "заплановано")
    r = client.get("/movies")
    assert r.status_code == 200 and len(r.get_json()) == 2
    assert r.get_json()[0] == {"id": 1, "title": "Матриця", "year": 1999, "status": "переглянуто",
                               "rating": 10, "date": r.get_json()[0]["date"]}


def test_filters(client):
    add(client)
    add(client, "Дюна", 2021, "заплановано")
    assert len(client.get("/movies?status=заплановано").get_json()) == 1
    assert len(client.get("/movies?title=дюн").get_json()) == 1
    assert client.get("/movies?status=колись").status_code == 400
    assert client.get("/movies?year=давно").status_code == 400


@pytest.mark.parametrize("body", [
    None,                                                          # без тіла
    [1, 2],                                                        # не об'єкт
    {"title": "А"},                                                # немає полів
    {"title": "А", "year": "абв", "status": "переглянуто"},        # рік текстом
    {"title": "А", "year": 2000, "status": "переглянуто", "rating": 15},
    {"title": None, "year": 2000, "status": "переглянуто"},       # null
    {"title": "А", "year": True, "status": "переглянуто"},        # true замість числа
    {"title": "x'); DROP TABLE movies; --", "year": 2000, "status": "переглянуто"},
])
def test_add_rejects_bad_input(client, body):
    r = client.post("/movies", json=body) if body is not None else client.post("/movies")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_reports(client):
    add(client, rating=10)
    add(client, "Дюна", 2021, rating=8)
    add(client, "Олдбой", 2003, "заплановано")
    assert client.get("/report").get_json()["total"] == 3
    statuses = {r["status"]: r for r in client.get("/report/statuses").get_json()}
    assert statuses["переглянуто"]["count"] == 2
    assert statuses["переглянуто"]["average_rating"] == 9.0
    assert statuses["дивлюсь"]["count"] == 0


def test_unknown_address_and_method(client):
    assert client.get("/nema").status_code == 404
    assert client.put("/movies").status_code == 405


def test_users_do_not_see_each_other(app_module, client):
    add(client, rating=10)
    anna = new_user(app_module, "anna")
    add(anna, "Дюна", 2021, "заплановано")
    assert [m["title"] for m in client.get("/movies").get_json()] == ["Матриця"]
    assert [m["title"] for m in anna.get("/movies").get_json()] == ["Дюна"]
    assert anna.get("/report").get_json()["total"] == 1
    # чужий фільм (id 1) і неіснуючий (id 99) дають однакову відповідь 404
    assert anna.delete("/movies/1").status_code == 404
    assert anna.delete("/movies/99").status_code == 404
    assert len(client.get("/movies").get_json()) == 1     # фільм vlad на місці
    assert client.delete("/movies/1").status_code == 200   # а сам власник видалити може
    assert client.get("/movies").get_json() == []


# ---------- адміністратор ----------

def test_admin_routes_need_admin(client):
    for r in (client.get("/admin/export"), client.get("/admin/log"),
              client.get("/admin/users"), client.delete("/admin/movies/1"),
              client.post("/admin/import", json=[])):
        assert r.status_code == 403
    # старий заголовок з лабораторної 10 більше нічого не дає
    assert client.get("/admin/log", headers={"X-Admin-Token": "будь-що"}).status_code == 403


def test_admin_delete_and_log(client, admin):
    add(client)
    add(client, "Дюна", 2021, "заплановано")
    assert admin.get("/me").get_json()["is_admin"] is True
    assert admin.delete("/admin/movies/1").status_code == 200   # чужий фільм, але це адмін
    assert admin.delete("/admin/movies/1").status_code == 404
    log = admin.get("/admin/log?limit=3").get_json()
    assert [(r["action"], r["movie_id"], r["user_id"]) for r in log] == [
        ("admin_delete", 1, 2), ("add", 2, 1), ("add", 1, 1)]
    assert admin.get("/admin/log?limit=abc").status_code == 400
    assert admin.get("/admin/log?limit=0").status_code == 400
    users = admin.get("/admin/users").get_json()
    assert [(u["login"], u["movies"]) for u in users] == [("vlad", 1), ("boss", 0)]
    assert all("password_hash" not in u for u in users)


def test_admin_export_and_import(client, admin):
    add(client)
    r = admin.post("/admin/import", json=[
        {"title": "Дюна", "year": 2021, "status": "заплановано"},
        {"title": "Олдбой", "year": 2003, "status": "переглянуто", "rating": 9}])
    assert r.status_code == 201 and r.get_json() == {"imported": 2}
    r = admin.post("/admin/import", json=[
        {"title": "Добрий", "year": 2000, "status": "переглянуто"},
        {"title": "Поганий", "year": "абв", "status": "переглянуто"}])
    assert r.status_code == 400                                  # все або нічого
    exported = admin.get("/admin/export").get_json()
    assert [(m["title"], m["user_id"]) for m in exported] == [("Матриця", 1), ("Дюна", 2), ("Олдбой", 2)]
    assert len(client.get("/movies").get_json()) == 1            # імпорт пішов адміну, не vlad
