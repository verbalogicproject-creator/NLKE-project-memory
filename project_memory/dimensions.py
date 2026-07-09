"""The memory dimension palette — a curated, deterministic rules signal.

Dimensions are *named-attribute embeddings*: interpretable [0, 1] floats, not
neural vectors. They form declared_core's rules signal — a ranker you can read
line by line and know exactly why a score is what it is.

project_memory deliberately ships **the declared_core `DEFAULT` 12-dim palette**
as its memory palette, unchanged. That is a considered decision, not a shortcut:

  1. Those 12 "meta-level" dimensions measure the *retrieval relationship* between
     an item and a query (match precision, semantic coverage, synthesis
     potential, error-recovery signal, storage tier, …) — exactly what ranking a
     memory needs. Several are already memory-aware out of the box: a crystallized
     *fact* outranks a raw *episode* on ``storage_tier``; a gotcha/invariant scores
     high on ``error_recovery``; a claim+reason scores high on ``synthesis_potential``.

  2. The source knowledge-graph lab catalogued 56 / 70 / 350 dimensions, but that
     high-D work is *designed, not shipped*. The proven small schema (this one)
     beats the impressive large one. Dimensions are a **menu to subset, not a
     target to chase** — see the ecosystem plan's "dimensions verdict".

  3. Domain palettes (visual style, physics role, cost tier, …) belong in the
     consumer that *has* that domain, not in a general memory library. That is why
     the game-content dimensions from the source project are intentionally absent
     here — they were specific to a game engine.

If your project has structure worth measuring, declare your own palette with
`custom(...)` and register scorers for it via `declared_core.register_dimension_scorer`.
Dimensions you never score add noise, not signal — keep the palette curated.
"""

from __future__ import annotations

from declared_core import (
    DEFAULT_DIMENSIONS,
    DimensionDef,
    DimensionSchema,
    register_dimension_scorer,
    score_item,
    score_summary,
)

# The curated memory palette: declared_core's proven, domain-agnostic 12 dims.
MEMORY_DIMENSIONS: DimensionSchema = DEFAULT_DIMENSIONS


def custom(*dims: DimensionDef) -> DimensionSchema:
    """Build a custom dimension palette from `DimensionDef`s.

    Pass it to ``ProjectMemory.open(..., dimensions=...)``. Remember to register a
    scorer for any *new* dimension name (unregistered dims score a neutral 0.5)::

        from declared_core import register_dimension_scorer
        recency = DimensionDef("recency", "temporal", "Newer memory scores higher.")
        register_dimension_scorer("recency", lambda item, q, ctx: ...)
        schema = custom(*MEMORY_DIMENSIONS.dims, recency)
    """
    return DimensionSchema(dims)


def score(item: dict, query: str, schema: DimensionSchema = MEMORY_DIMENSIONS) -> dict[str, float]:
    """Score one item (episode/fact hit dict) against a query. Thin re-export."""
    return score_item(item, query, schema)


def overall(scores: dict[str, float]) -> float:
    """Collapse a dimension-score dict to a single [0, 1] value for ranking."""
    return score_summary(scores)


__all__ = [
    "MEMORY_DIMENSIONS",
    "DimensionDef",
    "DimensionSchema",
    "custom",
    "score",
    "overall",
    "register_dimension_scorer",
]
