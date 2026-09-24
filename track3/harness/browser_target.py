"""
harness/browser_target.py -- one uniform interface the agent loop drives regardless of
benchmark arm, so dumb_agent.py / llm_agent.py never need to know whether the guard is
even present.

    target = make_target(page, arm="B", task=task_dict, run_id=run_id)
    target.goto(url)
    obs = target.read_page()          # {"snapshot": {...}, "guard_warnings": [...]}
    target.click(ref)                 # raises BlockedError on BLOCK (arm B/C only)
    target.current_url

Arm A (no guard) is a real, distinct code path -- NOT "guard with every check
disabled" -- because CONTRACTS §9 / context.md §3 requires Arm A to demonstrate what
an unprotected agent does (it should get compromised), and a guard object standing
between the agent and the page even in a permanently-ALLOW configuration would still
be recording telemetry and provenance that arm A is specifically supposed to lack.
_NoGuardTarget below talks to Playwright directly and shares only the snapshot
extractor (adapters/_shared/snapshot.py) with the guarded path, so the agent sees an
identically-shaped observation in every arm -- the only variable the benchmark is
supposed to isolate is whether the guard is in the loop.
"""
from __future__ import annotations

from adapters._shared.snapshot import extract_raw_sync, ref_selector
from adapters._shared.telemetry import to_jsonable, verdict_event
from adapters.playwright import GuardBlocked, wrap

BlockedError = GuardBlocked  # re-exported so harness callers don't import adapters.*


class _NoGuardTarget:
    """Arm A: talks to Playwright directly. No audit, no session, no refusals --
    exactly what an agent with no bodyguard would do."""

    def __init__(self, page, run_id: str):
        self._page = page
        self._run_id = run_id

    @property
    def current_url(self) -> str:
        return self._page.url

    def read_page(self) -> dict:
        raw = extract_raw_sync(self._page)
        self._record("read", raw)
        return {"snapshot": raw, "guard_warnings": []}

    def goto(self, url: str) -> dict:
        self._page.goto(url, wait_until="domcontentloaded")
        self._record("navigate", extract_raw_sync(self._page), url=url)
        return {"ok": True, "url": self._page.url}

    def click(self, ref: str) -> dict:
        el = self._page.query_selector(ref_selector(ref))
        if el is None:
            return {"ok": False, "error": f"ref {ref} not found"}
        el.click()
        self._record("click", extract_raw_sync(self._page), ref=ref)
        return {"ok": True, "clicked": ref}

    def type(self, ref: str, text: str) -> dict:
        el = self._page.query_selector(ref_selector(ref))
        if el is None:
            return {"ok": False, "error": f"ref {ref} not found"}
        el.fill(text)
        self._record("type", extract_raw_sync(self._page), ref=ref)
        return {"ok": True, "typed_into": ref}

    def submit(self, ref: str) -> dict:
        el = self._page.query_selector(ref_selector(ref))
        if el is None:
            return {"ok": False, "error": f"ref {ref} not found"}
        with self._page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
            el.evaluate("form => form.requestSubmit ? form.requestSubmit() : form.submit()")
        self._record("submit", extract_raw_sync(self._page), ref=ref)
        return {"ok": True, "submitted": ref, "url": self._page.url}

    def _record(self, action_type: str, raw_snapshot: dict, **action_extra) -> None:
        # A synthetic "ALLOW / layer NONE" verdict -- arm A has no guard, but the
        # trace format stays identical across arms so the dashboard/bench runner
        # doesn't need arm-specific parsing.
        fake_verdict = {
            "decision": "ALLOW", "layer": "NONE", "llm_used": False,
            "reasons": [], "rewritten_action": None, "elapsed_ms": 0.0, "llm_calls": 0,
        }
        action = {"type": action_type, **action_extra}
        verdict_event(self._run_id, "harness-armA", action, fake_verdict,
                       extra={"url": raw_snapshot.get("url")})

    def close(self) -> None:
        pass


class _GuardedTarget:
    """Arm B / C: thin pass-through onto adapters.playwright.GuardedPage, translating
    its GuardBlocked-raising surface into the same {"ok": ...} dict shape
    _NoGuardTarget returns, so the agent loop's error handling doesn't need to branch
    on which arm is active."""

    def __init__(self, page, task: dict, enable_l3: bool, run_id: str):
        self._guarded = wrap(page, task=task, enable_l3=enable_l3, run_id=run_id)

    @property
    def current_url(self) -> str:
        return self._guarded.url

    def read_page(self) -> dict:
        return self._guarded.read_page()

    def goto(self, url: str) -> dict:
        return self._guarded.guard_goto(url)

    def click(self, ref: str) -> dict:
        return self._guarded.guard_click(ref)

    def type(self, ref: str, text: str) -> dict:
        return self._guarded.guard_type(ref, text)

    def submit(self, ref: str) -> dict:
        return self._guarded.guard_submit(ref)

    def close(self) -> None:
        pass


def make_target(page, arm: str, task: dict, run_id: str):
    """arm: 'A' (no guard), 'B' (guard, enable_l3=False), 'C' (guard, enable_l3=True)."""
    arm = arm.upper()
    if arm == "A":
        return _NoGuardTarget(page, run_id)
    if arm in ("B", "C"):
        return _GuardedTarget(page, task, enable_l3=(arm == "C"), run_id=run_id)
    raise ValueError(f"unknown arm {arm!r} -- expected A, B, or C")
