"""
service/app.py -- form factor C from context.md §2: POST /audit.

A thin FastAPI wrapper over guard.audit(), for harnesses that own their own browser
(any language -- they only need to speak HTTP/JSON) instead of using the MCP server or
the Playwright shim. Also the one form factor guard/'s CONTRACTS.md-native
`audit_dict()` function was clearly designed for: JSON in, JSON out, exactly this
request/response shape.

Endpoints:
    POST /audit     {snapshot, action, task, config?, session_id?} -> Verdict dict
    POST /observe   {session_id, snapshot, action, executed} -> {ok: true}
    GET  /healthz   liveness + which guard implementation is active

Why /observe exists (not in CONTRACTS.md, an adapter-level addition -- flagged in the
final report): guard.audit() is pure and stateless by design (CONTRACTS §8), but
guard.session.GuardSession gives precheck_optins provenance ("did the AGENT check this
box, or did the page arrive with it checked") ACROSS multiple audit() calls in one run.
A stateless HTTP endpoint can't infer "the harness actually executed the action I just
approved" on its own -- only the caller knows that, since the caller (not this service)
owns the browser and does the actual click/type/submit. So the caller is expected to
call /observe immediately after it executes whatever /audit ALLOWed or REWROTE, mirroring
exactly what adapters/mcp/server.py and adapters/playwright/shim.py do in-process. A
caller that never calls /observe still gets a fully correct L1/L3 result on every
/audit call -- it only loses the L1 precheck_optins "agent vs. page" distinction across
turns, which degrades to guard's page-wide pre-checked-box signal, not to silence.

Run:
    uvicorn service.app:app --host 127.0.0.1 --port 8990
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from adapters._shared import guard_client as gc
from adapters._shared.telemetry import emit, to_jsonable

app = FastAPI(title="AI Bodyguard audit service", version="1.0.0")

_sessions_lock = threading.Lock()
_sessions: dict = {}  # session_id -> GuardSession (real or stub)


def _get_or_create_session(session_id: Optional[str]):
    if not session_id:
        return None
    with _sessions_lock:
        if session_id not in _sessions:
            _sessions[session_id] = gc.make_session(session_id)
        return _sessions[session_id]


class AuditRequest(BaseModel):
    snapshot: dict = Field(..., description="PageSnapshot per CONTRACTS.md §5, raw JSON")
    action: dict = Field(..., description="Action per CONTRACTS.md §6")
    task: dict = Field(..., description="TaskDescriptor per CONTRACTS.md §1")
    config: dict = Field(default_factory=dict, description="{'enable_l3': bool, ...}")
    session_id: Optional[str] = Field(
        None, description="Opaque id scoping a GuardSession across calls in one run. "
                            "Omit for a stateless one-shot audit (fine for arm A/B smoke "
                            "checks; loses cross-turn precheck_optins provenance).",
    )
    run_id: Optional[str] = Field(None, description="Telemetry run id; defaults to session_id or 'service'.")


class ObserveRequest(BaseModel):
    session_id: str
    snapshot: dict
    action: dict
    executed: bool = True


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "guard_source": gc.GUARD_SOURCE, "active_sessions": len(_sessions)}


@app.post("/audit")
def audit(req: AuditRequest) -> dict:
    t0 = time.perf_counter()
    try:
        snapshot = gc.snapshot_from_raw(req.snapshot)
        action = gc.action_of(**{k: v for k, v in req.action.items() if k in ("type", "ref", "text", "url", "summary")})
        task = gc.task_from_raw(req.task)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"malformed request: {exc}") from exc

    session = _get_or_create_session(req.session_id)
    enable_l3 = bool(req.config.get("enable_l3", False))
    config = gc.make_config(enable_l3, session)

    verdict = gc.audit(snapshot, action, task, config, session=session)

    run_id = req.run_id or req.session_id or "service"
    emit(run_id, {
        "type": "guard_decision", "source": "service", "action": to_jsonable(action),
        "verdict": to_jsonable(verdict), "url": snapshot.url,
    })

    result = to_jsonable(verdict)
    result["_service_elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return result


@app.post("/observe")
def observe(req: ObserveRequest) -> dict:
    session = _get_or_create_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=400, detail="session_id required")
    try:
        snapshot = gc.snapshot_from_raw(req.snapshot)
        action = gc.action_of(**{k: v for k, v in req.action.items() if k in ("type", "ref", "text", "url", "summary")})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"malformed request: {exc}") from exc
    gc.observe(session, snapshot, action, executed=req.executed)
    return {"ok": True}


@app.delete("/session/{session_id}")
def drop_session(session_id: str) -> dict:
    with _sessions_lock:
        existed = _sessions.pop(session_id, None) is not None
    return {"ok": True, "existed": existed}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("GUARD_SERVICE_PORT", "8990")))
