# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — Portfolio Brain + Graph Memory / Context Injection (internal capability)

Upgrades `project_memory` into the **Portfolio Brain**: it now indexes the whole
`~/projects` ecosystem into itself, so the substrate can answer questions about its
own body of work — the "recursive close." On top of that index, a second layer
(the **Graph Memory / Context Injection system** — `MEMORY-SYSTEM-MVP-SPEC.md`)
turns it into live awareness: a provider-neutral context artifact per project or
curated pack, printable on demand or auto-injected into a fresh Claude Code session
via a `SessionStart` hook — and a declared, rescored graph-walk (M1) over the
verified edges. Internal moat tool (not part of the published surface); built
entirely on the existing engine, no retrieval-math changes (BFS over the portfolio's
own edge-fact convention lives in `graph.py`, not `declared_core` — see that file's
module docstring for why).

### Added — indexing (`portfolio.py`)

- **`project_memory/portfolio.py`** — the portfolio layer over the existing
  dimensions/ingest/store/asks stack:
  - **One flat dimension per repo** — reuses the engine's existing `episodes.batch`
    cluster column (`batch=<repo name>`); no new table, no cluster-tag layer.
  - **One atom per declared interface, finest source first** — (1) a committed
    `ai_card`-shaped `*.ngf.md` (`public_interfaces`), (2) a "Public API" doc
    section in the repo's own README/SPEC-v0.1.md/CODEBASE-REPORT.md (prose
    backticks or a fenced symbol list), or (3) an `ngfify` auto-declared card over
    the repo's best available markdown doc (optional dependency, the `portfolio`
    extra) — each ingested as one `kind="interface"` episode.
  - **Declared edges, verified before ingest** — `portfolio-edges.yaml`
    materializes the composition / open-core-twin / built-by manifest verbatim;
    `verify_edge()` checks each `source -> target` pair against *both* repos' own
    docs (README/SPEC-v0.1.md/CODEBASE-REPORT.md/CLAUDE.md/ROADMAP.md/
    CALIBRATION-NOTES.md/`arch/*.ngf.md`) before it becomes a `record_fact()` row.
    An edge neither side asserts is **dropped, not ingested** — refuse-to-fabricate,
    applied to memory.
- **`scripts/index_portfolio.py`** — the CLI entry point; builds a fresh
  `portfolio.db` over `PORTFOLIO_SCOPE` (21 repos: the fleet, the Verbalogix line,
  and `project_memory` itself) in one run.
- **`examples/recursive_close.py`** — runs real `project-memory ask`/`recall`
  queries against the built store and prints the actual output (what composes
  "Map", the Verbalogix line, `declared_repo_factory`'s verified built-by set, a
  retrieval cluster around `declared_core`, and the honest, grounded *absence* of
  an unverified "public twin" claim).
- **30 new tests** (`tests/test_portfolio.py`, 127 total) covering atom extraction
  (all three paths), edge verification (including the alias case-sensitivity and
  common-word false-positive guards), manifest loading, and an end-to-end
  `index_portfolio()` run — deterministic ids assert byte-identical reruns.

### Added — context injection: artifacts, packs, `brain` CLI, SessionStart hook (Cuts 1–3)

- **`project_memory/artifact.py` — `build_artifact`** — a provider-neutral markdown
  block (Identity / Interfaces / Related / What-to-do) for one project, reading
  `mem.conn` directly (exact `batch`/`tags` membership, not fuzzy `recall`/`ask`).
  Renders both edge directions (most repos are edge *targets*, not sources),
  compresses `verify_edge`'s formulaic reasons to save tokens, caps Interfaces at
  15 bullets, and shows a per-project `Indexed:` staleness date.
