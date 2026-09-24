"""
harness/oracle_client.py -- thin client for sites/_oracle/server.py (CONTRACTS §3),
used by the CLI to score compromise events after a run. Stdlib-only (urllib), so
scoring never depends on whatever HTTP library happens to be installed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

ORACLE_URL = "http://127.0.0.1:8900"


def fetch_events(run_id: str, base_url: str = ORACLE_URL) -> list:
    """GET /oracle/events?run_id=... -> list of fired-trap events for this run.
    Returns [] (not an error) if the oracle server isn't running -- a harness run
    against a site with no oracle wired up, or during offline replay, shouldn't crash
    scoring just because there's nothing to report."""
    url = f"{base_url}/oracle/events?{urllib.parse.urlencode({'run_id': run_id})}"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("events", [])
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError):
        return []


def fetch_task(site_url: str) -> dict:
    """GET {site_origin}/task.json -- CONTRACTS §1."""
    origin = _origin(site_url)
    with urllib.request.urlopen(f"{origin}/task.json", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _origin(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}"
