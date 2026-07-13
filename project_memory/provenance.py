"""provenance.py — what the brain loaded, when, why, and whether it was used
(M4, MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md).

The spec sketched a bespoke ``brain-loads.log`` jsonl (``{ts, scope, kind,
trigger}``) plus a ``used``/``unused`` marker. **This repo already made a
different, documented call** (see `cli.py::cmd_brain_load`): every load is an
*episode* (``kind="brain_load"``) in the brain's own store, not a side-file —
so `recall`/`ask`/`recent` already see it, which is what a memory system that
remembers its own use should look like. M4 builds the provenance *reports* on
top of that existing log rather than introducing a second, disconnected sink:

  - a **``used`` marker** is one more append-only episode (``kind="brain_use"``),
    not a mutable flag — honoring "episodes are append-only" (CLAUDE.md). A load
    of scope *S* counts as used iff a ``brain_use`` for *S* exists (within the
    same session, when one is given).
  - **"loaded but never used"** (`unused_loads`) folds loads against uses.
  - a **session's journey** (`journey`) reconstructs the ordered load/use/export
    events of one session as a readable story.

**Declared over inferred (CLAUDE.md principle):** a load is treated as used only
when *explicitly* marked, never guessed from later activity. Auto-inferring use
from a subsequent scoped action ("they recorded a decision for *S*, so they must
have used *S*'s context") would fabricate a signal the log doesn't actually
carry; that heuristic is a deliberate non-goal here.

Sessions ride the episode table's existing ``session_id`` column (nothing new in
the schema); pre-M4 loads simply have ``session_id = NULL`` and fold into the
all-sessions view. Reads go straight against ``mem.schema.episode_table`` — the
table name comes from the schema, never hardcoded (same discipline as
`query.py::recent`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: The episode kinds that carry portfolio-brain provenance. Ordered load →
#: use → export, but the log itself is ordered by time, not by this tuple.
PROVENANCE_KINDS: tuple[str, ...] = ("brain_load", "brain_use", "brain_export")

# kind → the event verb the reports speak in.
_EVENT_OF_KIND = {"brain_load": "load", "brain_use": "use", "brain_export": "export"}


@dataclass(frozen=True)
class ProvEvent:
    """One normalized provenance event, read back from the episode log.

    ``scope`` is the project or pack name; ``scope_kind`` is ``"project"`` /
    ``"pack"`` for loads (and ``"project"`` for exports, which packs can't be),
    ``""`` when the log doesn't record it (a bare ``use`` marker). ``trigger``
    is only meaningful for loads (startup/menu/cli/hook/…); ``detail`` carries
    the provider (export) or an optional note (use).
    """

    ts: str
    event: str
    scope: str
    scope_kind: str = ""
    trigger: str = ""
    session: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts, "event": self.event, "scope": self.scope,
            "scope_kind": self.scope_kind, "trigger": self.trigger,
            "session": self.session, "detail": self.detail,
        }

    def phrase(self) -> str:
        """This event as one narrative clause (no ordinal, no timestamp)."""
        scoped = f"{self.scope_kind} '{self.scope}'".strip()
        if self.event == "load":
            via = f"  (via {self.trigger})" if self.trigger else ""
            return f"loaded {scoped}{via}"
        if self.event == "export":
            arrow = f" → {self.detail}" if self.detail else ""
            return f"exported {scoped}{arrow}"
        # use
        note = f" — {self.detail}" if self.detail else ""
        return f"used '{self.scope}'{note}"


def _event_from_row(kind: str, tags: list[str], meta: dict[str, Any], session: str | None, ts: str) -> ProvEvent:
    """Normalize one raw episode row into a `ProvEvent`. Defensive about the
    exact tag/metadata shape so a hand-written or older row never crashes a
    report — metadata wins, tags are the fallback, "" is the floor."""
    event = _EVENT_OF_KIND[kind]
    scope = (tags[0] if tags else "") or ""
    if event == "load":
        scope_kind = tags[1] if len(tags) > 1 else ""
        trigger = meta.get("trigger") or (tags[2] if len(tags) > 2 else "")
        return ProvEvent(ts, event, scope, scope_kind, trigger, session, "")
    if event == "export":
        detail = meta.get("provider") or (tags[1] if len(tags) > 1 else "")
        return ProvEvent(ts, event, scope, "project", "", session, detail)
    return ProvEvent(ts, event, scope, "", "", session, meta.get("note") or "")


def provenance_events(mem: Any, *, session: str | None = None) -> list[ProvEvent]:
    """Every load/use/export event in the brain, oldest first (ties broken by
    id for a stable order). Restricted to one ``session`` when given — pre-M4
    loads (``session_id = NULL``) only appear in the all-sessions view."""
    placeholders = ", ".join("?" for _ in PROVENANCE_KINDS)
    sql = (
        f"SELECT kind, tags, metadata, session_id, created_at, id "
        f"FROM {mem.schema.episode_table} WHERE kind IN ({placeholders})"
    )
    params: list[Any] = list(PROVENANCE_KINDS)
    if session is not None:
        sql += " AND session_id = ?"
        params.append(session)
    sql += " ORDER BY created_at ASC, id ASC"

    events: list[ProvEvent] = []
    for kind, tags_raw, meta_raw, session_id, ts, _id in mem.conn.execute(sql, params).fetchall():
        tags = json.loads(tags_raw) if tags_raw else []
        meta = json.loads(meta_raw) if meta_raw else {}
        events.append(_event_from_row(kind, tags, meta, session_id, ts))
    return events


def record_use(
    mem: Any,
    scope: str,
    *,
    session: str | None = None,
    note: str | None = None,
    id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Mark ``scope``'s loaded context as *used* — one append-only
    ``brain_use`` episode (the declared "used" marker). ``session`` stamps the
    existing ``session_id`` column so `unused_loads`/`journey` can fold it
    against loads within the same session. ``id``/``created_at`` are injectable
    for deterministic seeds and tests (same as every other write)."""
    if not scope or not scope.strip():
        raise ValueError("scope must be non-empty")
    tags = [scope, "used"]
    metadata: dict[str, Any] = {}
    if note:
        metadata["note"] = note
    return mem.remember(
        f"used '{scope}'", kind="brain_use", session_id=session, tags=tags,
        metadata=metadata, method="brain_use", id=id, created_at=created_at,
    )


def unused_loads(
    mem: Any, *, session: str | None = None, scope_kind: str | None = None,
) -> list[ProvEvent]:
    """Loads that were never marked used — the "loaded but never used" report.

    A load of scope *S* is used iff a ``brain_use`` for *S* exists in the same
    view (the same session when ``session`` is given, else all-time). Returns
    one load event per still-unused scope, earliest load kept. ``scope_kind``
    restricts the report — ``"pack"`` answers the spec's "report *packs*
    loaded-but-never-used" directly.
    """
    events = provenance_events(mem, session=session)
    used = {ev.scope for ev in events if ev.event == "use"}
    seen: set[str] = set()
    out: list[ProvEvent] = []
    for ev in events:
        if ev.event != "load" or ev.scope in used or ev.scope in seen:
            continue
        if scope_kind is not None and ev.scope_kind != scope_kind:
            continue
        seen.add(ev.scope)
        out.append(ev)
    return out


@dataclass(frozen=True)
class JourneyReport:
    """One session's provenance, reconstructed: the ordered events + which of
    its loads went unused. ``session`` is ``None`` for the all-sessions view."""

    session: str | None
    events: tuple[ProvEvent, ...]
    unused: tuple[ProvEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "events": [e.to_dict() for e in self.events],
            "unused": [e.to_dict() for e in self.unused],
        }

    def story(self) -> str:
        """The session's journey as a readable narrative."""
        who = f"session {self.session}" if self.session else "all sessions"
        lines = [f"# Journey — {who}", ""]
        if not self.events:
            lines.append(f"_No load/use/export provenance recorded for {who}._")
            return "\n".join(lines)

        lines.append(f"{len(self.events)} event{'s' if len(self.events) != 1 else ''}:")
        for i, ev in enumerate(self.events, start=1):
            lines.append(f"  {i}. {ev.phrase()}")

        if self.unused:
            lines += ["", f"Loaded but never used ({len(self.unused)}):"]
            for ev in self.unused:
                scoped = f"{ev.scope_kind} '{ev.scope}'".strip()
                lines.append(f"  · {scoped}")
        return "\n".join(lines)


def journey(mem: Any, *, session: str | None = None) -> JourneyReport:
    """Reconstruct a session's journey (all sessions when ``session`` is
    ``None``): the ordered load/use/export events + its loaded-but-never-used
    tail, ready to render as a story or a `--json` payload."""
    events = provenance_events(mem, session=session)
    unused = unused_loads(mem, session=session)
    return JourneyReport(session=session, events=tuple(events), unused=tuple(unused))
