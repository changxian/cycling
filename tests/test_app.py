import base64
import io
import json
import re
import sqlite3
import time
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
    monkeypatch.setattr("backend.app.post_public", call)
    return call


def image_upload():
    stream = io.BytesIO()
    Image.new("RGB", (80, 60), (32, 120, 90)).save(stream, "PNG")
    stream.seek(0)
    return stream, "ride.png"


def test_upload_creates_small_thumbnail_and_preserves_original(app, client):
    login(client)
    stream = io.BytesIO()
    Image.effect_noise((2200, 1600), 100).convert("RGB").save(stream, "PNG")
    original = stream.getvalue()
    stream.seek(0)
    response = post(client, "/api/journals", {
        "date": "2026-09-12", "photos": (stream, "large.png"),
    })
    assert response.status_code == 200
    name = response.get_json()["journal"]["groups"][0]["photos"][0]
    thumbnail = Path(app.config["PHOTO_DIR"], "thumbs", name + ".jpg")
    assert thumbnail.exists()
    assert 0 < thumbnail.stat().st_size < 200_000
    assert Path(app.config["PHOTO_DIR"], name).read_bytes() == original
    assert client.get("/tmp/thumbs/" + name + ".jpg").data == thumbnail.read_bytes()
    assert client.get("/cycling/photos/" + name).data == original


def test_legacy_thumbnail_is_generated_on_request(app, client):
    name = "a" * 32 + ".png"
    stream, _ = image_upload()
    Path(app.config["PHOTO_DIR"], name).write_bytes(stream.getvalue())
    response = client.get("/cycling/photos/thumbs/" + name + ".jpg")
    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"
    assert len(response.data) < 200_000
    assert client.get("/cycling/photos/thumbs/" + "b" * 32 + ".png.jpg").status_code == 404
    assert client.get("/tmp/thumbs/" + name + ".jpg").status_code == 302
    thumbnail = Path(app.config["PHOTO_DIR"], "thumbs", name + ".jpg")
    modified = thumbnail.stat().st_mtime_ns
    assert client.get("/cycling/photos/thumbs/" + name + ".jpg").data == response.data
    assert thumbnail.stat().st_mtime_ns == modified


def test_legacy_story_uses_thumbnail_without_rewriting_archive(app, client):
    name = "a" * 32 + ".png"
    html = '<a href="/cycling/photos/' + name + '"><img src="/cycling/photos/' + name + '"></a>'
    path = Path(app.config["OUTPUT_DIR"], "20260912_2.html")
    path.write_text(html)
    response = client.get("/cycling/20260912_2.html")
    assert response.status_code == 200
    assert 'src="/cycling/photos/thumbs/' + name + '.jpg"' in response.get_data(as_text=True)
    assert 'href="/cycling/photos/' + name + '"' in response.get_data(as_text=True)
    assert path.read_text() == html


def test_thumbnail_preserves_orientation_and_transparency(app, client):
    login(client)
    stream = io.BytesIO()
    photo = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
    exif = Image.Exif()
    exif[274] = 6
    photo.save(stream, "PNG", exif=exif)
    stream.seek(0)
    response = post(client, "/api/journals", {"date": "2026-09-12", "photos": (stream, "transparent.png")})
    name = response.get_json()["journal"]["groups"][0]["photos"][0]
    with Image.open(Path(app.config["PHOTO_DIR"], "thumbs", name + ".jpg")) as thumbnail:
        assert thumbnail.size == (40, 80)
        assert thumbnail.getpixel((0, 0)) == (255, 255, 255)


