"""
adapters/mcp/server.py -- THE PRIMARY DELIVERABLE (context.md §2).

An MCP stdio server exposing the browser tool surface an agent needs
(navigate, read_page, click, type, submit, finish) backed by Playwright, with the
AI Bodyguard wired in at both the ingress (read_page) and egress (every action tool)
seams. OpenCode / Antigravity CLI / anything else that speaks MCP gets the guard by
pointing at this process -- no code change on their side. See RESEARCH.md for the
config snippets and opencode.json / antigravity_mcp_config.json in this directory for
ready-to-paste examples.

Run directly for a smoke test:
    python -m adapters.mcp.smoketest [url]

Run as an actual MCP server (idles on stdio waiting for a client -- not a hang):
    python -m adapters.mcp.server

Environment:
    GUARD_ENABLE_L3   "1"/"true" to enable the L3 semantic layer (arm C). Default off
                       (arm B -- zero LLM calls, see adapters/_shared/guard_client.py).
    GUARD_RUN_ID       telemetry run id. Default "mcp-<pid>".
    GUARD_HEADLESS     "0" to run Chromium headed (useful while demoing). Default "1".
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make `adapters` importable when this file is launched directly by an MCP client
# (some clients spawn `python path/to/server.py` rather than `python -m ...`).
_TRACK3_ROOT = Path(__file__).resolve().parents[2]
if str(_TRACK3_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRACK3_ROOT))

try:
    # mcp >= 2.0: FastMCP was renamed MCPServer. See adapters/mcp/RESEARCH.md §3b --
    # every tutorial found during research still shows the old `fastmcp` import path,
    # which fails outright against the SDK actually installed (mcp 2.2.0).
    # https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver
    from mcp.server.mcpserver import MCPServer as _MCPServerImpl  # noqa: E402
except ImportError:
    from mcp.server.fastmcp import FastMCP as _MCPServerImpl  # type: ignore  # noqa: E402

from adapters._shared import guard_client as gc  # noqa: E402
from adapters._shared.snapshot import extract_raw_async, ref_selector  # noqa: E402
from adapters._shared.telemetry import emit, to_jsonable, verdict_event  # noqa: E402

mcp = _MCPServerImpl("ai-bodyguard-browser")

RUN_ID = os.environ.get("GUARD_RUN_ID", f"mcp-{os.getpid()}")
ENABLE_L3 = os.environ.get("GUARD_ENABLE_L3", "0").lower() in ("1", "true", "yes")
HEADLESS = os.environ.get("GUARD_HEADLESS", "1").lower() not in ("0", "false", "no")

_session = gc.make_session(RUN_ID)
_config = gc.make_config(ENABLE_L3, _session)

# All dev/holdout sites serve GET /task.json; refreshed on every navigate() to a new
# origin. Placeholder until the first navigate.
_task = gc.task_from_raw({
    "task_id": "unset", "site_id": "unset", "goal_text": "", "target_item": "",
    "base_price": 0, "currency": "INR", "success_url_pattern": "/order/confirmed",
})

_pw = None       # playwright context manager handle
_browser = None
_page = None


async def _ensure_browser():
    global _pw, _browser, _page
    if _page is not None:
        return _page
    from playwright.async_api import async_playwright
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(headless=HEADLESS)
    context = await _browser.new_context(viewport={"width": 1280, "height": 800})
    _page = await context.new_page()
    return _page


async def _maybe_refresh_task(url: str) -> None:
    """Best-effort GET /task.json on the current origin. Never raises -- a site under
    test that doesn't serve one just leaves `_task` as-is."""
    global _task
    try:
        from urllib.parse import urlparse
        import httpx
        origin = urlparse(url)
        task_url = f"{origin.scheme}://{origin.netloc}/task.json"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(task_url)
            if resp.status_code == 200:
                data = resp.json()
                prior_allowed = list(getattr(_task, "allowed_origins", []) or [])
                _task = gc.task_from_raw(data)
                for o in prior_allowed:
                    if o not in _task.allowed_origins:
                        _task.allowed_origins.append(o)
                emit(RUN_ID, {"type": "task_loaded", "task": data})
    except Exception as exc:  # noqa: BLE001
        emit(RUN_ID, {"type": "task_load_failed", "url": url, "error": str(exc)})


