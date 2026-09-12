import secrets
import sys
from pathlib import Path
from unittest.mock import patch

from flask import send_from_directory
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import create_app


def main():
    directory = Path(sys.argv[1])
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    application = create_app({
        "TESTING": True, "SECRET_KEY": secrets.token_hex(32),
        "DATABASE": str(directory / "test.sqlite3"), "PHOTO_DIR": str(directory / "photos"),
        "OUTPUT_DIR": str(directory / "cycling"), "SESSION_COOKIE_SECURE": False,
        "USERNAME": "root", "PASSWORD": "browser-root-test",
    })

    @application.get("/")
    @application.get("/login")
    @application.get("/register")
    @application.get("/settings")
    @application.get("/gallery")
    def test_page():
        return send_from_directory(frontend, "index.html")

    @application.get("/src/<path:filename>")
    def test_script(filename):
        return send_from_directory(frontend / "src", filename)

    @application.get("/assets/<path:filename>")
    def test_asset(filename):
        return send_from_directory(frontend / "assets", filename)

    original_guard = application.before_request_funcs[None][0]

    def guard():
        from flask import request
        if request.endpoint not in {"test_page", "test_script", "test_asset"}:
            return original_guard()

    application.before_request_funcs[None][0] = guard
    with patch("backend.app.generate_copy", return_value=("浏览器测试故事", [{"style": "poetic", "text": "本地模拟故事"}])):
        server = make_server("127.0.0.1", 0, application, threaded=True)
        print(server.server_port, flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
