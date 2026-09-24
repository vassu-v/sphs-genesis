"""guard.ingress - sanitize a PageSnapshot before the agent reads it.

Egress containment stops a hijacked agent from acting.  Ingress prevention is
better: the hostile instruction never enters the agent's context in the first
place, so there is nothing to resist.

Two operations, both conservative:

* **strip** - text that is in the DOM but hidden from humans is removed
  wholesale.  A human user could not read it, so removing it costs the agent
  nothing it was entitled to.
* **neutralize** - *visible* text that matches injection phrasing has only the
  matched spans redacted.  The surrounding sentence survives, because visible
  page copy is often exactly what the agent needs to do its job, and shredding
  it would fail the "task completed" half of the benchmark.

Everything removed is recorded in an :class:`IngressReport` for the dashboard:
"here is what we took out, here is why" is the evidence a judge asks for.

Pure and synchronous.  The input snapshot is never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .l1_structural import _element_visibility, _text_node_visibility
from .patterns import find_injection_matches
from .types import GuardConfig, PageSnapshot, Reason

__all__ = ["IngressReport", "StrippedItem", "sanitize", "neutralize_text"]


@dataclass
class StrippedItem:
    ref: str
    where: str  # "textNode" | "element.text" | "element.name" | "attrs.aria-label" | ...
    operation: str  # "strip" | "neutralize"
    reason: str  # "hidden" | "injection-phrasing"
    hiddenBy: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    originalLength: int = 0
    originalPreview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "where": self.where,
            "operation": self.operation,
            "reason": self.reason,
            "hiddenBy": list(self.hiddenBy),
            "patterns": list(self.patterns),
            "originalLength": self.originalLength,
            "originalPreview": self.originalPreview,
        }


@dataclass
class IngressReport:
    url: str = ""
    items: List[StrippedItem] = field(default_factory=list)
    hidden_nodes_removed: int = 0
    injection_spans_neutralized: int = 0
    characters_removed: int = 0
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "hidden_nodes_removed": self.hidden_nodes_removed,
            "injection_spans_neutralized": self.injection_spans_neutralized,
            "characters_removed": self.characters_removed,
            "items": [i.to_dict() for i in self.items],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }

    def as_reasons(self) -> List[Reason]:
        """The same telemetry expressed as Reasons, for a unified timeline."""
        out: List[Reason] = []
        for item in self.items:
            out.append(
                Reason(
                    check="ingress_" + item.operation,
                    severity="medium" if item.reason == "hidden" else "low",
                    message=(
                        f"Ingress {item.operation}ped {item.originalLength} characters at "
                        f"{item.ref} ({item.where}) - {item.reason}."
                    ),
                    evidence=item.to_dict(),
                    layer="L0",
                    ref=item.ref,
                    category="C3",
                )
            )
        return out


def neutralize_text(text: Optional[str], redaction: str) -> Tuple[str, List[str]]:
    """Redact injection spans inside otherwise legitimate text.

    Returns ``(clean_text, matched_pattern_ids)``.  Spans are replaced back to
    front so earlier offsets stay valid.
    """
    if not text:
        return text or "", []
    matches = find_injection_matches(text, max_matches=32)
    spans = [
        (m["span"][0], m["span"][1], m["patternId"])
        for m in matches
        if m.get("against") == "raw" and m.get("span")
    ]
    if not spans:
        # The match was only found after normalization (zero-width padding,
        # case games).  Offsets do not map back safely, so redact wholesale.
        if matches:
            return redaction, [m["patternId"] for m in matches]
        return text, []
    spans.sort(key=lambda s: s[0], reverse=True)
    out = text
    for start, end, _pid in spans:
        out = out[:start] + redaction + out[end:]
    return out, [s[2] for s in spans]


def sanitize(
    snapshot: PageSnapshot, config: Optional[GuardConfig] = None
) -> Tuple[PageSnapshot, IngressReport]:
    """Return ``(sanitized_copy, report)``.  The input is left untouched."""
    import time

    t0 = time.perf_counter()
    cfg = config or GuardConfig()
    clean = snapshot.copy()
    report = IngressReport(url=snapshot.url)

    def record(item: StrippedItem) -> None:
        report.items.append(item)
        report.characters_removed += item.originalLength if item.operation == "strip" else 0
        if item.operation == "strip":
            report.hidden_nodes_removed += 1
        else:
            report.injection_spans_neutralized += len(item.patterns)

    # ---- 1. hidden text nodes: remove entirely ----------------------------
    kept_nodes = []
    for tn in clean.textNodes:
        hidden_by, _ = _text_node_visibility(tn, clean, cfg)
        extractor_hidden = tn.visible is False or bool(tn.hiddenBy)
        if cfg.ingress_strip_hidden_text and (hidden_by or extractor_hidden):
            merged = list(dict.fromkeys(list(hidden_by) + list(tn.hiddenBy or [])))
            record(
                StrippedItem(
                    ref=tn.ref,
                    where="textNode",
                    operation="strip",
                    reason="hidden",
                    hiddenBy=merged or ["reported-hidden"],
                    patterns=[m["patternId"] for m in find_injection_matches(tn.text)],
                    originalLength=len(tn.text or ""),
                    originalPreview=(tn.text or "")[:200],
                )
            )
            continue  # dropped: the agent never sees it
        if cfg.ingress_neutralize_injection:
            cleaned, pats = neutralize_text(tn.text, cfg.ingress_redaction)
            if pats:
                record(
                    StrippedItem(
                        ref=tn.ref,
                        where="textNode",
                        operation="neutralize",
                        reason="injection-phrasing",
                        patterns=pats,
                        originalLength=len(tn.text or ""),
                        originalPreview=(tn.text or "")[:200],
                    )
                )
                tn.text = cleaned
        kept_nodes.append(tn)
    clean.textNodes = kept_nodes

    # ---- 2. elements ------------------------------------------------------
    for el in clean.elements:
        hidden_by, _ = _element_visibility(el, clean, cfg)
        text_fields: List[Tuple[str, str]] = [("text", "element.text"), ("name", "element.name")]

        if hidden_by and cfg.ingress_strip_hidden_text:
            for attr, where in text_fields:
                value = getattr(el, attr, None)
                if value:
                    record(
                        StrippedItem(
                            ref=el.ref,
                            where=where,
                            operation="strip",
                            reason="hidden",
                            hiddenBy=hidden_by,
                            patterns=[m["patternId"] for m in find_injection_matches(value)],
                            originalLength=len(str(value)),
                            originalPreview=str(value)[:200],
                        )
                    )
                    setattr(el, attr, "")
            for key in ("aria-label", "title", "alt", "placeholder"):
                if el.attrs.get(key):
                    value = str(el.attrs[key])
                    record(
                        StrippedItem(
                            ref=el.ref,
                            where=f"attrs.{key}",
                            operation="strip",
                            reason="hidden",
                            hiddenBy=hidden_by,
                            patterns=[m["patternId"] for m in find_injection_matches(value)],
                            originalLength=len(value),
                            originalPreview=value[:200],
                        )
                    )
                    el.attrs[key] = ""
            # Mark it so the agent-facing snapshot carries the explanation.
            el.extra["guardHiddenBy"] = hidden_by
            continue

        if not cfg.ingress_neutralize_injection:
            continue
        for attr, where in text_fields:
            value = getattr(el, attr, None)
            cleaned, pats = neutralize_text(value, cfg.ingress_redaction)
            if pats:
                record(
                    StrippedItem(
                        ref=el.ref,
                        where=where,
                        operation="neutralize",
                        reason="injection-phrasing",
                        patterns=pats,
                        originalLength=len(str(value)),
                        originalPreview=str(value)[:200],
                    )
                )
                setattr(el, attr, cleaned)
        for key in ("aria-label", "title", "alt", "placeholder"):
            value = el.attrs.get(key)
            if not value:
                continue
            cleaned, pats = neutralize_text(str(value), cfg.ingress_redaction)
            if pats:
                record(
                    StrippedItem(
                        ref=el.ref,
                        where=f"attrs.{key}",
                        operation="neutralize",
                        reason="injection-phrasing",
                        patterns=pats,
                        originalLength=len(str(value)),
                        originalPreview=str(value)[:200],
                    )
                )
                el.attrs[key] = cleaned

    # ---- 3. document title -------------------------------------------------
    if cfg.ingress_neutralize_injection and clean.title:
        cleaned, pats = neutralize_text(clean.title, cfg.ingress_redaction)
        if pats:
            record(
                StrippedItem(
                    ref="#document-title",
                    where="title",
                    operation="neutralize",
                    reason="injection-phrasing",
                    patterns=pats,
                    originalLength=len(clean.title),
                    originalPreview=clean.title[:200],
                )
            )
            clean.title = cleaned

    report.elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return clean, report
