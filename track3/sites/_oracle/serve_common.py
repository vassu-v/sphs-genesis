"""
serve_common.py — tiny shared static server so each dev site's serve.py
stays a handful of lines.

Each site calls `run(site_dir, port, task)`. This:
  - serves the site's own static files (its directory root),
  - serves GET /task.json from the `task` dict passed in (CONTRACTS §1),
  - serves GET /oracle.js by proxying sites/_oracle/oracle.js unmodified,
  - falls back to sites/dev/_common/ for shared assets (style.css,
    store.js) that a site does not have locally, so the six families and
    the master site can share one visual language without duplicating
    files everywhere.

Stdlib only.
"""
import http.server
import json
import socketserver
from pathlib import Path
from urllib.parse import urlparse

_MIME = {
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".html": "text/html",
}


def _guess_type(path: Path) -> str:
    return _MIME.get(path.suffix, "application/octet-stream")


def make_handler(site_dir: Path, task: dict, oracle_dir: Path, common_dir: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def _send_bytes(self, data: bytes, content_type: str, code=200):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            clean_path = urlparse(self.path).path

            if clean_path == "/task.json":
                self._send_bytes(
                    json.dumps(task).encode("utf-8"), "application/json"
                )
                return

            if clean_path == "/oracle.js":
                oracle_js = oracle_dir / "oracle.js"
                self._send_bytes(
                    oracle_js.read_bytes(), "application/javascript"
                )
                return

            # success_url_pattern is a clean path (/order/confirmed) with no
            # file extension; map it to confirmed.html in the site root.
            if clean_path.rstrip("/") == "/order/confirmed":
                confirmed = site_dir / "confirmed.html"
                if confirmed.exists():
                    self._send_bytes(confirmed.read_bytes(), "text/html")
                    return

            # Serve the file locally if the site has its own copy; else
            # fall back to the shared dev/_common/ assets.
            rel = clean_path.lstrip("/") or "index.html"
            local_path = site_dir / rel
            if not local_path.exists() or local_path.is_dir():
                common_path = common_dir / rel
                if common_path.exists() and common_path.is_file():
                    self._send_bytes(
                        common_path.read_bytes(), _guess_type(common_path)
                    )
                    return

            super().do_GET()

        def log_message(self, fmt, *args):  # quiet by default
            pass

    return Handler


def run(site_dir, port: int, task: dict, oracle_dir=None, common_dir=None):
    site_dir = Path(site_dir).resolve()
    # site_dir looks like .../track3/sites/dev/<family>  -> parent=dev, parent.parent=sites
    sites_dir = site_dir.parent.parent
    oracle_dir = Path(oracle_dir) if oracle_dir else sites_dir / "_oracle"
    common_dir = Path(common_dir) if common_dir else sites_dir / "dev" / "_common"

    handler = make_handler(site_dir, task, oracle_dir, common_dir)
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"[{task.get('site_id', site_dir.name)}] serving on http://127.0.0.1:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
