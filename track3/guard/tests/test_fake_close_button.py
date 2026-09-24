"""fake_close_button - the label picks the candidate, the effect decides."""

from __future__ import annotations

from guard import audit
from guard.l1_structural import check_fake_close_button
from guard.types import Action

from .conftest import element, load_snapshot, snapshot


def test_close_glyph_that_submits_is_blocked(task, config):
    snap = load_snapshot("fake_close_modal")
    verdict = audit(snap, Action(type="click", ref="ref_70"), task, config)
    assert verdict.decision == "BLOCK"
    r = [x for x in verdict.reasons if x.check == "fake_close_button"][0]
    assert "submit" in r.evidence["dangerousEffects"]
    assert r.evidence["isActionTarget"] is True


def test_no_thanks_that_navigates_to_subscribe_is_blocked(task, config):
    snap = load_snapshot("fake_close_modal")
    verdict = audit(snap, Action(type="click", ref="ref_71"), task, config)
    assert verdict.decision == "BLOCK"
    r = [x for x in verdict.reasons if x.check == "fake_close_button"][0]
    assert set(r.evidence["dangerousEffects"]) >= {"navigate", "subscription-mutate"}
    assert r.evidence["href"] == "/subscribe?plan=monthly&auto=1"


def test_structured_handler_metadata_is_used_when_available(task, config):
    snap = snapshot(
        elements=[
            element("ref_c", name="Dismiss", attrs={}, handlers=["cart-mutate"]),
        ]
    )
    reasons = check_fake_close_button(snap, Action(type="click", ref="ref_c"), task, config)
    assert reasons and reasons[0].evidence["dangerousEffects"] == ["cart-mutate"]


# ---- negative -----------------------------------------------------------


def test_honest_close_button_is_not_flagged(task, config):
    snap = load_snapshot("fake_close_modal")
    verdict = audit(snap, Action(type="click", ref="ref_72"), task, config)
    flagged = [r for r in verdict.reasons if r.check == "fake_close_button" and r.ref == "ref_72"]
    assert flagged == []


def test_ordinary_buttons_are_not_candidates(task, config):
    snap = load_snapshot("benign_checkout")
    assert check_fake_close_button(snap, Action(type="click", ref="ref_10"), task, config) == []


def test_close_link_to_hash_is_not_navigation(task, config):
    snap = snapshot(elements=[element("ref_h", name="Close", attrs={"href": "#"})])
    assert check_fake_close_button(snap, Action(type="click", ref="ref_h"), task, config) == []
