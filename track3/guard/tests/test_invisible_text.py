"""invisible_text - every CSS technique, plus the colour maths."""

from __future__ import annotations

from guard import audit
from guard.colors import colors_indistinguishable, contrast_ratio, delta_e, parse_color
from guard.l1_structural import analyze_visibility, check_invisible_text
from guard.types import Action, Box, ComputedStyle, GuardConfig

from .conftest import DEFAULT_STYLE, element, load_snapshot, snapshot


def hidden_by_for(style, box=None, in_tree=True, cfg=None):
    snap = snapshot()
    hidden, _ev = analyze_visibility(
        Box.from_dict(box or {"x": 10, "y": 10, "w": 200, "h": 20}),
        ComputedStyle.from_dict({**DEFAULT_STYLE, **style}),
        in_tree,
        snap,
        cfg or GuardConfig(),
    )
    return hidden


# ---- positive: each technique -------------------------------------------


def test_opacity_zero():
    assert "opacity-zero" in hidden_by_for({"opacity": 0.0})


def test_font_size_zero():
    assert "font-size-zero" in hidden_by_for({"fontSize": 0})


def test_visibility_hidden_while_in_a11y_tree():
    hb = hidden_by_for({"visibility": "hidden"}, in_tree=True)
    assert "visibility-hidden" in hb and "aria-only" in hb


def test_offscreen_left():
    assert "offscreen" in hidden_by_for({}, box={"x": -9999, "y": 100, "w": 200, "h": 20})


def test_offscreen_via_transform():
    assert "offscreen" in hidden_by_for({"transform": "translate(-9999px, 0px)"})


def test_clip_path_inset_full():
    assert "clipped" in hidden_by_for({"clipPath": "inset(100%)"})


def test_clip_path_inset_halves_meet():
    assert "clipped" in hidden_by_for({"clipPath": "inset(50% 50% 50% 50%)"})


def test_legacy_clip_rect_zero():
    assert "clipped" in hidden_by_for({"clip": "rect(0px, 0px, 0px, 0px)"})


def test_zero_size_box():
    assert "zero-size" in hidden_by_for({}, box={"x": 10, "y": 10, "w": 0, "h": 0})


def test_display_none():
    assert "zero-size" in hidden_by_for({"display": "none"}, box={"x": 0, "y": 0, "w": 0, "h": 0})


def test_scale_zero():
    assert "zero-size" in hidden_by_for({"transform": "scale(0)"})


def test_colour_matches_background_is_perceptual_not_string_equality():
    # Different strings, same colour to a human eye.
    assert "color-matches-background" in hidden_by_for(
        {"color": "rgb(254, 255, 255)", "backgroundColor": "#ffffff"}
    )
    assert "color-matches-background" in hidden_by_for(
        {"color": "hsl(0, 0%, 100%)", "backgroundColor": "rgb(255,255,255)"}
    )


def test_all_five_techniques_in_one_page(task, config):
    snap = load_snapshot("hidden_injection")
    reasons = check_invisible_text(snap, Action(type="read"), task, config)
    found = set()
    for r in reasons:
        found.update(r.evidence.get("hiddenBy", []))
    for technique in ("opacity-zero", "font-size-zero", "color-matches-background", "offscreen", "clipped"):
        assert technique in found, f"{technique} not detected"


def test_acting_on_an_invisible_target_blocks(task, config):
    snap = snapshot(
        elements=[element("ref_ghost", name="Confirm", style={"opacity": 0.0})],
    )
    verdict = audit(snap, Action(type="click", ref="ref_ghost"), task, config)
    assert verdict.decision == "BLOCK"
    assert any(
        r.check == "invisible_text" and r.evidence.get("scope") == "action-target" for r in verdict.reasons
    )


def test_hidden_text_elsewhere_does_not_block_a_benign_click(task, config):
    """Crucial for the 'task completed' half of the benchmark: a page with
    hidden junk on it is still shoppable."""
    snap = load_snapshot("hidden_injection")
    verdict = audit(snap, Action(type="click", ref="ref_21"), task, config)  # "Buy once"
    assert verdict.decision == "ALLOW"
    assert any(r.check == "invisible_text" for r in verdict.reasons), "but it is still reported"


# ---- negative -----------------------------------------------------------


def test_ordinary_styling_is_clean():
    assert hidden_by_for({}) == []
    assert hidden_by_for({"color": "#111111", "backgroundColor": "#ffffff"}) == []
    assert hidden_by_for({"color": "#555555", "backgroundColor": "#f4f4f4"}) == []


def test_small_print_is_not_hidden():
    assert hidden_by_for({"fontSize": 11, "color": "#555555"}) == []


def test_scrolled_content_is_not_offscreen():
    """getBoundingClientRect is viewport-relative, so scrolled-past content has
    a negative y.  That is not the `left:-9999px` attack."""
    assert hidden_by_for({}, box={"x": 40, "y": -300, "w": 600, "h": 20}) == []
    assert hidden_by_for({}, box={"x": 40, "y": 2000, "w": 600, "h": 20}) == []


def test_transparent_background_is_unknown_not_suspicious():
    verdict, ev = colors_indistinguishable("#ffffff", "rgba(0,0,0,0)")
    assert verdict is None
    assert ev["reason"] == "background-transparent"


def test_benign_page_has_no_invisible_text_findings(task, config):
    snap = load_snapshot("benign_checkout")
    assert check_invisible_text(snap, Action(type="click", ref="ref_10"), task, config) == []


def test_colour_helpers():
    assert parse_color("#fff") == (255, 255, 255, 1.0)
    assert parse_color("rgba(0,0,0,0.5)") == (0.0, 0.0, 0.0, 0.5)
    assert parse_color("not-a-colour") is None
    assert contrast_ratio((0, 0, 0, 1.0), (255, 255, 255, 1.0)) > 20
    assert delta_e((255, 255, 255, 1.0), (255, 255, 255, 1.0)) == 0.0