def test_export_displays_thumbnail_with_original_link(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    response = post(client, "/api/generate", {"styles": "poetic", "photos": image_upload()})
    record = response.get_json()["record"]
    name = record["photos"][0]
    html = client.get(response.get_json()["html_url"]).get_data(as_text=True)
    assert 'src="/cycling/photos/thumbs/' + name + '.jpg"' in html
    assert 'href="/cycling/photos/' + name + '"' in html
    assert client.get("/api/rides").get_json()["items"][0]["thumbnail"] == "/tmp/thumbs/" + name + ".jpg"


@pytest.mark.parametrize(
    ("image_format", "filename", "expected_suffix"),
    [
        ("JPEG", "ride.jpg", ".jpg"),
        ("PNG", "ride.png", ".png"),
        ("WEBP", "ride.webp", ".webp"),
        ("HEIF", "iphone-photo.heic", ".jpg"),
    ],
)
def test_generate_accepts_common_and_iphone_photo_formats(
    app, client, monkeypatch, image_format, filename, expected_suffix
):
    """HEIF uploads are converted because browsers cannot reliably render them."""
    if image_format == "HEIF":
        pillow_heif = pytest.importorskip("pillow_heif")
        pillow_heif.register_heif_opener()
    stream = io.BytesIO()
    Image.new("RGB", (80, 60), (32, 120, 90)).save(stream, image_format)
    stream.seek(0)
    configure(client)
    fake_ai(monkeypatch)

    response = post(
        client,
        "/api/generate",
        {"styles": "poetic", "photos": (stream, filename)},
    )

    assert response.status_code == 200
    photo = response.get_json()["record"]["photos"][0]
    assert photo.endswith(expected_suffix)
    with Image.open(Path(app.config["PHOTO_DIR"], photo)) as saved:
        assert saved.format in {"JPEG", "PNG", "WEBP"}


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "P", "L", "I;16"])
@pytest.mark.parametrize("mime", ["image/png", "application/octet-stream"])
def test_journal_saves_uppercase_png_with_varied_pixel_modes(app, client, mode, mime):
    """实际 PNG 内容不应受大写后缀、透明度、位深或 MIME 声明影响。"""
    login(client)
    stream = io.BytesIO()
    Image.new(mode, (80, 60)).save(stream, "PNG")
    original = stream.getvalue()
    stream.seek(0)
    response = post(client, "/api/journals", {
        "date": "2026-09-12",
        "photos": (stream, "手机截屏.PNG", mime),
    })
    assert response.status_code == 200, response.get_json()
    groups = response.get_json()["journal"]["groups"]
    assert len(groups) == 1 and len(groups[0]["photos"]) == 1
    name = groups[0]["photos"][0]
    assert Path(app.config["PHOTO_DIR"], name).read_bytes() == original
    assert client.get("/tmp/" + name).mimetype == "image/png"
    assert get_journal_groups(client, "2026-09-12") == groups


def test_journal_converts_mpo_named_png_to_primary_jpeg(app, client):
    """手机多图像 JPEG 即使使用 PNG 后缀，也应保存可显示的主图。"""
    login(client)
    stream = io.BytesIO()
    Image.new("RGB", (80, 60), (240, 20, 20)).save(
        stream, "MPO", save_all=True,
        append_images=[Image.new("RGB", (80, 60), (20, 20, 240))],
    )
    stream.seek(0)
    response = post(client, "/api/journals", {
        "date": "2026-09-12",
        "photos": (stream, "IMG_8051.PNG", "image/png"),
    })
    assert response.status_code == 200, response.get_json()
    groups = response.get_json()["journal"]["groups"]
    name = groups[0]["photos"][0]
    assert name.endswith(".jpg")
    with Image.open(Path(app.config["PHOTO_DIR"], name)) as saved:
        assert saved.format == "JPEG"
        assert saved.size == (80, 60)
        red, green, blue = saved.getpixel((40, 30))
        assert red > 200 and green < 50 and blue < 50
    assert client.get("/tmp/" + name).mimetype == "image/jpeg"
    assert get_journal_groups(client, "2026-09-12") == groups


def fake_ai_segmented(monkeypatch, styles=("poetic",)):
    """fake_ai 的异步版：按 system 提示词区分「单段故事」与「最终故事」两种调用形态。

    每次 AI 调用都记录 {prompt, images, kind}；图片取 user 消息里的 image_url 数量，
    便于断言压缩后的图片体积。"""
    calls = []
    def call(endpoint, **kwargs):
        messages = kwargs["json"]["messages"]
        user = messages[1]["content"]
        if isinstance(user, list):
            images = [part for part in user[1:] if part.get("type") == "image_url"]
            payload = json.loads(user[0]["text"])
        else:
            images = []
            payload = json.loads(user)
        calls.append({"prompt": payload, "images": images, "segment": "故事文案正文" in messages[0]["content"]})
        if calls[-1]["segment"]:
            result = {"text": ["山风掠过车把，群山渐渐亮起。", "桥下流水映着夕阳。", "停在街角的小店，热茶暖了双手。"][sum(c["segment"] for c in calls) - 1]}
        else:
            result = {"title": "山风里的骑行", "entries": [
                {"style": style, "text": style + "：风从山间吹来。"} for style in styles
            ]}
        return Mock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": json.dumps(result)}}]},
        )
    monkeypatch.setattr("backend.app.requests.post", call)
    return calls


