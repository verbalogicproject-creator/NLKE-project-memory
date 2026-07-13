"""Tests for `project_memory.graph` (M1 — real graph-walk).

Builds tiny synthetic edge-fact graphs directly via `record_fact` (the same
`tags=[source, target, "edge", category]` convention `portfolio.py` writes),
mirroring `test_artifact.py`'s pattern for hand-seeded edges — no need for a
full `index_portfolio` run to exercise pure graph-walk logic.
"""

from __future__ import annotations

from project_memory import ProjectMemory
from project_memory.graph import (
    _MAX_HITS,
    EDGE_CATEGORIES,
    edges_touching,
    known_projects,
    walk,
)


def _edge(mem: ProjectMemory, source: str, target: str, category: str) -> None:
    mem.record_fact(
        f"{source} {category} {target}.",
        reason=f"{source}'s own docs name '{target}'",
        tags=[source, target, "edge", category],
    )


def _mark_known(mem: ProjectMemory, *names: str) -> None:
    """Give each name at least one indexed episode, so `known_projects` (and
    therefore a GraphHit's `resolved`) treats it as a real, indexed project."""
    for name in names:
        mem.remember(f"{name}: placeholder milestone.", kind="milestone", batch=name)


def test_edges_touching_forward_and_reverse():
    mem = ProjectMemory.open()
    _edge(mem, "a", "b", "composes")
    forward = edges_touching(mem, "a")
    reverse = edges_touching(mem, "b")
    assert len(forward) == 1 and forward[0].other == "b" and forward[0].direction == "forward"
    assert len(reverse) == 1 and reverse[0].other == "a" and reverse[0].direction == "reverse"
    mem.close()


def test_known_projects_reflects_indexed_batches():
    mem = ProjectMemory.open()
    _mark_known(mem, "a", "b")
    assert known_projects(mem) == {"a", "b"}
    mem.close()


def test_walk_hops1_matches_edges_touching():
    mem = ProjectMemory.open()
    _edge(mem, "a", "b", "composes")
    _edge(mem, "a", "d", "built_by")
    _mark_known(mem, "a", "b")
    hits = walk(mem, "a", hops=1)
    nodes = {h.node for h in hits}
    assert nodes == {"b", "d"}
    b_hit = next(h for h in hits if h.node == "b")
    assert len(b_hit.path) == 1 and b_hit.score == EDGE_CATEGORIES["composes"]["weight"]
    assert b_hit.resolved is True
    d_hit = next(h for h in hits if h.node == "d")
    assert d_hit.resolved is False  # "d" was never given an episode
    mem.close()


def test_walk_hops2_discovers_second_hop_and_scores_it_lower():
    mem = ProjectMemory.open()
    _edge(mem, "a", "b", "composes")
    _edge(mem, "b", "c", "composes")
    _edge(mem, "a", "d", "built_by")
    _mark_known(mem, "a", "b")
    hits = {h.node: h for h in walk(mem, "a", hops=2)}

    assert set(hits) == {"b", "c", "d"}
    assert hits["c"].score < hits["b"].score  # 2-hop discounted below the 1-hop it routes through
    assert len(hits["c"].path) == 2
    assert hits["c"].path[0].other == "b" and hits["c"].path[1].other == "c"
    assert hits["c"].resolved is False  # "c" was never given an episode

    # A 2-hop composes->composes chain (0.6) can still outrank a weaker 1-hop
    # built_by (0.5) — a deliberate consequence of the declared weight/decay
    # formula, not a bug; documents the actual ordering, not an aspiration.
    assert hits["c"].score > hits["d"].score
    mem.close()


def test_walk_never_routes_back_to_the_origin():
    mem = ProjectMemory.open()
    _edge(mem, "a", "b", "composes")
    _edge(mem, "b", "c", "composes")
    _edge(mem, "c", "a", "composes")  # closes a 3-node cycle back to "a"
    hits = walk(mem, "a", hops=2)
    assert "a" not in {h.node for h in hits}


def test_walk_hops_cap_excludes_a_third_hop_neighbor():
    mem = ProjectMemory.open()
    _edge(mem, "a", "b", "composes")
    _edge(mem, "b", "c", "composes")
    _edge(mem, "c", "e", "composes")  # 3 hops from a
    hits = walk(mem, "a", hops=2)
    assert {h.node for h in hits} == {"b", "c"}
    assert "e" not in {h.node for h in hits}


def test_walk_dedup_keeps_the_higher_scoring_path():
    mem = ProjectMemory.open()
    # Two 2-hop routes to "x": a->p->x (composes, composes -> score 0.6)
    # and a->q->x (built_by, built_by -> score 0.15). Both reach the same
    # node; only the stronger path's score should survive.
    _edge(mem, "a", "p", "composes")
    _edge(mem, "p", "x", "composes")
    _edge(mem, "a", "q", "built_by")
    _edge(mem, "q", "x", "built_by")
    hits = {h.node: h for h in walk(mem, "a", hops=2)}
    assert hits["x"].score == 0.6
    assert hits["x"].path[0].other == "p"  # the winning path, not the q-route
    mem.close()


def test_walk_caps_total_hits():
    mem = ProjectMemory.open()
    for i in range(_MAX_HITS + 10):
        _edge(mem, "hub", f"leaf{i}", "composes")
    hits = walk(mem, "hub", hops=1)
    assert len(hits) == _MAX_HITS
    mem.close()


def test_walk_rejects_hops_below_1():
    import pytest

    mem = ProjectMemory.open()
    with pytest.raises(ValueError):
        walk(mem, "a", hops=0)
    mem.close()
