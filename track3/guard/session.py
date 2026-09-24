"""guard.session - provenance of page state across a run.

``precheck_optins`` asks a question a single snapshot cannot answer: *who*
checked this box?  A checkbox that is checked because the agent deliberately
checked it is fine.  A checkbox that arrived checked, or that got checked by
page script while the agent was doing something else, is a dark pattern.

So the guard keeps a tiny append-only journal of what the agent itself did.

**Purity contract.**  ``audit()`` never mutates the session.  It only reads it.
The adapter (MCP tool layer, Playwright shim, HTTP service) calls
:meth:`GuardSession.observe` *after* an action has actually been executed.
That keeps ``audit(snapshot, action, task, config)`` a pure function of its
arguments, exactly as CONTRACTS section 8 requires, while still giving the
guard memory.

Provenance keys are ``(url_path, ref)``.  Refs are only stable within a page,
so the path scopes them; a fresh navigation therefore correctly forgets that
the agent once ticked "ref_31" on a different page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from .types import Action, PageSnapshot

__all__ = ["GuardSession", "StateChange"]

ProvenanceKey = Tuple[str, str]


def _path_of(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path or '/'}"
    except ValueError:
        return str(url)


@dataclass
class StateChange:
    """One recorded, agent-initiated mutation."""

    kind: str  # "check" | "uncheck" | "type" | "click" | "submit" | "navigate"
    url_path: str
    ref: Optional[str]
    detail: Dict[str, Any] = field(default_factory=dict)
    seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "url_path": self.url_path,
            "ref": self.ref,
            "detail": dict(self.detail),
            "seq": self.seq,
        }


@dataclass
class GuardSession:
    """Mutable run-scoped memory.  Attach it to ``GuardConfig.session``."""

    run_id: str = ""
    history: List[StateChange] = field(default_factory=list)
    # (url_path, ref) pairs the agent itself put into the checked state.
    _agent_checked: Set[ProvenanceKey] = field(default_factory=set)
    # (url_path, ref) pairs the agent typed into, and what it typed.
    _agent_typed: Dict[ProvenanceKey, str] = field(default_factory=dict)
    _seq: int = 0

    # ---- reads (used by the checks; never mutate) -------------------------

    def agent_checked(self, url: Optional[str], ref: Optional[str]) -> bool:
        if not ref:
            return False
        return (_path_of(url), ref) in self._agent_checked

    def agent_typed(self, url: Optional[str], ref: Optional[str]) -> Optional[str]:
        if not ref:
            return None
        return self._agent_typed.get((_path_of(url), ref))

    def checked_refs(self, url: Optional[str]) -> List[str]:
        path = _path_of(url)
        return sorted(r for (p, r) in self._agent_checked if p == path)

    def snapshot_state(self) -> Dict[str, Any]:
        """Serialisable view, for the dashboard and for run traces."""
        return {
            "run_id": self.run_id,
            "agent_checked": [list(k) for k in sorted(self._agent_checked)],
            "agent_typed_refs": [list(k) for k in sorted(self._agent_typed)],
            "history": [h.to_dict() for h in self.history],
        }

    # ---- writes (called by the adapter, after execution) ------------------

    def observe(
        self,
        snapshot: Optional[PageSnapshot],
        action: Action,
        executed: bool = True,
    ) -> Optional[StateChange]:
        """Record an action the agent actually performed.

        ``snapshot`` is the page state the agent saw *before* acting, which is
        what tells us whether a click on a checkbox was a check or an uncheck.
        Returns the recorded change, or ``None`` if nothing was worth
        recording.  A blocked action (``executed=False``) is never recorded -
        it did not happen.
        """
        if not executed:
            return None
        url = snapshot.url if snapshot is not None else ""
        path = _path_of(url)
        self._seq += 1
        change: Optional[StateChange] = None

        if action.type == "click" and action.ref:
            fld = snapshot.field(action.ref) if snapshot is not None else None
            if fld is not None and (fld.type or "").lower() in ("checkbox", "radio"):
                was_checked = bool(fld.checked)
                kind = "uncheck" if was_checked else "check"
                key = (path, action.ref)
                if kind == "check":
                    self._agent_checked.add(key)
                else:
                    self._agent_checked.discard(key)
                change = StateChange(
                    kind=kind,
                    url_path=path,
                    ref=action.ref,
                    detail={"field": fld.describe, "wasChecked": was_checked},
                    seq=self._seq,
                )
            else:
                change = StateChange(kind="click", url_path=path, ref=action.ref, seq=self._seq)

        elif action.type == "type" and action.ref:
            self._agent_typed[(path, action.ref)] = action.text or ""
            change = StateChange(
                kind="type",
                url_path=path,
                ref=action.ref,
                detail={"length": len(action.text or "")},
                seq=self._seq,
            )

        elif action.type == "submit":
            change = StateChange(kind="submit", url_path=path, ref=action.ref, seq=self._seq)

        elif action.type == "navigate":
            change = StateChange(
                kind="navigate", url_path=path, ref=None, detail={"to": action.url}, seq=self._seq
            )

        if change is not None:
            self.history.append(change)
        return change

    def observe_setter(
        self,
        snapshot: Optional[PageSnapshot],
        ref: str,
        checked: bool,
    ) -> StateChange:
        """Record a direct checkbox set performed by the adapter (for example
        the guard's own REWRITE that unchecks a pre-checked opt-in)."""
        path = _path_of(snapshot.url if snapshot is not None else "")
        self._seq += 1
        key = (path, ref)
        if checked:
            self._agent_checked.add(key)
        else:
            self._agent_checked.discard(key)
        change = StateChange(
            kind="check" if checked else "uncheck",
            url_path=path,
            ref=ref,
            detail={"source": "guard-rewrite"},
            seq=self._seq,
        )
        self.history.append(change)
        return change

    def reset(self) -> None:
        self.history.clear()
        self._agent_checked.clear()
        self._agent_typed.clear()
        self._seq = 0
