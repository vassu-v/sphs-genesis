"""
harness/dumb_agent.py -- the scripted, deterministic, ZERO-LLM agent policy.

Built FIRST and independently of any model provider so the whole pipeline
(browser -> snapshot -> guard -> execute -> oracle -> scoring) is testable offline,
under quota exhaustion, or with no API key configured at all. This is also what makes
Arm B's "zero LLM calls" claim end-to-end verifiable in one command, not just at the
guard layer: `--agent dumb` guarantees no network call to any model provider happens
anywhere in the run, on top of GuardConfig(enable_l3=False) guaranteeing the guard
itself makes none.

Policy (deliberately simple, text/role driven, no CSS-class or site-specific
knowledge): at each page, look for the FIRST visible interactive element whose
accessible name matches this step's intent vocabulary, in priority order --

    1. checkout intent : "add to cart", "buy now"
    2. continue intent  : "continue to checkout", "continue", "proceed to checkout"
    3. pay intent       : "place order", "pay now", "submit order", "confirm order",
                          "complete purchase"

and, before ever submitting a form, uncheck every checkbox that is currently checked
and is not one of the task's required identity fields (CONTRACTS §1) -- that is the
mechanical form of "decline every optional add-on ... the agent did not itself check".

This is intentionally naive about anything adversarial: it does NOT try to out-think a
decoy (it simply never targets text outside its vocabulary, so a "Free Gift Bundle" or
"Yes, keep me updated" decoy is never a candidate action in the first place), and it
does NOT know about hit-testing, hidden text, or undisclosed amounts -- catching those
is the guard's job, not the agent's. That separation of concerns is the point: Arm B
pairs this agent with the guard and should pass; Arm A pairs it with nothing and
should not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

CHECKOUT_PHRASES = ("add to cart", "buy now", "add to bag")
CONTINUE_PHRASES = ("continue to checkout", "proceed to checkout", "continue", "go to checkout")
PAY_PHRASES = ("place order", "pay now", "submit order", "confirm order", "complete purchase", "pay")

# Required per CONTRACTS §1's synthetic identity -- these are legitimately typed into
# the task, so a checked/filled state on a field carrying one of these is not a
# consent violation. Nothing else the agent didn't itself check should stay checked.
REQUIRED_FIELD_HINTS = ("name", "email", "address", "card", "exp", "cvv", "password")


@dataclass
class DumbAgentState:
    """Per-run scratch state the CLI keeps and passes back in on every call --
    dumb_agent.py itself is otherwise a pure function of (snapshot, task, state).

    IMPORTANT: refs are only stable within one page (a fresh navigation gets a fresh
    per-page counter starting at ref_0 -- see adapters/_shared/snapshot_js.py and
    guard/session.py's own docstring on exactly this point). Bookkeeping sets here are
    therefore keyed by (url, ref), never by bare ref, or "ref_8" on page 3 would
    silently be treated as already-handled just because SOME earlier page also had a
    ref_8 that got clicked."""
    steps_taken: int = 0
    unchecked_refs: set = field(default_factory=set)   # {(url, ref)}
    clicked_refs: set = field(default_factory=set)      # {(url, ref)}
    done: bool = False

    # -- BLOCK-awareness (harness bug fix: a dumb agent that can't re-plan after a
    # BLOCK just stalls forever retrying/abandoning the one thing it needed to do).
    # Keyed by (url, action_type, ref). Only a hard BLOCK goes here -- a REWRITE means
    # the guard already executed a safe substitute for us (e.g. unticking a pre-checked
    # box before a submit), so the very next attempt of the *same* action is expected
    # to succeed and must not be treated as "already tried, give up".
    blocked_hard: set = field(default_factory=set)
    submit_attempts: dict = field(default_factory=dict)  # {(url, form_ref): count}
    last_block_reason: Optional[str] = None

    MAX_SUBMIT_ATTEMPTS = 3

    def on_block(self, url: str, action: dict, verdict: dict) -> None:
        """Called by the harness CLI whenever an action raised BlockedError, so the
        agent can react on its NEXT turn instead of blindly repeating the mistake."""
        reasons = (verdict or {}).get("reasons") or []
        top = reasons[0] if reasons else {}
        self.last_block_reason = (
            f"{action.get('type')} {action.get('ref')} blocked by "
            f"{top.get('check', 'unknown_check')}: {top.get('message', 'no message')}"
        )
        decision = (verdict or {}).get("decision")
        key = (url, action.get("type"), action.get("ref"))
        if decision == "BLOCK" and action.get("type") != "submit":
            self.blocked_hard.add(key)
        # A blocked "submit" is deliberately NOT added here: submit has its own
        # bounded-retry bookkeeping in `submit_attempts` (state can change between
        # attempts -- a precheck REWRITE, a since-declined add-on -- so one BLOCK
        # shouldn't permanently rule it out; see `next_action`'s submit branch for the
        # cap that keeps this from looping forever).
        # decision == "REWRITE": no permanent exclusion either -- the guard already
        # carried out a safe substitute (session-provenance recorded), so retrying the
        # same action next turn is the intended recovery path, not a stall.


def _visible(el: dict) -> bool:
    c = el.get("computed") or {}
    box = el.get("box") or {}
    if c.get("opacity") == 0:
        return False
    if c.get("visibility") in ("hidden", "collapse"):
        return False
    if c.get("display") == "none":
        return False
    if (box.get("w") or 0) <= 0 or (box.get("h") or 0) <= 0:
        return False
    return True


def _label(el: dict) -> str:
    return (el.get("name") or el.get("text") or el.get("attrs", {}).get("aria-label") or "").strip().lower()


def _reachable(el: dict) -> bool:
    """True when nothing else is painted on top of this element's centre point, per
    the same hitTestRef the guard's flagship hit_test check uses. A dumb text-phrase
    match has no notion of z-order or modals, so two controls can share a word
    ("Continue as guest" underneath a modal vs. "No thanks, continue" inside it) and
    the wrong one being first in DOM order would waste a whole turn getting BLOCKed
    for exactly the reason the guard exists. Preferring the reachable one is not
    working around the guard -- it's the dumb agent behaving like it can actually see
    the screen, which a sighted human clicking the obviously-on-top modal button
    would do without thinking about it."""
    hit = el.get("hitTestRef")
    return hit is None or hit == el.get("ref")


def _find_by_phrases(elements: list, phrases: tuple, exclude_refs: set) -> Optional[dict]:
    fallback = None
    for el in elements:
        if el["ref"] in exclude_refs:
            continue
        if not _visible(el):
            continue
        label = _label(el)
        if any(p in label for p in phrases):
            if _reachable(el):
                return el
            if fallback is None:
                fallback = el
    return fallback


def _find_unchecked_target(elements: list):
    """Checked checkboxes the agent should consider unchecking, in order.

    Deliberately does NOT include checkboxes that are literally invisible to the
    agent (zero-size / aria-only / etc, per the same `_visible()` test the guard's own
    invisible_text/hit_test checks use): clicking an element you cannot perceive is
    itself flagged by the guard as suspicious ("the agent is being steered into an
    element nobody can see") independent of what that element does, so a dumb policy
    that only acts on what it can see is both the honest behavior AND the one that
    doesn't trip that check. A dark pattern hidden this way is still caught: if it
    stays checked through to submit, guard/l1_structural.py's page-wide
    precheck_optins scan still fires on it there -- this loop just isn't the thing
    that pokes it directly."""
    for el in elements:
        if el.get("attrs", {}).get("type") != "checkbox":
            continue
        if not el.get("checked"):
            continue
        if not _visible(el) or not _reachable(el):
            continue
        label = _label(el)
        if any(h in label for h in REQUIRED_FIELD_HINTS):
            continue
        yield el


DISMISS_PHRASES = CONTINUE_PHRASES + ("no thanks", "close", "dismiss", "not now")


def _obstruction_present(elements: list) -> bool:
    """True when something on the page is currently covering something else (e.g. a
    modal). While that's true, an otherwise-correct action targeting whatever's
    underneath will get BLOCKed for exactly the reason the guard exists, so the dumb
    agent looks for a REACHABLE dismiss-ish control first rather than blindly working
    through its normal priority order into a wall of refusals."""
    return any(not _reachable(el) for el in elements if _visible(el))


def _find_submit_button(elements: list, exclude_refs: set) -> Optional[dict]:
    return _find_by_phrases(elements, PAY_PHRASES, exclude_refs=exclude_refs)


def next_action(snapshot: dict, task: dict, state: DumbAgentState) -> Optional[dict]:
    """Returns a guard Action dict ({"type": ..., "ref": ...} etc.) or None when the
    dumb agent believes the task is already complete / has nothing left to try."""
    state.steps_taken += 1
    url = snapshot.get("url", "")
    success_pattern = task.get("success_url_pattern") or "/order/confirmed"

    if success_pattern in url:
        state.done = True
        return {"type": "finish", "summary": f"Reached {url}, matching success pattern {success_pattern!r}."}

    elements = snapshot.get("elements") or []
    forms = snapshot.get("forms") or []

    hard_blocked_clicks = {ref for (u, t, ref) in state.blocked_hard if u == url and t == "click"}
    clicked_here = {ref for (u, ref) in state.clicked_refs if u == url} | hard_blocked_clicks

    # 0. Something is covering something else (a modal, most likely) -- clear that
    #    FIRST, before anything downstream reads as `covered` to the guard just
    #    because it's sitting underneath. Only acts when a REACHABLE dismiss-ish
    #    control actually exists; otherwise falls through to the normal priorities
    #    (e.g. an obstruction with no obvious dismiss button is not this agent's
    #    problem to solve -- the guard blocking whatever it touches is correct).
    if _obstruction_present(elements):
        el = _find_by_phrases(elements, DISMISS_PHRASES, exclude_refs=clicked_here)
        if el is not None and _reachable(el):
            state.clicked_refs.add((url, el["ref"]))
            return {"type": "click", "ref": el["ref"]}

    # 1. Decline every optional pre-checked extra before ever touching submit --
    #    one at a time (each click may need a fresh snapshot afterward), remembering
    #    which refs were already handled this run so we don't loop forever on a ref
    #    the guard itself already neutralized (e.g. via REWRITE).
    unchecked_here = {ref for (u, ref) in state.unchecked_refs if u == url} | hard_blocked_clicks
    for cb in _find_unchecked_target(elements):
        if cb["ref"] in unchecked_here:
            continue
        state.unchecked_refs.add((url, cb["ref"]))
        return {"type": "click", "ref": cb["ref"]}

    # 2. Walk the honest funnel BEFORE ever submitting: add to cart -> continue/
    #    dismiss-any-modal -> pay. Checked ahead of the explicit form-submit step
    #    (3) below on purpose -- a "continue" control (which also covers a benign
    #    modal's real decline button, e.g. "No thanks, continue") may need to be
    #    clicked first, and until it is, anything underneath a modal reads as
    #    `covered` to the guard's geometry checks, including the order total.
    for phrases in (CHECKOUT_PHRASES, CONTINUE_PHRASES):
        el = _find_by_phrases(elements, phrases, exclude_refs=clicked_here)
        if el is not None:
            state.clicked_refs.add((url, el["ref"]))
            return {"type": "click", "ref": el["ref"]}

    # 3. If a checkout/payment form is present and nothing is left to decline or
    #    dismiss, submit it. Submit is special-cased vs. an ordinary click: a BLOCK on
    #    submit is frequently resolved by the guard's own REWRITE machinery (e.g.
    #    unticking a pre-checked box) or by state that changed since the last attempt,
    #    so unlike a plain click we deliberately retry it -- but only up to
    #    MAX_SUBMIT_ATTEMPTS, and never once it's in blocked_hard for THIS url/form
    #    (a hard, repeated BLOCK the agent has no lever to fix).
    if forms:
        form_ref = forms[0]["ref"]
        submit_key = (url, "submit", form_ref)
        attempts = state.submit_attempts.get((url, form_ref), 0)
        pay_btn = _find_submit_button(elements, exclude_refs=clicked_here)
        can_submit = (
            pay_btn is not None
            and submit_key not in state.blocked_hard
            and attempts < state.MAX_SUBMIT_ATTEMPTS
        )
        if can_submit:
            state.submit_attempts[(url, form_ref)] = attempts + 1
            if attempts + 1 >= state.MAX_SUBMIT_ATTEMPTS:
                # Last allowed attempt: if the guard blocks this one too, on_block's
                # BLOCK branch plus this cap keeps the NEXT call from trying again --
                # see the submit_key check above.
                state.blocked_hard.add(submit_key)
            return {"type": "submit", "ref": form_ref}

    # 4. Fallback: a pay-labelled control that isn't inside a <form> at all.
    el = _find_by_phrases(elements, PAY_PHRASES, exclude_refs=clicked_here)
    if el is not None:
        state.clicked_refs.add((url, el["ref"]))
        return {"type": "click", "ref": el["ref"]}

    # Nothing recognizable left to do.
    return None
