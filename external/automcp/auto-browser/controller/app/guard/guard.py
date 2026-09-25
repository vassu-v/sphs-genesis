"""ShoavGuard: thin controller-side wrapper around the S.H.O.A.V. filter core.

Wiring only (C-1). The gateway behavior hooks (C-3/C-4/C-5) are owned by
another agent; this module exposes the guard object, its mode/counters, and
fail-open decide helpers with no gateway imports.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

GUARD_MODES = ("off", "observe", "enforce")
GUARD_FAILS = ("open", "closed")

_COUNTER_KEYS = (
    "ingress_allow",
    "ingress_rewrite",
    "ingress_block",
    "ingress_escalate",
    "egress_allow",
    "egress_block",
    "egress_escalate",
    "errors",
    "fail_open",
)


class ShoavGuard:
    """Owns filter instances plus mode, fail policy, and verdict counters."""

    def __init__(
        self,
        mode: str = "observe",
        fail: str = "open",
        ingress_filter: Any | None = None,
        egress_filter: Any | None = None,
    ) -> None:
        self.mode = mode if mode in GUARD_MODES else "observe"
        self.fail = fail if fail in GUARD_FAILS else "open"
        self.ingress_filter = ingress_filter
        self.egress_filter = egress_filter
        self.counters: dict[str, int] = {key: 0 for key in _COUNTER_KEYS}

    @classmethod
    def from_settings(cls, settings: Any) -> "ShoavGuard | None":
        """Build a guard from controller Settings, or None when off.

        Returns None when SHOAV_GUARD_MODE is off (zero overhead path) and
        when the filter core cannot be loaded (fail open with a log line).
        """
        raw_mode = getattr(settings, "shoav_guard_mode", "off") or "off"
        mode = str(raw_mode).strip().lower()
        if mode == "off":
            return None
        if mode not in GUARD_MODES:
            logger.warning("unknown SHOAV_GUARD_MODE=%r, guard disabled", raw_mode)
            return None
        raw_fail = getattr(settings, "shoav_guard_fail", "open") or "open"
        fail = str(raw_fail).strip().lower()
        if fail not in GUARD_FAILS:
            logger.warning("unknown SHOAV_GUARD_FAIL=%r, using open", raw_fail)
            fail = "open"

        from .loader import load_filter_classes

        ingress_cls, egress_cls = load_filter_classes(settings)
        if ingress_cls is None and egress_cls is None:
            logger.warning("shoav filters unavailable, guard disabled (fail open)")
            return None
        try:
            ingress = ingress_cls() if ingress_cls is not None else None
            egress = egress_cls() if egress_cls is not None else None
        except Exception:
            logger.warning("shoav filter init failed, guard disabled (fail open)", exc_info=True)
            return None
        return cls(mode=mode, fail=fail, ingress_filter=ingress, egress_filter=egress)

    def _fail_open_result(self, stage: str, reason: str) -> dict[str, Any]:
        self.counters["errors"] += 1
        if self.fail == "closed":
            key = "ingress_block" if stage == "ingress" else "egress_block"
            self.counters[key] += 1
            return {
                "verdict": "BLOCK",
                "enforced": True,
                "mode": self.mode,
                "reason": reason,
                "note": "shoav filter error, fail closed",
            }
        self.counters["fail_open"] += 1
        return {
            "verdict": "ALLOW",
            "enforced": False,
            "mode": self.mode,
            "reason": reason,
            "note": "shoav filter error, fail open",
        }

    def decide_ingress(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run the ingress filter over an observation-shaped payload.

        Never raises: filter exceptions degrade to ALLOW with a guard note,
        unless fail policy is closed (then BLOCK). In observe mode the
        returned verdict is advisory and enforced is always False.
        """
        payload = dict(payload or {})
        if self.ingress_filter is None:
            return {
                "verdict": "ALLOW",
                "enforced": False,
                "mode": self.mode,
                "reason": "ingress filter unavailable",
                "note": "fail open",
            }
        try:
            result = self.ingress_filter.process(payload)
        except Exception as exc:
            logger.warning("shoav ingress filter failed: %s", exc, exc_info=True)
            return self._fail_open_result("ingress", f"ingress filter error: {exc}")
        verdict = str(result.get("verdict", "ALLOW")).upper()
        key = f"ingress_{verdict.lower()}"
        if key in self.counters:
            self.counters[key] += 1
        enforced = self.mode == "enforce" and verdict in ("REWRITE", "BLOCK", "ESCALATE")
        return {
            "verdict": verdict,
            "enforced": enforced,
            "mode": self.mode,
            "reason": result.get("telemetry", ""),
            "findings": result.get("findings", {}),
            "result": result,
        }

    def decide_egress(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run the egress filter over a click-shaped arg dict.

        Expects {"expected_ref": str, "hit_result": dict}. Missing keys or a
        missing filter degrade to ALLOW with a note. Never raises.
        """
        args = dict(args or {})
        if self.egress_filter is None:
            return {
                "verdict": "ALLOW",
                "enforced": False,
                "mode": self.mode,
                "reason": "egress filter unavailable",
                "note": "fail open",
            }
        expected_ref = args.get("expected_ref")
        hit_result = args.get("hit_result")
        if not expected_ref or not isinstance(hit_result, dict):
            return {
                "verdict": "ALLOW",
                "enforced": False,
                "mode": self.mode,
                "reason": "egress check skipped: missing expected_ref or hit_result",
                "note": "fail open",
            }
        try:
            result = self.egress_filter.verify_click(expected_ref, hit_result)
        except Exception as exc:
            logger.warning("shoav egress filter failed: %s", exc, exc_info=True)
            return self._fail_open_result("egress", f"egress filter error: {exc}")
        verdict = str(result.get("verdict", "ALLOW")).upper()
        key = f"egress_{verdict.lower()}"
        if key in self.counters:
            self.counters[key] += 1
        enforced = self.mode == "enforce" and verdict in ("BLOCK", "ESCALATE")
        return {
            "verdict": verdict,
            "enforced": enforced,
            "mode": self.mode,
            "reason": result.get("reason", ""),
            "result": result,
        }

    def snapshot(self) -> dict[str, Any]:
        """Status shape for the future GET /live-api/guard route (C-2)."""
        return {
            "mode": self.mode,
            "fail": self.fail,
            "counters": dict(self.counters),
            "ingress_available": self.ingress_filter is not None,
            "egress_available": self.egress_filter is not None,
        }
