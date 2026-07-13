"""Writing to memory: remember episodes, crystallize + supersede facts.

Two write paths, mirroring the two-table model:

  - `remember(...)` appends an **episode** — an event. Episodes are append-only:
    remembering "the build broke again" twice records it twice, because it
    happened twice. Each is kind-validated against the schema's taxonomy.

  - `record_fact(...)` writes a durable **claim**, optionally superseding an
    older one. Facts are the *updatable* layer: when reality changes you don't
    delete the old fact, you supersede it, preserving the chain.

`remember(..., auto_fact=True)` does both: append the episode and crystallize it
into a fact in one call — the common "this decision is also a standing fact" case.

Every write accepts an explicit ``id`` and ``created_at`` so seeds and tests can
be fully deterministic; both default to a fresh uuid / UTC-now otherwise.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .schema import MemorySchema
from .store import new_id, now_iso


def remember(
    conn: sqlite3.Connection,
    schema: MemorySchema,
    content: str,
    *,
    kind: str = "general",
    session_id: str | None = None,
    batch: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    method: str = "manual",
    id: str | None = None,
    created_at: str | None = None,
    auto_fact: bool = False,
    reason: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Append an episode. With ``auto_fact=True`` also crystallize it as a fact.

    ``supersedes`` (only meaningful with ``auto_fact=True``) retires that fact
    id in the same call — "this decision replaces that one" in one step,
    instead of a separate ``record_fact`` call.

    Returns ``{"id", "kind", "fact_id"}`` (``fact_id`` is ``None`` unless a fact
    was crystallized).
    """
    if not content or not content.strip():
        raise ValueError("episode content must be non-empty")
    schema.validate_kind(kind)

    ep_id = id or new_id()
    ts = created_at or now_iso()
    conn.execute(
        # OR IGNORE: a caller-supplied deterministic `id` colliding with an
        # existing row means "this exact episode was already remembered" (the
        # portfolio indexer's re-run case) — a benign no-op, not an error.
        f"INSERT OR IGNORE INTO {schema.episode_table} "
        "(id, content, kind, session_id, batch, tags, metadata, method, schema_version, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ep_id, content, kind, session_id, batch,
            json.dumps(tags or []), json.dumps(metadata or {}),
            method, schema.schema_version, ts,
        ),
    )

    fact_id: str | None = None
    if auto_fact:
        fact_id = record_fact(
            conn, schema, content,
            reason=reason, source_episode_id=ep_id, tags=tags,
            method="auto_fact", created_at=ts, supersedes=supersedes,
        )["id"]

    conn.commit()
    return {"id": ep_id, "kind": kind, "fact_id": fact_id}


def record_fact(
    conn: sqlite3.Connection,
    schema: MemorySchema,
    claim: str,
    *,
    reason: str | None = None,
    source_episode_id: str | None = None,
    tags: list[str] | None = None,
    method: str = "manual",
    id: str | None = None,
    created_at: str | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Write a durable fact. If ``supersedes`` is given, retire that fact and
    point it at this new one (history preserved, not deleted).

    Returns ``{"id", "supersedes"}``.
    """
    if not claim or not claim.strip():
        raise ValueError("fact claim must be non-empty")

    fact_id = id or new_id()
    ts = created_at or now_iso()
    conn.execute(
        # OR IGNORE: same rationale as `remember` — a deterministic id colliding
        # with an existing row (the portfolio indexer's re-run case) is a
        # benign no-op, not an error.
        f"INSERT OR IGNORE INTO {schema.fact_table} "
        "(id, claim, reason, source_episode_id, tags, method, schema_version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fact_id, claim, reason, source_episode_id,
            json.dumps(tags or []), method, schema.schema_version, ts, ts,
        ),
    )
    if supersedes:
        conn.execute(
            f"UPDATE {schema.fact_table} "
            "SET status = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?",
            (fact_id, ts, supersedes),
        )
    conn.commit()
    return {"id": fact_id, "supersedes": supersedes}


def invalidate_fact(
    conn: sqlite3.Connection,
    schema: MemorySchema,
    fact_id: str,
    *,
    updated_at: str | None = None,
) -> bool:
    """Mark a fact invalidated (it was wrong, not merely outdated). Returns
    whether a row changed."""
    ts = updated_at or now_iso()
    cur = conn.execute(
        f"UPDATE {schema.fact_table} SET status = 'invalidated', updated_at = ? WHERE id = ?",
        (ts, fact_id),
    )
    conn.commit()
    return cur.rowcount > 0
