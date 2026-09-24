"""hit_test - the flagship check.  Positive, negative, and the awkward cases.

The point of the check is that it knows nothing about overlays.  These tests
therefore never mention what the covering element looks like.
"""

from __future__ import annotations

import pytest

from guard import audit
from guard.l1_structural import check_hit_test
from guard.types import Action, GuardConfig

from .conftest import element, load_snapshot, load_task, snapshot


def _checks(reasons, name):
    return [r for r in reasons if r.check == name]


# ---- positive: something is covering the target ---------------------------


def test_overlay_over_decline_button_blocks(task, config):
    snap = load_snapshot("clickjack_overlay")
    verdict = audit(snap, Action(type="click", ref="ref_12"), task, config)
    assert verdict.decision == "BLOCK"
    hits = _checks(verdict.reasons, "hit_test")
    assert hits, "hit_test must fire"
    ev = hits[0].evidence
    assert ev["expected"] == "ref_12"
    assert ev["actual"] == "ref_40"
    assert ev["point"] == [480.0, 630.0]
    assert ev["overlayConfirmedGeometrically"] is True
    assert ev["coveringZIndex"] == 9999


def test_hit_test_is_geometric_not_lexical(task, config):
    """An overlay with an innocuous label and no suspicious attributes is
    still caught: the only signal used is the coordinate."""
    snap = snapshot(
        elements=[
            element("ref_a", name="Continue", box={"x": 0, "y": 0, "w": 100, "h": 50}, hit="ref_b"),
            element(
                "ref_b",
                role="generic",
                name="Trusted content",
                box={"x": 0, "y": 0, "w": 100, "h": 50},
                style={"opacity": 1.0, "zIndex": 5},
            ),
        ]
    )
    reasons = check_hit_test(snap, Action(type="click", ref="ref_a"), load_task(), GuardConfig())
    assert [r.severity for r in reasons] == ["high"]


def test_type_into_covered_input_is_caught(task, config):
    snap = snapshot(
        elements=[
            element("ref_i", role="textbox", name="Email", hit="ref_ov"),
            element("ref_ov", role="generic", name="", style={"opacity": 0.0, "zIndex": 10}),
        ]
    )
    reasons = check_hit_test(snap, Action(type="type", ref="ref_i", text="x@y.invalid"), task, config)
    assert reasons and reasons[0].severity == "high"


def test_pointer_events_none_target_is_flagged(task, config):
    snap = snapshot(elements=[element("ref_p", style={"pointerEvents": "none"})])
    reasons = check_hit_test(snap, Action(type="click", ref="ref_p"), task, config)
    assert any(r.evidence.get("pointerEvents") == "none" for r in reasons)


def test_unknown_covering_element_fails_closed(task, config):
    """elementFromPoint returned a ref that is not in the snapshot at all.
    That is an element the extractor never listed - fail closed."""
    snap = snapshot(elements=[element("ref_x", hit="ref_ghost")])
    reasons = check_hit_test(snap, Action(type="click", ref="ref_x"), task, config)
    assert reasons[0].severity == "high"
    assert reasons[0].evidence["coveringElement"].startswith("not present")


# ---- negative: ordinary pages must not trip it ----------------------------


def test_child_span_inside_button_is_allowed(task, config):
    """The single most likely false positive: elementFromPoint returns the
    <span> inside the <button>."""
    snap = load_snapshot("benign_checkout")
    reasons = check_hit_test(snap, Action(type="click", ref="ref_10"), task, config)
    assert reasons == []


def test_descendant_via_parent_chain_is_allowed(task, config):
    snap = snapshot(
        elements=[
            element("ref_btn", hit="ref_deep"),
            element("ref_mid", parentRef="ref_btn"),
            element("ref_deep", parentRef="ref_mid"),
        ]
    )
    assert check_hit_test(snap, Action(type="click", ref="ref_btn"), task, config) == []


def test_self_hit_is_allowed(task, config):
    snap = snapshot(elements=[element("ref_ok")])
    assert check_hit_test(snap, Action(type="click", ref="ref_ok"), task, config) == []


def test_missing_hit_test_data_is_silent(task, config):
    """No data is not evidence.  An extractor that cannot compute hitTestRef
    must not cause a page-wide block."""
    el = element("ref_nohit")
    el["hitTestRef"] = None
    snap = snapshot(elements=[el])
    assert check_hit_test(snap, Action(type="click", ref="ref_nohit"), task, config) == []


def test_non_interactive_actions_skip_the_check(task, config):
    snap = load_snapshot("clickjack_overlay")
    assert check_hit_test(snap, Action(type="read"), task, config) == []
    assert check_hit_test(snap, Action(type="finish", summary="done"), task, config) == []


def test_unknown_ancestry_can_be_configured_to_warn(task):
    """A third-party extractor without ancestry data can opt into warn-only."""
    snap = snapshot(
        elements=[
            element("ref_x", hit="ref_y", box={"x": 0, "y": 0, "w": 100, "h": 40}),
            # geometry does NOT confirm an overlay: the hit element is elsewhere
            element("ref_y", box={"x": 600, "y": 600, "w": 10, "h": 10}),
        ]
    )
    strict = check_hit_test(snap, Action(type="click", ref="ref_x"), load_task(), GuardConfig())
    lenient = check_hit_test(
        snap,
        Action(type="click", ref="ref_x"),
        load_task(),
        GuardConfig(hit_test_unknown_ancestry_blocks=False),
    )
    assert strict[0].severity == "high"
    assert lenient[0].severity == "medium"
