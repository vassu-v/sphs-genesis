"""
One JSONL telemetry writer shared by every adapter and the harness, so the dashboard
and bench runner (owned by other agents) can consume a single consistent event shape
regardless of which form factor produced it.

Default sink: track3/bench/telemetry/<run_id>.jsonl (created on first write). Override
with GUARD_TELEMETRY_DIR env var. One JSON object per line, append-only, flushed every
write so a crash never loses the tail (demo-resilience requirement in context.md §7).
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from pathlib import Path

_LOCK = threading.Lock()

_TRACK3_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _TRACK3_ROOT / "bench" / "telemetry"


def _telemetry_dir() -> Path:
    d = Path(os.environ.get("GUARD_TELEMETRY_DIR", str(_DEFAULT_DIR)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def emit(run_id: str, event: dict) -> None:
    """Append one telemetry event. `event` should already be JSON-serializable
    (plain dicts/lists/str/num/bool/None) -- callers use `verdict_to_event` or
    `to_jsonable` below to get there from dataclasses/enums."""
    record = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "run_id": run_id, **event}
    path = _telemetry_dir() / f"{run_id}.jsonl"
    line = json.dumps(record, default=str)
    with _LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def to_jsonable(obj):
    """Best-effort conversion of dataclasses/enums/nested structures to plain JSON.
    Prefers a `.to_dict()` method when present (guard.types objects all have one --
    that is the canonical CONTRACTS.md-shaped serialization) over generic
    dataclasses.asdict, which would also happily serialize guard's internal `extra`
    bookkeeping fields in whatever raw form they're in."""
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return to_jsonable(obj.to_dict())
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return to_jsonable(asdict(obj))
    if hasattr(obj, "value") and hasattr(obj, "name") and not isinstance(obj, (dict, list)):
        # Enum
        try:
            return obj.value
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


def verdict_event(run_id: str, source: str, action, verdict, extra: dict | None = None) -> dict:
    """Build (and emit) a standard 'guard_decision' telemetry record. `source` is one
    of 'mcp', 'playwright-shim', 'service', 'harness'. Returns the record for callers
    that also want to log/print it."""
    event = {
        "type": "guard_decision",
        "source": source,
        "action": to_jsonable(action),
        "verdict": to_jsonable(verdict),
    }
    if extra:
        event.update(to_jsonable(extra))
    emit(run_id, event)
    return event
