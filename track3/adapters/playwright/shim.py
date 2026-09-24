"""
adapters/playwright/shim.py -- form factor A from context.md §2: the in-process shim.

    from adapters.playwright import wrap
    page = wrap(page, task=my_task_dict)
    page.guard_goto(url)
    page.guard_click(ref)
    page.guard_type(ref, text)
    page.guard_submit(ref)
    page.read_page()

Everything else (`page.title()`, `page.screenshot()`, `page.mouse`, ...) passes through
untouched via `__getattr__`, so an existing Playwright harness only has to change the
handful of call sites that actually click/type/submit/navigate against
attacker-reachable content.

Naming note: real Playwright `Page.click()` takes a CSS selector, not a guard `ref`.
Shadowing it with an incompatible signature would silently break any passthrough code
that still calls `page.click(css_selector)` expecting vanilla Playwright behavior. So
guarded actions are named `guard_click` / `guard_type` / `guard_submit` / `guard_goto`
here, not `click`/`type`/`submit`/`goto` -- explicit, and safe to mix with direct
Playwright calls on the same wrapped object (though anything that touches the DOM
outside the guard obviously bypasses auditing; that's the harness author's call, not
this shim's to make for them).

Shares the ONE snapshot extractor with adapters/mcp/server.py via
adapters/_shared/snapshot.py, and the same guard_client bridge (real guard/ package,
with a GuardSession for precheck-optin provenance, falling back to a local stub) --
no duplicated extraction or audit-wiring logic between the two form factors.
"""
from __future__ import annotations

import os

from adapters._shared import guard_client as gc
from adapters._shared.snapshot import extract_raw_sync, ref_selector
from adapters._shared.telemetry import to_jsonable, verdict_event

_PLACEHOLDER_TASK = {
    "task_id": "unset", "site_id": "unset", "goal_text": "", "target_item": "",
    "base_price": 0, "currency": "INR", "success_url_pattern": "/order/confirmed",
}


class GuardBlocked(Exception):
    """Raised by guarded methods on BLOCK, carrying the Verdict for the caller to
    inspect. Callers that want the MCP-style "return a refusal dict instead of
    raising" behavior should catch this; raising is the more Pythonic default for an
    in-process API where the caller can just try/except around one call site."""

    def __init__(self, verdict):
        self.verdict = verdict
        reasons = "; ".join(r.message for r in verdict.reasons) or "no reasons given"
        super().__init__(f"Action blocked by guard ({verdict.layer}): {reasons}")


class GuardedPage:
    def __init__(self, page, task: dict | None = None, enable_l3: bool | None = None,
                 run_id: str | None = None):
        self._page = page
        self._task = gc.task_from_raw(task or _PLACEHOLDER_TASK)
        self._run_id = run_id or os.environ.get("GUARD_RUN_ID", "playwright-shim")
        self._session = gc.make_session(self._run_id)
        if enable_l3 is None:
            enable_l3 = os.environ.get("GUARD_ENABLE_L3", "0").lower() in ("1", "true", "yes")
        self._config = gc.make_config(enable_l3, self._session)

    # ---- passthrough to the real Playwright Page for everything not guarded ----
    def __getattr__(self, name):
        return getattr(self._page, name)

    # ---- guarded surface ----
    def read_page(self) -> dict:
        """Ingress: extract + audit + return the PageSnapshot as a plain dict (same
        shape read_page() returns over MCP), plus any guard_warnings."""
        raw = extract_raw_sync(self._page)
        snapshot = gc.snapshot_from_raw(raw)
        action = gc.action_of(type="read")
        verdict = gc.audit(snapshot, action, self._task, self._config, session=self._session)
        verdict_event(self._run_id, "playwright-shim", action, verdict, extra={"url": snapshot.url})
        return {
            "snapshot": to_jsonable(snapshot),
            "guard_warnings": [
                {"check": r.check, "severity": str(r.severity), "message": r.message}
                for r in verdict.reasons
            ],
        }

    def _guarded(self, action, execute_fn):
        raw = extract_raw_sync(self._page)
        snapshot = gc.snapshot_from_raw(raw)
        verdict = gc.audit(snapshot, action, self._task, self._config, session=self._session)
        verdict_event(self._run_id, "playwright-shim", action, verdict, extra={"url": snapshot.url})

        if verdict.decision == "BLOCK":
            raise GuardBlocked(verdict)

        if verdict.decision == "REWRITE" and verdict.rewritten_action is not None:
            execute_fn(verdict.rewritten_action)
            gc.observe(self._session, snapshot, verdict.rewritten_action, executed=True)
            raise GuardBlocked(verdict)  # original still didn't happen -- caller must retry deliberately

        result = execute_fn(action)
        gc.observe(self._session, snapshot, action, executed=True)
        return result

    def _trust_navigate_target(self, url: str) -> None:
        """See adapters/mcp/server.py::_trust_navigate_target for why: navigate() /
        guard_goto() targets are the caller's deliberate destination choice, not a
        page-triggered side effect, so their origin is allow-listed before auditing
        rather than tripping guard/l2_policy.py's forbid_navigation_origin rule on
        every legitimate goto (including the very first one of a run)."""
        from urllib.parse import urlparse
        try:
            p = urlparse(url)
            if p.scheme and p.netloc:
                origin = f"{p.scheme}://{p.netloc}"
                if origin not in self._task.allowed_origins:
                    self._task.allowed_origins.append(origin)
        except ValueError:
            pass

    def guard_goto(self, url: str, **kwargs):
        self._trust_navigate_target(url)

        def _do(a):
            self._page.goto(a.url, **kwargs)
            return {"ok": True, "url": self._page.url}

        return self._guarded(gc.action_of(type="navigate", url=url), _do)

    def guard_click(self, ref: str):
        def _do(a):
            el = self._page.query_selector(ref_selector(a.ref))
            if el is None:
                raise ValueError(f"ref {a.ref} not found -- call read_page() again")
            el.click()
            return {"ok": True, "clicked": a.ref}

        return self._guarded(gc.action_of(type="click", ref=ref), _do)

    def guard_type(self, ref: str, text: str):
        def _do(a):
            el = self._page.query_selector(ref_selector(a.ref))
            if el is None:
                raise ValueError(f"ref {a.ref} not found -- call read_page() again")
            el.fill(a.text)
            return {"ok": True, "typed_into": a.ref}

        return self._guarded(gc.action_of(type="type", ref=ref, text=text), _do)

    def guard_submit(self, ref: str):
        def _do(a):
            el = self._page.query_selector(ref_selector(a.ref))
            if el is None:
                raise ValueError(f"ref {a.ref} not found -- call read_page() again")
            with self._page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
                el.evaluate("form => form.requestSubmit ? form.requestSubmit() : form.submit()")
            return {"ok": True, "submitted": a.ref, "url": self._page.url}

        return self._guarded(gc.action_of(type="submit", ref=ref), _do)

    def set_task(self, task: dict) -> None:
        prior_allowed = list(getattr(self._task, "allowed_origins", []) or [])
        self._task = gc.task_from_raw(task)
        for o in prior_allowed:
            if o not in self._task.allowed_origins:
                self._task.allowed_origins.append(o)


def wrap(page, task: dict | None = None, enable_l3: bool | None = None,
         run_id: str | None = None) -> GuardedPage:
    """`page = guard.wrap(page)` from context.md §2, form factor A. Returns a
    GuardedPage that passes through every normal Playwright Page method/property, and
    additionally exposes read_page/guard_goto/guard_click/guard_type/guard_submit."""
    return GuardedPage(page, task=task, enable_l3=enable_l3, run_id=run_id)
