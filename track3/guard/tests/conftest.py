"""Shared fixtures.  Everything here is synthetic and local to guard/tests/ -
the guard test suite deliberately does not depend on track3/sites/, which
another agent owns and is building concurrently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from guard.session import GuardSession
from guard.types import Action, GuardConfig, PageSnapshot, TaskDescriptor

FIXTURES = Path(__file__).parent / "fixtures"


def load_snapshot(name: str) -> PageSnapshot:
    with open(FIXTURES / f"{name}.json", "r", encoding="utf-8") as fh:
        return PageSnapshot.from_dict(json.load(fh))


def load_task(name: str = "task_checkout") -> TaskDescriptor:
    with open(FIXTURES / f"{name}.json", "r", encoding="utf-8") as fh:
        return TaskDescriptor.from_dict(json.load(fh))


# ---- builders for one-off synthetic cases --------------------------------

DEFAULT_STYLE: Dict[str, Any] = {
    "opacity": 1.0,
    "fontSize": 14,
    "color": "#111111",
    "backgroundColor": "#ffffff",
    "visibility": "visible",
    "display": "block",
    "zIndex": 0,
    "pointerEvents": "auto",
    "clipPath": "none",
    "transform": "none",
}


def element(
    ref: str,
    role: str = "button",
    name: str = "Button",
    box: Optional[Dict[str, float]] = None,
    hit: Optional[str] = None,
    style: Optional[Dict[str, Any]] = None,
    attrs: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ref": ref,
        "role": role,
        "name": name,
        "text": kwargs.pop("text", name),
        "box": box or {"x": 100, "y": 100, "w": 120, "h": 40},
        "computed": {**DEFAULT_STYLE, **(style or {})},
        "attrs": attrs or {},
        "inAccessibilityTree": kwargs.pop("inAccessibilityTree", True),
        "hitTestRef": hit if hit is not None else ref,
    }
    out.update(kwargs)
    return out


def snapshot(
    url: str = "http://127.0.0.1:8901/cart",
    elements: Optional[List[Dict[str, Any]]] = None,
    forms: Optional[List[Dict[str, Any]]] = None,
    text_nodes: Optional[List[Dict[str, Any]]] = None,
    amounts: Optional[List[Dict[str, Any]]] = None,
    title: str = "Checkout",
) -> PageSnapshot:
    return PageSnapshot.from_dict(
        {
            "url": url,
            "title": title,
            "viewport": {"w": 1280, "h": 800},
            "elements": elements or [],
            "forms": forms or [],
            "textNodes": text_nodes or [],
            "amounts": amounts or [],
        }
    )


@pytest.fixture
def task() -> TaskDescriptor:
    return load_task()


@pytest.fixture
def config() -> GuardConfig:
    """Arm B: deterministic layers only, zero LLM calls."""
    return GuardConfig(enable_l3=False, session=GuardSession(run_id="test"))


@pytest.fixture
def session(config: GuardConfig) -> GuardSession:
    return config.session


@pytest.fixture
def click():
    def _click(ref: str) -> Action:
        return Action(type="click", ref=ref)

    return _click


@pytest.fixture
def submit():
    def _submit(ref: str) -> Action:
        return Action(type="submit", ref=ref)

    return _submit
