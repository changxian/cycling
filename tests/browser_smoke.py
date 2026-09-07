"""Optional browser smoke test: python tests/browser_smoke.py (requires Playwright)."""

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


class FakeAI(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        content = request["messages"][1]["content"]
        prompt = json.loads(
            content[0]["text"] if isinstance(content, list) else content
        )
        result = {
            "title": "把山间的风，骑进今天",
            "entries": [
                {
                    "style": style["style"],
                    "text": "清晨出发，车轮碾过安静的山路。风拂过肩膀，远处的山脊渐渐清晰。\n\n有些快乐不需要目的地，只要一直向前，就能在每个转弯遇见新的风景。把这一程留给自己，也把今天好好收藏。",
                }
                for style in prompt["风格"]
            ],
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "choices": [
                        {"message": {"content": json.dumps(result, ensure_ascii=False)}}
                    ]
                }
            ).encode()
        )


def check_layout(page):
    page.wait_for_function(
        "!window.lucide || document.querySelectorAll('[data-lucide]:not(svg)').length === 0"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        "Horizontal overflow"
    )
    assert page.locator("img").evaluate_all(
        "images => images.every(img => img.complete && img.naturalWidth > 0)"
    ), "Broken image"


def main():
    artifacts = Path("test-results")
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "browser-test",
                "DATABASE": str(root / "db.sqlite3"),
                "OUTPUT_DIR": str(root / "cycling"),
                "PHOTO_DIR": str(root / "photos"),
            }
        )
        web = make_server("127.0.0.1", 0, app, threaded=True)
        provider = ThreadingHTTPServer(("127.0.0.1", 0), FakeAI)
        for server in (web, provider):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{web.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1024}, device_scale_factor=1
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin)
                page.screenshot(
                    path=str(artifacts / "login-desktop.png"), full_page=True
                )
                check_layout(page)
                page.locator('[name="username"]').fill("root")
                page.locator('[name="password"]').fill("admin123")
                page.get_by_role("button", name="登录", exact=True).click()
                page.wait_for_url(origin + "/")
                assert page.locator("#ride-form").get_attribute("action") == "/upload"
                check_layout(page)
                page.screenshot(
                    path=str(artifacts / "home-desktop.png"), full_page=True
                )
                page.get_by_role("button", name="生成骑行故事").click()
                assert "至少选择" in page.locator("#form-message").inner_text()
                page.locator('nav a[href="/settings"]').click()
                page.locator('[name="base_url"]').fill(
                    f"http://127.0.0.1:{provider.server_port}/v1"
                )
                page.locator('[name="api_key"]').fill("browser-fixture-key")
                page.get_by_role("button", name="保存配置").click()
                page.locator("#settings-message.success").wait_for()
                assert page.locator('[name="api_key"]').input_value() == ""
                check_layout(page)
                page.screenshot(
                    path=str(artifacts / "settings-desktop.png"), full_page=True
                )
                page.locator('nav a[href="/"]').click()
                page.locator('[name="date"]').fill("2026-09-07")
                page.locator('[name="distance"]').fill("56.4")
                page.locator('[name="duration"]').fill("02:30")
                page.locator('[name="elevation"]').fill("680")
                page.locator('[name="speed"]').fill("22.6")
                page.locator('[name="cadence"]').fill("82")
                page.locator('[name="heart_rate"]').fill("138")
                page.locator('[value="poetic"]').check()
                page.locator('[value="diary"]').check()
                page.locator("#photo-input").set_input_files("static/cycling.jpg")
                assert page.locator(".photo-preview").count() == 1
                page.locator(".remove-photo").click()
                assert page.locator(".photo-preview").count() == 0
                page.locator("#photo-input").set_input_files("static/cycling.jpg")
                page.get_by_role("button", name="生成骑行故事").click()
                page.wait_for_url("**/generate?date=2026-09-07")
                assert page.locator(".story-entry").count() == 2
                check_layout(page)
                page.screenshot(
                    path=str(artifacts / "result-desktop.png"), full_page=True
                )
                page.get_by_role("link", name="返回修改").click()
                assert page.locator('[name="distance"]').input_value() == "56.4"
                assert page.locator('[value="poetic"]').is_checked()
                assert page.locator('[name="retained_photos"]').count() == 1
                for width in (390, 320):
                    page.set_viewport_size({"width": width, "height": 844})
                    for route, label in (
                        ("/?edit=2026-09-07", "home"),
                        ("/settings", "settings"),
                        ("/generate?date=2026-09-07", "result"),
                        ("/gallery", "gallery"),
                        ("/cycling/20260907.html", "html"),
                    ):
                        page.goto(origin + route)
                        check_layout(page)
                        page.screenshot(
                            path=str(artifacts / f"{label}-{width}.png"), full_page=True
                        )
                page.set_viewport_size({"width": 1440, "height": 1024})
                page.goto(origin + "/gallery")
                assert page.locator(".gallery-item").count() == 1
                page.screenshot(
                    path=str(artifacts / "gallery-desktop.png"), full_page=True
                )
                page.get_by_role("button", name="退出登录").click()
                page.wait_for_url("**/login")
                page.set_viewport_size({"width": 390, "height": 844})
                check_layout(page)
                page.screenshot(
                    path=str(artifacts / "login-mobile.png"), full_page=True
                )
                page.goto(origin + "/cycling/20260907.html")
                assert page.url.endswith("/login")
                assert not errors, errors
                browser.close()
                print(
                    "Browser smoke passed: login, config, upload, generate, edit, gallery, logout; 1440/390/320 px; no JS errors, broken images, or horizontal overflow."
                )
        finally:
            web.shutdown()
            provider.shutdown()


if __name__ == "__main__":
    main()
