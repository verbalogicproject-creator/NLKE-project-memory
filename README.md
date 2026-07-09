# project_memory

[![tests](https://img.shields.io/badge/tests-97%20passing-brightgreen)](tests/)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![deps](https://img.shields.io/badge/required%20deps-1-blue)](pyproject.toml)

**A declared, AI-optional memory for agents and projects.** Remember what happened
(*episodes*) and what you concluded (*facts*); recall it in natural language; and —
the part no other memory has — refuse to synthesize contradictory facts into MUD.

Local-first, deterministic, `$0`. One required dependency ([`declared_core`](https://github.com/verbalogicproject-creator/NLKE-declared_core), the retrieval engine). No API keys. A dense
semantic signal is optional and degrades *byte-identically* to lexical.

> **The thesis:** *declared > inferred.* You write down the structure of what you
> remember; determinism, speed, offline operation, and explainability come for free.
> The one thing an LLM can't be trusted to do to its own memory — merge two facts
> that *shouldn't* be merged — is guarded by a deterministic epistemic check.

---

## Quickstart (60 seconds)

`declared_core` isn't on PyPI yet, so install the engine first (one line), then this:

```bash
pip install -e ../declared_core     # the engine (clone it alongside this repo)
pip install -e .                    # project_memory
```

```python
from project_memory import ProjectMemory

mem = ProjectMemory.open()                       # in-memory; pass a path to persist
mem.remember("We chose SQLite over Postgres for the local-first store.",
             kind="decision", auto_fact=True, reason="zero-ops, single-file backups")
mem.remember("FTS5 triggers crash on NULL columns — coalesce every value to ''.",
             kind="gotcha", tags=["fts5"])

for h in mem.recall("why sqlite", limit=2):
    print(f"[{h['table']:>8}] {(h.get('content') or h.get('claim'))[:60]}")

print(mem.ask("why not Postgres?", name="why_not").answer[:88])

s = mem.synthesize(
    "From a security perspective, plaintext tokens are an unacceptable risk.",
    "From a business perspective, plaintext tokens were cheap and worked.")
print(f"synthesize → {s.verdict.upper()}: {s.mud_reason[:52]}")
```

```text
[episodes] We chose SQLite over Postgres for the local-first store.
[   facts] We chose SQLite over Postgres for the local-first store.
closest recorded rationale: We chose SQLite over Postgres for the local-first store.
synthesize → REFUSE: Layer 3 — lighting/perspective conflict (compat=0.40
```

No corpus of your own yet? Explore the packaged demo memory:

```bash
project-memory demo
```

```text
project-memory demo — 8 episodes, 5 facts

recall('offline search'):
  [episodes] Milestone: Orchard v0.1 shipped — local notes, offline FTS5 search, UTC ti
  [episodes] Invariant: note search must keep working with no network. Any feature that
  [episodes] We chose SQLite FTS5 + BM25 for note search so search works fully offline

ask('why did we store timestamps in UTC?', why_not):
  → known issue: Gotcha: created_at was stored as a naive local datetime, so notes reordered when the user changed

synthesize(security-view, business-view):
  verdict: REFUSE — Layer 3 — lighting/perspective conflict (compat=0.40)
```

---

## How it fits together (read bottom-up)

```
      ┌──────────────────────────────────────────────────────────────┐
      │  your agent / CLI / MCP client                                │
      └──────────────────────────────────────────────────────────────┘
                     │ remember / recall / ask / synthesize
      ┌──────────────────────────────────────────────────────────────┐
      │  project_memory                                               │
      │    ingest    episodes (events) + facts (claims, supersedable) │
      │    recall    hybrid query over both, joined episode → fact    │
      │    asks       11 NL question types → one AnswerShape          │
      │    synthesis-mud   5+1 axes → 6-layer check → refuse / bridge │
      │    dimensions      curated 12-dim rules signal (declared)     │
      └──────────────────────────────────────────────────────────────┘
                     │ CorpusSchema (2 tables + 1 link)
      ┌──────────────────────────────────────────────────────────────┐
      │  declared_core   BM25 · structural expansion · RRF ·          │
      │                  intent-adaptive fusion · dimensions · dense  │
      └──────────────────────────────────────────────────────────────┘
                     │
      ┌──────────────────────────────────────────────────────────────┐
      │  SQLite + FTS5   (one file; nothing else required)            │
      └──────────────────────────────────────────────────────────────┘
```

`project_memory` is a thin, opinionated **application layer**. All retrieval math
lives in `declared_core`; this repo turns two tables — episodes and facts — into
that engine's corpus, then adds the memory-specific parts: writing, an NL front
door, the ask surface, and the synthesis-mud guard.

## What you get

- **Two-table memory over SQLite+FTS5** — episodes (append-only events) and facts
  (durable, supersedable claims), joined so a matched episode expands to its facts.
- **Hybrid recall** — BM25 + structural expansion + intent-adaptive fusion, from
  `declared_core`. Deterministic and explainable (every hit says which signals found it).
- **Eleven natural-language asks** — `why_not`, `can_i`, `how_do_i`, `what_for`,
  `route`, `how_does_connect`, `snapshot`, `recommend`, `similar_to`, `debug`,
  `optimize_for` — each returns one uniform `AnswerShape`.
- **synthesis-mud** — the epistemic guard: assess two facts on 5+1 axes, run a
  6-layer compatibility check, and **refuse / bridge / clean** with a *calibrated*
  confidence. Catches opinion-as-fact, perspective collision, certainty inflation.
- **A curated dimension palette** — 12 declared, deterministic [0,1] scorers (no ML).
- **CLI + MCP server** — `project-memory …` (all `--json`) and a stdlib MCP server.
- **Optional dense recall** — bring any embedder; it degrades to nothing cleanly.

## Feature / API map

| You want to… | Use | Ships in |
|---|---|---|
| Record an event | `mem.remember(text, kind=…)` | `ingest.py` |
| Record / update a durable claim | `mem.record_fact(…, supersedes=…)` | `ingest.py` |
| Search memory | `mem.recall(query, table=…)` | `query.py` |
| Ask a question | `mem.ask(q, name=…)` | `asks.py` |
| Guard a fact merge | `mem.synthesize(a, b)` | `synthesis_mud.py` |
| Declare your taxonomy | `MemorySchema(kinds=…)` | `schema.py` |
| Score by dimension | `optimize_for` ask / `dimensions.score` | `dimensions.py` |
| Add semantic recall | `ProjectMemory.open(..., embedder=…)` | `dense.py` |
| Serve to an agent | `examples/mcp_server.py` | examples |

## Prerequisites

- **Python ≥ 3.10**
- **`declared_core`** (the engine) — clone it beside this repo; `pip install -e ../declared_core`.
- **numpy** — only for the optional `[dense]` extra.

## Repo layout

```
project_memory/
├── schema.py         # MemorySchema → a declared_core CorpusSchema (episodes + facts + link)
├── store.py          # build the two tables; install FTS via declared_core
├── ingest.py         # remember / record_fact / supersede (append-only episodes)
├── query.py          # ProjectMemory — the object you use; recall + ask + synthesize
├── asks.py           # AnswerShape + the eleven asks + intent routing
├── nl.py             # the NL front door: intent + entity extraction
├── dimensions.py     # the curated 12-dim rules palette (declared_core.DEFAULT)
├── synthesis_mud.py  # the epistemic guard (5+1 axes, 6-layer MUD detection)
├── dense.py          # optional embedder → declared_core NumpyVectorIndex
├── presets.py        # ready MemorySchemas (generic / agent / research)
├── cli.py            # the `project-memory` command
├── demo.py           # build_demo() + hash_embedder()
└── demo_corpus/      # a deterministic demo memory (JSON)
docs/                 # numbered teaching chapters 00–10
examples/             # runnable, self-verifying; incl. an MCP server
tests/                # 97 tests
```

## Design choices (why it's built this way)

- **Episodes and facts are separate tables.** Events are append-only (they
  happened); claims are updatable (you supersede, never delete). Conflating them
  loses either history or the ability to correct. The declared episode→fact link
  means recall follows structure, not just keywords.
- **Retrieval math lives in `declared_core`, not here.** This repo is a thin layer.
  If a change is about BM25/structural/RRF/intent, it belongs in the engine — so
  every repo in the family improves together. ([Why declared_core.](https://github.com/verbalogicproject-creator/NLKE-declared_core))
- **The taxonomy is the only project-specific knob.** `kinds=` is user-declared;
  everything else generalizes. No game/app/domain specifics are baked in.
- **synthesis-mud is the differentiator.** Most RAG answers "what's similar?".
  This also answers "would merging these be *clean* or *muddy*?" — and refuses to
  muddy, with a reason. It's deterministic and AI-less; see
  [`docs/06-synthesis-mud.md`](docs/06-synthesis-mud.md).
- **We ship 12 dimensions, not 350.** The proven small palette beats the
  impressive large one; dimensions are a menu to subset, not a target. See
  [`docs/05-dimensions.md`](docs/05-dimensions.md).
- **AI is optional, and proven so.** A dead embedder returns byte-identical
  results to no embedder (there's a test that asserts exactly that).

## Reading paths

- **New here:** [`docs/00-mental-model.md`](docs/00-mental-model.md) → the Quickstart above → [`docs/01-remember-and-recall.md`](docs/01-remember-and-recall.md).
- **"Just show me the asks":** [`docs/04-asks.md`](docs/04-asks.md).
- **"The synthesis thing":** [`docs/06-synthesis-mud.md`](docs/06-synthesis-mud.md).
- **Wiring to Claude Code:** [`docs/10-claude-code-mcp.md`](docs/10-claude-code-mcp.md).
- **Extending / contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODEBASE-REPORT.md`](CODEBASE-REPORT.md).

## Contributing

Issues and PRs welcome — keep the invariants in [`CLAUDE.md`](CLAUDE.md) (BM25 is
the floor; dense degrades to nothing; ingest is append-only; schema validation
fails loud). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Acknowledgements

Built on the "declared > inferred" methodology and the colour-theory synthesis
guard developed by **Eyal Nof** across NLKE-Declarum and its predecessors. The
retrieval engine is `declared_core`, extracted from the same lineage.

## License

MIT © 2026 Eyal Nof. See [`LICENSE`](LICENSE).