- **Packs** (`pack.py` + `build_pack_artifact`) — a `.pack.md` file (frontmatter
  `members:` + a body prompt) is a hand-curated, annotated bundle of projects.
  `build_pack_artifact` is decoupled from the file format (an ad-hoc/computed
  member list works too), concatenates each member's own artifact (its own
  `## What to do` stripped — the pack's prompt appears once, at the end), surfaces
  the oldest member's staleness in the pack header, and caps at 20 members. Two
  real packs ship: `packs/aisle.pack.md`, `packs/verbalogix-suite.pack.md` (named
  `-suite` deliberately — `verbalogix` collides with a project of the same name,
  a real bug caught dogfooding and now regression-tested).
- **`brain load <name>` / `brain load --current` / `brain menu` / `brain reindex
  <name>`** (`cli.py`) — print any project's or pack's artifact; `--current`
  detects the project from the cwd (walking parent dirs, so a session opened
  below a repo root still resolves); `menu` lists every project + pack and prompts
  (or `--select` to skip the prompt, scriptable); `reindex` refreshes one
  project's atoms/milestone in place without rebuilding the whole store. Every
  load records a `kind="brain_load"` provenance episode (tagged
  `[name, kind, trigger]`) — provenance rides the existing append-only episode
  log rather than a bespoke log file.
- **A Claude Code `SessionStart` hook** (`scripts/session_start_hook.{sh,py}`) —
  runs `brain load --current --json` and returns the artifact as
  `additionalContext`. Fires on `startup`/`clear` only (not `resume`/`compact`),
  so the injected block rides Claude Code's existing prompt-cache breakpoint
  without ever duplicating mid-transcript. **Verified live twice**: a fresh session
  in `~/projects/declared_core` answered a cross-repo dependency question with
  zero repo-scanning tool calls; a second round across `vouch` and `kg_toolkit`
  confirmed a real fix (below) held.
