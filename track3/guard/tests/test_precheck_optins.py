"""precheck_optins - provenance, and the REWRITE that keeps the task alive."""

from __future__ import annotations

from guard import audit
from guard.l1_structural import check_precheck_optins
from guard.session import GuardSession
from guard.types import Action, GuardConfig

from .conftest import element, load_snapshot, snapshot


def _form(fields):
    return [{"ref": "ref_f", "action": "/pay", "method": "post", "fields": fields}]


def test_site_prechecked_addon_is_caught_and_rewritten(task, config):
    snap = load_snapshot("billing_traps")
    verdict = audit(snap, Action(type="submit", ref="ref_7"), task, config)
    refs = {r.ref for r in verdict.reasons if r.check == "precheck_optins"}
    assert {"ref_71", "ref_72"} <= refs
    assert verdict.decision in ("BLOCK", "REWRITE")


def test_rewrite_unchecks_rather_than_blocking_when_that_is_enough(task, config):
    """A page whose ONLY problem is a pre-checked add-on should be repaired,
    not refused: the benchmark scores task completion too."""
    snap = snapshot(
        elements=[element("ref_b", name="Pay", attrs={"type": "submit"}, formRef="ref_f")],
        forms=_form(
            [
                {
                    "ref": "ref_ins",
                    "name": "insurance",
                    "type": "checkbox",
                    "checked": True,
                    "label": "Add protection plan",
                }
            ]
        ),
    )
    verdict = audit(snap, Action(type="submit", ref="ref_f"), task, config)
    assert verdict.decision == "REWRITE"
    assert verdict.rewritten_action.type == "click"
    assert verdict.rewritten_action.ref == "ref_ins"
    assert verdict.rewritten_action.extra["intent"] == "uncheck"


def test_agent_checked_box_is_not_flagged(task):
    """Provenance: the same DOM state is innocent when the agent caused it."""
    session = GuardSession(run_id="t")
    config = GuardConfig(enable_l3=False, session=session)
    snap = snapshot(
        forms=_form(
            [
                {
                    "ref": "ref_gift",
                    "name": "gift_wrap",
                    "type": "checkbox",
                    "checked": False,
                    "label": "Gift wrap this order",
                }
            ]
        )
    )
    # the agent ticks it itself
    session.observe(snap, Action(type="click", ref="ref_gift"))

    after = snapshot(
        forms=_form(
            [
                {
                    "ref": "ref_gift",
                    "name": "gift_wrap",
                    "type": "checkbox",
                    "checked": True,
                    "label": "Gift wrap this order",
                }
            ]
        )
    )
    assert check_precheck_optins(after, Action(type="submit", ref="ref_f"), task, config) == []


def test_unchecking_clears_the_provenance(task):
    session = GuardSession(run_id="t")
    config = GuardConfig(enable_l3=False, session=session)
    checked = snapshot(
        forms=_form([{"ref": "ref_x", "name": "extra", "type": "checkbox", "checked": False, "label": "Extra"}])
    )
    session.observe(checked, Action(type="click", ref="ref_x"))  # check
    now_checked = snapshot(
        forms=_form([{"ref": "ref_x", "name": "extra", "type": "checkbox", "checked": True, "label": "Extra"}])
    )
    session.observe(now_checked, Action(type="click", ref="ref_x"))  # uncheck again
    assert session.agent_checked(now_checked.url, "ref_x") is False


def test_blocked_action_is_never_recorded_as_agent_intent(task):
    session = GuardSession(run_id="t")
    snap = snapshot(
        forms=_form([{"ref": "ref_y", "name": "sub", "type": "checkbox", "checked": False, "label": "Subscribe"}])
    )
    session.observe(snap, Action(type="click", ref="ref_y"), executed=False)
    assert session.agent_checked(snap.url, "ref_y") is False


def test_required_terms_checkbox_is_reported_but_never_unticked(task, config):
    snap = load_snapshot("benign_checkout")
    reasons = check_precheck_optins(snap, Action(type="submit", ref="ref_3"), task, config)
    terms = [r for r in reasons if r.ref == "ref_13"]
    assert terms and terms[0].severity == "low"
    assert "rewrite" not in terms[0].evidence


def test_unchecked_boxes_are_never_flagged(task, config):
    snap = snapshot(
        forms=_form([{"ref": "ref_n", "name": "insurance", "type": "checkbox", "checked": False, "label": "Insurance"}])
    )
    assert check_precheck_optins(snap, Action(type="submit", ref="ref_f"), task, config) == []


def test_check_only_applies_to_submitting_actions(task, config):
    snap = load_snapshot("billing_traps")
    assert check_precheck_optins(snap, Action(type="read"), task, config) == []
