from project_memory import MEMORY_DIMENSIONS, custom_dimensions
from project_memory.dimensions import DimensionDef, overall, score


def test_palette_is_twelve():
    assert len(MEMORY_DIMENSIONS) == 12


def test_fact_outranks_episode_on_storage_tier():
    fact = score({"claim": "X is the store of record", "reason": "y"}, "store")
    episode = score({"content": "we talked about the store"}, "store")
    assert fact["storage_tier"] >= episode["storage_tier"]


def test_gotcha_scores_error_recovery():
    s = score({"content": "FTS5 trigger crash", "kind": "gotcha"}, "trigger")
    assert s["error_recovery"] == 1.0


def test_overall_in_range():
    s = score({"content": "offline search works", "kind": "insight"}, "offline search")
    assert 0.0 <= overall(s) <= 1.0


def test_custom_palette():
    extra = DimensionDef("recency", "temporal", "Newer scores higher.")
    schema = custom_dimensions(*MEMORY_DIMENSIONS.dims, extra)
    assert len(schema) == 13
    assert "recency" in schema.names
    # unregistered new dim scores neutral, not crash
    assert score({"content": "x"}, "x", schema)["recency"] == 0.5
