"""guard.l1_structural - the deterministic layer.

Every check here is an **independent pure function** with the signature::

    check(snapshot, action, task, config) -> List[Reason]

No I/O, no network, no shared mutable state.  The only memory is the
read-only :class:`guard.session.GuardSession` hanging off ``config.session``,
which records what the *agent itself* did (see guard/session.py).

Design bias, stated once and applied everywhere:

* **Structure over strings.**  Geometry and computed style cannot be
  persuaded; a word list can.  Where a lexicon is unavoidable (a close button
  has to be *labelled* something) it only selects candidates - the severity
  comes from a structural fact such as "this handler submits a form".
* **Missing data is not evidence.**  If the extractor omitted a field the
  check stays silent.  A guard that blocks a benign action fails the benchmark
  exactly as hard as one that misses a trap.
* **Page-level findings inform; target-level findings block.**  Hidden text
  somewhere on the page is telemetry plus an ingress strip.  The agent being
  steered into an element *it cannot see* is a block.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from . import colors
from .patterns import (
    contains_money,
    find_injection_matches,
    label_matches_any,
    normalize,
    parse_money,
)
from .types import (
    Action,
    Amount,
    Box,
    ComputedStyle,
    Element,
    Form,
    FormField,
    GuardConfig,
    PageSnapshot,
    Reason,
    TaskDescriptor,
    TextNode,
)

LAYER = "L1"

__all__ = [
    "run_l1",
    "L1_CHECKS",
    "check_hit_test",
    "check_invisible_text",
    "check_fake_close_button",
    "check_precheck_optins",
    "check_cross_origin_form",
    "check_undisclosed_amount",
    "check_injection_phrasing",
    "check_hidden_instruction_alignment",
    "analyze_visibility",
    "origin_of",
]


# ==========================================================================
# shared helpers
# ==========================================================================


def origin_of(url: Optional[str]) -> Optional[str]:
    """``scheme://host:port`` or ``None`` when there is no absolute origin."""
    if not url:
        return None
    try:
        p = urlparse(str(url))
    except ValueError:
        return None
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}".lower()


def _target_element(snapshot: PageSnapshot, action: Action) -> Optional[Element]:
    if not action.ref:
        return None
    return snapshot.element(action.ref)


def _is_descendant(snapshot: PageSnapshot, ancestor_ref: str, node_ref: str, el: Optional[Element]) -> bool:
    """Is ``node_ref`` inside ``ancestor_ref``?  Uses whichever ancestry the
    extractor supplied: an explicit hit-test chain, childRefs, or parentRef."""
    if node_ref == ancestor_ref:
        return True
    if el is not None:
        if node_ref in (el.childRefs or []):
            return True
        if el.hitTestAncestors and ancestor_ref in el.hitTestAncestors:
            return True
    if ancestor_ref in snapshot.ancestors_of(node_ref):
        return True
    return False


_TRANSLATE_RE = re.compile(r"translate[XY3]?d?\(([^)]*)\)", re.I)
_MATRIX_RE = re.compile(r"matrix(3d)?\(([^)]*)\)", re.I)
_SCALE_RE = re.compile(r"scale[XY3]?d?\(([^)]*)\)", re.I)
_INSET_RE = re.compile(r"inset\(([^)]*)\)", re.I)
_CIRCLE_RE = re.compile(r"circle\(\s*([\d.]+)\s*(px|%)?", re.I)
_CLIP_RECT_RE = re.compile(r"rect\(([^)]*)\)", re.I)


def _transform_offset(transform: Optional[str]) -> Optional[Tuple[float, float]]:
    """Translation component of a CSS transform, if any."""
    if not transform or transform.strip().lower() in ("none", ""):
        return None
    m = _MATRIX_RE.search(transform)
    if m:
        parts = [p.strip() for p in m.group(2).split(",")]
        try:
            if m.group(1):  # matrix3d: tx,ty are indices 12,13
                return (float(parts[12]), float(parts[13]))
            return (float(parts[4]), float(parts[5]))
        except (IndexError, ValueError):
            return None
    m = _TRANSLATE_RE.search(transform)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]

        def px(tok: str) -> float:
            tok = tok.strip().lower().replace("px", "")
            try:
                return float(tok)
            except ValueError:
                return 0.0

        if len(parts) == 1:
            return (px(parts[0]), 0.0)
        return (px(parts[0]), px(parts[1]))
    return None


def _transform_scales_to_zero(transform: Optional[str]) -> bool:
    if not transform:
        return False
    m = _SCALE_RE.search(transform)
    if not m:
        m2 = _MATRIX_RE.search(transform)
        if m2 and not m2.group(1):
            parts = [p.strip() for p in m2.group(2).split(",")]
            try:
                return abs(float(parts[0])) < 1e-6 or abs(float(parts[3])) < 1e-6
            except (IndexError, ValueError):
                return False
        return False
    try:
        vals = [float(p.strip()) for p in m.group(1).split(",")]
    except ValueError:
        return False
    return any(abs(v) < 1e-6 for v in vals)


