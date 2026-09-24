"""guard.colors - CSS colour parsing and *perceptual* distance.

Why this file exists: "text the same colour as the background" must never be
detected by string equality.  ``#ffffff`` vs ``rgb(254, 255, 255)`` vs
``rgba(255,255,255,0.98)`` are the same attack and must all be caught, while
``#111111`` on ``#ffffff`` must not be.

Two independent measures are computed and either one firing is enough:

* **WCAG contrast ratio** - the accessibility standard for legibility.
  1.0 means identical luminance, 21.0 is black on white.
* **CIE76 deltaE** in CIELAB - perceptual colour distance.  Catches the case
  where two colours have similar luminance but the standard would still call
  them legible, and vice versa.

Pure functions, no dependencies beyond the standard library.
"""

from __future__ import annotations

import math
import re
from typing import Optional, Tuple

RGBA = Tuple[float, float, float, float]  # 0-255, 0-255, 0-255, 0-1

__all__ = [
    "parse_color",
    "contrast_ratio",
    "delta_e",
    "colors_indistinguishable",
    "is_transparent",
]

# A deliberately small named-colour table: the ones a hand-written trap page
# actually uses.  Everything else parses through the numeric forms, which is
# what a browser's getComputedStyle returns anyway (always `rgb()`/`rgba()`).
_NAMED = {
    "black": (0, 0, 0, 1.0),
    "white": (255, 255, 255, 1.0),
    "red": (255, 0, 0, 1.0),
    "lime": (0, 255, 0, 1.0),
    "green": (0, 128, 0, 1.0),
    "blue": (0, 0, 255, 1.0),
    "yellow": (255, 255, 0, 1.0),
    "cyan": (0, 255, 255, 1.0),
    "aqua": (0, 255, 255, 1.0),
    "magenta": (255, 0, 255, 1.0),
    "fuchsia": (255, 0, 255, 1.0),
    "silver": (192, 192, 192, 1.0),
    "gray": (128, 128, 128, 1.0),
    "grey": (128, 128, 128, 1.0),
    "maroon": (128, 0, 0, 1.0),
    "olive": (128, 128, 0, 1.0),
    "navy": (0, 0, 128, 1.0),
    "teal": (0, 128, 128, 1.0),
    "purple": (128, 0, 128, 1.0),
    "orange": (255, 165, 0, 1.0),
    "transparent": (0, 0, 0, 0.0),
}

_RGB_RE = re.compile(
    r"^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)$",
    re.I,
)
_HSL_RE = re.compile(
    r"^hsla?\(\s*([-\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%(?:[\s,/]+([\d.]+%?))?\s*\)$",
    re.I,
)


def _num(tok: str, scale: float = 255.0) -> float:
    tok = tok.strip()
    if tok.endswith("%"):
        return float(tok[:-1]) / 100.0 * scale
    return float(tok)


