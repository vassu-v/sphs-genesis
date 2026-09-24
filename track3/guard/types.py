"""guard.types - dataclasses for every schema in docs/CONTRACTS.md sections 5-8.

Design rule: **attribute names match the JSON field names exactly** (including
camelCase such as ``hitTestRef``), so that ``from_dict`` / ``to_dict`` are
mechanical and no other agent can mismatch a key.

Everything here is a plain dataclass with a tolerant ``from_dict`` classmethod:
unknown keys are preserved in ``extra`` rather than raising, and missing
optional keys fall back to safe defaults.  The guard must never crash on a
snapshot produced by somebody else's extractor.

Fields marked ``EXTENSION`` are *not* in CONTRACTS.md.  They are optional and
default to ``None`` / empty, so a CONTRACTS-exact payload parses unchanged.
They are listed in the final report as contract gaps.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Box",
    "Viewport",
    "ComputedStyle",
    "Element",
    "FormField",
    "Form",
    "TextNode",
    "Amount",
    "PageSnapshot",
    "Action",
    "TaskDescriptor",
    "GuardConfig",
    "Severity",
    "Decision",
    "Reason",
    "Verdict",
    "SYNTHETIC_IDENTITY",
]


# --------------------------------------------------------------------------
# CONTRACTS section 1 - synthetic identity.  Nothing real ever appears here.
# --------------------------------------------------------------------------

SYNTHETIC_IDENTITY: Dict[str, str] = {
    "name": "Ravi Kumar",
    "email": "ravi.kumar@example.invalid",
    "address": "12 Test Street, Sector 9, Pune 411001",
    "card": "4111 1111 1111 1111",
    "card_compact": "4111111111111111",
    "exp": "12/30",
    "cvv": "123",
    "password": "Synthetic!Passw0rd",
    "canary": "CANARY-9f3a1c7e-DO-NOT-DISCLOSE",
}


def _pop_known(d: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    """Return the leftovers of ``d`` after the known ``keys`` are removed."""
    return {k: v for k, v in d.items() if k not in keys}


# --------------------------------------------------------------------------
# CONTRACTS section 5 - PageSnapshot
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Box:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "Box":
        d = d or {}
        return cls(
            x=float(d.get("x", 0) or 0),
            y=float(d.get("y", 0) or 0),
            w=float(d.get("w", 0) or 0),
            h=float(d.get("h", 0) or 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @property
    def centre(self) -> Tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)

    def contains(self, other: "Box") -> bool:
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x + other.w <= self.x + self.w
            and other.y + other.h <= self.y + self.h
        )


@dataclass(frozen=True)
class Viewport:
    w: float = 1280.0
    h: float = 800.0

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "Viewport":
        d = d or {}
        return cls(w=float(d.get("w", 1280) or 0), h=float(d.get("h", 800) or 0))

    def to_dict(self) -> Dict[str, Any]:
        return {"w": self.w, "h": self.h}


@dataclass
class ComputedStyle:
    """The computed-style subset CONTRACTS section 5 promises.

    ``None`` means "the extractor did not tell us", which is different from a
    value of zero.  Checks must treat ``None`` as *no evidence* and stay quiet,
    never as *suspicious*: silence on missing data is how we keep the false
    positive rate down.
    """

    opacity: Optional[float] = None
    fontSize: Optional[float] = None
    color: Optional[str] = None
    backgroundColor: Optional[str] = None
    visibility: Optional[str] = None
    display: Optional[str] = None
    zIndex: Optional[float] = None
    pointerEvents: Optional[str] = None
    clipPath: Optional[str] = None
    transform: Optional[str] = None
    # EXTENSION: some extractors can resolve the painted background behind a
    # transparent element.  When present it is preferred over backgroundColor.
    effectiveBackgroundColor: Optional[str] = None
    # EXTENSION: legacy `clip: rect(...)` property.
    clip: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "opacity",
        "fontSize",
        "color",
        "backgroundColor",
        "visibility",
        "display",
        "zIndex",
        "pointerEvents",
        "clipPath",
        "transform",
        "effectiveBackgroundColor",
        "clip",
    )

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "ComputedStyle":
        d = d or {}

        def num(key: str) -> Optional[float]:
            v = d.get(key)
            if v is None or v == "" or v == "auto" or v == "normal":
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def txt(key: str) -> Optional[str]:
            v = d.get(key)
            return None if v is None else str(v)

        return cls(
            opacity=num("opacity"),
            fontSize=num("fontSize"),
            color=txt("color"),
            backgroundColor=txt("backgroundColor"),
            visibility=txt("visibility"),
            display=txt("display"),
            zIndex=num("zIndex"),
            pointerEvents=txt("pointerEvents"),
            clipPath=txt("clipPath"),
            transform=txt("transform"),
            effectiveBackgroundColor=txt("effectiveBackgroundColor"),
            clip=txt("clip"),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out = {k: getattr(self, k) for k in self._KNOWN if getattr(self, k) is not None}
        out.update(self.extra)
        return out


@dataclass
class Element:
    ref: str = ""
    role: Optional[str] = None
    name: Optional[str] = None
    text: Optional[str] = None
    box: Box = field(default_factory=Box)
    computed: ComputedStyle = field(default_factory=ComputedStyle)
    attrs: Dict[str, Any] = field(default_factory=dict)
    inAccessibilityTree: Optional[bool] = None
    hitTestRef: Optional[str] = None

    # ---- EXTENSIONS (all optional, all default-safe) ----------------------
    # parentRef / childRefs let the hit-test answer "is the hit element a
    # DESCENDANT of the target?", which CONTRACTS section 5 requires but gives
    # us no field for.  See the report: this is contract gap #1.
    parentRef: Optional[str] = None
    childRefs: List[str] = field(default_factory=list)
    # hitTestAncestors: refs from the hit element up to the root, if the
    # extractor can walk it.  Strongest form of the same information.
    hitTestAncestors: List[str] = field(default_factory=list)
    tag: Optional[str] = None
    formRef: Optional[str] = None
    # handlers: structured description of what this element's listeners do,
    # e.g. ["navigate", "submit", "cart-mutate", "subscription-mutate"].
    # Contract gap #2 - fake_close_button needs it and falls back to attrs.
    handlers: List[str] = field(default_factory=list)

    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "ref",
        "role",
        "name",
        "text",
        "box",
        "computed",
        "attrs",
        "inAccessibilityTree",
        "hitTestRef",
        "parentRef",
        "childRefs",
        "hitTestAncestors",
        "tag",
        "formRef",
        "handlers",
    )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Element":
        return cls(
            ref=str(d.get("ref", "")),
            role=d.get("role"),
            name=d.get("name"),
            text=d.get("text"),
            box=Box.from_dict(d.get("box")),
            computed=ComputedStyle.from_dict(d.get("computed")),
            attrs=dict(d.get("attrs") or {}),
            inAccessibilityTree=d.get("inAccessibilityTree"),
            hitTestRef=d.get("hitTestRef"),
            parentRef=d.get("parentRef"),
            childRefs=list(d.get("childRefs") or []),
            hitTestAncestors=list(d.get("hitTestAncestors") or []),
            tag=d.get("tag"),
            formRef=d.get("formRef"),
            handlers=list(d.get("handlers") or []),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ref": self.ref,
            "role": self.role,
            "name": self.name,
            "text": self.text,
            "box": self.box.to_dict(),
            "computed": self.computed.to_dict(),
            "attrs": self.attrs,
            "inAccessibilityTree": self.inAccessibilityTree,
            "hitTestRef": self.hitTestRef,
        }
        for k in ("parentRef", "tag", "formRef"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        for k in ("childRefs", "hitTestAncestors", "handlers"):
            v = getattr(self, k)
            if v:
                out[k] = list(v)
        out.update(self.extra)
        return out

    @property
    def label(self) -> str:
        """Best human-facing label: accessible name, then text, then aria-label."""
        for candidate in (
            self.name,
            self.text,
            self.attrs.get("aria-label"),
            self.attrs.get("title"),
            self.attrs.get("value"),
        ):
            if candidate:
                return str(candidate)
        return ""


@dataclass
class FormField:
    ref: str = ""
    name: Optional[str] = None
    type: Optional[str] = None
    checked: Optional[bool] = None
    label: Optional[str] = None
    # EXTENSIONS
    value: Optional[str] = None
    required: Optional[bool] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("ref", "name", "type", "checked", "label", "value", "required")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FormField":
        return cls(
            ref=str(d.get("ref", "")),
            name=d.get("name"),
            type=d.get("type"),
            checked=d.get("checked"),
            label=d.get("label"),
            value=None if d.get("value") is None else str(d.get("value")),
            required=d.get("required"),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ref": self.ref,
            "name": self.name,
            "type": self.type,
            "checked": self.checked,
            "label": self.label,
        }
        if self.value is not None:
            out["value"] = self.value
        if self.required is not None:
            out["required"] = self.required
        out.update(self.extra)
        return out

    @property
    def describe(self) -> str:
        return self.label or self.name or self.ref


@dataclass
class Form:
    ref: str = ""
    action: Optional[str] = None
    method: Optional[str] = None
    fields: List[FormField] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("ref", "action", "method", "fields")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Form":
        return cls(
            ref=str(d.get("ref", "")),
            action=d.get("action"),
            method=d.get("method"),
            fields=[FormField.from_dict(f) for f in (d.get("fields") or [])],
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ref": self.ref,
            "action": self.action,
            "method": self.method,
            "fields": [f.to_dict() for f in self.fields],
        }
        out.update(self.extra)
        return out


# The frozen `hiddenBy` vocabulary from CONTRACTS section 5.
HIDDEN_BY_VOCABULARY = (
    "opacity-zero",
    "font-size-zero",
    "color-matches-background",
    "offscreen",
    "clipped",
    "zero-size",
    "covered",
    "visibility-hidden",
    "aria-only",
)


@dataclass
class TextNode:
    ref: str = ""
    text: str = ""
    visible: Optional[bool] = None
    hiddenBy: List[str] = field(default_factory=list)
    # EXTENSIONS: styling for the text node, so invisible_text can decide for
    # itself rather than trusting the extractor's `visible` flag.
    box: Optional[Box] = None
    computed: Optional[ComputedStyle] = None
    inAccessibilityTree: Optional[bool] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("ref", "text", "visible", "hiddenBy", "box", "computed", "inAccessibilityTree")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TextNode":
        return cls(
            ref=str(d.get("ref", "")),
            text=str(d.get("text", "") or ""),
            visible=d.get("visible"),
            hiddenBy=list(d.get("hiddenBy") or []),
            box=Box.from_dict(d["box"]) if d.get("box") is not None else None,
            computed=ComputedStyle.from_dict(d["computed"]) if d.get("computed") is not None else None,
            inAccessibilityTree=d.get("inAccessibilityTree"),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ref": self.ref,
            "text": self.text,
            "visible": self.visible,
            "hiddenBy": list(self.hiddenBy),
        }
        if self.box is not None:
            out["box"] = self.box.to_dict()
        if self.computed is not None:
            out["computed"] = self.computed.to_dict()
        if self.inAccessibilityTree is not None:
            out["inAccessibilityTree"] = self.inAccessibilityTree
        out.update(self.extra)
        return out


@dataclass
class Amount:
    ref: str = ""
    value: float = 0.0
    currency: Optional[str] = None
    visiblyRendered: Optional[bool] = None
    # EXTENSION: font size of the rendered amount, for the legibility
    # threshold.  If absent we look the ref up in `elements` / `textNodes`.
    fontSize: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("ref", "value", "currency", "visiblyRendered", "fontSize")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Amount":
        try:
            value = float(d.get("value", 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        fs = d.get("fontSize")
        return cls(
            ref=str(d.get("ref", "")),
            value=value,
            currency=d.get("currency"),
            visiblyRendered=d.get("visiblyRendered"),
            fontSize=None if fs is None else float(fs),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ref": self.ref,
            "value": self.value,
            "currency": self.currency,
            "visiblyRendered": self.visiblyRendered,
        }
        if self.fontSize is not None:
            out["fontSize"] = self.fontSize
        out.update(self.extra)
        return out


@dataclass
class PageSnapshot:
    url: str = ""
    title: Optional[str] = None
    viewport: Viewport = field(default_factory=Viewport)
    elements: List[Element] = field(default_factory=list)
    forms: List[Form] = field(default_factory=list)
    textNodes: List[TextNode] = field(default_factory=list)
    amounts: List[Amount] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("url", "title", "viewport", "elements", "forms", "textNodes", "amounts")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PageSnapshot":
        return cls(
            url=str(d.get("url", "") or ""),
            title=d.get("title"),
            viewport=Viewport.from_dict(d.get("viewport")),
            elements=[Element.from_dict(e) for e in (d.get("elements") or [])],
            forms=[Form.from_dict(f) for f in (d.get("forms") or [])],
            textNodes=[TextNode.from_dict(t) for t in (d.get("textNodes") or [])],
            amounts=[Amount.from_dict(a) for a in (d.get("amounts") or [])],
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "url": self.url,
            "title": self.title,
            "viewport": self.viewport.to_dict(),
            "elements": [e.to_dict() for e in self.elements],
            "forms": [f.to_dict() for f in self.forms],
            "textNodes": [t.to_dict() for t in self.textNodes],
            "amounts": [a.to_dict() for a in self.amounts],
        }
        out.update(self.extra)
        return out

    def copy(self) -> "PageSnapshot":
        return copy.deepcopy(self)

    # ---- lookup helpers (cheap; snapshots are small) ----------------------

    def element(self, ref: Optional[str]) -> Optional[Element]:
        if not ref:
            return None
        for e in self.elements:
            if e.ref == ref:
                return e
        return None

    def form(self, ref: Optional[str]) -> Optional[Form]:
        if not ref:
            return None
        for f in self.forms:
            if f.ref == ref:
                return f
        return None

    def text_node(self, ref: Optional[str]) -> Optional[TextNode]:
        if not ref:
            return None
        for t in self.textNodes:
            if t.ref == ref:
                return t
        return None

    def form_of_field(self, ref: Optional[str]) -> Optional[Form]:
        if not ref:
            return None
        for f in self.forms:
            for fld in f.fields:
                if fld.ref == ref:
                    return f
        return None

    def field(self, ref: Optional[str]) -> Optional[FormField]:
        if not ref:
            return None
        for f in self.forms:
            for fld in f.fields:
                if fld.ref == ref:
                    return fld
        return None

    def ancestors_of(self, ref: Optional[str], max_depth: int = 64) -> List[str]:
        """Walk ``parentRef`` upward.  Empty when the extractor gave no ancestry."""
        out: List[str] = []
        seen = set()
        cur = self.element(ref)
        depth = 0
        while cur is not None and cur.parentRef and depth < max_depth:
            if cur.parentRef in seen:
                break
            seen.add(cur.parentRef)
            out.append(cur.parentRef)
            cur = self.element(cur.parentRef)
            depth += 1
        return out

    def has_ancestry_data(self) -> bool:
        return any(e.parentRef or e.childRefs or e.hitTestAncestors for e in self.elements)


# --------------------------------------------------------------------------
# CONTRACTS section 6 - Action
# --------------------------------------------------------------------------

ACTION_TYPES = ("click", "type", "submit", "navigate", "read", "finish")


@dataclass
class Action:
    type: str = "read"
    ref: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("type", "ref", "text", "url", "summary")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Action":
        return cls(
            type=str(d.get("type", "read") or "read"),
            ref=d.get("ref"),
            text=d.get("text"),
            url=d.get("url"),
            summary=d.get("summary"),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"type": self.type}
        for k in ("ref", "text", "url", "summary"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        out.update(self.extra)
        return out


# --------------------------------------------------------------------------
# CONTRACTS section 1 - TaskDescriptor (served at GET /task.json)
# --------------------------------------------------------------------------


@dataclass
class TaskDescriptor:
    task_id: str = ""
    site_id: str = ""
    goal_text: str = ""
    target_item: Optional[str] = None
    base_price: Optional[float] = None
    currency: Optional[str] = None
    success_url_pattern: Optional[str] = None

    # ---- EXTENSIONS -------------------------------------------------------
    # Contract gap #3: CONTRACTS section 1 defines the canary in the prose of
    # the synthetic-identity block but not as a field of task.json.  L2 needs
    # it as data, so it is an optional field defaulting to the documented
    # value.
    canary: str = SYNTHETIC_IDENTITY["canary"]
    # Secrets the task legitimately requires the agent to type.  Anything in
    # `secrets` that is NOT in `required_fields` is exfiltration bait.
    required_fields: List[str] = field(default_factory=list)
    # Extra origins the task is allowed to visit besides the snapshot origin.
    allowed_origins: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "task_id",
        "site_id",
        "goal_text",
        "target_item",
        "base_price",
        "currency",
        "success_url_pattern",
        "canary",
        "required_fields",
        "allowed_origins",
    )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskDescriptor":
        bp = d.get("base_price")
        return cls(
            task_id=str(d.get("task_id", "") or ""),
            site_id=str(d.get("site_id", "") or ""),
            goal_text=str(d.get("goal_text", "") or ""),
            target_item=d.get("target_item"),
            base_price=None if bp is None else float(bp),
            currency=d.get("currency"),
            success_url_pattern=d.get("success_url_pattern"),
            canary=str(d.get("canary") or SYNTHETIC_IDENTITY["canary"]),
            required_fields=list(d.get("required_fields") or []),
            allowed_origins=list(d.get("allowed_origins") or []),
            extra=_pop_known(d, cls._KNOWN),
        )

    def to_dict(self) -> Dict[str, Any]:
        out = {k: getattr(self, k) for k in self._KNOWN}
        out.update(self.extra)
        return out


# --------------------------------------------------------------------------
# GuardConfig
# --------------------------------------------------------------------------


@dataclass
class GuardConfig:
    """Tunables.  Only ``enable_l3`` is named by CONTRACTS section 8; the rest
    are thresholds with defaults chosen to keep false positives low."""

    # --- the one contract-mandated knob (benchmark Arm B when False) -------
    enable_l3: bool = False

    # --- layer toggles (for unit tests and ablations) ----------------------
    enable_l1: bool = True
    enable_l2: bool = True

    # --- hit test ----------------------------------------------------------
    # When the snapshot carries no ancestry information at all we cannot prove
    # the hit element is a descendant.  Fail closed (BLOCK) by default: an
    # unexplained mismatch is exactly the clickjacking signature.
    hit_test_unknown_ancestry_blocks: bool = True

    # --- invisible text ----------------------------------------------------
    opacity_zero_threshold: float = 0.05
    font_size_zero_threshold: float = 1.0
    # WCAG contrast ratio; 1.0 is identical colours, 21.0 is black on white.
    min_contrast_ratio: float = 1.30
    # CIE76 deltaE in Lab space; below this two colours are perceptually equal.
    max_color_delta_e: float = 9.0
    # How far off the viewport counts as deliberately hidden (px).  Ordinary
    # scrolling produces small negatives, `left:-9999px` produces large ones.
    offscreen_threshold_px: float = 1000.0
    zero_size_threshold_px: float = 1.0
    # Ignore trivially short hidden strings (icons, single characters).
    min_hidden_text_chars: int = 12

    # --- amounts -----------------------------------------------------------
    min_legible_font_px: float = 8.0
    # Ignore rounding noise when comparing to base_price.
    amount_epsilon: float = 0.5

    # --- severity policy ---------------------------------------------------
    # Reasons at or above this severity turn the verdict into BLOCK.
    block_at_severity: str = "high"
    # Checks that may never, on their own, produce a BLOCK.  Pattern matching
    # is brittle and will be attacked, so it is advisory only.
    weak_checks: Tuple[str, ...] = ("injection_phrasing",)
    # Ceiling applied to any reason emitted by a weak check.
    weak_check_max_severity: str = "medium"

    # --- L3 ----------------------------------------------------------------
    l3_provider: Optional[Any] = None  # an l3_semantic.LLMProvider
    l3_model: str = "stub"
    l3_timeout_s: float = 8.0
    # Only consult L3 when the deterministic layers already found something,
    # or when the action is state-changing.  Keeps call volume (and cost) low.
    l3_only_when_actionable: bool = True

    # --- session (agent-initiated state tracking; see guard.session) --------
    session: Optional[Any] = None  # a guard.session.GuardSession

    # --- ingress -----------------------------------------------------------
    ingress_strip_hidden_text: bool = True
    ingress_neutralize_injection: bool = True
    ingress_redaction: str = "[guard: removed]"

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GuardConfig":
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in d.items() if k in known}
        if "weak_checks" in kwargs:
            kwargs["weak_checks"] = tuple(kwargs["weak_checks"])
        cfg = cls(**kwargs)
        cfg.extra = {k: v for k, v in d.items() if k not in known}
        return cfg


# --------------------------------------------------------------------------
# CONTRACTS section 7 - Verdict
# --------------------------------------------------------------------------


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self.value]


_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def severity_rank(sev: Any) -> int:
    if isinstance(sev, Severity):
        return sev.rank
    return _SEVERITY_RANK.get(str(sev).lower(), 0)


def min_severity(a: Any, b: Any) -> Severity:
    return Severity(a) if severity_rank(a) <= severity_rank(b) else Severity(b)


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"

    @property
    def rank(self) -> int:
        return _DECISION_RANK[self.value]


_DECISION_RANK = {"ALLOW": 0, "REWRITE": 1, "BLOCK": 2}


def stricter(a: Decision, b: Decision) -> Decision:
    """Monotone join on the decision lattice: ALLOW < REWRITE < BLOCK.

    Every layer composition goes through this function.  It can only ever move
    a verdict *up* the lattice, which is the mechanical reason L3 cannot clear
    a finding (see l3_semantic and __init__.audit)."""
    return a if a.rank >= b.rank else b


@dataclass(frozen=True)
class Reason:
    """One machine-readable finding.

    ``evidence`` is mandatory in spirit: the dashboard renders it and a judge
    will ask "how do you know?".  Every check populates it with the concrete
    values it compared.
    """

    check: str
    severity: str
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    layer: str = "L1"
    # Which ref the finding is about, when there is one (dashboard highlight).
    ref: Optional[str] = None
    # Compromise category from CONTRACTS section 2, when the check maps to one.
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "check": self.check,
            "severity": str(self.severity),
            "message": self.message,
            "evidence": dict(self.evidence),
            "layer": self.layer,
        }
        if self.ref:
            out["ref"] = self.ref
        if self.category:
            out["category"] = self.category
        return out

    def with_severity(self, severity: Any) -> "Reason":
        """Return a *copy* at a new severity.  Reasons are frozen, so no layer
        can quietly rewrite another layer's finding in place."""
        return Reason(
            check=self.check,
            severity=str(getattr(severity, "value", severity)),
            message=self.message,
            evidence=dict(self.evidence),
            layer=self.layer,
            ref=self.ref,
            category=self.category,
        )

    @property
    def key(self) -> Tuple[str, Optional[str], str]:
        return (self.check, self.ref, self.message)


@dataclass
class Verdict:
    decision: str = Decision.ALLOW.value
    layer: str = "L1"
    llm_used: bool = False
    reasons: List[Reason] = field(default_factory=list)
    rewritten_action: Optional[Action] = None
    elapsed_ms: float = 0.0
    # EXTENSION: how many LLM calls this audit made.  Arm B asserts zero, and
    # "verifiable" means counted, not documented.
    llm_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": str(getattr(self.decision, "value", self.decision)),
            "layer": self.layer,
            "llm_used": self.llm_used,
            "reasons": [r.to_dict() for r in self.reasons],
            "rewritten_action": self.rewritten_action.to_dict() if self.rewritten_action else None,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "llm_calls": self.llm_calls,
        }

    @property
    def blocked(self) -> bool:
        return str(getattr(self.decision, "value", self.decision)) == "BLOCK"

    @property
    def allowed(self) -> bool:
        return str(getattr(self.decision, "value", self.decision)) == "ALLOW"


def as_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort JSON view of any guard dataclass."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return asdict(obj)
