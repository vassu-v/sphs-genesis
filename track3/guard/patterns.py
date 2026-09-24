"""guard.patterns - loader for the extensible data files.

Everything brittle lives in ``guard/data/*.json`` so it can be extended during
a live Q&A without touching code.  Override any of them with an env var:

    GUARD_INJECTION_PATTERNS=/path/to/patterns.json
    GUARD_LEXICONS=/path/to/lexicons.json
    GUARD_POLICY_RULES=/path/to/rules.json

Loads are cached; call :func:`reload` after editing a file in a live session.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).with_name("data")

__all__ = [
    "InjectionPattern",
    "injection_patterns",
    "lexicons",
    "policy_rule_data",
    "reload",
    "find_injection_matches",
    "label_matches_any",
]


@dataclass(frozen=True)
class InjectionPattern:
    id: str
    regex: "re.Pattern[str]"
    severity: str
    description: str


_cache: Dict[str, Any] = {}


def _load_json(env_var: str, filename: str) -> Dict[str, Any]:
    path = os.environ.get(env_var) or str(DATA_DIR / filename)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def reload() -> None:
    """Drop the cache so the next access re-reads the JSON from disk."""
    _cache.clear()


def injection_patterns() -> List[InjectionPattern]:
    if "injection" not in _cache:
        raw = _load_json("GUARD_INJECTION_PATTERNS", "injection_patterns.json")
        out: List[InjectionPattern] = []
        for p in raw.get("patterns", []):
            try:
                compiled = re.compile(p["regex"], re.I | re.M)
            except re.error:  # a bad pattern must never take the guard down
                continue
            out.append(
                InjectionPattern(
                    id=str(p.get("id", "unnamed")),
                    regex=compiled,
                    severity=str(p.get("severity", "low")),
                    description=str(p.get("description", "")),
                )
            )
        _cache["injection"] = out
    return _cache["injection"]


def lexicons() -> Dict[str, List[str]]:
    if "lexicons" not in _cache:
        raw = _load_json("GUARD_LEXICONS", "lexicons.json")
        _cache["lexicons"] = {
            k: [str(x).lower() for x in v] for k, v in raw.items() if isinstance(v, list) and k != "notes"
        }
    return _cache["lexicons"]


def policy_rule_data() -> Dict[str, Any]:
    if "policy" not in _cache:
        _cache["policy"] = _load_json("GUARD_POLICY_RULES", "policy_rules.json")
    return _cache["policy"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def normalize(text: Optional[str]) -> str:
    """Lowercase, collapse whitespace, strip zero-width and bidi characters.

    Homoglyph and zero-width padding are the cheapest way to dodge a word
    list, so they are removed before matching.
    """
    if not text:
        return ""
    t = str(text)
    t = t.replace("​", "").replace("‌", "").replace("‍", "").replace("﻿", "")
    t = t.replace("‪", "").replace("‫", "").replace("‬", "")
    t = t.replace("‭", "").replace("‮", "")
    return _WS.sub(" ", t).strip().lower()


def find_injection_matches(text: Optional[str], max_matches: int = 8) -> List[Dict[str, Any]]:
    """Return machine-readable match records for the dashboard."""
    if not text:
        return []
    haystack = str(text)
    normalized = normalize(haystack)
    out: List[Dict[str, Any]] = []
    for pat in injection_patterns():
        for source, label in ((haystack, "raw"), (normalized, "normalized")):
            m = pat.regex.search(source)
            if m:
                out.append(
                    {
                        "patternId": pat.id,
                        "severity": pat.severity,
                        "description": pat.description,
                        "matchedText": m.group(0)[:160],
                        "span": [m.start(), m.end()],
                        "against": label,
                    }
                )
                break
        if len(out) >= max_matches:
            break
    return out


def label_matches_any(label: Optional[str], lexicon_key: str) -> Optional[str]:
    """Return the lexicon entry that matched ``label``, or ``None``.

    Exact match first (so a button whose whole label is "x" matches the close
    lexicon), then containment for multi-word phrases.
    """
    norm = normalize(label)
    if not norm:
        return None
    words = lexicons().get(lexicon_key, [])
    for w in words:
        if norm == w:
            return w
    for w in words:
        if len(w) < 3:
            continue
        if " " in w or not w.isalnum():
            # multi-word phrase: plain containment is safe
            if w in norm:
                return w
        elif re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", norm):
            # single word: require word boundaries, so "tip" does not match
            # "multiple" and "extra" does not match "extraordinary"
            return w
    return None


def contains_money(text: Optional[str]) -> bool:
    norm = normalize(text)
    if not norm:
        return False
    if any(sym in norm for sym in lexicons().get("money_symbols", [])):
        return True
    return bool(re.search(r"\d[\d,]*(\.\d{1,2})?\s*(inr|usd|eur|gbp|rs)\b", norm))


def parse_money(text: Optional[str]) -> List[Tuple[float, str]]:
    """Extract ``(value, matched_text)`` pairs from free text."""
    if not text:
        return []
    out: List[Tuple[float, str]] = []
    for m in re.finditer(
        r"(?:[₹$€£¥]|\brs\.?\s?|\binr\s?|\busd\s?)\s*([\d,]+(?:\.\d{1,2})?)"
        r"|([\d,]+(?:\.\d{1,2})?)\s*(?:inr|usd|eur|gbp|rupees)\b",
        str(text),
        re.I,
    ):
        raw = m.group(1) or m.group(2)
        try:
            out.append((float(raw.replace(",", "")), m.group(0).strip()))
        except (TypeError, ValueError):
            continue
    return out
