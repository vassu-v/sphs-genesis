"""
Oracle receiver — CONTRACTS.md §3.

Listens on 127.0.0.1:8900. Every mock site (dev and holdout) includes
oracle.js unmodified; when a trap actually fires, the browser POSTs an event
here and it is appended, one JSON object per line, to
track3/bench/oracle_log.jsonl.

Routes:
  POST /oracle/event            append one event line
  GET  /oracle/events?run_id=.. return events for a run (all events if
                                 run_id is omitted)
  POST /oracle/reset            truncate the log (fresh benchmark run)

No third-party dependencies — stdlib only, so this starts on a bare
Python 3.10 install.
"""
import datetime
import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 8900

# track3/sites/_oracle/server.py -> parents[0]=_oracle parents[1]=sites parents[2]=track3
TRACK3_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = TRACK3_ROOT / "bench"
LOG_PATH = BENCH_DIR / "oracle_log.jsonl"

_LOCK = threading.Lock()


class OracleHandler(BaseHTTPRequestHandler):
    server_version = "OracleReceiver/1.0"

    # -- helpers ---------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet by default
        pass

    # -- HTTP verbs --------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/oracle/event":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                event = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json({"ok": False, "error": "invalid json body"}, 400)
                return

            event.setdefault(
                "fired_at",
                datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            )

            BENCH_DIR.mkdir(parents=True, exist_ok=True)
            with _LOCK:
                with LOG_PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")

            self._json({"ok": True})
            return

        if parsed.path == "/oracle/reset":
            BENCH_DIR.mkdir(parents=True, exist_ok=True)
            with _LOCK:
                LOG_PATH.write_text("", encoding="utf-8")
            self._json({"ok": True})
            return

        self._json({"ok": False, "error": "not found"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/oracle/events":
            qs = parse_qs(parsed.query)
            run_id = (qs.get("run_id") or [None])[0]

            events = []
            if LOG_PATH.exists():
                with _LOCK:
                    text = LOG_PATH.read_text(encoding="utf-8")
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if run_id is None or obj.get("run_id") == run_id:
                        events.append(obj)

            self._json({"run_id": run_id, "count": len(events), "events": events})
            return

        if parsed.path in ("/", "/health"):
            self._json({"ok": True, "service": "oracle", "log": str(LOG_PATH)})
            return

        self._json({"ok": False, "error": "not found"}, 404)


def main():
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    with socketserver.ThreadingTCPServer((HOST, PORT), OracleHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"[oracle] listening on http://{HOST}:{PORT}  log={LOG_PATH}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
