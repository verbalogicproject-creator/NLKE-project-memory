# Codebase report

A map of the code for a reviewer or a future maintainer. As of 2026-07-12
(v0.1.0 + the Portfolio Brain / Graph Memory layer, M0–M2, M4, M5, and M6 shipped).

## Shape

- **~4,908 lines of Python** across 22 modules in `project_memory/` — roughly
  **2,070 lines / 12 modules of published core library**, **827 lines** of
  shared CLI (`cli.py`, dispatches to both layers), and **~2,011 lines / 9
  modules of internal Portfolio Brain** (not part of the published surface —
  see below).
- **325 tests** (~3,530 lines) across 20 `test_*.py` files in `tests/`, all green.
- **11 doc chapters** (`docs/00–10`), **6 self-verifying examples**
  (`01_remember_and_recall.py` … `05_dense_optional.py` + `recursive_close.py`)
  + **two MCP servers** (`examples/mcp_server.py` for core memory,
  `examples/mcp_portfolio_server.py` for the Portfolio Brain, M6).
- **A packaged demo memory** (`project_memory/demo_corpus/demo_memory.json`)
  and **3 real `.pack.md` files** (`aisle`, `verbalogix-suite`,
  `aria-app-builder`).
- One required runtime dependency: `declared_core` (the engine). `numpy` only
  for the optional `[dense]` extra; `PyYAML` + `ngfify` only for the optional
  `[portfolio]` extra (internal capability, not needed to `import
  project_memory`).

## The dependency boundary

