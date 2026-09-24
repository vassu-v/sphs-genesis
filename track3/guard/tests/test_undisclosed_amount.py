"""undisclosed_amount - money the user cannot see, or was never quoted."""

from __future__ import annotations

from guard import audit
from guard.l1_structural import check_undisclosed_amount
from guard.types import Action

from .conftest import element, load_snapshot, snapshot


def _amt(**kw):
    base = {"ref": "ref_a", "value": 399, "currency": "INR", "visiblyRendered": True}
    base.update(kw)
    return base


def test_amount_not_visibly_rendered(task, config):
    # scoped to a decision-relevant action: the agent is about to pay
    snap = snapshot(amounts=[_amt(visiblyRendered=False)])
    reasons = check_undisclosed_amount(snap, Action(type="submit", ref="ref_f"), task, config)
    assert reasons[0].severity == "high"
    assert reasons[0].category == "C1"


def test_amount_below_legibility_threshold(task, config):
    snap = snapshot(amounts=[_amt(ref="ref_t", value=2898, fontSize=4)])
    reasons = check_undisclosed_amount(snap, Action(type="submit", ref="ref_f"), task, config)
    assert reasons[0].severity == "high"
    assert reasons[0].evidence["fontSize"] == 4


def test_amount_hidden_by_css_on_its_element(task, config):
    snap = snapshot(
        elements=[element("ref_h", role="generic", name="3,998", style={"opacity": 0.0})],
        amounts=[_amt(ref="ref_h", value=3998)],
    )
    reasons = check_undisclosed_amount(snap, Action(type="submit", ref="ref_f"), task, config)
    assert reasons and "opacity-zero" in reasons[0].evidence["hiddenBy"]


def test_money_smuggled_in_hidden_form_state(task, config):
    snap = load_snapshot("billing_traps")
    reasons = check_undisclosed_amount(snap, Action(type="submit", ref="ref_7"), task, config)
    smuggled = [r for r in reasons if r.evidence.get("source") == "form-state"]
    assert smuggled and smuggled[0].evidence["parsedValue"] == 2898.0


def test_billing_trap_page_blocks_the_payment(task, config):
    snap = load_snapshot("billing_traps")
    verdict = audit(snap, Action(type="submit", ref="ref_7"), task, config)
    assert verdict.decision == "BLOCK"
    checks = {r.check for r in verdict.reasons}
    assert "undisclosed_amount" in checks
    assert "no_submit_above_base_price" in checks


# ---- negative -----------------------------------------------------------


def test_base_price_exactly_is_clean(task, config):
    snap = snapshot(amounts=[_amt(value=2499)])
    assert check_undisclosed_amount(snap, Action(type="read"), task, config) == []


def test_visible_struck_through_list_price_does_not_block(task, config):
    """'Was 3,499, now 2,499' is honest retail copy, not a hidden charge."""
    snap = load_snapshot("benign_checkout")
    verdict = audit(snap, Action(type="submit", ref="ref_3"), task, config)
    assert verdict.decision == "ALLOW"
    over = [r for r in verdict.reasons if r.check == "undisclosed_amount"]
    assert all(r.severity in ("low", "medium") for r in over)


def test_cheaper_amounts_are_never_flagged(task, config):
    snap = snapshot(amounts=[_amt(value=99, ref="ref_ship"), _amt(value=0, ref="ref_free")])
    assert check_undisclosed_amount(snap, Action(type="read"), task, config) == []
