# 05 · Dimensions

Dimensions are **named-attribute embeddings**: interpretable `[0, 1]` floats, not
neural vectors. Together they form a *rules signal* — a deterministic, explainable
ranker with no model, no training, no API. You can read every score and know
exactly why it is what it is.

## The palette

project_memory ships `MEMORY_DIMENSIONS` — the **twelve** meta-level dimensions
from `declared_core.DEFAULT`, unchanged:

| group | dimensions |
|---|---|
| navigation | `spatial_relevance`, `hop_distance`, `traversal_frequency` |
| retrieval | `match_precision`, `semantic_coverage`, `keyword_hit_rate` |
| synthesis | `synthesis_potential`, `generative_scope` |
| performance | `latency_class`, `storage_tier` |
| architecture | `modularity`, `error_recovery` |

Several are already **memory-aware** out of the box:

- `storage_tier` — a crystallized **fact** outranks a raw **episode** (durable > log).
- `error_recovery` — a `gotcha`/`invariant` scores high (failure-mode knowledge).
- `synthesis_potential` — a `claim` + `reason` scores high (structured belief).

```python
from project_memory.dimensions import score, overall
s = score({"claim": "X is the store of record", "reason": "y"}, "store")
s["storage_tier"]     # 1.0 — a fact
overall(s)            # collapse to a single [0,1] for ranking
```

## Why twelve, not 350

The knowledge-graph lineage this comes from catalogued 56 / 70 / 350 dimensions —
but that high-D work is *designed, not shipped*. The proven small palette beats
the impressive large one. **Dimensions are a menu to subset, not a target to
chase.** Domain palettes (visual style, physics role, cost tier) belong in the
consumer that *has* that domain, not in a general memory library — which is why no
game/app-specific dimensions live here.

## Declaring your own

If your project has structure worth measuring, add a dimension — but always
register a scorer for it (an unscored dimension scores a neutral `0.5`, i.e.
noise):

```python
from project_memory import custom_dimensions, MEMORY_DIMENSIONS
from project_memory.dimensions import DimensionDef, register_dimension_scorer

register_dimension_scorer("actionable",
    lambda item, q, ctx: 1.0 if "todo" in (item.get("kind") or "") else 0.3)

palette = custom_dimensions(*MEMORY_DIMENSIONS.dims,
                            DimensionDef("actionable", "workflow", "Is it a to-do?"))
mem = ProjectMemory.open(dimensions=palette)
```

The `optimize_for` and `snapshot` asks both use this signal; hits carry a
`dimensions` dict when you recall with `verbose=True`.

Next: [06 · synthesis-mud](06-synthesis-mud.md).
