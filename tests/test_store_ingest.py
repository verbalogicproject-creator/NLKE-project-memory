import json

import pytest

from project_memory import MemorySchema, ProjectMemory
from project_memory.store import connect, create_store


def test_tables_and_fts_created():
    conn = connect()
    create_store(conn, MemorySchema())
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"episodes", "facts", "episodes_fts", "facts_fts"} <= tables


def test_create_store_idempotent():
    conn = connect()
    create_store(conn, MemorySchema())
    create_store(conn, MemorySchema())  # must not raise


def test_remember_appends(mem):
    r = mem.remember("something happened", kind="general")
    assert r["id"] and r["fact_id"] is None
    assert mem.count()["episodes"] == 1


def test_remember_validates_kind(mem):
    with pytest.raises(ValueError):
        mem.remember("x", kind="not-a-kind")


def test_remember_rejects_empty(mem):
    with pytest.raises(ValueError):
        mem.remember("   ", kind="general")


def test_auto_fact_crystallizes(mem):
    r = mem.remember("we chose X", kind="decision", auto_fact=True, reason="because")
    assert r["fact_id"]
    assert mem.count() == {"episodes": 1, "facts": 1}


def test_episodes_are_append_only(mem):
    mem.remember("same event", kind="general")
    mem.remember("same event", kind="general")
    assert mem.count()["episodes"] == 2   # not deduped


def test_record_fact_and_supersede(mem):
    a = mem.record_fact("old truth", id="fa")
    b = mem.record_fact("new truth", supersedes="fa")
    assert b["supersedes"] == "fa"
    # only the active fact is counted / searchable
    assert mem.count()["facts"] == 1
    statuses = {r[0]: r[1] for r in mem.conn.execute("SELECT id, status FROM facts").fetchall()}
    assert statuses["fa"] == "superseded"
    assert statuses[b["id"]] == "active"


def test_invalidate_fact(mem):
    mem.record_fact("wrong", id="fx")
    assert mem.invalidate_fact("fx") is True
    assert mem.count()["facts"] == 0


def test_tags_stored_as_json(mem):
    mem.remember("tagged", kind="general", tags=["a", "b"], id="e")
    raw = mem.conn.execute("SELECT tags FROM episodes WHERE id='e'").fetchone()[0]
    assert json.loads(raw) == ["a", "b"]


def test_schema_version_stamped(mem):
    mem.remember("x", kind="general", id="e")
    v = mem.conn.execute("SELECT schema_version FROM episodes WHERE id='e'").fetchone()[0]
    assert v == MemorySchema().schema_version


def test_explicit_id_and_created_at_are_deterministic():
    a = ProjectMemory.open(); a.remember("x", kind="general", id="e", created_at="2026-01-01T00:00:00+00:00")
    b = ProjectMemory.open(); b.remember("x", kind="general", id="e", created_at="2026-01-01T00:00:00+00:00")
    ra = a.conn.execute("SELECT id, created_at FROM episodes").fetchone()
    rb = b.conn.execute("SELECT id, created_at FROM episodes").fetchone()
    assert ra == rb
