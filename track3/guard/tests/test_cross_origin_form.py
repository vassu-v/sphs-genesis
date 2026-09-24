"""cross_origin_form - pure origin comparison."""

from __future__ import annotations

from guard import audit
from guard.l1_structural import check_cross_origin_form, origin_of
from guard.types import Action, TaskDescriptor

from .conftest import element, load_snapshot, load_task, snapshot


def _forms(action_url):
    return [{"ref": "ref_f", "action": action_url, "method": "post", "fields": []}]


def test_off_origin_form_action_blocks_submit(task, config):
    snap = load_snapshot("exfiltration_form")
    verdict = audit(snap, Action(type="submit", ref="ref_9"), task, config)
    assert verdict.decision == "BLOCK"
    r = [x for x in verdict.reasons if x.check == "cross_origin_form"][0]
    assert r.evidence["documentOrigin"] == "http://127.0.0.1:8905"
    assert r.evidence["formActionOrigin"] == "http://127.0.0.1:8999"


def test_different_port_is_a_different_origin(task, config):
    snap = snapshot(forms=_forms("http://127.0.0.1:9999/collect"))
    reasons = check_cross_origin_form(snap, Action(type="submit", ref="ref_f"), task, config)
    assert reasons and reasons[0].severity == "high"


def test_formaction_override_on_a_button_is_caught(task, config):
    snap = snapshot(
        elements=[element("ref_b", name="Pay", attrs={"type": "submit", "formaction": "https://evil.example/collect"})],
        forms=_forms("/pay"),
    )
    reasons = check_cross_origin_form(snap, Action(type="click", ref="ref_b"), task, config)
    assert any(r.evidence["where"].startswith("Submit button") for r in reasons)


# ---- negative -----------------------------------------------------------


def test_same_origin_absolute_action_is_fine(task, config):
    snap = snapshot(forms=_forms("http://127.0.0.1:8901/pay"))
    assert check_cross_origin_form(snap, Action(type="submit", ref="ref_f"), task, config) == []


def test_relative_action_is_fine(task, config):
    snap = snapshot(forms=_forms("/pay"))
    assert check_cross_origin_form(snap, Action(type="submit", ref="ref_f"), task, config) == []


def test_empty_action_is_fine(task, config):
    snap = snapshot(forms=_forms(""))
    assert check_cross_origin_form(snap, Action(type="submit", ref="ref_f"), task, config) == []


def test_task_can_allowlist_a_payment_gateway(config):
    task = TaskDescriptor.from_dict(
        {**load_task().to_dict(), "allowed_origins": ["http://127.0.0.1:8999"]}
    )
    snap = load_snapshot("exfiltration_form")
    assert check_cross_origin_form(snap, Action(type="submit", ref="ref_9"), task, config) == []


def test_origin_helper():
    assert origin_of("http://127.0.0.1:8901/cart?x=1") == "http://127.0.0.1:8901"
    assert origin_of("/relative") is None
    assert origin_of(None) is None
