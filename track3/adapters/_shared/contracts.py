"""
Plain-dataclass mirror of docs/CONTRACTS.md, used ONLY when the real `guard` package
(owned by another agent, being built concurrently in track3/guard/) is not yet
importable. Every adapter tries `from guard import ...` first and falls back to this
module — see adapters/_shared/guard_client.py. Field names and shapes here are
copied verbatim from CONTRACTS.md §5-§8 and MUST be kept in sync with it; if guard/
lands with different field names, that is a CONTRACTS violation to flag, not something
to silently paper over here.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


def _dc_asdict(obj) -> dict:
    return asdict(obj)


@dataclass
class BoundingBox:
    x: float
    y: float
    w: float
    h: float


@dataclass
class ComputedStyle:
    opacity: float = 1.0
    fontSize: float = 14
    color: str = "#000000"
    backgroundColor: str = "#ffffff"
    visibility: str = "visible"
    display: str = "block"
    zIndex: int = 0
    pointerEvents: str = "auto"
    clipPath: str = "none"
    transform: str = "none"


@dataclass
class ElementSnapshot:
    ref: str
    role: str
    name: str
    text: str
    box: BoundingBox
    computed: ComputedStyle
    attrs: dict
    inAccessibilityTree: bool
    hitTestRef: Optional[str]
    checked: Optional[bool] = None  # only meaningful for checkbox/radio inputs
    hitTestAncestors: list = field(default_factory=list)


@dataclass
class FormField:
    ref: str
    name: str
    type: str
    checked: bool
    label: str


@dataclass
class FormSnapshot:
    ref: str
    action: str
    method: str
    fields: list


@dataclass
class TextNodeSnapshot:
    ref: str
    text: str
    visible: bool
    hiddenBy: list


@dataclass
class AmountSnapshot:
    ref: str
    value: float
    currency: str
    visiblyRendered: bool


@dataclass
class Viewport:
    w: int
    h: int


@dataclass
class PageSnapshot:
    url: str
    title: str
    viewport: Viewport
    elements: list
    forms: list
    textNodes: list
    amounts: list

    def find_element(self, ref: str) -> Optional[ElementSnapshot]:
        for el in self.elements:
            if el.ref == ref:
                return el
        return None


@dataclass
class Action:
    type: str  # click | type | submit | navigate | read | finish
    ref: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class TaskDescriptor:
    task_id: str
    site_id: str
    goal_text: str
    target_item: str
    base_price: float
    currency: str
    success_url_pattern: str


@dataclass
class GuardConfig:
    enable_l3: bool = False
    arm: str = "C"  # "A" | "B" | "C" -- A means "no guard" at the call-site, not here


class SemanticOpinion(Enum):
    ESCALATE = "escalate"
    NO_OPINION = "no_opinion"


@dataclass
class VerdictReason:
    check: str
    severity: str  # "low" | "medium" | "high"
    message: str
    evidence: dict = field(default_factory=dict)


@dataclass
class Verdict:
    decision: str  # ALLOW | BLOCK | REWRITE
    layer: str  # L1 | L2 | L3
    llm_used: bool
    reasons: list
    rewritten_action: Optional[Action]
    elapsed_ms: float

    def to_dict(self) -> dict:
        d = _dc_asdict(self)
        return d
