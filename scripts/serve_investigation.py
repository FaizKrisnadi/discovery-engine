"""Local read-only investigation server (127.0.0.1 only, GET only).

Usage: .venv/bin/python scripts/serve_investigation.py [port]
"""
from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.webapp import dispatch  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        status, ctype, body = dispatch("GET", u.path, parse_qs(u.query))
        data = body.encode() if isinstance(body, str) else body  # /raw returns bytes
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802  (interface is read-only by design)
        self.send_response(405)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"read-only interface: POST not allowed")

    def log_message(self, fmt, *args):  # quiet
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("127.0.0.1", port), Handler)  # localhost only, never 0.0.0.0
    print(f"read-only investigation interface at http://127.0.0.1:{port}/ (Ctrl-C to stop)")
    server.serve_forever()
