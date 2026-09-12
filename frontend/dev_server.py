"""Static frontend server with a same-origin development API proxy."""
import argparse
import http.client
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_ROOT = Path(__file__).resolve().parent
PAGE_PATHS = {"/", "/login", "/register", "/settings", "/story-schemes", "/gallery", "/generate"}
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "content-length", "server", "date",
}


class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, backend_url, **kwargs):
        self.backend = urlsplit(backend_url)
        super().__init__(*args, directory=str(PUBLIC_ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def is_backend_path(self):
        return urlsplit(self.path).path.startswith(("/api/", "/cycling/", "/tmp/"))

    def json_error(self, status, message):
        body = json.dumps({"error": message}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def proxy(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.json_error(400, "请求长度无效。")
        if length < 0 or length > 40 * 1024 * 1024:
            return self.json_error(413, "上传内容不能超过 40 MB。")
        if self.headers.get("Transfer-Encoding"):
            return self.json_error(400, "开发代理不接受分块上传。")
        # Forward only request data and session headers, never arbitrary proxy metadata.
        headers = {name: self.headers[name] for name in (
            "Content-Type", "Cookie", "X-CSRF-Token", "Accept"
        ) if name in self.headers}
        payload = self.rfile.read(length) if length else None
        connection_type = http.client.HTTPSConnection if self.backend.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(self.backend.hostname, self.backend.port, timeout=150)
        try:
            connection.request(self.command, self.path, body=payload, headers=headers)
            upstream = connection.getresponse()
            body = upstream.read()
        except (OSError, http.client.HTTPException):
            return self.json_error(502, "无法连接后端服务，请确认后端已启动。")
        finally:
            connection.close()
        self.send_response(upstream.status)
        for name, value in upstream.getheaders():
            if name.lower() not in HOP_HEADERS and name.lower() != "cache-control":
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def serve_frontend(self):
        if self.is_backend_path():
            return self.proxy()
        route = urlsplit(self.path).path
        if route in PAGE_PATHS:
            self.path = "/index.html"
        elif route.startswith(("/assets/", "/src/")):
            target = Path(self.translate_path(self.path)).resolve()
            allowed_root = PUBLIC_ROOT / route.split("/")[1]
            if not target.is_file() or not target.is_relative_to(allowed_root):
                return self.send_error(404)
        else:
            return self.send_error(404)
        if self.command == "HEAD":
            return super().do_HEAD()
        return super().do_GET()

    do_GET = serve_frontend
    do_HEAD = serve_frontend

    def mutate(self):
        if not self.is_backend_path():
            return self.json_error(404, "没有找到此接口。")
        return self.proxy()

    do_POST = mutate
    do_PUT = mutate
    do_PATCH = mutate
    do_DELETE = mutate


def create_server(host="127.0.0.1", port=5173, backend_url="http://127.0.0.1:8000"):
    parts = urlsplit(backend_url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.path not in ("", "/") or parts.query or parts.fragment or parts.username:
        raise ValueError("Backend URL must be an HTTP(S) origin without a path")
    return ThreadingHTTPServer((host, port), partial(FrontendHandler, backend_url=backend_url))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    server = create_server(port=args.port, backend_url=args.backend)
    print(f"Frontend: http://127.0.0.1:{server.server_port} -> {args.backend}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