def parse_color(value: Optional[str]) -> Optional[RGBA]:
    """Parse a CSS colour into ``(r, g, b, a)``.  ``None`` if unparseable."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if not v:
        return None
    if v in _NAMED:
        return _NAMED[v]  # type: ignore[return-value]
    if v.startswith("#"):
        h = v[1:]
        try:
            if len(h) == 3 or len(h) == 4:
                comps = [int(c * 2, 16) for c in h]
            elif len(h) == 6 or len(h) == 8:
                comps = [int(h[i : i + 2], 16) for i in range(0, len(h), 2)]
            else:
                return None
        except ValueError:
            return None
        if len(comps) == 3:
            return (comps[0], comps[1], comps[2], 1.0)
        return (comps[0], comps[1], comps[2], comps[3] / 255.0)
    m = _RGB_RE.match(v)
    if m:
        try:
            r, g, b = (_num(m.group(i)) for i in (1, 2, 3))
            a = 1.0 if m.group(4) is None else _num(m.group(4), 1.0)
        except ValueError:
            return None
        return (r, g, b, max(0.0, min(1.0, a)))
    m = _HSL_RE.match(v)
    if m:
        try:
            h = float(m.group(1)) % 360.0 / 360.0
            s = float(m.group(2)) / 100.0
            light = float(m.group(3)) / 100.0
            a = 1.0 if m.group(4) is None else _num(m.group(4), 1.0)
        except ValueError:
            return None
        r, g, b = _hsl_to_rgb(h, s, light)
        return (r * 255.0, g * 255.0, b * 255.0, max(0.0, min(1.0, a)))
    return None


def _hsl_to_rgb(h: float, s: float, light: float) -> Tuple[float, float, float]:
    if s == 0:
        return (light, light, light)

    def hue(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = light * (1 + s) if light < 0.5 else light + s - light * s
    p = 2 * light - q
    return (hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3))


def is_transparent(value: Optional[str], threshold: float = 0.1) -> bool:
    c = parse_color(value)
    return c is not None and c[3] <= threshold


def _composite(fg: RGBA, bg: RGBA) -> RGBA:
    """Alpha-composite ``fg`` over an opaque-ish ``bg``."""
    a = fg[3]
    if a >= 1.0:
        return fg
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(c: RGBA) -> float:
    r, g, b = (_srgb_to_linear(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: RGBA, bg: RGBA) -> float:
    """WCAG 2.x contrast ratio in [1.0, 21.0]. Alpha is composited first."""
    fg_c = _composite(fg, bg if bg[3] >= 1.0 else (255.0, 255.0, 255.0, 1.0))
    bg_c = _composite(bg, (255.0, 255.0, 255.0, 1.0))
    l1 = relative_luminance(fg_c)
    l2 = relative_luminance(bg_c)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _to_lab(c: RGBA) -> Tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(x) for x in c[:3])
    # sRGB D65 -> XYZ
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    # D65 white point
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(fg: RGBA, bg: RGBA) -> float:
    """CIE76 perceptual distance in CIELAB.  ~2.3 is a just-noticeable
    difference; under ~9 the two colours read as the same colour at body-text
    size."""
    opaque_bg = _composite(bg, (255.0, 255.0, 255.0, 1.0))
    l1 = _to_lab(_composite(fg, opaque_bg))
    l2 = _to_lab(opaque_bg)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(l1, l2)))


def colors_indistinguishable(
    color: Optional[str],
    background: Optional[str],
    min_contrast_ratio: float = 1.30,
    max_delta_e: float = 9.0,
):
    """Return ``(verdict, evidence)``.

    ``verdict`` is ``None`` when we cannot tell (unparseable colour, or a
    transparent background whose true painted colour is unknown).  Unknown is
    reported as unknown - never as suspicious - to protect the false positive
    rate.
    """
    fg = parse_color(color)
    bg = parse_color(background)
    if fg is None or bg is None:
        return None, {"reason": "unparseable", "color": color, "backgroundColor": background}
    if fg[3] <= 0.05:
        # Fully transparent *text* is the opacity attack, reported elsewhere.
        return True, {
            "color": color,
            "backgroundColor": background,
            "textAlpha": fg[3],
            "measure": "text-alpha-zero",
        }
    if bg[3] <= 0.05:
        # Transparent background: the painted colour comes from an ancestor we
        # were not given.  Unknown, not suspicious.
        return None, {
            "reason": "background-transparent",
            "color": color,
            "backgroundColor": background,
        }
    ratio = contrast_ratio(fg, bg)
    de = delta_e(fg, bg)
    verdict = ratio < min_contrast_ratio or de < max_delta_e
    return verdict, {
        "color": color,
        "backgroundColor": background,
        "contrastRatio": round(ratio, 3),
        "deltaE": round(de, 3),
        "thresholds": {"minContrastRatio": min_contrast_ratio, "maxDeltaE": max_delta_e},
        "measure": "wcag-contrast+cie76",
    }
