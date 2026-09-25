"""Per-session state cache for the S.H.O.A.V. guard (C-1 wiring).

Thin wrapper with the same small API the filter core uses (get_or_create,
mark_touched, reset). C-5 owns touched tracking, navigation resets, and any
migration to the real filters.session_state.SessionStateStore.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GuardSessionEntry:
    session_id: str
    touched_refs: set[str] = field(default_factory=set)
    initial_form_snapshot: list[dict] | None = None
    last_cart_item_ids: set[str] = field(default_factory=set)

    def mark_touched(self, ref: str) -> None:
        self.touched_refs.add(ref)


class GuardSessionCache:
    """In-memory cache of GuardSessionEntry, keyed by session_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, GuardSessionEntry] = {}

    def get_or_create(self, session_id: str) -> GuardSessionEntry:
        entry = self._sessions.get(session_id)
        if entry is None:
            entry = GuardSessionEntry(session_id=session_id)
            self._sessions[session_id] = entry
        return entry

    def mark_touched(self, session_id: str, ref: str) -> None:
        self.get_or_create(session_id).mark_touched(ref)

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._sessions)


__all__ = ["GuardSessionCache", "GuardSessionEntry"]
