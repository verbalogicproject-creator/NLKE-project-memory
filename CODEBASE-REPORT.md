# Codebase report

A map of the code for a reviewer or a future maintainer. As of v0.1.0.

## Shape

- **~2,320 lines of Python** across 13 modules in `project_memory/`.
- **97 tests** (~660 lines) in `tests/`, all green.
- **11 doc chapters** (`docs/00–10`), **5 self-verifying examples** + an MCP server.
- **A packaged demo memory** (`project_memory/demo_corpus/demo_memory.json`).
- One runtime dependency: `declared_core` (the engine). `numpy` only for the
  optional `[dense]` extra.

## The dependency boundary

project_memory is a **thin application layer** over
[declared_core](https://github.com/verbalogicproject-creator/NLKE-declared_core).
The split:

| Concern | Lives in |
|---|---|
| BM25 / FTS5, structural expansion, RRF fusion, intent classifier, dimension scorers, `NumpyVectorIndex` | `declared_core` |
| Episode/fact data model, writing + supersession, NL asks, synthesis-mud, CLI, MCP | `project_memory` |

If a change is about *retrieval math*, it belongs in the engine; if it's about
*turning a project's memory into the engine's corpus*, it belongs here.

## Module tour

| Module | LOC | Responsibility |
|---|---|---|
| `synthesis_mud.py` | ~360 | The epistemic guard: 5+1 axes, assessor, five matrices, 6-layer MUD detection, `synthesize`, optional persistence. |
| `asks.py` | ~300 | `AnswerShape` + the eleven asks + intent routing. |
| `query.py` | ~230 | `ProjectMemory` — the object you use: recall + ask + synthesize + recent, dense caching, hit projection. |
| `cli.py` | ~230 | argparse CLI: `demo/remember/record/recall/ask/synthesize/recent/asks/kinds/dims`, all `--json`. |
| `ingest.py` | ~130 | `remember` / `record_fact` / `invalidate_fact` (append-only episodes, supersession). |
| `dense.py` | ~150 | Optional embedder → declared_core dense index; `http_embedder`; degradation. |
| `schema.py` | ~140 | `MemorySchema` → a two-table `CorpusSchema` + link. The generalization core. |
| `store.py` | ~110 | Build the episodes + facts tables; install FTS via declared_core. |
| `demo.py` | ~90 | `build_demo`, `demo_corpus_dir`, `hash_embedder`. |
| `nl.py` | ~95 | `understand` / `extract_entities` — the NL front door. |
| `dimensions.py` | ~75 | The curated 12-dim palette + `custom()` builder. |
| `presets.py` | ~45 | `generic` / `agent` / `research` schemas. |
| `__init__.py` | ~120 | The public API surface. |

## Data model

Two physical SQLite tables, derived from the `MemorySchema`:

- **`episodes`** — `id` (PK), `content`, `kind`, `session_id`, `batch`, `tags`
  (JSON), `metadata` (JSON), `method`, `schema_version`, `created_at`. Append-only.
- **`facts`** — `id` (PK), `claim`, `reason`, `source_episode_id` → episodes,
  `status` ∈ {active, superseded, invalidated}, `superseded_by` → facts, `tags`,
  `method`, `schema_version`, `created_at`, `updated_at`.

`declared_core` attaches an FTS5 shadow table + sync triggers over the searchable
columns of each. A `Link("facts","episodes","source_episode_id")` makes a matched
episode structurally expand to its crystallized facts.

## Control flow of a recall

```
mem.recall(text)
  └─ hybrid_query(text, corpus, conn, dense=?, use_intent=?)     [declared_core]
       ├─ bm25_search           over episode.content + fact.claim/reason
       ├─ expand_from_anchors    structural: kind/tag clusters + episode↔fact link
       ├─ dense.search           optional cosine (if embedder + numpy)
       ├─ score_item             declared 12-dim rules signal
       └─ classify_intent → weighted RRF (or weighted sum at scale)
  └─ [optional table filter] → project hits (strip _text/_tags, dimensions unless verbose)
```

## Control flow of a synthesis

```
mem.synthesize(a, b)
  └─ Fact.assess(a), Fact.assess(b)          # 5+1 axes from marker-word rules
  └─ detect_mud(fa, fb)                       # Layer 1 (is-fact) → axes 2..6, short-circuit
       └─ compatibilities via 5 typed matrices
  └─ verdict: refuse | bridge | clean
       └─ calibrated confidence = min(certainty) × mean(compat) [× 0.85 if bridge]
```

## Invariants worth preserving

- **BM25 is the floor.** Structural, dense, and rules are additive on top.
- **Dense degrades to nothing.** No embedder / no numpy / `None` ⇒ byte-identical
  to lexical (tested in `test_dense.py`).
- **Episodes append; facts supersede.** History is never destroyed.
- **Schema validation fails loud.** Unknown `kind` raises at write time.
- **synthesis-mud is deterministic + AI-less.** Typed axes, computed matrices,
  overridable per axis.

## Test coverage by area

`test_schema` (declaration + compilation), `test_store_ingest` (tables + writing +
supersession), `test_recall` (hybrid recall + link expansion + projection),
`test_nl` (entities + understand), `test_asks` (the eleven + routing + AnswerShape),
`test_dimensions` (palette + scoring), `test_synthesis_mud` (the worked examples +
matrices + calibration + persistence), `test_dense` (degradation + numpy-absent),
`test_cli` (all subcommands via `--json`), `test_demo` (determinism + the MUD pair).

## Known limits (see [ROADMAP.md](ROADMAP.md))

Five asks roadmapped; in-memory dense index (rebuilt per process); heuristic axis
assessment (overridable); text-only ingestion.
