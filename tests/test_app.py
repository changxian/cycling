import base64
import io
import json
import re
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from backend.app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "db.sqlite3"),
            "OUTPUT_DIR": str(tmp_path / "cycling"),
            "PHOTO_DIR": str(tmp_path / "photos"),
            "SESSION_COOKIE_SECURE": False,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def token(client):
    with client.session_transaction() as session:
        return session.get("csrf_token", "")


def login(client):
    bootstrap = client.get("/api/session").get_json()
    response = client.post(
        "/api/login",
        json={"username": "root", "password": "admin123"},
        headers={"X-CSRF-Token": bootstrap["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True
    assert response.get_json()["csrf_token"] != bootstrap["csrf_token"]


def post(client, path, data=None, json_data=None):
    return client.post(
        path,
        data=data,
        json=json_data,
        headers={"X-CSRF-Token": token(client), "Accept": "application/json"},
    )


def configure(client):
    login(client)
    assert (
        post(
            client,
            "/api/config",
            {"base_url": "https://ai.example/v1", "api_key": "private-test-key"},
        ).status_code
        == 200
    )


def fake_ai(monkeypatch, title="山风里的骑行", styles=("poetic",)):
    result = {
        "title": title,
        "entries": [
            {"style": s, "text": f"{s}：风从山间吹来。\n这一程，值得记住。"}
            for s in styles
        ],
    }
    call = Mock(
        return_value=Mock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": json.dumps(result)}}]},
        )
    )
    monkeypatch.setattr("backend.app.requests.post", call)
    return call


def image_upload():
    stream = io.BytesIO()
    Image.new("RGB", (80, 60), (32, 120, 90)).save(stream, "PNG")
    stream.seek(0)
    return stream, "ride.png"


def test_authentication_and_csrf(client):
    for path in [
        "/cycling/20260907.html",
    ]:
        assert client.get(path).status_code == 404
    assert client.get("/tmp/test.jpg").headers["Location"].endswith("/login")
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/auth/check").status_code == 401
    client.get("/api/session")
    assert (
        client.post(
            "/api/login", data={"username": "root", "password": "admin123"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/login",
            data={"username": "root", "password": "wrong", "csrf_token": token(client)},
        ).status_code
        == 401
    )
    login(client)
    assert client.get("/api/auth/check").status_code == 204
    assert client.post("/api/config", json={}).status_code == 400
    assert post(client, "/api/logout").get_json()["authenticated"] is False
    assert client.get("/api/config").status_code == 401


def test_settings_key_is_private_and_persistent(app, client):
    configure(client)
    config = client.get("/api/config").get_json()
    assert config == {
        "base_url": "https://ai.example/v1",
        "model": "gpt-4o",
        "has_key": True,
        "story_schemes": {},
    }
    assert b"private-test-key" not in client.get("/api/config").data
    assert (
        post(
            client,
            "/api/config",
            {
                "base_url": "https://ai.example/v1",
                "api_key": "",
                "model": "vision-model",
            },
        ).status_code
        == 200
    )
    assert (
        post(
            client,
            "/api/config",
            {"base_url": "https://other.example/v1", "api_key": ""},
        ).status_code
        == 400
    )
    restarted = create_app(
        {
            key: app.config[key]
            for key in ["DATABASE", "PHOTO_DIR", "OUTPUT_DIR", "SECRET_KEY", "TESTING"]
        }
    )
    other = restarted.test_client()
    login(other)
    assert other.get("/api/config").get_json()["model"] == "vision-model"


def test_generate_multiple_styles_with_vision_and_edit(app, client, monkeypatch):
    configure(client)
    call = fake_ai(monkeypatch, styles=("poetic", "funny"))
    response = post(
        client,
        "/api/generate",
        {
            "date": "2026-09-07",
            "distance": "56.4",
            "duration": "02:30",
            "styles": ["poetic", "funny"],
            "photos": image_upload(),
        },
    )
    assert response.status_code == 200
    result = response.get_json()
    record = result["record"]
    assert len(record["entries"]) == 2 and len(record["photos"]) == 1
    content = call.call_args.kwargs["json"]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert call.call_args.args[0] == "https://ai.example/v1/chat/completions"
    assert call.call_args.kwargs["allow_redirects"] is False
    html = Path(app.config["OUTPUT_DIR"], "20260907.html").read_text()
    assert "56.4" in html and "趣味搞笑" in html and "<style>" in html
    assert "private-test-key" not in html
    assert client.get("/api/result").get_json()["record"] == record
    edit = client.get("/api/rides/2026-09-07").get_json()["record"]
    assert edit["distance"] == "56.4" and edit["photos"] == record["photos"]
    assert client.get(result["html_url"]).status_code == 200
    assert client.get("/tmp/" + record["photos"][0]).mimetype == "image/jpeg"
    client.post("/api/logout", headers={"X-CSRF-Token": token(client)})
    assert client.get(result["html_url"]).status_code == 200
    assert client.get("/cycling/photos/" + record["photos"][0]).mimetype == "image/jpeg"
    assert client.get("/tmp/" + record["photos"][0]).status_code == 302
    login(client)
    fake_ai(monkeypatch)
    updated = post(
        client,
        "/api/generate",
        json_data={
            "date": "2026-09-07",
            "edit_date": "2026-09-07",
            "retained_photos": record["photos"],
            "styles": ["poetic"],
            "distance": "60",
        },
    )
    assert updated.status_code == 200
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM rides").fetchone()[0] == 1
    assert "60" in Path(app.config["OUTPUT_DIR"], "20260907.html").read_text()


def test_optional_fields_and_text_only_request(app, client, monkeypatch):
    configure(client)
    call = fake_ai(monkeypatch)
    response = post(client, "/api/generate", json_data={"styles": ["poetic"]})
    assert response.status_code == 200
    assert isinstance(call.call_args.kwargs["json"]["messages"][1]["content"], str)
    assert response.get_json()["record"]["photos"] == []
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", response.get_json()["record"]["date"])


def test_story_schemes_are_saved_and_added_to_matching_ai_prompt(client, monkeypatch):
    configure(client)
    reference = "第一人称，先写山路，再用平静的留白收尾。"
    assert post(client, "/api/config", {
        "base_url": "https://ai.example/v1", "api_key": "", "model": "gpt-4o",
        "story_scheme_poetic": reference,
    }).status_code == 200
    call = fake_ai(monkeypatch, styles=("poetic", "funny"))
    assert post(client, "/api/generate", {"styles": ["poetic", "funny"]}).status_code == 200
    payload = json.loads(call.call_args.kwargs["json"]["messages"][1]["content"])
    assert payload["风格参考方案"] == {"poetic": reference}
    assert client.get("/api/config").get_json()["story_schemes"] == {"poetic": reference}


def test_ai_images_are_compressed_and_multiple_exported_photos_rotate(app, client, monkeypatch):
    configure(client)
    call = fake_ai(monkeypatch)
    response = post(client, "/api/generate", {
        "date": "2026-09-08", "styles": "poetic",
        "photos": [image_upload(), image_upload()],
    })
    assert response.status_code == 200
    content = call.call_args.kwargs["json"]["messages"][1]["content"]
    for part in content[1:]:
        assert len(base64.b64decode(part["image_url"]["url"].split(",", 1)[1])) < 1024 * 1024
    html = Path(app.config["OUTPUT_DIR"], "20260908.html").read_text()
    assert "data-carousel" in html and "/cycling/photos/" in html


@pytest.mark.parametrize(
    "fields",
    [
        {"styles": []},
        {"styles": ["unknown"]},
        {"styles": "poetic"},
        {"distance": "-1"},
        {"speed": "NaN"},
        {"elevation": "inf"},
        {"duration": "02:78"},
        {"date": "2026-02-30"},
        {"heart_rate": "invalid"},
        {"retained_photos": ["../../secret"]},
    ],
)
def test_invalid_inputs_never_call_ai(client, monkeypatch, fields):
    configure(client)
    call = fake_ai(monkeypatch)
    assert (
        post(
            client, "/api/generate", json_data={"styles": ["poetic"], **fields}
        ).status_code
        == 400
    )
    call.assert_not_called()


def test_upload_validation_and_failed_generation_cleanup(app, client, monkeypatch):
    configure(client)
    call = fake_ai(monkeypatch)
    invalid = post(
        client,
        "/api/generate",
        {
            "styles": "poetic",
            "photos": (io.BytesIO(b"<script>bad</script>"), "fake.jpg"),
        },
    )
    assert invalid.status_code == 400
    call.assert_not_called()
    call.side_effect = requests.Timeout()
    failed = post(client, "/api/generate", {"styles": "poetic", "photos": image_upload()})
    assert failed.status_code == 504
    assert list(Path(app.config["PHOTO_DIR"]).iterdir()) == []
    assert list(Path(app.config["OUTPUT_DIR"]).iterdir()) == []


@pytest.mark.parametrize("status", [401, 429, 500, 302])
def test_provider_errors_are_readable_and_do_not_save(client, monkeypatch, status):
    configure(client)
    monkeypatch.setattr(
        "backend.app.requests.post", Mock(return_value=Mock(status_code=status))
    )
    response = post(client, "/api/generate", json_data={"styles": ["poetic"]})
    assert response.status_code == 502
    assert response.get_json()["error"]


def test_invalid_ai_json_preserves_previous_record(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    assert (
        post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-07"}).status_code
        == 200
    )
    previous = Path(app.config["OUTPUT_DIR"], "20260907.html").read_bytes()
    monkeypatch.setattr(
        "backend.app.requests.post",
        Mock(return_value=Mock(status_code=200, json=lambda: {"choices": []})),
    )
    assert (
        post(
            client,
            "/api/generate",
            {"styles": "poetic", "date": "2026-09-07", "photos": image_upload()},
        ).status_code
        == 502
    )
    assert Path(app.config["OUTPUT_DIR"], "20260907.html").read_bytes() == previous
    assert not list(Path(app.config["PHOTO_DIR"]).iterdir())


def test_gallery_scans_disk_and_orders_dates(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch, title="今天的骑行")
    post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-07"})
    output = Path(app.config["OUTPUT_DIR"])
    (output / "20260101.html").write_text("<title>旧年初的骑行</title>")
    (output / "20261201.html").write_text("<title>十二月的骑行</title>")
    (output / "20269999.html").write_text("<title>错误日期</title>")
    (output / "unrelated.html").write_text("<title>无关页面</title>")
    items = client.get("/api/rides").get_json()["items"]
    assert [item["title"] for item in items] == ["十二月的骑行", "今天的骑行", "旧年初的骑行"]


def test_ai_output_is_escaped(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch, title='<script>alert("x")</script>')
    post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-07"})
    html = Path(app.config["OUTPUT_DIR"], "20260907.html").read_text()
    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;" in html


def test_missing_configuration_and_protected_assets(client):
    login(client)
    assert (
        post(client, "/api/generate", json_data={"styles": ["poetic"]}).status_code
        == 400
    )
    assert client.get("/api/result").get_json() == {"record": None}
    assert client.get("/cycling/secret.key").status_code == 404
    assert client.get("/tmp/secret.key").status_code == 404
    assert client.get("/api/rides/missing").status_code == 404


def test_backend_only_serves_api_and_artifacts(client):
    login(client)
    for path in ["/", "/login", "/settings", "/gallery", "/generate", "/static/app.js"]:
        response = client.get(path)
        assert response.status_code == 404
        assert response.is_json
    meta = client.get("/api/meta").get_json()
    assert len(meta["styles"]) == 6 and len(meta["metrics"]) == 6
    assert meta["count"] == 0 and meta["configured"] is False


def test_api_returns_json_without_accept_header_and_protects_put(client):
    response = client.get("/api/rides")
    assert response.status_code == 401 and response.is_json
    login(client)
    assert client.put("/api/config", json={}).status_code == 400
    response = client.put("/api/config", json={"base_url": "https://ai.example/v1", "api_key": "secret"}, headers={"X-CSRF-Token": token(client)})
    assert response.status_code == 200
    assert response.get_json()["message"]


def test_logout_invalidates_session_and_rotates_csrf(client):
    login(client)
    old_token = token(client)
    response = post(client, "/api/logout")
    assert response.get_json()["csrf_token"] != old_token
    assert client.get("/api/meta").status_code == 401
    assert client.post("/api/login", json={"username": "root", "password": "admin123"}, headers={"X-CSRF-Token": old_token}).status_code == 400


def test_atomic_write_rollback(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-07"})
    previous = Path(app.config["OUTPUT_DIR"], "20260907.html").read_bytes()
    monkeypatch.setattr("backend.app.os.replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        post(
            client,
            "/api/generate",
            {"styles": "poetic", "date": "2026-09-07", "photos": image_upload()},
        )
    assert Path(app.config["OUTPUT_DIR"], "20260907.html").read_bytes() == previous
    assert not list(Path(app.config["OUTPUT_DIR"]).glob("*.tmp"))
    assert not list(Path(app.config["PHOTO_DIR"]).iterdir())
