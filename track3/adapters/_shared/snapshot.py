"""
Shapes the raw dict returned by SNAPSHOT_EXTRACTOR_JS (adapters/_shared/snapshot_js.py)
for consumption by the guard core, via adapters/_shared/guard_client.snapshot_from_raw.
Used by both the MCP server (async Playwright) and the Playwright shim (sync
Playwright) -- the extraction logic itself lives once, in JS; this module has no
opinion on which PageSnapshot class the raw dict becomes (that's guard_client's job,
since it depends on whether the real guard/ package or the local fallback is active).
"""
from __future__ import annotations

from adapters._shared.contracts import (
    Action, AmountSnapshot, BoundingBox, ComputedStyle, ElementSnapshot, FormField,
    FormSnapshot, PageSnapshot, TextNodeSnapshot, Viewport,
)
from adapters._shared.snapshot_js import SNAPSHOT_EXTRACTOR_JS


async def extract_raw_async(page) -> dict:
    """For the MCP server, which uses playwright.async_api."""
    return await page.evaluate(SNAPSHOT_EXTRACTOR_JS)


def extract_raw_sync(page) -> dict:
    """For the Playwright in-process shim, which uses playwright.sync_api."""
    return page.evaluate(SNAPSHOT_EXTRACTOR_JS)


def ref_selector(ref: str) -> str:
    return f'[data-guard-ref="{ref}"]'


# ---- local-fallback shaping (only exercised when guard/ is not importable) --------

def _shape_element(raw: dict) -> ElementSnapshot:
    return ElementSnapshot(
        ref=raw["ref"],
        role=raw["role"],
        name=raw["name"],
        text=raw["text"],
        box=BoundingBox(**raw["box"]),
        computed=ComputedStyle(**raw["computed"]),
        attrs=raw["attrs"],
        inAccessibilityTree=raw["inAccessibilityTree"],
        hitTestRef=raw["hitTestRef"],
        checked=raw.get("checked"),
        hitTestAncestors=raw.get("hitTestAncestors", []),
    )


def _shape_form(raw: dict) -> FormSnapshot:
    return FormSnapshot(
        ref=raw["ref"],
        action=raw["action"],
        method=raw["method"],
        fields=[FormField(**f) for f in raw["fields"]],
    )


def raw_to_snapshot(raw: dict) -> PageSnapshot:
    """CONTRACTS-shaped local dataclass version, used only by
    adapters/_shared/guard_stub.py when the real guard/ package isn't importable."""
    return PageSnapshot(
        url=raw["url"],
        title=raw["title"],
        viewport=Viewport(**raw["viewport"]),
        elements=[_shape_element(e) for e in raw["elements"]],
        forms=[_shape_form(f) for f in raw["forms"]],
        textNodes=[TextNodeSnapshot(**t) for t in raw["textNodes"]],
        amounts=[AmountSnapshot(**a) for a in raw["amounts"]],
    )
