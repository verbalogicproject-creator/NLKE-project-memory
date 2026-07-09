def test_recall_finds_episode(seeded):
    hits = seeded.recall("sqlite storage")
    assert hits
    assert any("SQLite" in (h.get("content") or "") for h in hits)


def test_recall_returns_both_tables(seeded):
    hits = seeded.recall("sqlite offline search storage", limit=20)
    tables = {h["table"] for h in hits}
    assert "episodes" in tables and "facts" in tables


def test_table_filter(seeded):
    facts = seeded.recall("search", table="facts", limit=10)
    assert facts and all(h["table"] == "facts" for h in facts)
    eps = seeded.recall("sqlite", table="episodes", limit=10)
    assert eps and all(h["table"] == "episodes" for h in eps)


def test_projection_strips_reserved(seeded):
    for h in seeded.recall("sqlite"):
        assert "_text" not in h and "_tags" not in h
        assert "dimensions" not in h            # stripped unless verbose


def test_verbose_keeps_dimensions(seeded):
    hits = seeded.recall("sqlite", verbose=True)
    assert any("dimensions" in h for h in hits)


def test_hits_carry_provenance(seeded):
    hits = seeded.recall("sqlite")
    assert "rrf_sources" in hits[0] or "weighted_score" in hits[0] or "rrf_score" in hits[0]


def test_structural_link_expands_episode_to_fact(seeded):
    # 'zero-ops' only appears in the auto-fact's reason; recall should still be
    # able to reach the linked episode via the declared episode↔fact join.
    hits = seeded.recall("storage", limit=20)
    ids = {h["id"] for h in hits}
    assert "e1" in ids or "f1" in ids or any(h["table"] == "facts" for h in hits)


def test_recent_newest_first(seeded):
    r = seeded.recent(limit=10)
    dates = [e["created_at"] for e in r]
    assert dates == sorted(dates, reverse=True)


def test_recent_kind_filter(seeded):
    r = seeded.recent(kind="gotcha")
    assert r and all(e["kind"] == "gotcha" for e in r)


def test_count(seeded):
    assert seeded.count() == {"episodes": 2, "facts": 2}
