import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

from backend.app import create_app
from backend.accounts import initialize_accounts
from test_app import app, client, configure, fake_ai, image_upload, login, post, token, wait_story_task


def register(client, username="rider_one", password="cycling-test-pass"):
    client.get("/api/session")
    return post(client, "/api/register", json_data={
        "username": username, "password": password, "confirm_password": password,
    })


def test_register_login_and_password_hash(app, client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["username"] == "rider_one"
    assert response.get_json()["is_admin"] is False
    with sqlite3.connect(app.config["DATABASE"]) as db:
        hashed = db.execute("SELECT password_hash FROM users WHERE username = 'rider_one'").fetchone()[0]
    assert hashed != "cycling-test-pass"
    assert check_password_hash(hashed, "cycling-test-pass")
    previous = token(client)
    assert post(client, "/api/logout").status_code == 200
    assert token(client) != previous
    assert post(client, "/api/login", json_data={"username": "rider_one", "password": "bad"}).status_code == 401
    assert post(client, "/api/login", json_data={"username": "rider_one", "password": "cycling-test-pass"}).status_code == 200


@pytest.mark.parametrize("name,password", [("root", "valid-pass"), ("ROOT", "valid-pass"), ("a", "valid-pass"), ("bad/name", "valid-pass"), ("valid_name", "short")])
def test_registration_rejects_invalid_credentials(client, name, password):
    assert register(client, name, password).status_code == 400


def test_registration_duplicate_and_csrf(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert client.post("/api/register", json={"username": "another", "password": "valid-pass"}).status_code == 400


def test_registration_does_not_accept_admin_role(client):
    client.get("/api/session")
    response = post(client, "/api/register", json_data={
        "username": "rider_admin", "password": "cycling-test-pass", "confirm_password": "cycling-test-pass", "is_admin": True,
    })
    assert response.status_code == 201
    assert response.get_json()["is_admin"] is False
    assert post(client, "/api/register", json_data={"username": "another_user", "password": "cycling-test-pass", "confirm_password": "different"}).status_code == 400


def test_accounts_have_separate_journals_gallery_and_settings(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    root_story = post(client, "/api/generate", {"date": "2026-09-13", "styles": "poetic", "photos": image_upload()}).get_json()["record"]
    first = app.test_client()
    second = app.test_client()
    assert register(first).status_code == 201
    assert register(second, "rider_two").status_code == 201
    assert first.get("/api/rides").get_json()["items"] == []
    assert not first.get("/api/config").get_json()["has_key"]
    for rider in (first, second):
        assert post(rider, "/api/config", {"base_url": "https://ai.example/v1", "api_key": "isolated-test-key"}).status_code == 200
    saved = post(first, "/api/journals", {"date": "2026-09-13", "text": "第一位骑行者", "photos": image_upload()})
    group = saved.get_json()["journal"]["groups"][0]
    assert second.get("/api/journals/2026-09-13").get_json()["journal"]["groups"] == []
    assert second.delete("/api/journals/2026-09-13/group/" + group["id"], headers={"X-CSRF-Token": token(second)}).status_code == 404
    assert second.get("/tmp/" + group["photos"][0]).status_code == 404
    assert second.get("/tmp/thumbs/" + group["photos"][0] + ".jpg").status_code == 404
    assert post(second, "/api/generate", {"date": "2026-09-13", "styles": "poetic", "retained_photos": group["photos"]}).status_code == 400
    first_story = post(first, "/api/generate", {"date": "2026-09-13", "styles": "poetic"}).get_json()["record"]
    assert second.get("/api/rides/2026-09-13").status_code == 404
    second_story = post(second, "/api/generate", {"date": "2026-09-13", "styles": "poetic"}).get_json()["record"]
    assert first.get("/api/rides").get_json()["items"][0]["filename"] == first_story["filename"]
    assert second.get("/api/rides").get_json()["items"][0]["filename"] == second_story["filename"]
    assert len(client.get("/api/rides").get_json()["items"]) == 3
    assert len({root_story["filename"], first_story["filename"], second_story["filename"]}) == 3
    for record in (root_story, first_story, second_story):
        assert Path(app.config["OUTPUT_DIR"], record["filename"]).is_file()
        for photo in record["photos"]:
            assert Path(app.config["PHOTO_DIR"], photo).is_file()


def test_background_tasks_keep_their_account_on_same_date(app, client, monkeypatch):
    login(client)
    first, second = app.test_client(), app.test_client()
    release = threading.Event()

    def segment(config, data, text, *args):
        assert release.wait(5)
        return text

    monkeypatch.setattr("backend.app.generate_segment_copy", segment)
    monkeypatch.setattr("backend.app.generate_copy", lambda *args: ("故事", [{"style": "poetic", "text": "测试故事"}]))
    tasks = []
    try:
        for rider, name in ((first, "first_rider"), (second, "second_rider")):
            assert register(rider, name).status_code == 201
            post(rider, "/api/config", {"base_url": "https://ai.example/v1", "api_key": "test-only"})
            for text in (name + "出发", name + "归来"):
                post(rider, "/api/journals", {"date": "2026-09-13", "text": text})
            result = post(rider, "/api/generate", {"date": "2026-09-13", "styles": "poetic"})
            assert result.status_code == 200
            tasks.append(result.get_json()["task"]["task_id"])
        assert second.get("/api/story-tasks/" + tasks[0]).status_code == 404
        assert first.get("/api/story-tasks/" + tasks[1]).status_code == 404
        assert client.get("/api/story-tasks/" + tasks[0]).status_code == 200
    finally:
        release.set()
    for rider, task_id, name in ((first, tasks[0], "first_rider"), (second, tasks[1], "second_rider")):
        assert wait_story_task(rider, task_id)["status"] == "done"
        record = rider.get("/api/result?date=2026-09-13").get_json()["record"]
        assert all(segment["text"].startswith(name) for segment in record["story_segments"])
        assert rider.get("/api/journals/2026-09-13").get_json()["journal"]["groups"] == []
        assert len(rider.get("/api/rides").get_json()["items"]) == 1
    assert len(client.get("/api/rides").get_json()["items"]) == 2


def test_old_database_is_preserved_and_assigned_to_root(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    record = {"date": "2026-09-12", "photos": [], "entries": [{"style": "poetic", "text": "旧故事"}], "styles": ["poetic"], "title": "旧故事"}
    journal = {"date": record["date"], "groups": [{"id": "legacy", "text": "旧手记", "photos": []}]}
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE rides (date TEXT PRIMARY KEY, payload TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE ride_journals (date TEXT PRIMARY KEY, payload TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE ai_config (id INTEGER PRIMARY KEY, base_url TEXT, api_key TEXT, model TEXT);
        """)
        db.execute("INSERT INTO rides (date,payload) VALUES (?,?)", (record["date"], json.dumps(record)))
        db.execute("INSERT INTO ride_journals (date,payload) VALUES (?,?)", (record["date"], json.dumps(journal)))
    config = {"TESTING": True, "SECRET_KEY": "legacy-test", "DATABASE": str(database), "PHOTO_DIR": str(tmp_path / "photos"), "OUTPUT_DIR": str(tmp_path / "cycling"), "SESSION_COOKIE_SECURE": False}
    application = create_app(config)
    path = Path(config["OUTPUT_DIR"], "20260912.html")
    path.write_text("<title>旧故事</title>")
    root = application.test_client()
    login(root)
    assert root.get("/api/journals/2026-09-12").get_json()["journal"]["groups"] == journal["groups"]
    assert len(root.get("/api/rides").get_json()["items"]) == 1
    newcomer = application.test_client()
    assert register(newcomer).status_code == 201
    assert newcomer.get("/api/rides").get_json()["items"] == []
    post(root, "/api/journals", {"date": "2026-09-12", "text": "新增手记"})
    restarted = create_app(config).test_client()
    login(restarted)
    assert len(restarted.get("/api/journals/2026-09-12").get_json()["journal"]["groups"]) == 2
    assert path.read_text() == "<title>旧故事</title>"
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM rides").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2


def test_simultaneous_initialization_creates_one_administrator(tmp_path):
    database = tmp_path / "concurrent.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE rides (date TEXT PRIMARY KEY, payload TEXT, updated_at TEXT);
            CREATE TABLE ride_journals (date TEXT PRIMARY KEY, payload TEXT, updated_at TEXT);
            CREATE TABLE ai_config (id INTEGER PRIMARY KEY, base_url TEXT, api_key TEXT, model TEXT, story_schemes TEXT);
            CREATE TABLE story_records (filename TEXT PRIMARY KEY, payload TEXT);
            CREATE TABLE story_tasks (task_id TEXT PRIMARY KEY, date TEXT, status TEXT);
        """)
    barrier = threading.Barrier(2)

    def initialize():
        with sqlite3.connect(database) as db:
            barrier.wait(timeout=5)
            initialize_accounts(db, "root", "initialization-test")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(initialize) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0] == 1


def test_administrator_environment_password_change_takes_effect(app, client):
    login(client)
    changed = create_app({**dict(app.config), "PASSWORD": "rotated-test-password"}).test_client()
    changed.get("/api/session")
    assert post(changed, "/api/login", json_data={"username": "root", "password": "admin123"}).status_code == 401
    assert post(changed, "/api/login", json_data={"username": "root", "password": "rotated-test-password"}).status_code == 200


@pytest.mark.parametrize("base_url", ["http://127.0.0.1/v1", "http://10.0.0.1/v1", "http://169.254.169.254/v1", "http://[::1]/v1"])
def test_regular_account_cannot_configure_private_ai_address(client, base_url):
    assert register(client).status_code == 201
    assert post(client, "/api/config", {"base_url": base_url, "api_key": "test-only"}).status_code == 400