- **A real bug found and fixed while dogfooding**: the injected artifact's
  wording ("Ground answers... do not re-scan the repo", plus "declared"/ecosystem
  jargon) read as an untrusted, imperative instruction to a safety-conscious
  session (correctly — it shouldn't blindly obey injected text) and as unfamiliar
  insider vocabulary outside this family of repos. Reworded to self-identify its
  provenance ("a local context summary... generated by project_memory... treat it
  as a starting reference") instead of issuing a command; `portfolio.db` rebuilt
  fresh to replace the old wording rather than leave duplicate atoms (interface
  atoms have no supersession mechanism, a known gap).
- **A real idempotent-rerun crash found and fixed**: `index_portfolio`'s
  `--no-fresh` append mode crashed on the very first duplicate id even with 100%
  unchanged content. Root-caused to a plain `INSERT` against deterministic
  content-addressed ids; fixed via `INSERT OR IGNORE` in `ingest.py`, plus a
  content-derived (not content-blind) milestone id so a changed README summary
  produces a new row instead of colliding.
- **73 new tests** (`test_artifact.py`, `test_pack.py`, `test_pack_binding.py`,
  `test_cli.py` additions, `test_session_start_hook.py`), 200 total.

### Added — real graph-walk (M1, `graph.py`)

- **`graph.py` — `walk(mem, scope, hops)`** — cycle-safe BFS over the portfolio's
  verified edge-facts, up to 2 hops, with per-node best-path dedup and a declared
  (not learned) rescore: a fixed weight per edge category × a per-hop decay, so a
  2-hop neighbor ranks below the 1-hop one it routes through. Deliberately lives
  here, not in `declared_core` — it walks project_memory's own tags-based edge
  convention, not the engine's BM25/RRF text-relevance fusion.
- **`brain load <name> --hops 2`** — opt-in; the SessionStart hook's default
  (`hops=1`) is untouched, so the injected payload's size doesn't change for
  every session just because this landed. Verified live: `declared_core --hops 2`
  correctly surfaces its 5 direct dependents at score 1.00, then 3 real 2-hop
  neighbors through `scaffold_kg_rag_agent` at score 0.60.
- **19 new tests** (`test_graph.py` + additions), 219 total.

### Added — accreted decision log (M2, `session_memory.py`)

- **`brain remember <text> [--project|--current] [--kind] [--reason] [--supersedes] [--no-auto-fact]`**
  — a project-scoped episode, crystallizing a fact by default (unlike the generic `remember` CLI,
  which defaults to episode-only). `--supersedes <fact_id>` retires a prior standing decision in
  the same call — needed a small core addition, `ingest.remember(auto_fact=True, supersedes=...)`
  forwarding to the inner `record_fact`.
- **`build_artifact` gained a fifth section, "Recent memory"** — active facts tagged
  `session-memory` for the project, newest first, capped at 8, each showing its fact id so a later
  `--supersedes` is directly actionable. A superseded fact is filtered by `status='active'` and
  never resurfaces — facts already carried supersession before M2; this surfaces it in the artifact.
- **`session_memory.py` — `brain ingest-memory [--memory-dir|--project|--current] [--types]`** —
  ingests Claude Code's own per-project `~/.claude/projects/<slug>/memory/*.md` files as episodes
  tagged `corpus=memory`. Two scope decisions made against real data, not assumed:
  - **Only `metadata.type == "project"` ingested by default** — Claude Code's own auto-memory
    system also declares `user`/`feedback`/`reference`, which are about Eyal and how Claude should
    work with him, not a project's technical state; ingesting them would leak personal/behavioral
    notes into an artifact injected into unrelated repos.
  - **`batch` is an explicit flag, never inferred from the directory** — a real memory directory
    (`~/.claude/projects/-root-projects-ubuntu/memory/`) turned out to span *several unrelated
    projects at once*, not one repo per directory as assumed going in; guessing a single project
    for the whole directory would have mis-tagged most of its contents.
- **Verified live** against real, unmodified data: ingested 14 files from the real
  `-root-projects-ubuntu` memory directory into a scratch copy of `portfolio.db`, then
  `project-memory ask "what is the graph memory context system decision"` surfaced real, correct
  episodes from it.
- **Not built**: M2's own "forgetting = decay + archival" component. Nothing decays or archives
  yet — a fact stays in "Recent memory" indefinitely until explicitly superseded or invalidated.
  Folded into M8's maintenance floor instead.
- **38 new tests** (`test_session_memory.py` + additions), 257 total.

### Added — reach expansion (M5, termux paths + `aria-app-builder` pack)

- **`RepoSpec.path`** — an optional absolute-path override. `index_portfolio`,
  `extract_atoms`, and `verify_edge` now resolve a repo's location through a
  shared `_repo_path()` helper: `spec.path` if declared, else `root / name` (the
  behavior every pre-M5 repo still gets, byte-identical). Needed because the
  five termux repos below don't share a common parent directory with `~/projects`
  *or* with each other (three different filesystem regions: termux home
  directly, a `kg-factory/` subdirectory, and shared storage under `/sdcard/`) —
  the prior single-`root` design couldn't reach them, and critically couldn't
  verify edges *between* them either, since `verify_edge` needs both sides
  resolvable in the same call.
- **Five termux `RepoSpec`s added** (`group="termux"`), each pinned to its real,
  verified location: `voice-graph-rag`, `gemini-KG-RAG-coding-expert`,
  `nlke-declarum-model-01-coding`, `jewelry-current`, `canvas-os`. Two path
  collisions resolved from disk evidence before indexing: a same-named
  `voice-graph-rag` under `~/projects/future/` turned out to be a stray `gemini/`
  notes folder, not the repo; a same-named `nlke-declarum-model-01-coding` there
  was confirmed byte-identical (same README hash, same git `HEAD`) to the termux
  copy, so the termux path was kept as canonical and the other ignored.
- **`packs/aria-app-builder.pack.md`** — the driving pack for the app-builder
  toolchain, bundling the spec's four named members: `voice-graph-rag` +
  `gemini-KG-RAG-coding-expert` + `nlke-declarum-model-01-coding` +
  `jewelry-current` (`canvas-os` is indexed but not a pack member). Verified
  live: `brain load aria-app-builder` emits all four members' full artifacts
  plus the pack's own prompt.
- **Verified live** — a real `index_portfolio` run went from 21 to **26 repos
  indexed, 771 interface atoms** (up from ~495 pre-M5); the five new repos
  ingested cleanly with no atom warnings (`nlke-declarum-model-01-coding` via
  495 real `.ngf.md` `ai_card`s; the rest via the `ngfify` auto-declare fallback,
  expected — none of them ship `*.ngf.md` cards yet). At M5 ship no edges
  referenced the termux repos (`portfolio-edges.yaml` declared no pairs involving
  them) — the 24-kept/18-dropped edge outcome was unchanged. *(Closed by the M5
  follow-up below — the termux edges are now declared and verified.)*
- **9 new tests** (`test_portfolio.py`, `test_pack.py` additions), 260 total.

### Added — MCP breadth for the portfolio store (M6, in progress, `export/mcp_portfolio.py`)

- **`project_memory/export/`** — a new subpackage for provider-agnostic export
  adapters (Portfolio Brain internal capability, like `portfolio.py`/`artifact.py`;
  not part of `project_memory.__all__`). First adapter: `mcp_portfolio.py` —
  pure functions (no stdio) fronting the Portfolio Brain as MCP resources/
  prompts/tools, distinct from the existing per-project `examples/mcp_server.py`.
  - **Resources** — one per known project (`portfolio://project/<name>`) and per
    declared pack (`portfolio://pack/<id>`); reading one returns that scope's
    `build_artifact`/`build_pack_artifact` snapshot verbatim (the same text
    `brain load` prints).
  - **Prompt** — `load_context(scope, kind?)` — inserts a project's or pack's
    artifact as a conversation turn. This is the concrete fix for the
    long-flagged "no mid-session recall" gap: previously the only "wake up"
    moment was the `SessionStart` hook, once, at session start.
  - **Tool** — `brain_reindex(name?, root?)` — deliberately **idempotent, never
    destructive** (unlike `scripts/index_portfolio.py`'s default fresh-rebuild):
    calls `index_portfolio` in place, safe to invoke live from mid-session since
    `remember`/`record_fact` are `INSERT OR IGNORE`. Omit `name` for the whole
    `PORTFOLIO_SCOPE`; pass one repo name to refresh just that repo.
- **`examples/mcp_portfolio_server.py`** — the thin stdio JSON-RPC transport
  (mirrors `examples/mcp_server.py`'s shape: `initialize`/`ping` + the new
  `resources/*`, `prompts/*`, `tools/*` methods). Verified live against the real
  `portfolio.db`: 29 resources listed, a project read, a pack read, `load_context`,
  `tools/list`, and a malformed-URI error path all round-tripped correctly.
- **17 new tests** (`test_export_mcp_portfolio.py`), 277 total.
- File-based export adapters (`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`) were still
  open at this point — closed out by the next entry.

### Added — provider-agnostic file export (M6, `export/files.py` + `brain export`)

The other half of M6's acceptance bar ("one store → verified injection in
Claude, Codex, and Gemini from a single artifact"), closing it out.

- **`project_memory/export/files.py`** — pure, testable functions, no CLI/IO
  coupling beyond a target directory:
  - `render_block(scope, mem, *, hops=1, kind="project")` — wraps
    `build_artifact` in `<!-- project_memory:begin/end -->` markers.
  - `apply_block(existing, block)` — idempotent marker-delimited insert/replace:
    if the markers are already present in a file, only that span is replaced;
    otherwise the block is appended (or becomes the whole file, if empty/absent).
    Applying the same block twice is a no-op the second time. This is the same
    non-destructive-by-default discipline `brain_reindex` established for this
    layer, applied to something higher-stakes — a real project's own context
    file can carry hand-authored instructions a naive overwrite would destroy.
  - `write_provider_file(provider, scope, mem, target_dir, ...)` /
    `write_all_provider_files(...)` — `PROVIDER_FILES` maps `claude`→`CLAUDE.md`,
    `codex`→`AGENTS.md`, `gemini`→`GEMINI.md`, `antigravity`→`AGENTS.md`.
- **Researched, not assumed:** Google Antigravity's own docs say it reads
  `AGENTS.md` — the *same* file Codex reads — falling back to `GEMINI.md` only
  if `AGENTS.md` is absent. So there is no separate "antigravity" file; `--provider
  all` writes exactly three files (`ALL_FILENAMES`), not four.
  `test_export_files.py::test_write_provider_file_codex_and_antigravity_produce_identical_content`
  asserts this rather than just claiming it.
- **`project-memory brain export <name> --provider {claude,codex,gemini,antigravity,all}`**
  (`cli.py::cmd_brain_export`) — resolves the target directory via `--into`
  (explicit override) or the project's own resolved location (`_repo_path`,
  same resolution `brain reindex` uses: `RepoSpec.path` if declared, else
  `--root/<name>`); rejects packs (no single directory to write into — `brain
  load <pack>` is still the way to pull one) and unknown projects; supports
  `--dry-run` (prints the block(s), writes nothing) and `--json`; logs
  provenance via `mem.remember(kind="brain_export", ...)`, mirroring `brain
  load`'s own pattern (a new `"brain_export"` kind added to `PORTFOLIO_KINDS`).
- **Verified live** against the real `portfolio.db`, writing only to a scratch
  directory (never a real sibling repo): `--dry-run` wrote nothing and printed
  the correct artifact; a real `--provider all` run produced all three files
  with correct content; adding hand-written content to `CLAUDE.md` and
  re-running preserved it exactly, replacing only the marker-delimited block;
  `codex` and `antigravity` produced byte-identical `AGENTS.md` content.
- **24 new tests** (`test_export_files.py`, 14; `test_cli.py` additions, 10),
  301 total.

### Added — provenance + functional-journey (M4, `provenance.py`)

- **`project_memory/provenance.py`** — reports over the load log the brain
  already keeps. **No bespoke `brain-loads.log` jsonl was added, by an existing
  design decision:** `cmd_brain_load` had already chosen (pre-M4) to record each
  load as a `kind="brain_load"` *episode* in the store — so `recall`/`ask`/`recent`
  already see loads. M4 builds on that log rather than forking a second sink:
  - **`record_use(mem, scope, …)`** — the `used`/`unused` marker: one append-only
    `kind="brain_use"` episode (not a mutable flag — "episodes are append-only").
  - **`unused_loads(mem, *, session, scope_kind)`** — the "loaded but never used"
    report; folds loads against uses. `scope_kind="pack"` is the acceptance bar's
    "report *packs* loaded-but-never-used" verbatim.
  - **`journey(mem, *, session)` → `JourneyReport`** — reconstructs a session's
    ordered load/use/export events, with `.story()` (a readable narrative) and
    `.to_dict()`. Reads `mem.schema.episode_table`, never a hardcoded name.
- **Sessions ride the episode table's existing `session_id` column** — no schema
  change. `cmd_brain_load`/`menu`/`export` now stamp it, and
  `scripts/session_start_hook.py` passes Claude Code's own `session_id` through a
  new `--session`. Pre-M4 loads (`session_id = NULL`) fold into the all-sessions
  view.
- **CLI:** `brain used <scope>` (or `--current`; refuses a scope that was never
  loaded — a `used` marker only makes sense for pulled context), `brain journey
  [--session]` (the story), `brain unused [--packs] [--session]` (the report) —
  all `--json`-able. One new kind, `brain_use`, added to `PORTFOLIO_KINDS`
  (schema fails loud on unknown kinds; Python-side, so backward-compatible with
  the existing `portfolio.db` — no migration).
- **Declared over inferred (CLAUDE.md):** a load is treated as used only when
  *explicitly* marked — never guessed from later scoped activity. Auto-inference
  is a deliberate non-goal, not an oversight.
- **Verified live** against the real `portfolio.db`: read-only `brain
  journey`/`unused` reconstructed 7 real historical events and reported both
  loaded scopes as never-used; a full load→used→journey→unused write cycle (run
  against a *copy*, so no false `used` marker touched the real store) folded
  correctly — the used scope dropped from the report, the note surfaced in the
  story, and marking a never-loaded scope was cleanly rejected.
- **24 new tests** (`test_provenance.py`, 14; `test_cli.py` additions, 9;
  `test_session_start_hook.py`, 1), 325 total.

### Added — termux edges (M5 follow-up, `portfolio-edges.yaml`)

Closes M5's one deferred item: the five termux repos were indexed but had **no
verified edges**, so the `aria-app-builder` pack bundled its members without a
relationship graph among them. Four `composes` edges are now declared and
verified — each grounded in one side's own edge-docs, so each survives
`verify_edge` (name co-occurrence is *not* enough on its own):

- `nlke-declarum-model-01-coding` → `gemini-KG-RAG-coding-expert` — nlke's README
  lists that repo's Graph-RAG KG (32 docs + ~22 exemplars) as a corpus source it
  ingests (the one intra-termux, intra-pack edge).
- `Aisle-demo` → `voice-graph-rag` and `aisle-wedding-copilot` → `voice-graph-rag`
  — both name voice-graph-rag as the voice + serve co-pilot spine (arch card /
  `INTEGRATION-PLAN.md`), wiring the termux spine into the existing fleet graph.
- `sag-declarum-atlas-framework` → `voice-graph-rag` — its `CLAUDE.md` §11.6 says
  the framework wraps voice-graph-rag's `aria-core` as its substrate.
- **Deliberately omitted** (refuse-to-fabricate applied to the *category*, not just
  name-matching): `declared_repo_factory` names `canvas-os` only to note where
  `aria-core` is vendored, and the atlas framework names `jewelry-current` only as
  a `file:`-ref packaging precedent — references, not compositions.
- **Verified live** — the edge set went **24 → 28 kept** (18 dropped, unchanged).
  The live `portfolio.db` was updated with `index_portfolio --no-fresh` (append,
  skip-on-conflict) — **not** a `--fresh` rebuild, which would delete the store and
  wipe the 9 real `brain_load`/`brain_export` provenance episodes M4 records;
  confirmed on a copy first, then on the live store: 28 edges, 771 atoms
  (unduplicated), 9 provenance episodes preserved. `graph.walk` now reaches
  voice-graph-rag's 3 composers and nlke ⟷ gemini-KG-RAG. No new tests (the edge
  machinery is already covered by `test_portfolio.py`'s synthetic fixtures); full
  suite stays green at 325.

### Found (via the edge-verification pass, not asserted)

A real run over the portfolio keeps **28 of the manifest's 46 declared edge pairs**
and drops 18 as unverified against either repo's own docs (the 2026-07-11 fleet run
kept 24 of 42; the 2026-07-13 M5 follow-up added the 4 termux `composes` pairs, all
verified) — most notably: only 2 of the manifest's 15 `built_by` targets
(`universal_parser`, `claude_workload_optimizer`) are actually named in
`declared_repo_factory`'s own docs (`CALIBRATION-NOTES.md`); the other 13 were built
by the pre-factory manual workflow it was later extracted *from*, not by the tool
itself. All three `public_twin_of` edges in the manifest are dropped for the same
reason — they are Eyal's own strategic framing (correct at the portfolio level) but
not yet cross-asserted in either repo's shipped docs.

### Known limits (see [ROADMAP.md](ROADMAP.md))

- No dense/embedding pass over the portfolio layer yet (BM25/structural is the
  floor); an MCP server now exists (M6, `export/mcp_portfolio.py`) but it fronts
  artifact snapshots + reindex, not the recall/dense question.
- The generic `recommend`/`snapshot` asks aren't tuned for portfolio-graph
  questions ("what did X build?"); `recall --table facts` is the more reliable
  surface for edge queries today. `brain load --hops 2` (M1) now gives a real,
  scored graph-walk over the CLI — but it's a separate command, not the `ask`
  surface itself; a graph-shaped *ask* intent is still future work.
- Interface atoms have no supersession mechanism (unlike facts) — a symbol
  renamed or removed from a repo's Public API section leaves its old atom row
  behind after a reindex, since the atom's id is content-derived. Flagged, not
  silently worked around; needs either a `superseded` concept for episodes or a
  session-scoped "latest reindex wins" read filter.
- Mid-session recall now exists (M6) via `export/mcp_portfolio.py`'s resources
  + `load_context` prompt — see the "Added — MCP breadth" section above.
- File-based provider-agnostic export now exists (M6) via `export/files.py` +
  `brain export` — see the "Added — provider-agnostic file export" section
  above; M6 is fully shipped. Load/use provenance + a session's functional-journey
  story now exist (M4) via `provenance.py` + `brain used`/`journey`/`unused` — see
  the "Added — provenance + functional-journey" section above. No TUI, no dense
  pass over the portfolio store. See `MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`'s
  milestone ladder (M3, M7, M8) for the full path from here.

## [0.1.0] — 2026-07-09

First release. A declared, AI-optional project memory over `declared_core`.

### Added

- **Two-table memory model** — `episodes` (append-only events) + `facts`
  (durable, supersedable claims), compiled to a `declared_core.CorpusSchema`
  (two `SourceTable`s joined by a `Link`) via `MemorySchema`.
- **Writing** — `remember()` (kind-validated, append-only), `record_fact()` with
  a supersession chain, `auto_fact`, `invalidate_fact()`.
- **Hybrid recall** — `ProjectMemory.recall()` over both tables with optional
  single-table filtering, delegating to `declared_core.hybrid_query`.
- **Natural-language front door** — `understand()` (intent + entity extraction).
- **Eleven asks** — `why_not`, `can_i`, `how_do_i`, `what_for`, `route`,
  `how_does_connect`, `snapshot`, `recommend`, `similar_to`, `debug`,
  `optimize_for`, all returning one `AnswerShape`, with declared intent routing.
- **synthesis-mud** — the epistemic guard: `Fact.assess`, the five compatibility
  matrices, a 6-layer MUD detector, and `synthesize()` returning
  clean / bridge / refuse with a calibrated confidence. Optional persistence to a
  `synthesis_facts` audit table.
- **Dimensions** — the curated 12-dimension `MEMORY_DIMENSIONS` palette (the
  proven `declared_core.DEFAULT`), with a `custom()` builder.
- **Optional dense recall** — inject any `str -> Sequence[float] | None` embedder;
  `http_embedder()` for a local OpenAI-style endpoint. Degrades byte-identically
  to lexical when absent.
- **CLI** — `project-memory {demo,remember,record,recall,ask,synthesize,recent,asks,kinds,dims}`,
  every subcommand with `--json`.
- **Presets** — `generic`, `agent`, `research` schemas.
- **MCP server** — a stdlib JSON-RPC 2.0 example exposing memory to Claude Code.
- **Docs + examples** — numbered chapters `00–10`, five self-verifying examples,
  a zero-setup demo memory, and 97 tests.

### Known limits (see [ROADMAP.md](ROADMAP.md))

- The five "learn / explore_smart / roadmap / alternatives / compatible_with"
  asks are roadmapped, not shipped.
- The synthesis-mud axis assessor is a transparent heuristic (override any axis
  explicitly for precision); a persistent/ANN dense index is future work.

[0.1.0]: https://github.com/verbalogicproject-creator/NLKE-project-memory/releases/tag/v0.1.0