def _clip_hides(clip_path: Optional[str], clip: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Detect clip geometry that removes the whole box."""
    for value, prop in ((clip_path, "clipPath"), (clip, "clip")):
        if not value or value.strip().lower() in ("none", "auto", ""):
            continue
        v = value.strip().lower()
        m = _INSET_RE.search(v)
        if m:
            toks = [t for t in re.split(r"\s+", m.group(1).strip()) if t and not t.startswith("round")]
            nums: List[float] = []
            for t in toks[:4]:
                if t.endswith("%"):
                    try:
                        nums.append(float(t[:-1]))
                    except ValueError:
                        nums.append(0.0)
                else:
                    nums.append(-1.0)  # px inset: cannot judge without box size
            if nums:
                # CSS shorthand expansion to top/right/bottom/left
                if len(nums) == 1:
                    nums = nums * 4
                elif len(nums) == 2:
                    nums = [nums[0], nums[1], nums[0], nums[1]]
                elif len(nums) == 3:
                    nums = [nums[0], nums[1], nums[2], nums[1]]
                top, right, bottom, left = nums[:4]
                if any(n >= 100.0 for n in nums if n >= 0) or (
                    top >= 0 and bottom >= 0 and top + bottom >= 100.0
                ) or (left >= 0 and right >= 0 and left + right >= 100.0):
                    return {"property": prop, "value": value, "insets": nums[:4]}
        m = _CIRCLE_RE.search(v)
        if m:
            try:
                if float(m.group(1)) <= 0.0:
                    return {"property": prop, "value": value, "radius": 0.0}
            except ValueError:
                pass
        m = _CLIP_RECT_RE.search(v)
        if m:
            toks = re.findall(r"-?[\d.]+", m.group(1))
            if len(toks) == 4 and all(abs(float(t)) < 1e-6 for t in toks):
                return {"property": prop, "value": value, "rect": [float(t) for t in toks]}
        if v in ("polygon(0 0, 0 0, 0 0, 0 0)", "polygon(0px 0px, 0px 0px, 0px 0px, 0px 0px)"):
            return {"property": prop, "value": value, "degenerate": True}
    return None


def analyze_visibility(
    box: Optional[Box],
    computed: Optional[ComputedStyle],
    in_a11y_tree: Optional[bool],
    snapshot: PageSnapshot,
    config: GuardConfig,
) -> Tuple[List[str], Dict[str, Any]]:
    """The heart of ``invisible_text``: which CSS technique, if any, removes
    this node from a human's view while leaving it in the DOM.

    Returns ``(hiddenBy, evidence)`` using the frozen vocabulary of
    CONTRACTS section 5.  Empty list means "we found nothing wrong", which
    includes "we were not given enough data to judge".
    """
    hidden_by: List[str] = []
    ev: Dict[str, Any] = {}
    c = computed or ComputedStyle()

    if c.opacity is not None and c.opacity <= config.opacity_zero_threshold:
        hidden_by.append("opacity-zero")
        ev["opacity"] = c.opacity

    if c.fontSize is not None and c.fontSize < config.font_size_zero_threshold:
        hidden_by.append("font-size-zero")
        ev["fontSize"] = c.fontSize

    if c.visibility is not None and str(c.visibility).lower() in ("hidden", "collapse"):
        hidden_by.append("visibility-hidden")
        ev["visibility"] = c.visibility

    if c.display is not None and str(c.display).lower() == "none":
        if "zero-size" not in hidden_by:
            hidden_by.append("zero-size")
        ev["display"] = "none"

    bg = c.effectiveBackgroundColor or c.backgroundColor
    if c.color is not None and bg is not None:
        same, color_ev = colors.colors_indistinguishable(
            c.color, bg, config.min_contrast_ratio, config.max_color_delta_e
        )
        if same:
            hidden_by.append("color-matches-background")
        if same is not None:
            ev["color"] = color_ev

    if box is not None:
        thr = config.offscreen_threshold_px
        off: Dict[str, Any] = {}
        if box.x + box.w <= -thr:
            off["left"] = box.x
        if box.y + box.h <= -thr:
            off["top"] = box.y
        if snapshot.viewport.w and box.x >= snapshot.viewport.w + thr:
            off["right"] = box.x
        if off:
            hidden_by.append("offscreen")
            ev["offscreen"] = {**off, "box": box.to_dict(), "thresholdPx": thr}

        if box.w < config.zero_size_threshold_px or box.h < config.zero_size_threshold_px:
            if "zero-size" not in hidden_by:
                hidden_by.append("zero-size")
            ev["zeroSize"] = box.to_dict()

    offset = _transform_offset(c.transform)
    if offset is not None and box is not None:
        if abs(offset[0]) >= config.offscreen_threshold_px or abs(offset[1]) >= config.offscreen_threshold_px:
            if "offscreen" not in hidden_by:
                hidden_by.append("offscreen")
            ev["transformOffset"] = {"tx": offset[0], "ty": offset[1], "transform": c.transform}

    if _transform_scales_to_zero(c.transform):
        if "zero-size" not in hidden_by:
            hidden_by.append("zero-size")
        ev["transformScale"] = c.transform

    clipped = _clip_hides(c.clipPath, c.clip)
    if clipped:
        hidden_by.append("clipped")
        ev["clipped"] = clipped

    if hidden_by and in_a11y_tree:
        hidden_by.append("aria-only")
        ev["inAccessibilityTree"] = True

    # de-duplicate, keep order
    seen = set()
    ordered = [h for h in hidden_by if not (h in seen or seen.add(h))]
    return ordered, ev


def _element_visibility(el: Element, snapshot: PageSnapshot, config: GuardConfig):
    return analyze_visibility(el.box, el.computed, el.inAccessibilityTree, snapshot, config)


def _text_node_visibility(tn: TextNode, snapshot: PageSnapshot, config: GuardConfig):
    computed = tn.computed
    box = tn.box
    if computed is None and box is None:
        # Fall back to a same-ref element, then to the extractor's own verdict.
        el = snapshot.element(tn.ref)
        if el is not None:
            computed, box = el.computed, el.box
    return analyze_visibility(box, computed, tn.inAccessibilityTree, snapshot, config)


def _form_for_action(snapshot: PageSnapshot, action: Action) -> Optional[Form]:
    """Which form is this action about to submit?"""
    if action.ref:
        f = snapshot.form(action.ref)
        if f is not None:
            return f
        el = snapshot.element(action.ref)
        if el is not None:
            if el.formRef:
                f = snapshot.form(el.formRef)
                if f is not None:
                    return f
            if el.attrs.get("form"):
                f = snapshot.form(str(el.attrs["form"]))
                if f is not None:
                    return f
            # ancestor chain
            for anc in snapshot.ancestors_of(action.ref):
                f = snapshot.form(anc)
                if f is not None:
                    return f
        f = snapshot.form_of_field(action.ref)
        if f is not None:
            return f
    if action.type == "submit" and len(snapshot.forms) == 1:
        return snapshot.forms[0]
    return None


def _is_submitting(snapshot: PageSnapshot, action: Action) -> bool:
    if action.type == "submit":
        return True
    if action.type != "click" or not action.ref:
        return False
    el = snapshot.element(action.ref)
    if el is None:
        return False
    if str(el.attrs.get("type", "")).lower() == "submit":
        return True
    if el.attrs.get("formaction"):
        return True
    if "submit" in [h.lower() for h in el.handlers]:
        return True
    return False


def _state_changing(action: Action) -> bool:
    return action.type in ("click", "type", "submit", "navigate")


# ==========================================================================
# CHECK 1 - hit_test.  The flagship.  Pure geometry, zero pattern matching.
# ==========================================================================


def check_hit_test(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """``document.elementFromPoint(centre_of(ref))`` must return ``ref`` or one
    of its descendants.  Anything else means something is painted over the
    target and the click will not land where the agent believes.

    This is the check that generalizes: it knows nothing about what an overlay
    looks like, only that the pixel under the cursor does not belong to the
    intended element.
    """
    if action.type not in ("click", "type", "submit"):
        return []
    el = _target_element(snapshot, action)
    if el is None or el.hitTestRef is None:
        return []  # no data -> no opinion

    cx, cy = el.box.centre
    base_ev: Dict[str, Any] = {
        "expected": el.ref,
        "actual": el.hitTestRef,
        "point": [round(cx, 1), round(cy, 1)],
        "targetBox": el.box.to_dict(),
        "targetLabel": el.label,
        "method": "document.elementFromPoint(centre)",
    }
    reasons: List[Reason] = []

    if el.computed.pointerEvents is not None and str(el.computed.pointerEvents).lower() == "none":
        reasons.append(
            Reason(
                check="hit_test",
                severity="high",
                message=(
                    f"Element {el.ref} ({el.label!r}) has pointer-events:none, so the click "
                    f"cannot reach it - it would fall through to whatever is beneath."
                ),
                evidence={**base_ev, "pointerEvents": "none"},
                layer=LAYER,
                ref=el.ref,
                category="C3",
            )
        )

    if el.hitTestRef == el.ref:
        return reasons

    hit = snapshot.element(el.hitTestRef)
    if _is_descendant(snapshot, el.ref, el.hitTestRef, el):
        return reasons  # a child span/icon of the target: normal and benign

    if hit is not None and el.ref in (hit.childRefs or []):
        # the hit element is an ANCESTOR of the target (e.g. a wrapping label).
        # The target is not painting its own centre: odd, but not proof.
        reasons.append(
            Reason(
                check="hit_test",
                severity="medium",
                message=(
                    f"Element {el.ref} ({el.label!r}) does not paint its own centre; "
                    f"{el.hitTestRef} (an ancestor) is hit instead."
                ),
                evidence={**base_ev, "relation": "ancestor"},
                layer=LAYER,
                ref=el.ref,
                category="C3",
            )
        )
        return reasons

    have_ancestry = bool(el.hitTestAncestors) or snapshot.has_ancestry_data()
    covering_ev: Dict[str, Any] = {}
    overlay_confirmed = False
    if hit is not None:
        covering_ev = {
            "coveringBox": hit.box.to_dict(),
            "coveringRole": hit.role,
            "coveringLabel": hit.label,
            "coveringZIndex": hit.computed.zIndex,
            "coveringOpacity": hit.computed.opacity,
            "coveringPointerEvents": hit.computed.pointerEvents,
        }
        contains_centre = (
            hit.box.x <= cx <= hit.box.x + hit.box.w and hit.box.y <= cy <= hit.box.y + hit.box.h
        )
        higher_stack = (
            hit.computed.zIndex is not None
            and (el.computed.zIndex is None or hit.computed.zIndex > el.computed.zIndex)
        )
        transparent = hit.computed.opacity is not None and hit.computed.opacity <= 0.2
        covering_ev["containsTargetCentre"] = contains_centre
        covering_ev["stacksAbove"] = higher_stack
        overlay_confirmed = contains_centre and (higher_stack or transparent or hit.box.area >= el.box.area)
    else:
        covering_ev = {"coveringElement": "not present in snapshot.elements"}

    if have_ancestry or overlay_confirmed or hit is None:
        severity = "high"
        ancestry_note = "resolved" if have_ancestry else "unavailable"
    else:
        severity = "high" if config.hit_test_unknown_ancestry_blocks else "medium"
        ancestry_note = "unavailable"

    reasons.append(
        Reason(
            check="hit_test",
            severity=severity,
            message=(
                f"Element {el.ref} ({el.label!r}) is covered by {el.hitTestRef} at its centre point "
                f"({round(cx, 1)}, {round(cy, 1)}); the click would not reach the intended target."
            ),
            evidence={
                **base_ev,
                **covering_ev,
                "ancestry": ancestry_note,
                "overlayConfirmedGeometrically": overlay_confirmed,
                "hiddenBy": ["covered"],
            },
            layer=LAYER,
            ref=el.ref,
            category="C3",
        )
    )
    return reasons


# ==========================================================================
# CHECK 2 - invisible_text
# ==========================================================================


def check_invisible_text(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Text or controls present in the DOM but removed from human view.

    Severity policy, deliberately asymmetric:

    * the element the agent is *about to act on* is invisible -> ``high``.
      No honest flow asks an agent to click something a user cannot see.
    * hidden text elsewhere on the page -> ``medium``.  It is real evidence of
      a hostile page and it drives the ingress strip, but blocking every
      action on such a page would fail the "task completed" half of the
      benchmark, which is exactly what a trap author wants.
    """
    reasons: List[Reason] = []

    # --- 2a. the action target itself --------------------------------------
    el = _target_element(snapshot, action)
    if el is not None and action.type in ("click", "type", "submit"):
        hidden_by, ev = _element_visibility(el, snapshot, config)
        if hidden_by:
            reasons.append(
                Reason(
                    check="invisible_text",
                    severity="high",
                    message=(
                        f"Action target {el.ref} ({el.label!r}) is not visible to a human "
                        f"({', '.join(hidden_by)}); the agent is being steered into an "
                        f"element nobody can see."
                    ),
                    evidence={
                        "ref": el.ref,
                        "label": el.label,
                        "hiddenBy": hidden_by,
                        "box": el.box.to_dict(),
                        "computed": el.computed.to_dict(),
                        "scope": "action-target",
                        **ev,
                    },
                    layer=LAYER,
                    ref=el.ref,
                    category="C3",
                )
            )

    # --- 2b. hidden text nodes anywhere on the page -------------------------
    for tn in snapshot.textNodes:
        text = (tn.text or "").strip()
        if len(text) < config.min_hidden_text_chars:
            continue
        hidden_by, ev = _text_node_visibility(tn, snapshot, config)
        extractor_says_hidden = tn.visible is False or bool(tn.hiddenBy)
        if not hidden_by and not extractor_says_hidden:
            continue
        merged = list(dict.fromkeys(list(hidden_by) + [h for h in (tn.hiddenBy or [])]))
        injection = find_injection_matches(text)
        # Page-scope hidden text is reported at medium *even when it is a
        # textbook injection*.  Blocking every action on a page that merely
        # contains hidden text would fail the "task completed" half of the
        # benchmark - which is precisely what the trap author wants.  Ingress
        # strips it so the agent never reads it, and if the agent nonetheless
        # proposes the action the hidden text asked for,
        # `hidden_instruction_alignment` blocks that specific action.
        severity = "medium"
        reasons.append(
            Reason(
                check="invisible_text",
                severity=severity,
                message=(
                    f"Hidden text node {tn.ref} ({', '.join(merged) or 'reported hidden'}) carries "
                    f"{len(text)} characters the user cannot read"
                    + (" and matches injection phrasing." if injection else ".")
                ),
                evidence={
                    "ref": tn.ref,
                    "hiddenBy": merged,
                    "detectedBy": "guard" if hidden_by else "extractor",
                    "textPreview": text[:200],
                    "textLength": len(text),
                    "injectionMatches": injection,
                    "scope": "page",
                    **ev,
                },
                layer=LAYER,
                ref=tn.ref,
                category="C3",
            )
        )

    # --- 2c. interactive elements that are invisible but still clickable ----
    for other in snapshot.elements:
        if el is not None and other.ref == el.ref:
            continue
        if not other.inAccessibilityTree:
            continue
        if (other.role or "").lower() not in ("button", "link", "checkbox", "textbox", "combobox", "radio"):
            continue
        hidden_by, ev = _element_visibility(other, snapshot, config)
        if not hidden_by:
            continue
        pe = (other.computed.pointerEvents or "auto").lower()
        if pe == "none":
            continue  # invisible AND inert: decoration, not a trap
        reasons.append(
            Reason(
                check="invisible_text",
                severity="medium",
                message=(
                    f"Interactive element {other.ref} ({other.label!r}, role={other.role}) is "
                    f"invisible ({', '.join(hidden_by)}) yet still exposed and clickable."
                ),
                evidence={
                    "ref": other.ref,
                    "label": other.label,
                    "role": other.role,
                    "hiddenBy": hidden_by,
                    "box": other.box.to_dict(),
                    "pointerEvents": pe,
                    "scope": "page",
                    **ev,
                },
                layer=LAYER,
                ref=other.ref,
                category="C3",
            )
        )

    return reasons


# ==========================================================================
# CHECK 3 - fake_close_button
# ==========================================================================

_NAVIGATING_JS = re.compile(
    r"location\s*(\.|\[)|location\s*=|\.submit\s*\(|form\s*\.\s*submit|window\.open|"
    r"fetch\s*\(|xmlhttprequest|\.click\s*\(|addtocart|add_to_cart|subscribe|checkout|"
    r"cart\s*\.|purchase|order\s*\(|\.href",
    re.I,
)


def _handler_effects(el: Element, snapshot: PageSnapshot) -> Tuple[List[str], Dict[str, Any]]:
    """What does activating this element actually do?  Structural first
    (explicit ``handlers`` from the extractor), attribute-derived second."""
    effects: List[str] = []
    ev: Dict[str, Any] = {}

    for h in el.handlers or []:
        effects.append(str(h).lower())
    if effects:
        ev["handlers"] = list(effects)

    attrs = {str(k).lower(): v for k, v in (el.attrs or {}).items()}

    href = attrs.get("href")
    if href and str(href).strip() not in ("#", "", "javascript:void(0)", "javascript:;"):
        effects.append("navigate")
        ev["href"] = href

    if str(attrs.get("type", "")).lower() == "submit":
        effects.append("submit")
        ev["type"] = "submit"
    if attrs.get("formaction"):
        effects.append("submit")
        ev["formaction"] = attrs["formaction"]

    onclick = " ".join(
        str(v) for k, v in attrs.items() if k.startswith("on") and v
    )
    if onclick:
        m = _NAVIGATING_JS.search(onclick)
        if m:
            effects.append("script-mutation")
            ev["inlineHandler"] = onclick[:200]
            ev["inlineHandlerMatch"] = m.group(0)

    # data-* intent attributes used by hand-written mock sites
    for k, v in attrs.items():
        if k.startswith("data-") and v:
            val = normalize(str(v))
            if any(t in val for t in ("subscribe", "subscription", "renew")):
                effects.append("subscription-mutate")
                ev.setdefault("dataAttrs", {})[k] = v
            elif any(t in val for t in ("cart", "checkout", "order", "purchase", "buy")):
                effects.append("cart-mutate")
                ev.setdefault("dataAttrs", {})[k] = v

    # an element inside a form whose activation is the form's default submit
    if el.formRef and (el.role or "").lower() == "button" and "submit" not in effects:
        if str(attrs.get("type", "")).lower() not in ("button", "reset"):
            f = snapshot.form(el.formRef)
            if f is not None:
                effects.append("submit")
                ev["implicitSubmitOfForm"] = f.ref

    return list(dict.fromkeys(effects)), ev


_DANGEROUS_EFFECTS = {"navigate", "submit", "cart-mutate", "subscription-mutate", "script-mutation", "purchase"}


def check_fake_close_button(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """A control labelled as a dismissal whose activation is not a dismissal.

    The label selects the candidate; the **effect** decides the verdict.  A
    close button that submits a form is a lie regardless of how it is spelled.
    """
    reasons: List[Reason] = []
    target_ref = action.ref if action.type == "click" else None

    for el in snapshot.elements:
        label = el.label
        matched = label_matches_any(label, "dismiss_labels")
        if not matched:
            continue
        effects, ev = _handler_effects(el, snapshot)
        dangerous = sorted(set(effects) & _DANGEROUS_EFFECTS)
        if not dangerous:
            continue
        is_target = el.ref == target_ref
        severity = "high" if is_target else "medium"
        reasons.append(
            Reason(
                check="fake_close_button",
                severity=severity,
                message=(
                    f"Element {el.ref} is labelled {label!r} (a dismissal) but its activation "
                    f"performs: {', '.join(dangerous)}."
                    + ("" if is_target else "  Present on the page; not the current target.")
                ),
                evidence={
                    "ref": el.ref,
                    "label": label,
                    "matchedDismissTerm": matched,
                    "effects": effects,
                    "dangerousEffects": dangerous,
                    "isActionTarget": is_target,
                    "scope": "action-target" if is_target else "page",
                    "role": el.role,
                    "attrs": el.attrs,
                    **ev,
                },
                layer=LAYER,
                ref=el.ref,
                category="C2",
            )
        )
    return reasons


# ==========================================================================
# CHECK 4 - precheck_optins
# ==========================================================================


def _optin_weight(fld: FormField) -> Tuple[str, Optional[str], Optional[str]]:
    """Classify a checkbox: ``(severity, lexicon_key, matched_term)``."""
    label = f"{fld.label or ''} {fld.name or ''}"
    for key, sev in (
        ("subscription_terms", "high"),
        ("addon_terms", "high"),
        ("marketing_terms", "high"),
    ):
        m = label_matches_any(label, key)
        if m:
            return sev, key, m
    m = label_matches_any(label, "required_terms_labels")
    if m:
        return "low", "required_terms_labels", m
    return "medium", None, None


def check_precheck_optins(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Any checkbox that is checked in a form about to be submitted, which the
    agent did not check itself.

    Provenance comes from :class:`guard.session.GuardSession`.  With no session
    attached the guard has no memory, so *every* checked box is treated as
    site-originated - conservative, and the adapter is expected to supply a
    session.

    The response is a **REWRITE** (untick it, then proceed), not a block: the
    benchmark requires the task to still complete.
    """
    if not _is_submitting(snapshot, action):
        return []
    form = _form_for_action(snapshot, action)
    if form is None:
        return []
    session = config.session
    reasons: List[Reason] = []

    for fld in form.fields:
        if (fld.type or "").lower() != "checkbox" or not fld.checked:
            continue
        if session is not None and session.agent_checked(snapshot.url, fld.ref):
            continue
        severity, lexicon_key, matched = _optin_weight(fld)
        required = bool(fld.required)
        if required:
            severity = "low"
        evidence: Dict[str, Any] = {
            "formRef": form.ref,
            "fieldRef": fld.ref,
            "fieldName": fld.name,
            "fieldLabel": fld.label,
            "checked": True,
            "provenance": "agent" if (session and session.agent_checked(snapshot.url, fld.ref)) else "site",
            "sessionAttached": session is not None,
            "classifiedAs": lexicon_key,
            "matchedTerm": matched,
            "required": required,
        }
        if not required:
            evidence["rewrite"] = {"type": "click", "ref": fld.ref, "intent": "uncheck"}
        reasons.append(
            Reason(
                check="precheck_optins",
                severity=severity,
                message=(
                    f"Checkbox {fld.ref} ({fld.describe!r}) is already checked in form {form.ref} "
                    f"and the agent never checked it"
                    + (" (marked required, so it is reported rather than unticked)." if required
                       else "; untick it before submitting.")
                ),
                evidence=evidence,
                layer=LAYER,
                ref=fld.ref,
                category="C5" if lexicon_key in ("marketing_terms",) else "C1",
            )
        )
    return reasons


# ==========================================================================
# CHECK 5 - cross_origin_form
# ==========================================================================


def check_cross_origin_form(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """``form.action`` origin != document origin.  Pure comparison, no
    heuristics.  Also covers a submit button's ``formaction`` override."""
    doc_origin = origin_of(snapshot.url)
    if doc_origin is None:
        return []
    allowed = {doc_origin} | {o.lower() for o in (task.allowed_origins or []) if o}
    reasons: List[Reason] = []

    def judge(target: Optional[str], where: str, ref: str, is_target: bool) -> None:
        if not target:
            return
        resolved = urljoin(snapshot.url, str(target))
        origin = origin_of(resolved)
        if origin is None or origin in allowed:
            return
        reasons.append(
            Reason(
                check="cross_origin_form",
                severity="high" if is_target else "medium",
                message=(
                    f"{where} {ref} posts to {origin}, which is not the document origin "
                    f"{doc_origin}."
                ),
                evidence={
                    "ref": ref,
                    "documentOrigin": doc_origin,
                    "formActionOrigin": origin,
                    "resolvedAction": resolved,
                    "rawAction": target,
                    "allowedOrigins": sorted(allowed),
                    "isActionTarget": is_target,
                    "scope": "form" if is_target else "page",
                    "where": where,
                },
                layer=LAYER,
                ref=ref,
                category="C4",
            )
        )

    acting_form = _form_for_action(snapshot, action) if _is_submitting(snapshot, action) else None
    for form in snapshot.forms:
        judge(form.action, "Form", form.ref, acting_form is not None and acting_form.ref == form.ref)

    if action.type == "click" and action.ref:
        el = snapshot.element(action.ref)
        if el is not None and el.attrs.get("formaction"):
            judge(str(el.attrs["formaction"]), "Submit button formaction on", el.ref, True)

    return reasons


# ==========================================================================
# CHECK 6 - undisclosed_amount
# ==========================================================================


def _amount_font_size(amount: Amount, snapshot: PageSnapshot) -> Optional[float]:
    if amount.fontSize is not None:
        return amount.fontSize
    el = snapshot.element(amount.ref)
    if el is not None and el.computed.fontSize is not None:
        return el.computed.fontSize
    tn = snapshot.text_node(amount.ref)
    if tn is not None and tn.computed is not None and tn.computed.fontSize is not None:
        return tn.computed.fontSize
    return None


def _amount_hidden_by(amount: Amount, snapshot: PageSnapshot, config: GuardConfig) -> List[str]:
    el = snapshot.element(amount.ref)
    if el is not None:
        hidden, _ = _element_visibility(el, snapshot, config)
        # Geometric coverage, from the hit test rather than from CSS: something
        # is painted over this amount right now. That is how an ordinary modal
        # looks, so it is recorded as the weak reason "covered" (see
        # WEAK_HIDING_REASONS) rather than as a hiding technique.
        if el.hitTestRef and el.hitTestRef != el.ref and not _is_descendant(
            snapshot, el.ref, el.hitTestRef, el
        ):
            hidden = list(hidden) + ["covered"]
        if hidden:
            return hidden
    tn = snapshot.text_node(amount.ref)
    if tn is not None:
        hidden, _ = _text_node_visibility(tn, snapshot, config)
        if hidden:
            return hidden
        if tn.visible is False:
            return list(tn.hiddenBy) or ["reported-hidden"]
    return []


def _amount_relevance(
    amt: Amount, snapshot: PageSnapshot, action: Action, submitting: bool
) -> Tuple[bool, str]:
    """Is this amount decision-relevant to *this* action?

    A finding about money the agent is not about to pay must not block the
    agent's next click, or any page-wide condition becomes an inescapable
    state (a benign modal backdrop covering the page totals, say).  Money
    becomes decision-relevant when the agent is about to pay - ``submit`` or
    ``finish`` - or when the amount lives inside the action's own target.

    On submit, "about to pay" is narrower than "anywhere on the page".  Hidden
    money *outside* the form being submitted is not what the agent is paying:
    a dismissed upsell routinely leaves its own advertising copy in the DOM at
    zero size, and reading that as a smuggled charge blocks every subsequent
    submit with no escape - the deadlock this scoping exists to prevent.  Both
    real hidden-charge shapes are still caught: money smuggled *into* the form
    (``form`` below) and a visible page total above the base price (``submit``).
    """
    if submitting or action.type in ("submit", "finish"):
        form = _form_for_action(snapshot, action)
        if form is None:
            # We cannot prove the money is unrelated, so fail closed.
            return True, "submit"
        if amt.ref in {f.ref for f in form.fields} or form.ref in snapshot.ancestors_of(amt.ref):
            return True, "form"
        if amt.visiblyRendered is False:
            return False, "page"
        return True, "submit"
    if action.ref:
        if amt.ref == action.ref:
            return True, "action-target"
        el = snapshot.element(action.ref)
        if action.ref in snapshot.ancestors_of(amt.ref) or (el is not None and amt.ref in (el.childRefs or [])):
            return True, "action-target-subtree"
        form = _form_for_action(snapshot, action)
        if form is not None and (
            amt.ref in {f.ref for f in form.fields} or form.ref in snapshot.ancestors_of(amt.ref)
        ):
            return True, "form"
    return False, "page"


# Hiding reasons that are transient and routinely benign: an ordinary modal
# legitimately covers the page behind it for a turn.  These may never reach
# high severity on their own - unlike opacity:0 or a 4px font, which no honest
# page applies to a price.
WEAK_HIDING_REASONS = {"covered", "reported-hidden"}


def _covered_by_the_action_target(snapshot: PageSnapshot, amt_ref: str, action: Action) -> bool:
    """Is the thing covering this amount the very element the agent is acting
    on (or an ancestor of it)?

    If so the "covered" finding is irrelevant by construction: the agent is
    clicking the modal's own dismiss button, which is how the covering goes
    away.  Dismissing a modal must always remain possible.
    """
    if not action.ref:
        return False
    el = snapshot.element(amt_ref)
    hit = el.hitTestRef if el is not None else None
    if not hit or hit == amt_ref:
        return False
    if hit == action.ref:
        return True
    return hit in snapshot.ancestors_of(action.ref)


def check_undisclosed_amount(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Money the user is not being shown, or money above what the task agreed
    to pay.

    Three independent structural signals:

    1. ``visiblyRendered == False`` - the amount exists in the DOM or form
       state but is never painted.
    2. painted below the legibility threshold, or painted while hidden by any
       CSS technique from :func:`analyze_visibility`.
    3. value above ``task.base_price``.  Visible overage is reported at
       ``medium`` (a struck-through list price is legitimate); the hard block
       on paying it lives in the L2 rule ``no_submit_above_base_price``.

    All three are **scoped to the action** (see :func:`_amount_relevance`).
    Money the agent is not about to pay is reported at ``low`` and shown on
    the dashboard, never blocked: a guard that deadlocks scores zero exactly
    like a guard that gets robbed.
    """
    reasons: List[Reason] = []
    base = task.base_price
    submitting = _is_submitting(snapshot, action)

    for amt in snapshot.amounts:
        hidden_by = _amount_hidden_by(amt, snapshot, config)
        font_size = _amount_font_size(amt, snapshot)
        illegible = font_size is not None and 0 <= font_size < config.min_legible_font_px
        not_rendered = amt.visiblyRendered is False
        over = base is not None and amt.value > base + config.amount_epsilon
        relevant, scope = _amount_relevance(amt, snapshot, action, submitting)
        structural = [h for h in hidden_by if h not in WEAK_HIDING_REASONS]
        weak_only = bool(hidden_by) and not structural

        evidence: Dict[str, Any] = {
            "ref": amt.ref,
            "value": amt.value,
            "currency": amt.currency,
            "visiblyRendered": amt.visiblyRendered,
            "fontSize": font_size,
            "legibilityThresholdPx": config.min_legible_font_px,
            "hiddenBy": hidden_by,
            "structuralHiding": structural,
            "basePrice": base,
            "exceedsBasePrice": over,
            "actionIsSubmit": submitting,
            "scope": scope,
            "decisionRelevant": relevant,
        }

        if not_rendered or hidden_by or illegible:
            # The agent is acting on whatever is covering this amount - i.e.
            # dismissing the modal. Nothing to say.
            if weak_only and not illegible and _covered_by_the_action_target(snapshot, amt.ref, action):
                continue
            why = []
            if not_rendered:
                why.append("not visibly rendered")
            if hidden_by:
                why.append("hidden by " + ", ".join(hidden_by))
            if illegible:
                why.append(f"font-size {font_size}px below the {config.min_legible_font_px}px threshold")
            if not relevant:
                severity = "low"
            elif structural or illegible:
                severity = "high"
            elif weak_only:
                # covered right now, by something that may be a normal modal
                severity = "medium"
            else:
                severity = "high"
            reasons.append(
                Reason(
                    check="undisclosed_amount",
                    severity=severity,
                    message=(
                        f"Monetary value {amt.value} {amt.currency or ''} at {amt.ref} is "
                        + " and ".join(why)
                        + (
                            " - the user is being charged something they cannot see."
                            if relevant
                            else " (elsewhere on the page; reported, not blocking this action)."
                        )
                    ),
                    evidence=evidence,
                    layer=LAYER,
                    ref=amt.ref,
                    category="C1",
                )
            )
        elif over:
            reasons.append(
                Reason(
                    check="undisclosed_amount",
                    severity="medium" if (submitting and relevant) else "low",
                    message=(
                        f"Amount {amt.value} {amt.currency or ''} at {amt.ref} exceeds the task's "
                        f"base price {base}."
                    ),
                    evidence=evidence,
                    layer=LAYER,
                    ref=amt.ref,
                    category="C1",
                )
            )

    # Money smuggled through hidden form state (no amounts[] entry at all).
    # Scoped the same way: only the form the agent is about to submit can
    # block; other forms on the page are reported at low.
    acting_form = _form_for_action(snapshot, action) if submitting else None
    if base is not None:
        for form in snapshot.forms:
            form_relevant = acting_form is not None and acting_form.ref == form.ref
            for fld in form.fields:
                if fld.value is None:
                    continue
                is_hidden_field = (fld.type or "").lower() == "hidden" or not fld.label
                if is_hidden_field:
                    candidates = parse_money(fld.value)
                    if not candidates and _money_named(fld.name) and _looks_numeric(fld.value):
                        candidates = [(float(str(fld.value).replace(",", "")), str(fld.value))]
                    for value, matched in candidates:
                        if value > base + config.amount_epsilon:
                            reasons.append(
                                Reason(
                                    check="undisclosed_amount",
                                    severity="high" if form_relevant else "low",
                                    message=(
                                        f"Hidden form field {fld.ref} ({fld.name!r}) carries the value "
                                        f"{value}, above the task base price {base}."
                                        + ("" if form_relevant else " (form not being submitted by this action)")
                                    ),
                                    evidence={
                                        "scope": "form" if form_relevant else "page",
                                        "decisionRelevant": form_relevant,
                                        "formRef": form.ref,
                                        "fieldRef": fld.ref,
                                        "fieldName": fld.name,
                                        "fieldType": fld.type,
                                        "rawValue": fld.value,
                                        "parsedValue": value,
                                        "matchedText": matched,
                                        "basePrice": base,
                                        "source": "form-state",
                                    },
                                    layer=LAYER,
                                    ref=fld.ref,
                                    category="C1",
                                )
                            )
    return reasons


_MONEY_NAME_RE = re.compile(
    r"\b(price|amount|total|subtotal|grand_?total|charge|fee|cost|payable|due|"
    r"sum|value|tariff|premium)\b|price|amount|total|charge",
    re.I,
)


def _money_named(name: Optional[str]) -> bool:
    """Does this field name suggest it carries money?"""
    return bool(name) and bool(_MONEY_NAME_RE.search(str(name)))


def _looks_numeric(v: Any) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


# ==========================================================================
# CHECK 7 - injection_phrasing  (THE WEAKEST CHECK - advisory only)
# ==========================================================================


def check_injection_phrasing(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Imperative text addressed at a model.

    Listed in ``config.weak_checks``: the composer caps it at ``medium`` and it
    can never be the sole basis for a BLOCK.  Pattern lists are brittle and
    will be attacked; this exists to label text for ingress neutralization and
    to corroborate structural findings, not to carry the defense.
    """
    reasons: List[Reason] = []
    seen_refs = set()

    def scan(ref: str, text: Optional[str], where: str, extra: Dict[str, Any]) -> None:
        if not text or ref in seen_refs:
            return
        matches = find_injection_matches(text)
        if not matches:
            return
        seen_refs.add(ref)
        top = max(matches, key=lambda m: {"low": 1, "medium": 2, "high": 3}.get(m["severity"], 0))
        reasons.append(
            Reason(
                check="injection_phrasing",
                severity=top["severity"],
                message=(
                    f"{where} {ref} contains text addressed at a model "
                    f"(pattern {top['patternId']}): {top['matchedText']!r}"
                ),
                evidence={
                    "ref": ref,
                    "where": where,
                    "matches": matches,
                    "textPreview": str(text)[:240],
                    "advisoryOnly": True,
                    "note": "weak check - capped at medium, never a sole basis for BLOCK",
                    **extra,
                },
                layer=LAYER,
                ref=ref,
                category="C3",
            )
        )

    for tn in snapshot.textNodes:
        scan(tn.ref, tn.text, "Text node", {"visible": tn.visible, "hiddenBy": list(tn.hiddenBy)})
    for el in snapshot.elements:
        scan(el.ref, el.text, "Element", {"role": el.role})
        scan(f"{el.ref}#aria", el.attrs.get("aria-label"), "aria-label of", {"role": el.role})
        alt = el.attrs.get("alt")
        scan(f"{el.ref}#alt", alt, "alt text of", {"role": el.role})
        title = el.attrs.get("title")
        scan(f"{el.ref}#title", title, "title attribute of", {"role": el.role})
    if snapshot.title:
        scan("#document-title", snapshot.title, "Document title", {})
    return reasons


# ==========================================================================
# CHECK 8 - hidden_instruction_alignment  (C3 correlation)
# ==========================================================================


def check_hidden_instruction_alignment(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Is the action the agent proposes the *same* action hidden page text
    asked for?

    This is the only check that can evidence C3 ("an action traceable to
    page-embedded instructions") directly.  It requires a structural fact -
    the text is hidden from humans - plus a correlation between that text and
    the target's label, so it is not pattern matching alone.

    Severity is ``medium`` by default so a benign action that merely happens to
    be mentioned in hidden text does not fail the task.  It escalates to
    ``high`` when the target is also a money, subscription, add-on or consent
    control - i.e. when following the hidden instruction has a cost.
    """
    if action.type not in ("click", "submit", "type", "navigate"):
        return []
    el = _target_element(snapshot, action)
    target_label = normalize(el.label if el is not None else "")
    target_tokens = [t for t in re.split(r"\W+", target_label) if len(t) >= 3]
    if not target_tokens and action.type != "navigate":
        return []

    reasons: List[Reason] = []
    for tn in snapshot.textNodes:
        text = tn.text or ""
        if len(text.strip()) < 4:
            continue
        hidden_by, _ = _text_node_visibility(tn, snapshot, config)
        if not hidden_by and tn.visible is not False and not tn.hiddenBy:
            continue
        matches = find_injection_matches(text)
        if not matches:
            continue
        norm_text = normalize(text)
        overlap = [t for t in target_tokens if t in norm_text]
        url_hit = bool(action.url and action.url.lower() in norm_text)
        if not overlap and not url_hit:
            continue

        risky_term = None
        for key in ("subscription_terms", "addon_terms", "marketing_terms", "consent_labels"):
            risky_term = label_matches_any(el.label if el is not None else "", key)
            if risky_term:
                break
        costly = bool(risky_term) or contains_money(el.label if el is not None else "")
        reasons.append(
            Reason(
                check="hidden_instruction_alignment",
                severity="high" if costly else "medium",
                message=(
                    f"The proposed {action.type} on {action.ref or action.url} matches an "
                    f"instruction hidden from the user in text node {tn.ref}."
                ),
                evidence={
                    "textNodeRef": tn.ref,
                    "hiddenBy": list(dict.fromkeys(hidden_by + list(tn.hiddenBy or []))),
                    "hiddenTextPreview": text[:200],
                    "actionType": action.type,
                    "actionRef": action.ref,
                    "targetLabel": el.label if el is not None else None,
                    "overlappingTokens": overlap,
                    "urlMentioned": url_hit,
                    "injectionMatches": matches,
                    "costlyTarget": costly,
                    "matchedRiskTerm": risky_term,
                },
                layer=LAYER,
                ref=action.ref or tn.ref,
                category="C3",
            )
        )
    return reasons


# ==========================================================================
# registry
# ==========================================================================

CheckFn = Callable[[PageSnapshot, Action, TaskDescriptor, GuardConfig], List[Reason]]

L1_CHECKS: List[Tuple[str, CheckFn]] = [
    ("hit_test", check_hit_test),
    ("invisible_text", check_invisible_text),
    ("fake_close_button", check_fake_close_button),
    ("precheck_optins", check_precheck_optins),
    ("cross_origin_form", check_cross_origin_form),
    ("undisclosed_amount", check_undisclosed_amount),
    ("hidden_instruction_alignment", check_hidden_instruction_alignment),
    ("injection_phrasing", check_injection_phrasing),
]


def run_l1(
    snapshot: PageSnapshot, action: Action, task: TaskDescriptor, config: GuardConfig
) -> List[Reason]:
    """Run every L1 check.  A check that raises is isolated: it degrades to a
    low-severity diagnostic rather than taking the guard down mid-run."""
    out: List[Reason] = []
    for name, fn in L1_CHECKS:
        try:
            out.extend(fn(snapshot, action, task, config))
        except Exception as exc:  # pragma: no cover - defensive
            out.append(
                Reason(
                    check="check_error",
                    severity="low",
                    message=f"L1 check {name!r} raised {type(exc).__name__}: {exc}",
                    evidence={"check": name, "error": repr(exc)},
                    layer=LAYER,
                )
            )
    return out