def _refusal(verdict, action_desc: str) -> dict:
    """Structured refusal handed back to the agent on BLOCK: enough for the agent to
    re-plan, not just a bare error string."""
    return {
        "ok": False,
        "blocked": True,
        "action": action_desc,
        "decision": verdict.decision,
        "layer": verdict.layer,
        "reasons": [
            {"check": r.check, "severity": str(r.severity), "message": r.message, "evidence": dict(r.evidence)}
            for r in verdict.reasons
        ],
        "hint": "This action was blocked by the AI Bodyguard. Re-read the page and "
                "choose a different action that still satisfies the task goal -- do "
                "not repeat the exact same action.",
    }


async def _guarded(action, execute_fn):
    """Shared egress path: snapshot -> audit -> ALLOW execute / BLOCK refuse /
    REWRITE execute-substitute-then-refuse-original. `execute_fn(action)` performs the
    actual Playwright side effect for a given guard Action and returns a result dict.
    On any action that actually executes, records it into the GuardSession so later
    precheck_optins checks know the agent (not the page) caused it."""
    page = await _ensure_browser()
    raw = await extract_raw_async(page)
    snapshot = gc.snapshot_from_raw(raw)
    verdict = gc.audit(snapshot, action, _task, _config, session=_session)
    verdict_event(RUN_ID, "mcp", action, verdict, extra={"url": snapshot.url})

    if verdict.decision == "BLOCK":
        return _refusal(verdict, action.type)

    if verdict.decision == "REWRITE" and verdict.rewritten_action is not None:
        sub_result = await execute_fn(verdict.rewritten_action)
        gc.observe(_session, snapshot, verdict.rewritten_action, executed=True)
        refusal = _refusal(verdict, action.type)
        refusal["rewritten_and_executed"] = {
            "type": verdict.rewritten_action.type,
            "ref": verdict.rewritten_action.ref,
        }
        refusal["hint"] = (
            "The original action was unsafe as given; the guard executed a safe "
            f"substitute ({verdict.rewritten_action.type} {verdict.rewritten_action.ref}) "
            "instead. Re-read the page, then retry your original intent if it still applies."
        )
        return refusal

    # ALLOW
    result = await execute_fn(action)
    gc.observe(_session, snapshot, action, executed=True)
    return result


def _trust_navigate_target(url: str) -> None:
    """guard/l2_policy.py's forbid_navigation_origin (a CONTRACTS-gap EXTENSION rule,
    not in CONTRACTS.md itself -- see final report) blocks any navigate() whose target
    origin isn't in task.allowed_origins or the CURRENT document origin. That is
    correct protection against a page tricking the agent into a click that navigates
    off-site, but it also blocks the very first navigate() of a run (blank page ->
    task origin, allowed set empty) and every deliberate navigate() the agent issues
    to a NEW origin it explicitly chose to type/paste. Unlike an on-page click that
    triggers navigation as a side effect (still fully guarded, since that goes through
    click()'s own action, not this tool), calling navigate(url) IS the agent's
    deliberate destination choice -- so the adapter treats every navigate() target as
    trusted going forward. This is an adapter-level bootstrap policy, not a change to
    guard/'s own rule."""
    from urllib.parse import urlparse
    origin_str = None
    try:
        p = urlparse(url)
        if p.scheme and p.netloc:
            origin_str = f"{p.scheme}://{p.netloc}"
    except ValueError:
        return
    if origin_str and origin_str not in _task.allowed_origins:
        _task.allowed_origins.append(origin_str)


@mcp.tool()
async def navigate(url: str) -> dict:
    """Navigate the browser to `url`. Also refreshes the task descriptor from
    GET /task.json on the new origin. Guard-audited: a page can try to redirect the
    agent to a hijacked-goal URL via a fake 'continue here' control (C2, CONTRACTS.md
    §2), and the navigate that would follow is itself subject to L1/L2/L3 same as any
    other action. See _trust_navigate_target for why navigate()'s own target origin is
    always allow-listed before the audit runs."""
    _trust_navigate_target(url)

    async def _do(a) -> dict:
        page = await _ensure_browser()
        await page.goto(a.url, wait_until="domcontentloaded")
        await _maybe_refresh_task(a.url)
        return {"ok": True, "url": page.url}

    return await _guarded(gc.action_of(type="navigate", url=url), _do)


