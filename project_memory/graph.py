"""graph.py — project_memory's own edge-fact graph: BFS + a declared,
transparent rescoring formula over the portfolio's cross-project edges.

Distinct from `declared_core`'s retrieval math (BM25/structural/RRF/intent,
which fuses ranked *text* relevance): this walks a small, explicit graph whose
edges are project_memory's own convention — facts tagged
``[source, target, "edge", category]`` (see ``portfolio.py``'s
``_edge_claim``) — not a `declared_core.CorpusSchema` `Link`. BFS over an
explicit typed-edge list is a different computation than fusing lexical/dense
signals, so it lives here, not in the engine repo (confirmed with Eyal
2026-07-11, MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md M1).

``edges_touching`` is the one primitive both the flat hops=1 render
(`artifact.py`) and this module's BFS (`walk`) share — hops=1 output is
byte-identical to pre-M1 `project_memory.artifact._project_edges`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .query import ProjectMemory

# Declared, not learned: each edge category's forward/reverse label (the
# 1-hop renderer's labels, unchanged from pre-M1) + a fixed confidence weight
# the rescore formula multiplies per hop. Extending the taxonomy is adding one
# line here, not touching graph-walk logic. An undeclared/custom category
# (e.g. a hand-`record_fact`'d edge) falls back to `_DEFAULT_WEIGHT` rather
# than crashing.
EDGE_CATEGORIES: dict[str, dict[str, Any]] = {
    "composes": {"forward": "composes", "reverse": "depended-on-by", "weight": 1.0},
    "public_twin_of": {"forward": "public-twin-of", "reverse": "has-public-twin", "weight": 0.7},
    "built_by": {"forward": "built", "reverse": "built-by", "weight": 0.5},
}
_DEFAULT_WEIGHT = 0.5

# Each additional hop discounts a path's score — a 2-hop neighbor ranks below
# a 1-hop one of the same category by design (0.6 is a starting tuning
# constant, not a calibrated one; see SoT §7's "BFS<=2" — nothing here claims
# to be more scientific than "declared and overridable").
_HOP_DECAY = 0.6

# Context-budget guard, same idiom as artifact.py's interface/pack caps: a
# hub node's 2-hop fan-out can be large; cap and let the score ordering pick
# the most relevant hits rather than truncating arbitrarily.
_MAX_HITS = 30


@dataclass(frozen=True)
class Hop:
    """One edge, from the point of view of the node it was reached from."""

    other: str
    category: str
    direction: str  # "forward" | "reverse"
    reason: str | None


@dataclass(frozen=True)
class GraphHit:
    """One node reachable from a BFS's starting scope, via its single
    best-scoring path (a node reachable by multiple paths keeps only one)."""

    node: str
    path: tuple[Hop, ...]
    score: float
    resolved: bool


def known_projects(mem: ProjectMemory) -> set[str]:
    """Every distinct `batch` with at least one indexed episode — the set a
    `(pending)` edge target is checked against, and what `brain load --current`
    matches a cwd's basename against."""
    rows = mem.conn.execute(f"SELECT DISTINCT batch FROM {mem.schema.episode_table}").fetchall()
    return {r[0] for r in rows if r[0]}


def edges_touching(mem: ProjectMemory, node: str) -> list[Hop]:
    """Every active edge-fact touching `node` (as source or target).

    The one query both the flat 1-hop render and BFS expansion share.
    """
    # `tags` is a JSON-array text blob, so this LIKE can't use a real index —
    # but as the fact table grows well past today's ~24 rows, it still prunes
    # candidates in SQL before they're pulled into Python and json.loads'd
    # (the expensive part). A `%`/`_` wildcard char inside `node` can only
    # widen the match, never narrow it, so this can't drop a true edge — the
    # exact tags-membership check below stays the authoritative filter.
    sql = (
        f"SELECT claim, reason, tags FROM {mem.schema.fact_table} "
        f"WHERE status = 'active' AND tags LIKE '%\"edge\"%' AND tags LIKE ?"
    )
    rows = mem.conn.execute(sql, (f'%"{node}"%',)).fetchall()
    hops: list[Hop] = []
    for claim, reason, tags_json in rows:
        tags = json.loads(tags_json or "[]")
        if len(tags) < 4 or tags[2] != "edge":
            continue
        source, target, category = tags[0], tags[1], tags[3]
        if node == source:
            hops.append(Hop(other=target, category=category, direction="forward", reason=reason))
        elif node == target:
            hops.append(Hop(other=source, category=category, direction="reverse", reason=reason))
    return hops


def _edge_weight(category: str) -> float:
    return EDGE_CATEGORIES.get(category, {}).get("weight", _DEFAULT_WEIGHT)


def walk(mem: ProjectMemory, scope: str, *, hops: int = 1) -> list[GraphHit]:
    """BFS from `scope` over the portfolio's edge-facts, up to `hops` hops.

    Each returned node is reached by exactly one path — its best-scoring one,
    if multiple exist — so a node reachable both directly and via a longer
    detour appears once, at its strongest path. `scope` itself, and any node
    already on the current path, is never revisited (cycle-safe regardless of
    how large `hops` grows). Capped at `_MAX_HITS` (score-descending) for
    context budget. Sorted score-descending; ties are not order-stable across
    calls (dict iteration order), which is fine — no caller depends on tie order.
    """
    if hops < 1:
        raise ValueError("walk needs hops >= 1")

    known = known_projects(mem)
    best: dict[str, GraphHit] = {}
    frontier: list[tuple[str, tuple[Hop, ...], float]] = [(scope, (), 1.0)]

    for depth in range(1, hops + 1):
        next_frontier: list[tuple[str, tuple[Hop, ...], float]] = []
        for node, path, path_score in frontier:
            visited = {scope} | {h.other for h in path}
            for hop in edges_touching(mem, node):
                if hop.other in visited:
                    continue
                new_path = path + (hop,)
                new_score = path_score * _edge_weight(hop.category) * (_HOP_DECAY ** (depth - 1))
                existing = best.get(hop.other)
                if existing is None or new_score > existing.score:
                    best[hop.other] = GraphHit(
                        node=hop.other, path=new_path, score=new_score, resolved=hop.other in known,
                    )
                if depth < hops:
                    next_frontier.append((hop.other, new_path, new_score))
        frontier = next_frontier

    return sorted(best.values(), key=lambda h: h.score, reverse=True)[:_MAX_HITS]
