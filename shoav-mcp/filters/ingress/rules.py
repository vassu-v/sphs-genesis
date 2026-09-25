"""Pure ingress detection rules.

Every function here takes and returns plain dicts/lists — no browser, no
network, no I/O — so each is directly unit-testable with fixture data.
Two of these (find_hidden_textful_nodes, flag_prechecked_toggles) work on
data Auto Browser's *existing* payload can already supply; the others need
the new STYLE_PROBE_SCRIPT capability from scripts.py wired in later.
"""

from __future__ import annotations

from ..constants import (
    INGRESS_BENIGN_HIDDEN_MARKERS,
    INGRESS_CONSENT_KEYWORDS,
    INGRESS_FLAGGABLE_TOGGLE_TYPES,
    INGRESS_INJECTION_KEYWORDS,
    INGRESS_MIN_FONT_SIZE_PX,
    INGRESS_NODE_BUDGET_TARGET,
    INGRESS_NODE_PRIORITY,
    INGRESS_OFFSCREEN_LEFT_PX,
    INGRESS_OPACITY_THRESHOLD,
    ZERO_WIDTH_CHARS,
)


def _is_offscreen(rect: dict, viewport: dict) -> bool:
    right = rect.get("right", 0)
    bottom = rect.get("bottom", 0)
    left = rect.get("left", 0)
    top = rect.get("top", 0)
    width = viewport.get("width", 0)
    height = viewport.get("height", 0)
    fully_outside = right < 0 or bottom < 0 or left > width or top > height
    return fully_outside or left < INGRESS_OFFSCREEN_LEFT_PX


def _is_benign_hidden(node: dict) -> bool:
    class_name = (node.get("class_name") or "").lower()
    return any(marker in class_name for marker in INGRESS_BENIGN_HIDDEN_MARKERS)


def find_hidden_textful_nodes(style_facts: list[dict]) -> dict:
    """Target 1: hidden-but-textful nodes, from STYLE_PROBE_SCRIPT output.

    Returns {"stripped": [...], "skipped_benign": [...]} — both lists are
    kept so telemetry can be honest about what was left alone and why.
    """
    stripped: list[dict] = []
    skipped_benign: list[dict] = []

    for node in style_facts:
        rect = node.get("rect", {})
        viewport = node.get("viewport", {})
        hidden = (
            node.get("display") == "none"
            or node.get("visibility") == "hidden"
            or node.get("opacity", 1.0) < INGRESS_OPACITY_THRESHOLD
            or node.get("font_size", 1.0) <= INGRESS_MIN_FONT_SIZE_PX
            or _is_offscreen(rect, viewport)
        )
        if not hidden:
            continue

        entry = {
            "ref": node.get("ref"),
            "tag": node.get("tag"),
            "snippet": (node.get("text_snippet") or "")[:50],
            "reason": "computed_style_hidden",
        }
        if _is_benign_hidden(node):
            skipped_benign.append(entry)
        else:
            stripped.append(entry)

    return {"stripped": stripped, "skipped_benign": skipped_benign}


def find_text_injections(text_blob: str) -> list[dict]:
    """Target 1 (text half): zero-width Unicode + suspicious HTML comments.

    Works on plain text/HTML Auto Browser already returns today
    (text_excerpt / get_html) — needs no new capability.
    """
    findings: list[dict] = []

    for ch in ZERO_WIDTH_CHARS:
        count = text_blob.count(ch)
        if count:
            findings.append({
                "reason": "zero_width_unicode",
                "char": f"U+{ord(ch):04X}",
                "count": count,
            })

    lowered = text_blob.lower()
    for keyword in INGRESS_INJECTION_KEYWORDS:
        if keyword in lowered:
            idx = lowered.index(keyword)
            findings.append({
                "reason": "suspicious_instruction_keyword",
                "keyword": keyword,
                "snippet": text_blob[max(0, idx - 20): idx + len(keyword) + 20],
            })

    return findings


def compact_node_budget(
    nodes: list[dict],
    max_nodes: int = INGRESS_NODE_BUDGET_TARGET,
) -> tuple[list[dict], bool]:
    """Target 4: bound the interactive-node count, prioritizing real controls.

    nodes are expected in Auto Browser's real interactables shape:
    {element_id, tag, type, role, label, bbox, ...}. Returns
    (possibly-truncated list, whether truncation happened).
    """
    if len(nodes) <= max_nodes:
        return list(nodes), False

    def priority(node: dict) -> int:
        tag = (node.get("tag") or "").lower()
        try:
            return INGRESS_NODE_PRIORITY.index(tag)
        except ValueError:
            return len(INGRESS_NODE_PRIORITY)

    ordered = sorted(enumerate(nodes), key=lambda pair: (priority(pair[1]), pair[0]))
    kept_indices = sorted(idx for idx, _ in ordered[:max_nodes])
    return [nodes[i] for i in kept_indices], True


def flag_prechecked_toggles(form_controls: list[dict]) -> list[dict]:
    """Target 3: pre-checked consent/marketing/add-on toggles.

    form_controls: [{"ref": str, "type": str, "checked": bool, "label": str}].
    Works today from Auto Browser's accessibility_outline, whose AX nodes
    already carry a `checked` field — no new capability required.
    Only checkbox/toggle/switch types are eligible (never radio/select),
    and only when the label/name matches a consent-ish keyword — see
    constants.py for the documented false-negative limitation this implies.
    """
    flagged: list[dict] = []
    for control in form_controls:
        control_type = (control.get("type") or "").lower()
        if control_type not in INGRESS_FLAGGABLE_TOGGLE_TYPES:
            continue
        if not control.get("checked"):
            continue
        label = (control.get("label") or control.get("ref") or "").lower()
        if any(keyword in label for keyword in INGRESS_CONSENT_KEYWORDS):
            flagged.append({
                "ref": control.get("ref"),
                "label": control.get("label"),
                "reason": "prechecked_consent_like_default",
            })
    return flagged