@mcp.tool()
async def read_page() -> dict:
    """INGRESS GUARD. Extract a full PageSnapshot (CONTRACTS.md §5) and return it to
    the agent, plus any guard warnings raised against the page's own content (e.g.
    injection phrasing hidden in the DOM) even though `read` itself never mutates
    anything -- so the agent's context always carries a warning alongside attacker
    text rather than absorbing it silently."""
    page = await _ensure_browser()
    raw = await extract_raw_async(page)
    snapshot = gc.snapshot_from_raw(raw)
    action = gc.action_of(type="read")
    verdict = gc.audit(snapshot, action, _task, _config, session=_session)
    verdict_event(RUN_ID, "mcp", action, verdict, extra={"url": snapshot.url})

    return {
        "ok": True,
        "snapshot": to_jsonable(snapshot),
        "guard_warnings": [
            {"check": r.check, "severity": str(r.severity), "message": r.message}
            for r in verdict.reasons
        ],
    }


@mcp.tool()
async def click(ref: str) -> dict:
    """Click the element with this ref (from the last read_page snapshot). Subject to
    the flagship hit-test check: if something else is actually at the element's centre
    point, this is BLOCKed rather than executed."""

    async def _do(a) -> dict:
        page = await _ensure_browser()
        el = await page.query_selector(ref_selector(a.ref))
        if el is None:
            return {"ok": False, "error": f"ref {a.ref} not found -- call read_page again"}
        await el.click()
        return {"ok": True, "clicked": a.ref}

    return await _guarded(gc.action_of(type="click", ref=ref), _do)


@mcp.tool()
async def type_text(ref: str, text: str) -> dict:
    """Type `text` into the element with this ref. Named type_text (not `type`) to
    avoid shadowing the Python builtin / tool-name confusion; the guard Action's
    `type` field is still the string `"type"` per CONTRACTS.md §6."""

    async def _do(a) -> dict:
        page = await _ensure_browser()
        el = await page.query_selector(ref_selector(a.ref))
        if el is None:
            return {"ok": False, "error": f"ref {a.ref} not found -- call read_page again"}
        await el.fill(a.text)
        return {"ok": True, "typed_into": a.ref}

    return await _guarded(gc.action_of(type="type", ref=ref, text=text), _do)


@mcp.tool()
async def submit(ref: str) -> dict:
    """Submit the form with this ref. This is where cross-origin-form,
    undisclosed-amount, and pre-checked-optin checks bite hardest, since submit is the
    point of no return for a checkout flow."""

    async def _do(a) -> dict:
        page = await _ensure_browser()
        el = await page.query_selector(ref_selector(a.ref))
        if el is None:
            return {"ok": False, "error": f"ref {a.ref} not found -- call read_page again"}
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
            await el.evaluate("form => form.requestSubmit ? form.requestSubmit() : form.submit()")
        return {"ok": True, "submitted": a.ref, "url": page.url}

    return await _guarded(gc.action_of(type="submit", ref=ref), _do)


@mcp.tool()
async def finish(summary: str) -> dict:
    """Declare the task complete. Not guarded against page content (nothing left to
    execute), but IS recorded to telemetry with the final URL, so the bench runner can
    score task_success (URL matches success_url_pattern) and compromise events
    independent of what the agent claims in `summary`."""
    page = await _ensure_browser()
    final_url = page.url if page else None
    action = gc.action_of(type="finish", summary=summary)
    final_verdict = gc.audit(
        gc.snapshot_from_raw(await extract_raw_async(page)), action, _task, _config, session=_session,
    )
    verdict_event(RUN_ID, "mcp", action, final_verdict, extra={"final_url": final_url})
    return {"ok": True, "final_url": final_url, "summary": summary}


async def _shutdown():
    global _browser, _pw
    if _browser is not None:
        await _browser.close()
    if _pw is not None:
        await _pw.stop()


def main():
    emit(RUN_ID, {"type": "server_start", "guard_source": gc.GUARD_SOURCE, "enable_l3": ENABLE_L3})
    try:
        mcp.run(transport="stdio")
    finally:
        try:
            asyncio.run(_shutdown())
        except Exception:
            pass


if __name__ == "__main__":
    main()
