# Contributing

Thanks for looking at `project_memory`. It is a small, deliberately-scoped repo;
contributions that keep it that way are the most welcome.

## Setup

`project_memory` installs standalone — the `declared_core` engine is vendored
in-repo (see `VENDORED.json`), so there is no sibling repo to install:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                # project_memory + pytest + numpy
pytest                                 # 97 tests, keep them green
```

## The shape of the codebase

`project_memory` is a **thin layer over `declared_core`**. Retrieval math (BM25,
structural expansion, RRF, intent classification, dimension scoring, the dense
index) belongs in the engine. This repo owns:

- the memory data model (episodes + facts) and its compilation to a `CorpusSchema`,
- writing (append-only episodes, supersedable facts),
- the natural-language ask surface,
- the synthesis-mud epistemic guard,
- the CLI and MCP surface.

If your change is about *how retrieval ranks*, it probably belongs in
`declared_core`. If it's about *turning a project's memory into that engine's
corpus*, it belongs here. See [`CODEBASE-REPORT.md`](CODEBASE-REPORT.md).

## Load-bearing invariants (don't break these)

1. **BM25 is the floor; dense is a booster.** Never make an embedder required. A
   dead / missing embedder must yield results byte-identical to no embedder —
   there is a test (`test_dense.py`) that asserts exactly this.
2. **Episodes are append-only; facts supersede, never delete.** Keep history.
3. **Schema validation fails loud.** An unknown episode `kind` raises — silent
   mis-indexing is worse than an error.
4. **The no-embedder path is deterministic.** No unseeded randomness or
   wall-clock ordering in recall; the demo rows carry explicit ids + timestamps
   precisely to stay reproducible.
5. **synthesis-mud stays deterministic and AI-less.** Compatibility is computed
   from typed axes, not learned. The assessor is a transparent heuristic; keep it
   overridable per axis.

## Adding things

- **A new ask?** Register it in `asks.py` with `@register("name")`, return an
  `AnswerShape`, add it to `ASK_NAMES`, wire a route in `_INTENT_ROUTES` if it
  should be auto-selected, and document it in `docs/04-asks.md`.
- **A new public symbol?** Export it in `__init__.py.__all__` **and** document it
  in `docs/08-api-reference.md`.
- **A new preset?** It's just a `MemorySchema` value in `presets.py`.
- **A new dimension?** Declare it in a `custom()` palette and register a scorer
  via `declared_core.register_dimension_scorer` — never ship a dimension you don't
  score (unscored dims add noise).

## Style

- Match the surrounding code: type hints, `from __future__ import annotations`,
  small functions, docstrings that explain *why*.
- Don't add a required dependency — the vendored `declared_core` engine adds
  none. `numpy` stays behind `[dense]`.
- Don't claim a feature in the README that isn't proven — put it in
  [`ROADMAP.md`](ROADMAP.md). The audience has real judgment.

## Authorship

Architected and authored by **Eyal Nof**. Please don't add co-author trailers to
commits in this repo.
