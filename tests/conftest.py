import pytest

from project_memory import MemorySchema, ProjectMemory, build_demo


@pytest.fixture
def mem():
    """A fresh in-memory ProjectMemory with the default schema."""
    m = ProjectMemory.open()
    yield m
    m.close()


@pytest.fixture
def demo():
    """The packaged, deterministic demo memory (Orchard)."""
    m = build_demo()
    yield m
    m.close()


@pytest.fixture
def seeded():
    """A small, hand-seeded memory with a known shape for recall assertions."""
    m = ProjectMemory.open()
    m.remember("We chose SQLite over Postgres for local-first storage.",
               kind="decision", tags=["storage"], id="e1", created_at="2026-01-01T00:00:00+00:00",
               auto_fact=True, reason="zero-ops")
    m.remember("FTS5 triggers crash on NULL columns; coalesce to ''.",
               kind="gotcha", tags=["fts5"], id="e2", created_at="2026-01-02T00:00:00+00:00")
    m.record_fact("Search runs fully offline.", reason="FTS5 + BM25",
                  tags=["search"], id="f2", created_at="2026-01-03T00:00:00+00:00")
    yield m
    m.close()