project_memory is a **thin application layer** over
[declared_core](https://github.com/verbalogicproject-creator/NLKE-declared_core).
The split:

| Concern | Lives in |
|---|---|
| BM25 / FTS5, structural expansion, RRF fusion, intent classifier, dimension scorers, `NumpyVectorIndex` | `declared_core` |
| Episode/fact data model, writing + supersession, NL asks, synthesis-mud, CLI, MCP | `project_memory` (core) |
| Repo indexing, verified edges, context artifacts, graph-walk, session-memory ingest, load/use provenance, MCP + file export adapters | `project_memory` (Portfolio Brain — internal, layered *on* the core, no new engine dependency) |

If a change is about *retrieval math*, it belongs in the engine; if it's
about *turning a project's memory into the engine's corpus*, it belongs in
the core; if it's about *indexing this machine's repos and injecting context
into agent sessions*, it belongs in the Portfolio Brain — see `graph.py`'s
module docstring for the one deliberate exception (a BFS over the
portfolio's own tag-based edge convention lives here, not in `declared_core`,
since it isn't the engine's BM25/RRF text-relevance fusion).

## Two layers, one package tree

| Layer | Audience | Modules |
|---|---|---|
| **Core library** (published) | anyone using `project_memory` in their own project | `schema.py`, `store.py`, `ingest.py`, `query.py`, `asks.py`, `nl.py`, `dimensions.py`, `synthesis_mud.py`, `dense.py`, `presets.py`, `demo.py`, `__init__.py` |
| **Portfolio Brain** (internal) | this machine, indexing its own `~/projects` ecosystem — a private moat tool | `portfolio.py`, `artifact.py`, `pack.py`, `graph.py`, `session_memory.py`, `provenance.py`, `export/mcp_portfolio.py`, `export/files.py` |
| **Shared** | both | `cli.py` — one argparse tree, core subcommands plus the `brain` subtree |

## Module tour — core library

| Module | LOC | Responsibility |
|---|---|---|
| `synthesis_mud.py` | 456 | The epistemic guard: 5+1 axes, assessor, five matrices, 6-layer MUD detection, `synthesize`, optional persistence. |
| `asks.py` | 450 | `AnswerShape` + the eleven asks + intent routing. |
| `query.py` | 226 | `ProjectMemory` — the object you use: recall + ask + synthesize + recent, dense caching, hit projection. |
| `ingest.py` | 148 | `remember` / `record_fact` / `invalidate_fact` (append-only episodes, supersession, `supersedes` forwarding). |
| `dense.py` | 151 | Optional embedder → declared_core dense index; `http_embedder`; degradation. |
| `schema.py` | 136 | `MemorySchema` → a two-table `CorpusSchema` + link. The generalization core. |
| `store.py` | 97 | Build the episodes + facts tables; install FTS via declared_core. |
| `nl.py` | 99 | `understand` / `extract_entities` — the NL front door. |
| `dimensions.py` | 79 | The curated 12-dim palette + `custom()` builder. |
| `demo.py` | 76 | `build_demo`, `demo_corpus_dir`, `hash_embedder`. |
| `presets.py` | 40 | `generic` / `agent` / `research` schemas. |
| `__init__.py` | 112 | The public API surface. |

## Module tour — Portfolio Brain (internal capability)

| Module | LOC | Responsibility |
|---|---|---|
| `portfolio.py` | 728 | Index `~/projects` (+ pinned out-of-root repos, M5) into the store: one `batch` dimension per repo, one episode per declared interface (3-path discovery: `ai_card` → Public-API doc → `ngfify` fallback), verified `composes`/`public_twin_of`/`built_by` edges (generate-and-verify against each repo's own docs, never hand-authored). |
| `artifact.py` | 330 | `build_artifact` — the 5-section provider-neutral context block (Identity / Interfaces / Related / Recent memory / What-to-do) for one project or a pack; `_scored_related_section` for the M1 graph-walk render. |
| `graph.py` | 149 | `walk()` — cycle-safe 1-2 hop BFS over verified edges with a declared (not learned) per-category-weight × per-hop-decay rescore. |
| `session_memory.py` | 138 | Ingest Claude Code's own per-project `~/.claude/projects/<slug>/memory/*.md` files as episodes (`corpus=memory`), `type=project` only by default. |
| `provenance.py` | 219 | M4: reports over the load log the brain already keeps (loads are `kind="brain_load"` episodes, not a side-file). `record_use` (the append-only `brain_use` `used`/`unused` marker), `unused_loads` (loaded-but-never-used, `--packs`), `journey(session)` → `JourneyReport.story()`/`.to_dict()`. Sessions ride the episodes' existing `session_id`. Declared, not inferred: use is only ever explicitly marked. |
| `pack.py` | 111 | `.pack.md` file format — `load_pack` / `find_pack` / `list_packs`, fail-loud on malformed frontmatter. |
| `export/mcp_portfolio.py` | 176 | M6: pure functions fronting the Portfolio Brain as MCP resources (`portfolio://project\|pack/<id>` → artifact snapshot), a `load_context` prompt, and one idempotent `brain_reindex` tool. |
| `export/files.py` | 111 | M6: the file-based export leg — `render_block`/`apply_block` (idempotent `<!-- project_memory:begin/end -->` marker insert/replace, never touching hand-written content outside the markers) and `write_provider_file`/`write_all_provider_files`, mapping `claude→CLAUDE.md`, `codex`/`antigravity`→`AGENTS.md` (a shared convention, verified against Antigravity's own docs, not assumed), `gemini→GEMINI.md`. `export/__init__.py` (49 LOC) re-exports both adapters' public functions. |

`cli.py` (827 LOC) is the shared dispatcher: the core subcommands
(`demo/remember/record/recall/ask/synthesize/recent/asks/kinds/dims`) plus
the `brain` subtree (`load/menu/reindex/export/used/journey/unused/remember/
ingest-memory`) that calls into the Portfolio Brain modules above.

## Data model

Two physical SQLite tables, derived from the `MemorySchema` — **unchanged by
the Portfolio Brain**, which reuses this exact schema shape (`PORTFOLIO_SCHEMA`
extends the default `kinds` with `interface`/`milestone`/`brain_load`, but
adds no new table):

- **`episodes`** — `id` (PK), `content`, `kind`, `session_id`, `batch`, `tags`
  (JSON), `metadata` (JSON), `method`, `schema_version`, `created_at`. Append-only.
- **`facts`** — `id` (PK), `claim`, `reason`, `source_episode_id` → episodes,
  `status` ∈ {active, superseded, invalidated}, `superseded_by` → facts, `tags`,
  `method`, `schema_version`, `created_at`, `updated_at`.

`declared_core` attaches an FTS5 shadow table + sync triggers over the searchable
columns of each. A `Link("facts","episodes","source_episode_id")` makes a matched
episode structurally expand to its crystallized facts. In the Portfolio Brain,
one repo = one `batch` value; a pack is not a table, just an annotated list of
`batch` values plus a prompt (`pack.py`).

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

## Control flow of a `brain load` (Portfolio Brain)

```
brain load <name> [--hops 1|2]
  └─ find_pack(name)?                                            [pack.py]
       └─ yes → build_pack_artifact: concat each member's build_artifact
                (each member's own "What to do" stripped) + the pack's own
                prompt once, at the end
       └─ no  → build_artifact(name)                              [artifact.py]
            ├─ _identity_section       (own README summary + staleness date)
            ├─ _interfaces_section     (its `kind="interface"` episodes, capped 15)
            ├─ _related_section        (hops=1: edges_touching)    [graph.py]
            │  or _scored_related_section (hops=2: walk(), declared rescore)
            ├─ _recent_memory_section  (`session-memory`-tagged active facts, capped 8)
            └─ _what_to_do_section     (pack prompt or a generic default)
  └─ records a kind="brain_load" provenance episode (tagged [name, kind, trigger])
```

## Control flow of an MCP portfolio pull (M6)

```
examples/mcp_portfolio_server.py  (stdio JSON-RPC transport, no logic of its own)
  └─ resources/read {uri: "portfolio://project|pack/<name>"}
       └─ read_resource → build_artifact(scope, mem, kind=...)        [same fn as `brain load`]
  └─ prompts/get {name: "load_context", arguments: {scope, kind?}}
       └─ get_prompt → build_artifact(...) wrapped as a {role, content} message
  └─ tools/call {name: "brain_reindex", arguments: {name?, root?}}
       └─ call_tool → index_portfolio(mem, root, edges_path, scope=[one repo] or PORTFOLIO_SCOPE)
            (idempotent: remember/record_fact are INSERT OR IGNORE — never deletes the store)
```

## Control flow of a `brain export` (M6, file-based leg)

```
brain export <name> --provider {claude,codex,gemini,antigravity,all}
  └─ known_projects(mem)?  no → error, exit 1 (packs unsupported — no single directory)
  └─ resolve target_dir: --into, else _repo_path(name, root, spec)     [portfolio.py, same as `brain reindex`]
  └─ target_dir.is_dir()?  no → error, exit 1
  └─ render_block(name, mem, hops) → build_artifact(...) wrapped in
     <!-- project_memory:begin/end --> markers                        [export/files.py]
  └─ --dry-run?  yes → print the block(s), write nothing
  └─ else: write_provider_file / write_all_provider_files
       └─ apply_block(existing_file_text, block)
            ├─ markers already present → replace only that span
            └─ absent → append (or become the whole file, if empty/absent)
  └─ records a kind="brain_export" provenance episode (tagged [name, provider])
```

## Control flow of `brain journey` / `used` / `unused` (M4, provenance)

```
brain used <scope> [--session]                                         [cli.py::cmd_brain_used]
  └─ resolve scope (positional or --current) → was it ever loaded? no → error, exit 1
  └─ record_use(mem, scope, session, note)                            [provenance.py]
       └─ append one kind="brain_use" episode (append-only marker, not a flag)

brain journey [--session]                                             [cli.py::cmd_brain_journey]
  └─ journey(mem, session)                                            [provenance.py]
       └─ provenance_events(mem, session): SELECT brain_load|use|export
          FROM {schema.episode_table} [ WHERE session_id=? ] ORDER BY created_at, id
       └─ unused_loads: fold loads vs uses (used = a brain_use for that scope in-view)
       └─ JourneyReport.story()  →  ordered events + the loaded-but-never-used tail

brain unused [--packs] [--session]                                   [cli.py::cmd_brain_unused]
  └─ unused_loads(mem, session, scope_kind="pack" if --packs)        [provenance.py]
```

## Invariants worth preserving

- **BM25 is the floor.** Structural, dense, and rules are additive on top.
- **Dense degrades to nothing.** No embedder / no numpy / `None` ⇒ byte-identical
  to lexical (tested in `test_dense.py`).
- **Episodes append; facts supersede.** History is never destroyed.
- **Schema validation fails loud.** Unknown `kind` raises at write time.
- **synthesis-mud is deterministic + AI-less.** Typed axes, computed matrices,
  overridable per axis.
- **Edges are generate-and-verify, never hand-authored.** An edge neither
  repo's own docs assert is dropped, not ingested (`portfolio.py`).
- **A repo's location resolves the same way unless overridden.** `RepoSpec.path`
  defaults to `None`, in which case every repo resolves via `root / name`
  (byte-identical to pre-M5 behavior); only an explicit override (for repos
  outside `~/projects`) diverges.
- **The hook's default payload doesn't grow.** `--hops 2` and "Recent memory"
  are additive, opt-in-sized sections — the `SessionStart` hook's `hops=1`
  default artifact is unchanged by either landing.

## Test coverage by area

**Core:** `test_schema` (declaration + compilation), `test_store_ingest`
(tables + writing + supersession), `test_recall` (hybrid recall + link
expansion + projection), `test_nl` (entities + understand), `test_asks` (the
eleven + routing + `AnswerShape`), `test_dimensions` (palette + scoring),
`test_synthesis_mud` (worked examples + matrices + calibration +
persistence), `test_dense` (degradation + numpy-absent), `test_demo`
(determinism + the MUD pair).

**Portfolio Brain:** `test_portfolio` (atom extraction all 3 paths, edge
verification incl. alias/false-positive guards, `RepoSpec.path` override,
end-to-end `index_portfolio` idempotency), `test_artifact` (all 5 sections,
hops=1/2, pack composition, recent-memory rendering/truncation), `test_pack`
/ `test_pack_binding` (file format, `list_packs`, the 3 real packs load),
`test_graph` (BFS correctness, cycle-safety, rescore formula), `test_session_memory`
(frontmatter parsing, type filtering, idempotent ingest), `test_session_start_hook`
(the hook's own JSON contract), `test_export_mcp_portfolio` (resources match
`build_artifact` byte-for-byte, prompt/tool error paths, idempotent
`brain_reindex` re-run), `test_export_files` (idempotent marker-block
insert/replace, `codex`/`antigravity` producing byte-identical `AGENTS.md`
content, hand-written content surviving a rerun untouched), `test_provenance`
(the `used` marker's append-only shape, load/use folding, session scoping incl.
a use in another session not counting, `--packs` filtering, the journey story
+ its `to_dict`; the hook's `session_id` pass-through is in
`test_session_start_hook`).

**Shared:** `test_cli` (every core subcommand + every `brain` subcommand,
including `export`/`used`/`journey`/`unused`, via `--json`).

## Known limits (see [ROADMAP.md](ROADMAP.md))

Core: five asks roadmapped; in-memory dense index (rebuilt per process);
heuristic axis assessment (overridable); text-only ingestion. Portfolio
Brain: no decay/archival (a fact stays in "Recent memory" until explicitly
superseded — M8); M4 is shipped (load/use provenance + a session's journey
story — `provenance.py`, `brain used`/`journey`/`unused`) but treats a load as
used only when *explicitly* marked, never inferred from later activity (a
deliberate non-goal, not an oversight); M6 is fully shipped (MCP
resources/prompts/`brain_reindex` tool, plus idempotent
`CLAUDE.md`/`AGENTS.md`/`GEMINI.md` file export); no TUI (M3); no dense pass
over the portfolio store (M7, optional). `aria-app-builder`'s termux members are
now wired into the graph — `portfolio-edges.yaml` declares four verified `composes`
edges involving them (24 → 28 kept edges live).
