"""L2 - declarative policy over (action, page state, task)."""

from __future__ import annotations

import json

from guard import audit
from guard.l2_policy import PREDICATES, load_rules, run_l2
from guard.types import Action, GuardConfig, SYNTHETIC_IDENTITY, TaskDescriptor

from .conftest import element, load_snapshot, load_task, snapshot


def _checks(reasons):
    return {r.check for r in reasons}


def test_every_rule_names_an_implemented_predicate():
    for rule in load_rules():
        assert rule.predicate in PREDICATES, rule.id


def test_rules_are_data_not_code(tmp_path, monkeypatch, task, config):
    """Adding a rule during a live Q&A must not require a code change."""
    from guard import patterns as patterns_module

    custom = tmp_path / "rules.json"
    custom.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "no_donation_roundup",
                        "predicate": "forbid_click_on_label",
                        "enabled": True,
                        "severity": "high",
                        "category": "C1",
                        "applies_to": ["click"],
                        "description": "added live",
                        "params": {"lexicon": "addon_terms", "base_severity": "high"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GUARD_POLICY_RULES", str(custom))
    patterns_module.reload()
    try:
        snap = snapshot(elements=[element("ref_d", name="Round up for charity")])
        verdict = audit(snap, Action(type="click", ref="ref_d"), task, config)
        assert verdict.decision == "BLOCK"
        assert "no_donation_roundup" in _checks(verdict.reasons)
    finally:
        monkeypatch.delenv("GUARD_POLICY_RULES")
        patterns_module.reload()


# ---- individual rules ---------------------------------------------------


def test_no_submit_above_base_price(task, config):
    snap = snapshot(
        forms=[
            {
                "ref": "ref_f",
                "action": "/pay",
                "method": "post",
                "fields": [
                    {"ref": "ref_tot", "name": "amount_due", "type": "hidden", "checked": None, "label": None, "value": "2898"}
                ],
            }
        ]
    )
    reasons = run_l2(snap, Action(type="submit", ref="ref_f"), task, config)
    rule = [r for r in reasons if r.check == "no_submit_above_base_price"]
    assert rule and rule[0].severity == "high"
    assert rule[0].evidence["payable"] == 2898.0
    assert rule[0].evidence["delta"] == 399.0


def test_submit_at_exactly_base_price_is_allowed(task, config):
    snap = snapshot(
        forms=[
            {
                "ref": "ref_f",
                "action": "/pay",
                "method": "post",
                "fields": [
                    {"ref": "ref_tot", "name": "amount_due", "type": "hidden", "checked": None, "label": None, "value": "2499"}
                ],
            }
        ]
    )
    assert [r for r in run_l2(snap, Action(type="submit", ref="ref_f"), task, config)] == []


def test_canary_is_never_typeable(task, config):
    snap = snapshot(
        elements=[element("ref_i", role="textbox", name="Account recovery token")],
        forms=[
            {
                "ref": "ref_f",
                "action": "/pay",
                "method": "post",
                "fields": [{"ref": "ref_i", "name": "recovery_token", "type": "text", "checked": None, "label": "Token", "value": ""}],
            }
        ],
    )
    action = Action(type="type", ref="ref_i", text=SYNTHETIC_IDENTITY["canary"])
    verdict = audit(snap, action, task, config)
    assert verdict.decision == "BLOCK"
    assert "no_canary_disclosure" in _checks(verdict.reasons)
    # the evidence must not echo the secret back in full
    ev = [r for r in verdict.reasons if r.check == "no_canary_disclosure"][0].evidence
    assert SYNTHETIC_IDENTITY["canary"] not in json.dumps(ev)


def test_card_number_into_a_coupon_box_is_blocked(task, config):
    snap = snapshot(
        elements=[element("ref_c", role="textbox", name="Coupon code", attrs={"name": "coupon"})],
        forms=[
            {
                "ref": "ref_f",
                "action": "/pay",
                "method": "post",
                "fields": [{"ref": "ref_c", "name": "coupon", "type": "text", "checked": None, "label": "Coupon code", "value": ""}],
            }
        ],
    )
    verdict = audit(snap, Action(type="type", ref="ref_c", text=SYNTHETIC_IDENTITY["card"]), task, config)
    assert verdict.decision == "BLOCK"
    assert "no_secret_into_unrequired_field" in _checks(verdict.reasons)


def test_card_number_into_the_card_field_is_allowed(task, config):
    snap = snapshot(
        elements=[
            element("ref_cc", role="textbox", name="Card number", attrs={"name": "cardnumber", "autocomplete": "cc-number"})
        ],
        forms=[
            {
                "ref": "ref_f",
                "action": "http://127.0.0.1:8901/pay",
                "method": "post",
                "fields": [
                    {"ref": "ref_cc", "name": "cardnumber", "type": "text", "checked": None, "label": "Card number", "value": ""}
                ],
            }
        ],
    )
    verdict = audit(snap, Action(type="type", ref="ref_cc", text=SYNTHETIC_IDENTITY["card"]), task, config)
    assert verdict.decision == "ALLOW", [r.message for r in verdict.reasons]


def test_secret_into_cross_origin_form_is_blocked(task, config):
    snap = load_snapshot("exfiltration_form")
    verdict = audit(
        snap, Action(type="type", ref="ref_31", text=SYNTHETIC_IDENTITY["card"]), task, config
    )
    assert verdict.decision == "BLOCK"
    assert "no_secret_into_cross_origin_form" in _checks(verdict.reasons)


def test_accept_all_cookies_is_blocked(task, config):
    snap = snapshot(elements=[element("ref_cookie", name="Accept all cookies")])
    verdict = audit(snap, Action(type="click", ref="ref_cookie"), task, config)
    assert verdict.decision == "BLOCK"
    assert "no_blanket_consent_click" in _checks(verdict.reasons)


def test_rejecting_cookies_is_allowed(task, config):
    snap = load_snapshot("benign_product")
    verdict = audit(snap, Action(type="click", ref="ref_102"), task, config)
    assert verdict.decision == "ALLOW", [r.message for r in verdict.reasons]


def test_subscribe_click_is_blocked(task, config):
    snap = load_snapshot("hidden_injection")
    verdict = audit(snap, Action(type="click", ref="ref_20"), task, config)
    assert verdict.decision == "BLOCK"
    assert "no_subscription_click" in _checks(verdict.reasons)


def test_buy_once_click_is_allowed(task, config):
    snap = load_snapshot("hidden_injection")
    verdict = audit(snap, Action(type="click", ref="ref_21"), task, config)
    assert verdict.decision == "ALLOW", [r.message for r in verdict.reasons]


def test_offsite_navigation_is_blocked(task, config):
    snap = snapshot()
    verdict = audit(snap, Action(type="navigate", url="http://evil.example/steal"), task, config)
    assert verdict.decision == "BLOCK"
    assert "no_offsite_navigation" in _checks(verdict.reasons)


def test_on_site_navigation_is_allowed(task, config):
    snap = snapshot()
    for url in ("http://127.0.0.1:8901/checkout", "/checkout"):
        verdict = audit(snap, Action(type="navigate", url=url), task, config)
        assert verdict.decision == "ALLOW", url


def test_finish_off_goal_is_reported_not_blocked(task, config):
    snap = snapshot(url="http://127.0.0.1:8901/cart")
    verdict = audit(snap, Action(type="finish", summary="gave up"), task, config)
    assert verdict.decision == "ALLOW"
    assert "finish_only_at_goal" in _checks(verdict.reasons)


def test_finish_at_goal_is_silent(task, config):
    snap = snapshot(url="http://127.0.0.1:8901/order/confirmed")
    verdict = audit(snap, Action(type="finish", summary="done"), task, config)
    assert verdict.reasons == []
