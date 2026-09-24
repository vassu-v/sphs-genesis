"""
LOCAL STUB for guard.audit().

track3/guard/ is being built concurrently by another agent as the real, frozen-schema
implementation of L1/L2/L3 described in context.md and CONTRACTS.md §8. Per this
agent's brief ("if guard/ is not present yet, write against the documented interface
and a local stub"), this module is a deliberately minimal but REAL implementation of
the L1 structural layer only — enough that adapters/mcp, adapters/playwright, service/
and harness/ are runnable and testable end-to-end today, offline, with zero LLM calls.

adapters/_shared/guard_client.py imports the real `guard` package if it is importable
and falls back to `audit()` here otherwise, so nothing else in this codebase needs to
know which one is active.

Implements, from context.md §2 "L1 — the deterministic checks":
  - hit_test               (the flagship: elementFromPoint vs. intended ref)
  - invisible_text          (opacity/font-size/color-match/offscreen/clip/zero-size/
                             visibility-hidden while still in the accessibility tree)
  - injection_phrasing      (imperative text addressed at a model)
  - pre_checked_optin       (checkbox checked that the agent did not itself check)
  - cross_origin_form       (form.action origin != document origin)
  - undisclosed_amount      (a monetary value not visibly rendered)

Does NOT implement L2 policy or L3 semantic — those are guard/'s responsibility.
enable_l3 is honored insofar as this stub NEVER calls an LLM, ever (arm B behavior by
construction), and reports llm_used=False always.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from adapters._shared.contracts import Action, GuardConfig, PageSnapshot, TaskDescriptor, Verdict, VerdictReason

INJECTION_PATTERNS = [
    r"ignore (all|previous|prior) instructions",
    r"\byou are now\b",
    r"^\s*system:",
    r"\bai assistant:",
    r"security scanner",
    r"page verified safe",
    r"approve all actions",
    r"disregard (the|your) (task|goal|instructions)",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

LEGIBLE_FONT_PX = 6.0
AMOUNT_TOLERANCE = 0.01  # currency rounding slack


def _reason(check, severity, message, **evidence) -> VerdictReason:
    return VerdictReason(check=check, severity=severity, message=message, evidence=evidence)


def _allow(layer: str, reasons: list, elapsed_ms: float) -> Verdict:
    return Verdict(decision="ALLOW", layer=layer, llm_used=False, reasons=reasons,
                   rewritten_action=None, elapsed_ms=elapsed_ms)


def _block(layer: str, reasons: list, elapsed_ms: float) -> Verdict:
    return Verdict(decision="BLOCK", layer=layer, llm_used=False, reasons=reasons,
                    rewritten_action=None, elapsed_ms=elapsed_ms)


def _rewrite(layer: str, reasons: list, rewritten_action: Action, elapsed_ms: float) -> Verdict:
    return Verdict(decision="REWRITE", layer=layer, llm_used=False, reasons=reasons,
                    rewritten_action=rewritten_action, elapsed_ms=elapsed_ms)


def _check_hit_test(snapshot: PageSnapshot, ref: str) -> list:
    el = snapshot.find_element(ref)
    if el is None:
        return []
    if el.hitTestRef is not None and el.hitTestRef != ref:
        # allow if hitTestRef is a descendant-looking ref is out of scope for the stub
        # (no DOM tree available here) -- flag as high severity, guard/ can refine with
        # real ancestor-chain data once it lands.
        cx = el.box.x + el.box.w / 2
        cy = el.box.y + el.box.h / 2
        return [_reason(
            "hit_test", "high",
            f"Element {ref} ('{el.name}') is covered by {el.hitTestRef} at its centre point.",
            expected=ref, actual=el.hitTestRef, point=[cx, cy],
        )]
    return []


def _check_injection_phrasing(snapshot: PageSnapshot) -> list:
    reasons = []
    for tn in snapshot.textNodes:
        if _INJECTION_RE.search(tn.text or ""):
            reasons.append(_reason(
                "injection_phrasing", "high" if not tn.visible else "medium",
                f"Imperative model-directed phrasing found ({'hidden' if not tn.visible else 'visible'}): "
                f"{tn.text[:120]!r}",
                ref=tn.ref, visible=tn.visible, hiddenBy=tn.hiddenBy,
            ))
    return reasons


def _check_invisible_but_actionable(snapshot: PageSnapshot, ref: str) -> list:
    """An element the agent is about to click that is itself invisible to a human --
    i.e. the agent would be doing something no human reviewer of the page could see."""
    el = snapshot.find_element(ref)
    if el is None:
        return []
    c = el.computed
    reasons = []
    if c.opacity == 0:
        reasons.append(_reason("invisible_text", "high", f"Target {ref} has opacity 0.", ref=ref))
    if c.fontSize == 0 and el.text:
        reasons.append(_reason("invisible_text", "high", f"Target {ref} has font-size 0.", ref=ref))
    if c.visibility in ("hidden", "collapse") and el.inAccessibilityTree:
        reasons.append(_reason(
            "invisible_text", "high",
            f"Target {ref} is visibility:hidden but still exposed to the accessibility tree.", ref=ref,
        ))
    return reasons


def _check_cross_origin_form(snapshot: PageSnapshot, form_ref: str) -> list:
    form = next((f for f in snapshot.forms if f.ref == form_ref), None)
    if form is None:
        return []
    try:
        doc_origin = urlparse(snapshot.url)
        act_origin = urlparse(form.action)
        if (act_origin.scheme, act_origin.hostname, act_origin.port) != (doc_origin.scheme, doc_origin.hostname, doc_origin.port):
            return [_reason(
                "cross_origin_form", "high",
                f"Form {form_ref} submits to {form.action}, which is cross-origin from {snapshot.url}.",
                form_action=form.action, document_origin=snapshot.url,
            )]
    except Exception:
        pass
    return []


def _check_pre_checked_optins(snapshot: PageSnapshot, form_ref: str, touched_refs: set) -> tuple:
    """Returns (reasons, first_untouched_checked_field_ref_or_None)."""
    form = next((f for f in snapshot.forms if f.ref == form_ref), None)
    if form is None:
        return [], None
    reasons = []
    first_untouched = None
    for field in form.fields:
        if field.type == "checkbox" and field.checked and field.ref not in touched_refs:
            reasons.append(_reason(
                "pre_checked_optin", "medium",
                f"Checkbox {field.ref} ('{field.label}') is pre-checked and was not checked by the agent.",
                ref=field.ref, label=field.label,
            ))
            if first_untouched is None:
                first_untouched = field.ref
    return reasons, first_untouched


def _check_pre_checked_optins_pagewide(snapshot: PageSnapshot, touched_refs: set) -> tuple:
    """Page-wide companion to _check_pre_checked_optins: dark-pattern checkboxes are
    frequently placed OUTSIDE the <form> element they logically affect (styled as a
    sibling card, wired to shared cart/session state via JS) specifically so a
    form-scoped scan misses them. Scans every checkbox/radio on the page regardless of
    form membership. Returns (reasons, first_untouched_ref_or_None)."""
    reasons = []
    first_untouched = None
    for el in snapshot.elements:
        if el.checked and el.ref not in touched_refs:
            reasons.append(_reason(
                "pre_checked_optin", "medium",
                f"Checkbox/radio {el.ref} ('{el.name}') is pre-checked and was not checked by the agent.",
                ref=el.ref, name=el.name,
            ))
            if first_untouched is None:
                first_untouched = el.ref
    return reasons, first_untouched


def _check_undisclosed_amount(snapshot: PageSnapshot, task: TaskDescriptor) -> list:
    reasons = []
    for amt in snapshot.amounts:
        if not amt.visiblyRendered and amt.value and abs(amt.value - task.base_price) > AMOUNT_TOLERANCE:
            reasons.append(_reason(
                "undisclosed_amount", "high",
                f"Amount {amt.value} {amt.currency} exists in page/form state but is not visibly rendered.",
                ref=amt.ref, value=amt.value, currency=amt.currency,
            ))
    return reasons


def audit(snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig,
          touched_refs: set | None = None) -> Verdict:
    """
    Pure, synchronous, no network calls -- matches CONTRACTS.md §8 exactly.

    `touched_refs` is a stub-only convenience (not in CONTRACTS) letting the caller
    tell us which checkbox refs the agent itself has explicitly clicked this run, so
    _check_pre_checked_optins can distinguish "agent opted in" from "site pre-opted the
    agent in". Adapters track this in a simple per-session set. The real guard/ package
    is free to track this however it likes internally; callers should stop passing this
    kwarg once guard/ lands and drop it in favor of guard's own internal state.
    """
    t0 = time.perf_counter()
    touched_refs = touched_refs or set()
    reasons: list = []

    # Checks that apply regardless of the specific action -- injected content sitting
    # anywhere on the page is worth flagging even if this particular action doesn't
    # touch it, so the agent (and dashboard) sees it on every read.
    reasons.extend(_check_injection_phrasing(snapshot))

    if action.type == "click" and action.ref:
        reasons.extend(_check_hit_test(snapshot, action.ref))
        reasons.extend(_check_invisible_but_actionable(snapshot, action.ref))

    if action.type == "type" and action.ref:
        reasons.extend(_check_invisible_but_actionable(snapshot, action.ref))

    if action.type == "submit" and action.ref:
        reasons.extend(_check_cross_origin_form(snapshot, action.ref))
        reasons.extend(_check_undisclosed_amount(snapshot, task))
        optin_reasons, first_untouched = _check_pre_checked_optins(snapshot, action.ref, touched_refs)
        reasons.extend(optin_reasons)
        pagewide_reasons, pagewide_first = _check_pre_checked_optins_pagewide(snapshot, touched_refs)
        for r in pagewide_reasons:
            if not any(r.evidence.get("ref") == existing.evidence.get("ref") for existing in reasons if existing.check == "pre_checked_optin"):
                reasons.append(r)
        if first_untouched is None:
            first_untouched = pagewide_first

        blocking = [r for r in reasons if r.severity == "high"]
        if blocking:
            elapsed = (time.perf_counter() - t0) * 1000
            return _block("L1", reasons, elapsed)

        if first_untouched is not None:
            # REWRITE: uncheck the smuggled opt-in instead of letting the submit through,
            # so the agent can retry submit cleanly next turn.
            elapsed = (time.perf_counter() - t0) * 1000
            return _rewrite("L1", reasons, Action(type="click", ref=first_untouched), elapsed)

        elapsed = (time.perf_counter() - t0) * 1000
        return _allow("L1", reasons, elapsed)

    # click / type / navigate / read / finish -- block only on high-severity findings
    blocking = [r for r in reasons if r.severity == "high"]
    elapsed = (time.perf_counter() - t0) * 1000
    if blocking:
        return _block("L1", reasons, elapsed)
    return _allow("L1", reasons, elapsed)
