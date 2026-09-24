"""
Single point of contact with the guard core. Every adapter (mcp, playwright, service)
imports from HERE, never directly from `guard` or from guard_stub.

track3/guard/ landed (built concurrently by another agent) while this adapter layer
was being built, exposing a considerably richer interface than CONTRACTS.md's minimal
`audit(snapshot, action, task, config)` alone documents:

  - guard.types.PageSnapshot / Action / TaskDescriptor / Element / ... all have
    mechanical `from_dict` / `to_dict`, so adapters never need their own dataclasses
    to talk to it -- raw JS-extractor dicts go in directly.
  - guard.session.GuardSession tracks WHICH checkboxes/fields the agent itself
    touched, across the whole run, keyed by (url_path, ref). This is what
    `precheck_optins` uses to tell "the agent opted in" from "the site opted the
    agent in" -- audit() itself stays pure and never mutates it; the ADAPTER calls
    `session.observe(snapshot, action, executed=True)` right after an action it just
    executed, and `session.observe_setter(...)` when the guard's own REWRITE flips a
    checkbox. See adapters/mcp/server.py and adapters/playwright/shim.py for the call
    sites -- both do this identically, factored through `observe()` below.
  - GuardConfig carries additional tunables beyond enable_l3 (thresholds, weak-check
    ceiling, etc.) with sane defaults; adapters only ever set enable_l3 and session.

If `guard` is not importable (e.g. this module is exercised in isolation, or run
against an older checkout before guard/ existed), everything falls back to
adapters/_shared/guard_stub.py -- an L1-only, zero-LLM, CONTRACTS-shaped
implementation good enough to keep the whole pipeline runnable end to end.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("guard_client")

try:
    import guard as _guard_pkg
    from guard import Action, GuardConfig, PageSnapshot, TaskDescriptor, Verdict
    from guard.session import GuardSession

    GUARD_SOURCE = f"guard-package:{getattr(_guard_pkg, '__version__', '?')}"

    def snapshot_from_raw(raw: dict) -> PageSnapshot:
        return PageSnapshot.from_dict(raw)

    def action_of(**kwargs) -> Action:
        return Action(**kwargs)

    def task_from_raw(raw: dict) -> TaskDescriptor:
        return TaskDescriptor.from_dict(raw)

    def make_session(run_id: str) -> GuardSession:
        return GuardSession(run_id=run_id)

    def make_config(enable_l3: bool, session: GuardSession | None) -> GuardConfig:
        cfg = GuardConfig(enable_l3=enable_l3)
        if session is not None:
            cfg.session = session
        return cfg

    def audit(snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig,
              session: GuardSession | None = None) -> Verdict:
        # `session` is accepted for signature parity with the stub branch; the real
        # guard reads provenance off config.session (attached by make_config), not a
        # separate parameter, so it's unused here on purpose.
        return _guard_pkg.audit(snapshot, action, task, config)

    def observe(session: GuardSession | None, snapshot: PageSnapshot, action: Action, executed: bool) -> None:
        if session is not None:
            session.observe(snapshot, action, executed=executed)

    def observe_setter(session: GuardSession | None, snapshot: PageSnapshot, ref: str, checked: bool) -> None:
        if session is not None and ref:
            session.observe_setter(snapshot, ref, checked)

    logger.info("guard_client: using real guard/ package (%s)", GUARD_SOURCE)

except ImportError:
    from adapters._shared.contracts import (
        Action, GuardConfig, PageSnapshot, TaskDescriptor, Verdict,
    )
    from adapters._shared.guard_stub import audit as _stub_audit
    from adapters._shared.snapshot import raw_to_snapshot as snapshot_from_raw  # noqa: F401

    GUARD_SOURCE = "local-stub"

    def action_of(**kwargs) -> Action:
        return Action(**kwargs)

    def task_from_raw(raw: dict) -> TaskDescriptor:
        return TaskDescriptor(
            task_id=raw.get("task_id", "unset"), site_id=raw.get("site_id", "unset"),
            goal_text=raw.get("goal_text", ""), target_item=raw.get("target_item", ""),
            base_price=raw.get("base_price", 0), currency=raw.get("currency", "INR"),
            success_url_pattern=raw.get("success_url_pattern", "/order/confirmed"),
        )

    class _StubSession:
        """Minimal stand-in for guard.session.GuardSession: just the touched-refs
        set the stub's precheck_optins check needs. No per-URL scoping -- fine for
        a fallback path whose job is "keep the pipeline alive", not full fidelity."""

        def __init__(self, run_id: str = ""):
            self.run_id = run_id
            self.touched_refs: set = set()

        def observe(self, snapshot, action, executed=True):
            if executed and action.type == "click" and action.ref:
                self.touched_refs.add(action.ref)

        def observe_setter(self, snapshot, ref, checked):
            if checked:
                self.touched_refs.add(ref)
            else:
                self.touched_refs.discard(ref)

    def make_session(run_id: str) -> _StubSession:
        return _StubSession(run_id)

    def make_config(enable_l3: bool, session: _StubSession | None) -> GuardConfig:
        return GuardConfig(enable_l3=enable_l3)

    def audit(snapshot, action, task, config, session: _StubSession | None = None) -> Verdict:
        touched = session.touched_refs if session is not None else None
        return _stub_audit(snapshot, action, task, config, touched_refs=touched)

    def observe(session, snapshot, action, executed: bool) -> None:
        if session is not None:
            session.observe(snapshot, action, executed=executed)

    def observe_setter(session, snapshot, ref: str, checked: bool) -> None:
        if session is not None and ref:
            session.observe_setter(snapshot, ref, checked)

    logger.warning(
        "guard_client: track3/guard/ not importable -- falling back to "
        "adapters/_shared/guard_stub.py (L1-only, zero LLM calls)."
    )

__all__ = [
    "audit", "GUARD_SOURCE", "snapshot_from_raw", "action_of", "task_from_raw",
    "make_session", "make_config", "observe", "observe_setter",
    "PageSnapshot", "Action", "TaskDescriptor", "GuardConfig", "Verdict",
]
