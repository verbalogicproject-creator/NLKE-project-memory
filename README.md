# project_memory

[![tests](https://img.shields.io/badge/tests-325%20passing-brightgreen)](tests/)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![deps](https://img.shields.io/badge/required%20deps-0-blue)](pyproject.toml)

**A declared, AI-optional memory for agents and projects.** Remember what happened
(*episodes*) and what you concluded (*facts*); recall it in natural language; and —
the part no other memory has — refuse to synthesize contradictory facts into MUD.

Local-first, deterministic, `$0`. Zero required dependencies — the retrieval engine
([`declared_core`](https://github.com/verbalogicproject-creator/NLKE-declared_core)) is vendored in-repo. No API keys. A dense
semantic signal is optional and degrades *byte-identically* to lexical.

> **The thesis:** *declared > inferred.* You write down the structure of what you
> remember; determinism, speed, offline operation, and explainability come for free.
> The one thing an LLM can't be trusted to do to its own memory — merge two facts
> that *shouldn't* be merged — is guarded by a deterministic epistemic check.

---

## Quickstart (60 seconds)

Install it standalone — the `declared_core` engine is vendored in-repo, so there's nothing else to clone:

```bash
pip install -e .                    # project_memory (declared_core is vendored)
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
- **CLI + MCP servers** — `project-memory …` (all `--json`) and two stdlib MCP
  servers (core memory; Portfolio Brain resources/prompts/tools).
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
| Serve the Portfolio Brain to an agent | `examples/mcp_portfolio_server.py` | examples |

## Portfolio Brain & Graph Memory (internal capability, `project_memory.{portfolio,artifact,pack,graph}`)

`project_memory` can also index **the whole `~/projects` ecosystem into itself** —
the "recursive close": the substrate builds a declared memory of its own body of
work, one flat dimension per repo (`batch=<repo name>`), one `remember()` atom per
declared interface (a committed `ai_card`, a repo's own "Public API" doc section,
or an `ngfify`-auto-declared fallback), and the cross-repo composition/twin/built-by
graph as verified `record_fact()` edges — verified against each repo's own docs at
ingest time, not taken on a manifest's say-so (an edge neither repo asserts is
**dropped, not ingested**). This is an internal capability (a private moat tool, not
part of the published surface) — see [`PORTFOLIO-BRAIN-SPEC.md`](PORTFOLIO-BRAIN-SPEC.md)
for the design and `project_memory/portfolio.py` for the implementation.

```bash
pip install -e '.[portfolio]'                 # PyYAML only (ngfify — the auto-declare fallback — is vendored)
python scripts/index_portfolio.py             # builds portfolio.db over ~/projects
python examples/recursive_close.py            # real CLI `ask`/`recall` queries against it
```

**On top of the index, a second layer turns it into live context injection** — the
part that makes an agent session *wake up already aware* of a repo instead of
re-scanning it, see [`MEMORY-SYSTEM-MVP-SPEC.md`](MEMORY-SYSTEM-MVP-SPEC.md) and
[`MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`](MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md) for the
full design + upgrade ladder:

- **`build_artifact`** (`artifact.py`) — a provider-neutral markdown block (identity,
  interfaces, 1-hop relationships, what-to-do) for one project, or a **pack**
  (`.pack.md` — a hand-curated, annotated bundle of member projects + a prompt;
  three real ones ship: `aisle`, `verbalogix-suite`, `aria-app-builder`).
- **`brain load <name>` / `brain menu`** (CLI) — print any project's or pack's
  artifact on demand; `menu` lists everything and lets you pick.
- **A Claude Code `SessionStart` hook** — auto-injects the current repo's artifact
  into a fresh session via `additionalContext`, verified live against a real
  session with zero repo-scanning tool calls.
- **`graph.walk`** (`graph.py`, M1) — `brain load <name> --hops 2` rescores a real
  1-2 hop BFS over the verified edges (a declared, transparent weight-per-category
  formula, not a learned model), opt-in so the hook's default payload stays small.
- **`brain remember` / `brain ingest-memory`** (`session_memory.py`, M2) — an
  accreted, project-scoped decision log: `brain remember "we chose X because Y"`
  crystallizes a supersedable fact that shows up in that project's artifact under
  "Recent memory"; `brain ingest-memory` pulls Claude Code's own per-project
  `~/.claude/.../memory/*.md` files into the same store (only `type: project`
  memories by default — the other types are about Eyal, not the project).
- **Reach expansion** (M5) — `RepoSpec.path` lets a repo live outside the shared
  `~/projects` root (termux paths, shared storage) instead of only `root/name`;
  `index_portfolio` and `verify_edge` resolve it transparently. Five termux repos
  are indexed this way, driving the `aria-app-builder` pack.
- **MCP breadth** (`export/mcp_portfolio.py`, M6) — a second MCP server
  fronting the Portfolio Brain itself: a **resource** per known project/pack
  (`portfolio://project/<name>`, `portfolio://pack/<id>`) that reads back its
  `build_artifact` snapshot, a **`load_context` prompt** to pull one into a
  conversation turn mid-session (closing the "no on-demand pull yet" gap),
  and one idempotent **`brain_reindex` tool**.
- **Provider-agnostic file export** (`export/files.py` + `brain export`, M6) —
  the same artifact, written as an idempotent marker-delimited block into
  `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` — the on-disk convention Claude
  Code/Codex/Gemini CLI/Google Antigravity each read at session start
  (Antigravity shares Codex's `AGENTS.md`, not a file of its own — verified
  against its own docs). A rerun replaces only project_memory's own block,
  leaving any hand-written instructions elsewhere in the file untouched.
- **Load/use provenance + functional-journey** (`provenance.py` + `brain
  used`/`journey`/`unused`, M4) — every load is already an episode; M4 adds a
  declared `used` marker, a per-session **journey** that reconstructs a session's
  ordered load/use/export events as a story, and an **unused** report ("which
  packs did I load and never use?"). Built on the load log the brain already
  keeps (not a second `brain-loads.log`), session-scoped via the episodes'
  `session_id` (which the `SessionStart` hook now passes through). A load counts
  as used only when *explicitly* marked — declared, not inferred.

```bash
project-memory brain load declared_core                 # one project's artifact
project-memory brain load declared_core --hops 2         # + rescored 2-hop neighbors
project-memory brain load aisle                          # a pack: 4 members + one prompt
project-memory brain load aria-app-builder                # a pack spanning termux repos
project-memory brain menu                                 # list everything, pick one
project-memory brain remember "we chose SQLite" --current --reason "zero-ops"
project-memory brain ingest-memory --current              # pull in Claude's own memory files
project-memory brain export declared_core --provider all   # write CLAUDE.md/AGENTS.md/GEMINI.md
project-memory brain used declared_core --session $S       # mark a load actually used (M4)
project-memory brain journey --session $S                  # reconstruct a session as a story
project-memory brain unused --packs                        # packs loaded but never used
```

Proven, not claimed: every piece above has a green test file (`tests/test_artifact.py`,
`test_pack.py`, `test_pack_binding.py`, `test_graph.py`, `test_session_memory.py`,
`test_session_start_hook.py`, `test_cli.py`, `test_portfolio.py`,
`test_export_mcp_portfolio.py`, `test_export_files.py`, `test_provenance.py`) and
has been dogfooded end-to-end, including against real, unmodified Claude Code
memory files, a real live export run, and real load/journey provenance reports
over the live `portfolio.db`. Explicitly **not** in this layer yet — a TUI and
dense/embedding recall over the portfolio store — see [`ROADMAP.md`](ROADMAP.md)
for the honest list.

## Prerequisites

- **Python ≥ 3.10** — that's the whole hard requirement.
- **`declared_core`** (the engine) — vendored in-repo (see `VENDORED.json`); no separate install.
- **numpy** — only for the optional `[dense]` extra.
- **PyYAML** — only for the optional `[portfolio]` extra (indexing; `portfolio.py`'s
  edge-manifest loading). `ngfify` (the auto-declare fallback) + `universal_parser` are
  vendored too, so the extra adds no dependency for them. `artifact.py` / `pack.py` /
  `graph.py` (the context-injection + graph-walk layer) add no further dependencies.

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
├── portfolio.py      # index ~/projects into the store (internal capability, see below)
├── artifact.py       # build_artifact — the provider-neutral context block (+ pack composition)
├── pack.py           # .pack.md file format: load_pack / find_pack / list_packs
├── graph.py          # BFS + declared rescoring over verified edges (M1)
├── session_memory.py # ingest Claude Code's own memory/*.md files as episodes (M2)
├── provenance.py     # load/use markers + a session's journey story (M4)
├── export/           # provider-agnostic export adapters (M6)
│   ├── mcp_portfolio.py  # Portfolio Brain MCP: resources/prompts/tools
│   └── files.py          # CLAUDE.md/AGENTS.md/GEMINI.md idempotent block export
├── packs/            # the real .pack.md files (aisle, verbalogix-suite, aria-app-builder)
└── demo_corpus/      # a deterministic demo memory (JSON)
docs/                 # numbered teaching chapters 00–10
examples/             # runnable, self-verifying; incl. two MCP servers + recursive_close.py
scripts/              # index_portfolio.py + session_start_hook.{sh,py} (Claude Code auto-injection)
portfolio-edges.yaml  # the declared composition/twin/built-by edge manifest
MEMORY-SYSTEM-MVP-SPEC.md          # the graph-memory/context-injection MVP design
MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md  # the upgrade ladder past the MVP
tests/                # 325 tests
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
