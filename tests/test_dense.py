"""The optional dense signal must degrade byte-identically to lexical."""

from project_memory import build_demo, dense_available, hash_embedder
from project_memory.dense import build_dense_index


QUERY = "timezone bug utc"


def _ids(mem):
    return [(h["table"], h["id"]) for h in mem.recall(QUERY, limit=10)]


def test_dead_embedder_is_byte_identical_to_no_dense():
    no_dense = _ids(build_demo())
    dead = _ids(build_demo(embedder=lambda t: None))
    assert no_dense == dead


def test_no_embedder_is_deterministic():
    assert _ids(build_demo()) == _ids(build_demo())


def test_live_embedder_still_returns_hits():
    if not dense_available():
        return  # numpy not installed → lexical-only path already covered above
    live = build_demo(embedder=hash_embedder()).recall(QUERY, limit=5)
    assert live


def test_build_dense_index_none_without_numpy(monkeypatch):
    # Simulate numpy-absent: build_dense_index returns None → dense degrades.
    import project_memory.dense as d
    monkeypatch.setattr(d, "dense_available", lambda: False)
    mem = build_demo()
    idx = build_dense_index(mem.conn, mem.schema, hash_embedder())
    assert idx is None


def test_dense_index_items_carry_table_and_id():
    if not dense_available():
        return
    mem = build_demo()
    from project_memory.dense import _iter_items
    items = _iter_items(mem.conn, mem.schema)
    assert items
    assert all("table" in it and "id" in it and it["_text"] for it in items)
    assert {it["table"] for it in items} == {"episodes", "facts"}
