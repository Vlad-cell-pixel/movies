"""Тести маршрутів Flask: без запуску сервера (test_client) і на окремій базі."""

import pytest

TOKEN = "test-token-123"
ADMIN = {"X-Admin-Token": TOKEN}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Порожня база і правильний токен на кожен тест."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    import app
    app.storage.init()
    app.app.config["TESTING"] = True
    return app.app.test_client()


def add(client, title="Матриця", year=1999, status="переглянуто", **extra):
    return client.post("/movies", json={"title": title, "year": year, "status": status, **extra})


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
    assert client.delete("/movies/1").status_code == 404     # публічного видалення немає


def test_admin_requires_token(client, monkeypatch):
    for headers in ({}, {"X-Admin-Token": "wrong"}):
        assert client.get("/admin/export", headers=headers).status_code == 403
        assert client.get("/admin/log", headers=headers).status_code == 403
        assert client.delete("/admin/movies/1", headers=headers).status_code == 403
    monkeypatch.delenv("ADMIN_TOKEN")                        # токен не налаштований: закрито для всіх
    assert client.get("/admin/export", headers={"X-Admin-Token": ""}).status_code == 403


def test_admin_delete_and_log(client):
    add(client)
    add(client, "Дюна", 2021, "заплановано")
    assert client.delete("/admin/movies/1", headers=ADMIN).status_code == 200
    assert client.delete("/admin/movies/1", headers=ADMIN).status_code == 404
    log = client.get("/admin/log?limit=10", headers=ADMIN).get_json()
    assert [(r["action"], r["movie_id"]) for r in log] == [("delete", 1), ("add", 2), ("add", 1)]
    assert len(client.get("/admin/log?limit=1", headers=ADMIN).get_json()) == 1
    assert client.get("/admin/log?limit=abc", headers=ADMIN).status_code == 400
    assert client.get("/admin/log?limit=0", headers=ADMIN).status_code == 400


def test_admin_import_all_or_nothing(client):
    r = client.post("/admin/import", headers=ADMIN, json=[
        {"title": "Матриця", "year": 1999, "status": "переглянуто", "rating": 10},
        {"title": "Дюна", "year": 2021, "status": "заплановано"}])
    assert r.status_code == 201 and r.get_json() == {"imported": 2}
    r = client.post("/admin/import", headers=ADMIN, json=[
        {"title": "Добрий", "year": 2000, "status": "переглянуто"},
        {"title": "Поганий", "year": "абв", "status": "переглянуто"}])
    assert r.status_code == 400
    assert len(client.get("/admin/export", headers=ADMIN).get_json()) == 2