def wait_story_task(client, task_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = client.get("/api/story-tasks/" + task_id).get_json()["task"]
        if task["status"] in ("done", "failed"):
            return task
        time.sleep(0.05)
    raise AssertionError("story task did not finish: " + json.dumps(task, ensure_ascii=False))


def save_journal(client, date, text="", photos=None, edit_group_id=None):
    payload = {"date": date, "text": text, "background_music": "0"}
    if edit_group_id:
        payload["edit_group_id"] = edit_group_id
    if photos:
        payload["photos"] = [(stream, name, "image/png") for stream, name in photos]
    return client.post(
        "/api/journals",
        data=payload,
        headers={"X-CSRF-Token": token(client), "Accept": "application/json"},
    )


def get_journal_groups(client, date):
    return client.get(f"/api/journals/{date}").get_json()["journal"]["groups"]


def delete_client(client, path):
    return client.delete(path, headers={"X-CSRF-Token": token(client), "Accept": "application/json"})


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
        "api_key_masked": "priv********-key",
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
    with app.app_context():
        stored = sqlite3.connect(app.config["DATABASE"]).execute(
            "SELECT api_key FROM user_ai_config WHERE owner_id = 1"
        ).fetchone()[0]
    assert stored == "private-test-key"
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
    assert client.get("/tmp/" + record["photos"][0]).mimetype == "image/png"
    client.post("/api/logout", headers={"X-CSRF-Token": token(client)})
    assert client.get(result["html_url"]).status_code == 200
    assert client.get("/cycling/photos/" + record["photos"][0]).mimetype == "image/png"
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
        assert db.execute("SELECT COUNT(*) FROM user_rides").fetchone()[0] == 1
    assert "60" in Path(app.config["OUTPUT_DIR"], "20260907_2.html").read_text()


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
    references = ["第一人称，先写山路，再用平静的留白收尾。", "从抵达山顶的画面开始倒叙。"]
    for reference in references:
        assert post(client, "/api/story-schemes", {
            "style": "poetic", "scheme_text": reference,
        }).status_code == 200
    schemes = client.get("/api/story-schemes").get_json()["story_schemes"]
    assert [item["text"] for item in schemes["poetic"]] == references[::-1]
    call = fake_ai(monkeypatch, styles=("poetic", "funny"))
    assert post(client, "/api/generate", {"styles": ["poetic", "funny"]}).status_code == 200
    payload = json.loads(call.call_args.kwargs["json"]["messages"][1]["content"])
    assert payload["风格参考方案"]["poetic"] in references
    assert client.get("/api/config").get_json()["story_schemes"] == schemes


def test_ai_images_are_compressed_and_multiple_photos_render_as_story_cards(app, client, monkeypatch):
    configure(client)
    calls = fake_ai_segmented(monkeypatch)
    response = post(client, "/api/generate", {
        "date": "2026-09-08", "styles": "poetic",
        "photos": [image_upload(), image_upload()],
    })
    assert response.status_code == 200
    task = response.get_json()["task"]
    assert task["status"] == "running" and task["total"] == 3  # 两张图各一段 + 一段终稿
    finished = wait_story_task(client, task["task_id"])
    assert finished["status"] == "done" and finished["done"] == 3
    record = client.get("/api/rides/2026-09-08").get_json()["record"]
    assert [item["photo"] for item in record["story_segments"]] == record["photos"]
    # 两张照片各对应一段故事文案；每张图都以压缩后的 base64 传给 AI。
    segment_calls = [c for c in calls if c["segment"]]
    assert len(segment_calls) == 2 and [len(c["images"]) for c in segment_calls] == [1, 1]
    for image in [i for c in segment_calls for i in c["images"]]:
        assert len(base64.b64decode(image["image_url"]["url"].split(",", 1)[1])) < 1024 * 1024
    html = Path(app.config["OUTPUT_DIR"], "20260908.html").read_text()
    assert "story-segments" in html and "/cycling/photos/" in html
    # 多图场景照片并入故事卡片，不再单独渲染照片轮播区块（外层脚本仍引用 data-carousel 选择器，无元素时无副作用）。
    assert 'class="story-photos"' not in html and 'data-carousel"' not in html and 'story-slide' not in html


def test_exported_story_page_has_no_site_navigation(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-07"})
    html = Path(app.config["OUTPUT_DIR"], "20260907.html").read_text()
    assert "story-nav" not in html and "story-footer" not in html
    for label in ("时光画廊", "AI 配置", "回到首页", "所有时光"):
        assert label not in html


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
    assert not [path for path in Path(app.config["PHOTO_DIR"]).rglob("*") if path.is_file()]
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
    assert not [path for path in Path(app.config["PHOTO_DIR"]).rglob("*") if path.is_file()]


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
    for path in ["/", "/login", "/settings", "/story-schemes", "/gallery", "/generate", "/static/app.js"]:
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
    assert not [path for path in Path(app.config["PHOTO_DIR"]).rglob("*") if path.is_file()]


def test_journal_save_binds_text_and_photos_into_group(app, client):
    login(client)
    assert save_journal(client, "2026-09-07", "路上的一段话", [image_upload()]).status_code == 200
    groups = get_journal_groups(client, "2026-09-07")
    assert len(groups) == 1
    assert groups[0]["text"] == "路上的一段话"
    assert len(groups[0]["photos"]) == 1
    # A photos-only save becomes an empty-text group.
    assert save_journal(client, "2026-09-07", "", [image_upload()]).status_code == 200
    groups = get_journal_groups(client, "2026-09-07")
    assert len(groups) == 2
    assert groups[1]["text"] == "" and len(groups[1]["photos"]) == 1


def test_journal_neither_text_nor_photo_is_rejected(client):
    login(client)
    assert save_journal(client, "2026-09-07", "", []).status_code == 400


def test_delete_text_group_removes_its_photos(client):
    login(client)
    save_journal(client, "2026-09-07", "一段", [image_upload(), image_upload()])
    group = get_journal_groups(client, "2026-09-07")[0]
    assert len(group["photos"]) == 2
    assert delete_client(client, f"/api/journals/2026-09-07/group/{group['id']}").status_code == 200
    assert get_journal_groups(client, "2026-09-07") == []


def test_delete_single_photo_keeps_group_text(client):
    login(client)
    save_journal(client, "2026-09-07", "一段", [image_upload(), image_upload()])
    group = get_journal_groups(client, "2026-09-07")[0]
    remaining = group["photos"][1]
    assert delete_client(client, f"/api/journals/2026-09-07/photo/{group['id']}/{group['photos'][0]}").status_code == 200
    groups = get_journal_groups(client, "2026-09-07")
    assert len(groups) == 1
    assert groups[0]["text"] == "一段"
    assert groups[0]["photos"] == [remaining]


def test_delete_last_photo_keeps_text_when_not_confirmed(client):
    login(client)
    save_journal(client, "2026-09-07", "又一段", [image_upload()])
    group = get_journal_groups(client, "2026-09-07")[0]
    assert delete_client(client, f"/api/journals/2026-09-07/photo/{group['id']}/{group['photos'][0]}").status_code == 200
    groups = get_journal_groups(client, "2026-09-07")
    assert len(groups) == 1
    assert groups[0]["text"] == "又一段" and groups[0]["photos"] == []


def test_delete_group_confirmed_removes_last_photo_and_text(client):
    login(client)
    save_journal(client, "2026-09-07", "最后一张", [image_upload()])
    group = get_journal_groups(client, "2026-09-07")[0]
    assert delete_client(client, f"/api/journals/2026-09-07/group/{group['id']}").status_code == 200
    assert get_journal_groups(client, "2026-09-07") == []


def test_edit_group_updates_text_and_appends_photos(client):
    login(client)
    save_journal(client, "2026-09-07", "原文案", [image_upload()])
    group = get_journal_groups(client, "2026-09-07")[0]
    assert save_journal(client, "2026-09-07", "改后文案", [image_upload()], edit_group_id=group["id"]).status_code == 200
    groups = get_journal_groups(client, "2026-09-07")
    assert len(groups) == 1
    assert groups[0]["text"] == "改后文案"
    assert len(groups[0]["photos"]) == 2


def test_legacy_flat_journal_migrates_to_groups(app, client):
    login(client)
    import sqlite3
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute(
        "INSERT INTO user_journals (owner_id, date, payload) VALUES (1, ?, ?)",
        ("2026-09-09", json.dumps({"date": "2026-09-09", "texts": [{"id": "a1", "text": "旧文案"}], "photos": ["p1.png", "p2.png"], "background_music": True}, ensure_ascii=False)),
    )
    db.commit()
    groups = get_journal_groups(client, "2026-09-09")
    assert {"id": "a1", "text": "旧文案", "photos": []} in groups
    assert {"id": "legacy", "text": "", "photos": ["p1.png", "p2.png"]} in groups


def test_generate_uses_group_texts_and_photos(app, client, monkeypatch):
    configure(client)
    save_journal(client, "2026-09-10", "中途记录A", [image_upload()])
    save_journal(client, "2026-09-10", "中途记录B")
    calls = fake_ai_segmented(monkeypatch, styles=("poetic",))
    response = post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-10"})
    assert response.status_code == 200
    task = response.get_json()["task"]
    assert task["total"] == 3  # 记录A 带图一段 + 记录B 无图一段 + 终稿一段
    finished = wait_story_task(client, task["task_id"])
    assert finished["status"] == "done"
    record = client.get("/api/rides/2026-09-10").get_json()["record"]
    assert record["story_segments"][0]["photo"] in record["photos"]
    assert record["story_segments"][1]["photo"] is None  # 无图组没有图片
    # 每个组各自成段：组内文案出现在对应分段提示词里，终稿汇总全部分段。
    assert [c["prompt"]["本组记录"] for c in calls if c["segment"]] == ["中途记录A", "中途记录B"]
    # 终稿不再直接吃原始组文案，而是把各段小故事汇总进“途中随手记录”。
    final_prompt = [c["prompt"] for c in calls if not c["segment"]][0]
    assert final_prompt["途中随手记录"] == [item["text"] for item in record["story_segments"]]
    html = Path(app.config["OUTPUT_DIR"], "20260910.html").read_text()
    assert "story-segment--text-only" in html


def test_same_day_stories_keep_html_and_clear_consumed_journal(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch, title="第一程")
    saved = save_journal(client, "2026-09-12", "第一程文字", [image_upload()]).get_json()["journal"]
    first = post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"}).get_json()
    original = Path(app.config["OUTPUT_DIR"], "20260912.html").read_bytes()
    assert client.get("/api/journals/2026-09-12").get_json()["journal"]["groups"] == []
    fake_ai(monkeypatch, title="第二程")
    save_journal(client, "2026-09-12", "第二程文字")
    second = post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"}).get_json()
    assert second["html_url"] == "/cycling/20260912_2.html"
    assert Path(app.config["OUTPUT_DIR"], "20260912.html").read_bytes() == original
    assert second["record"]["photos"] == []
    assert second["record"]["journal_entries"] == ["第二程文字"]
    assert client.get(second["html_url"]).status_code == 200
    assert client.get("/api/result").get_json()["filename"] == "20260912_2.html"
    items = client.get("/api/rides").get_json()["items"]
    assert [item["title"] for item in items] == ["第二程", "第一程"]
    assert client.get("/api/meta").get_json()["count"] == 2
    assert Path(app.config["PHOTO_DIR"], saved["groups"][0]["photos"][0]).exists()


def test_async_story_clears_only_unchanged_consumed_groups(app, client, monkeypatch):
    import threading
    configure(client)
    fake_ai_segmented(monkeypatch)
    save_journal(client, "2026-09-12", "第一段")
    save_journal(client, "2026-09-12", "第二段")
    from backend import app as backend_module
    original = backend_module.generate_copy
    entered, resume = threading.Event(), threading.Event()

    def delayed(*args, **kwargs):
        entered.set()
        assert resume.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(backend_module, "generate_copy", delayed)
    task = post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"}).get_json()["task"]
    try:
        assert entered.wait(5)
        save_journal(client, "2026-09-12", "下一程")
    finally:
        resume.set()
    assert wait_story_task(client, task["task_id"])["status"] == "done"
    groups = client.get("/api/journals/2026-09-12").get_json()["journal"]["groups"]
    assert [group["text"] for group in groups] == ["下一程"]


def test_direct_upload_clears_carousel_after_first_story(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    result = post(client, "/api/generate", {
        "date": "2026-09-12", "styles": "poetic", "photos": image_upload(),
    })
    assert result.status_code == 200
    assert client.get("/api/journals/2026-09-12").get_json()["journal"]["groups"] == []


@pytest.mark.parametrize("segmented", [False, True])
def test_generation_failure_keeps_journal(app, client, monkeypatch, segmented):
    configure(client)
    save_journal(client, "2026-09-12", "保留的记录", [image_upload()])
    if segmented:
        save_journal(client, "2026-09-12", "另一段记录")
    before = client.get("/api/journals/2026-09-12").get_json()["journal"]
    monkeypatch.setattr("backend.app.requests.post", Mock(side_effect=requests.ConnectionError()))
    response = post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"})
    if segmented:
        assert wait_story_task(client, response.get_json()["task"]["task_id"])["status"] == "failed"
    else:
        assert response.status_code == 502
    assert client.get("/api/journals/2026-09-12").get_json()["journal"] == before


def test_ai_configs_use_priority_and_fallback(app, client, monkeypatch):
    configure(client)
    assert post(client, "/api/config", {"base_url": "https://ai.example/low", "api_key": "low-key", "priority": "2", "new_config": "1"}).status_code == 200
    configs = client.get("/api/config").get_json()["configs"]
    assert [item["priority"] for item in configs] == [1, 2]
    calls = []
    def generate(config, *args, **kwargs):
        calls.append(config["api_key"])
        if config["api_key"] == "private-test-key":
            raise RuntimeError("primary failed")
        return "回退故事", [{"style": "poetic", "text": "回退文案"}]
    monkeypatch.setattr("backend.app.generate_copy", generate)
    result = post(client, "/api/generate", {"date": "2026-09-14", "styles": "poetic"})
    assert result.status_code == 200
    assert calls == ["private-test-key", "low-key"]


def test_existing_html_is_reserved_and_restart_keeps_story_metadata(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch, title="新故事")
    output = Path(app.config["OUTPUT_DIR"])
    (output / "20260912.html").write_text("<title>旧故事</title>")
    result = post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"}).get_json()
    assert result["html_url"] == "/cycling/20260912_2.html"
    assert (output / "20260912.html").read_text() == "<title>旧故事</title>"
    restarted = create_app(dict(app.config)).test_client()
    login(restarted)
    items = restarted.get("/api/rides").get_json()["items"]
    assert [item["title"] for item in items] == ["新故事", "旧故事"]


def test_export_failure_keeps_journal_and_previous_story(app, client, monkeypatch):
    configure(client)
    fake_ai(monkeypatch)
    post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"})
    original = Path(app.config["OUTPUT_DIR"], "20260912.html").read_bytes()
    save_journal(client, "2026-09-12", "不能丢失的记录")
    before = client.get("/api/journals/2026-09-12").get_json()["journal"]
    monkeypatch.setattr("backend.app.os.replace", Mock(side_effect=OSError("模拟写入失败")))
    with pytest.raises(OSError, match="模拟写入失败"):
        post(client, "/api/generate", {"date": "2026-09-12", "styles": "poetic"})
    assert client.get("/api/journals/2026-09-12").get_json()["journal"] == before
    assert Path(app.config["OUTPUT_DIR"], "20260912.html").read_bytes() == original
    assert client.get("/api/meta").get_json()["count"] == 1


@pytest.mark.parametrize("body, rejected", [
    ("骑" * 45, False),
    ("骑" * 46, True),
    ("山风掠过车把，远处的群山渐渐亮起。", True),
    ("山风掠过车把，远处的群山慢慢亮起。", True),
    ("山风掠过车把！远处的群山渐渐亮起！", True),
    ("停在街角的小店，热茶让双手暖了起来。", False),
])
def test_segment_copy_limits_length_and_repetition(monkeypatch, tmp_path, body, rejected):
    from backend.app import METRICS, UserError, generate_segment_copy
    monkeypatch.setattr("backend.app.ai_chat", lambda *args: {"text": body})
    data = {"date": "2026-09-12", "styles": ["poetic"], **{m[0]: None for m in METRICS}}
    previous = ["山风掠过车把，远处的群山渐渐亮起。", "桥下流水映着夕阳。"]
    if rejected:
        with pytest.raises(UserError):
            generate_segment_copy({}, data, "", [], [], tmp_path, previous)
    else:
        assert generate_segment_copy({}, data, "", [], [], tmp_path, previous) == body


def test_segment_requests_include_all_previous_passages(app, client, monkeypatch):
    configure(client)
    for text in ["山路", "河边", "茶店"]:
        save_journal(client, "2026-09-12", text)
    calls = fake_ai_segmented(monkeypatch)
    response = post(client, "/api/generate", {"styles": "poetic", "date": "2026-09-12"})
    finished = wait_story_task(client, response.get_json()["task"]["task_id"])
    assert finished["status"] == "done"
    segments = client.get("/api/rides/2026-09-12").get_json()["record"]["story_segments"]
    segment_calls = [c for c in calls if c["segment"]]
    for index, call in enumerate(segment_calls):
        assert call["prompt"]["此前已生成文案"] == [s["text"] for s in segments[:index]]
