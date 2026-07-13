# Graph Memory / Context System — MVP → v1.0 Upgrade Spec

**Status:** roadmap (2026-07-11) · **Author:** Eyal Nof · **Attribution:** Eyal Nof only, **no co-author trailer** · **Do NOT push** (internal moat tool).

> **What this doc is.** The full path from the shippable MVP to **v1.0 — the complete graph
> memory/context system**. It carries the context for every future upgrade in one place: the v1.0
> target, the invariants that hold across all phases, the milestone ladder (goal · components ·
> where-to-mine · acceptance · dependencies), and the sequencing.
>
> **Read alongside:**
> - `MEMORY-SYSTEM-MVP-SPEC.md` — the buildable MVP slice (= milestone **M0** here).
> - `/root/projects/aria-gameEngine-jewelry-canvas-os-awareness-memory-context-injection-source-of-truth-2026-07-11.ngf.md` — the SoT: full design, reference map (§1), tuning constants (§7).
> - Memory: `graph-memory-context-system` (the reframe + locked decisions + origin).

---

## 1. The v1.0 target (definition of done)

**v1.0 = one provider-agnostic external brain that genuinely REPLACES built-in agent memory** across
Claude Code / Codex / Gemini-CLI / Antigravity — one store, all projects, all agents. At v1.0 it does:

1. **Auto-injects awareness** — every agent, in every project, wakes up already knowing (SessionStart / equivalent).
2. **Real graph-walk** — follow typed, rescored edges 1–2 hops; the `[[links]]` are the retrieval graph.
3. **Packs** — load any curated subgraph on demand via a menu, each pack a self-describing meta-index node.
4. **Accreting session memory** — a curated + ingested log that remembers what was decided, with temporal supersession.
5. **Provenance** — every load/write recorded; loaded-but-unused is visible; usage captured as a functional-journey.
6. **Full reach** — Ubuntu + termux projects; the `aria-app-builder` pack live.
7. **Provider-agnostic export** — the neutral artifact adapts to CLAUDE.md / AGENTS.md / GEMINI.md / MCP.
8. **Dense booster** (optional) — local embeddings improve recall, degrade cleanly to lexical.
9. **Budgeted injection** — a ContextBudgeter packs to a token ceiling by priority × score, with a pinned set.
10. **A maintenance floor** — a golden-set regression (>90%), drift/backfill, archival, crystallization.
11. **A TUI for Eyal** — Browse / Graph / Dashboard over the same store.

Everything below is the ladder from M0 (MVP) to that target.

---

## 2. Cross-phase invariants (the seed laws — never violate in any milestone)

These come from `syntax-as-context` (origin + prototypes) and the reference systems. They hold from M0 to v1.0:

1. **The `[[links]]` ARE the edges.** The graph is not separate from the nodes; the links between them are the graph. Graph-walk = following links ("recursive comprehension").
2. **Edge type is carried by the section** the link sits in (`Dependencies:` = depends-on · `Related` = see-also · a hub category = cluster), plus the annotation = the edge's *reason*. Extract edge type from context, not only from a prefix token.
3. **Unresolved / "phantom" edges are first-class.** A link to a not-yet-indexed project is a valid *pending* edge, never an error. Model resolved/unresolved state.
4. **GENERATE the meta-index; never hand-author it.** The seed's own hand-written hub drifted the day it was written. Derive-and-verify (portfolio.py), refuse edges the docs don't assert.
5. **The selection→injection binding is TESTED and load-bearing.** (The `controll-interface` V1.1 shipped cosmetic toggles a router silently bypassed.) What you select must deterministically drive what is injected.
6. **A document can BE the memory.** The injection payload is a portable {state + relationships + what-to-do} artifact — provider-neutral by nature (this is what makes M6 free).
7. **Provenance on every write; capture usage as a functional-journey** (narrative, not raw timestamps).
8. **Right-size by corpus × volatility** (the jewelry lesson): small+stable → prompt-embed; volatile → fetch-on-demand, never index; large+stable → full RAG. The app-builder (future #11) ships this rule.
9. **Payload stays provider-neutral;** provider specifics live only in the M6 export adapters.
10. **Degrade gracefully.** Real corpora have truncated nodes and missing fields; parse partially and flag, never choke.

---

## 3. The milestone ladder (M0 → v1.0)

Milestone numbers here are the **upgrade path**; they reconcile to the SoT's P-phases as noted.
Each milestone is independently shippable and testable.

### M0 · MVP  *(= SoT P0 + thin P1/P2 — see `MEMORY-SYSTEM-MVP-SPEC.md`)*
Artifact generator · `.pack.md` nodes + loader · `brain` CLI (load/menu) · SessionStart hook · the tested binding. Ubuntu-first, Claude-first, rides the existing `portfolio.db`. **Baseline for everything below.**

### M1 · Real graph — scored graph-walk *(SoT P5 graph leg, pulled early because links = the thesis)*
- **Goal:** turn edges from static 1-hop text into a **rescored 1–2-hop typed-edge BFS**; the artifact's `hops` param actually traverses.
- **Components:** `project_memory/graph.py` (BFS + rescore) · a typed-edge taxonomy (extend `portfolio-edges.yaml` / a `relations.json`) · resolved/unresolved edge state in the store · harden the generated meta-index in `portfolio.py`.
- **Mine from:** nlke `~/projects/kggraph/nlke/core/{graph_expander,relationship_extractor,reranker,bm25,retrieval}.py`.
- **Acceptance:** "what composes X → their neighbors" returns rescored multi-hop results; phantom edges render as `(pending)`; the index is regenerated, not hand-edited.
- **Depends on:** M0.
- ✅ **Shipped 2026-07-11.** `project_memory/graph.py` — `edges_touching` (the shared 1-hop
  primitive, moved out of `artifact.py`, byte-identical output for hops=1), `EDGE_CATEGORIES`
  (declared forward/reverse labels + a fixed weight per category: `composes=1.0`,
  `public_twin_of=0.7`, `built_by=0.5` — a dict, not a learned model), and `walk(mem, scope,
  hops)` — BFS with per-node best-path dedup, cycle-safe (never revisits a node already on the
  current path, so any `hops` value terminates regardless of graph shape), capped at 30 hits.
  Score = product of per-hop category weights × `0.6^(depth-1)` — a 2-hop composes→composes
  chain (0.6) can outrank a weaker 1-hop `built_by` (0.5); documented as a real, currently-untuned
  consequence of the formula, not a bug.
  **Where it lives:** `graph.py`, not `declared_core` — resolved explicitly with Eyal before
  building: this walks project_memory's own edge-fact convention (tags-based, no
  `CorpusSchema.Link`), not declared_core's BM25/RRF fusion, so CLAUDE.md's "retrieval math
  belongs to declared_core" invariant doesn't apply here.
  **hops=2 is opt-in, not default** — `build_artifact(scope, mem, hops=1)` stays the exact
  pre-M1 behavior (what the SessionStart hook injects); `hops=2` renders a new "Related (1-2
  hops, scored)" section via `graph.walk`, wired to `brain load --hops 2`. Packs stay
  hops=1-only (each member's own block is built at hops=1). 19 new tests (`tests/test_graph.py`
  + additions to `test_artifact.py`/`test_cli.py`), 219 total (up from 200).
  **Verified live** against the real `portfolio.db`: `brain load declared_core --hops 2`
  correctly surfaces declared_core's 5 direct dependents at score 1.00, then 3 real 2-hop
  neighbors discovered through `scaffold_kg_rag_agent` (persona_guard, declarum-substrate,
  Aisle-demo) at score 0.60; a repo with zero edges degrades to "(no verified edges)" cleanly.
  **Not done from the original M1 scope:** the typed-edge taxonomy still lives as a `graph.py`
  dict, not an extended `portfolio-edges.yaml`/`relations.json` (deferred — no need yet with
  only 3 categories); `portfolio.py`'s meta-index generation itself is unchanged (it was already
  generate-and-verify, never hand-authored — nothing to harden).

### M2 · Session memory — the log that accretes *(SoT P3)*
- **Goal:** the brain remembers what was decided/done over time, event-sourced and temporal.
- **Components:** `brain remember "…"` (curate → append an episode) · ingest `~/.claude/.../memory/*.md` as episodes (source-tag `corpus=memory`) · crystallization (episodes → facts) · temporal supersession (`valid_from/until`, `status`) · forgetting = decay + archival (not deletion).
- **Mine from:** the research package (event-sourcing, supersession, decay) — SoT §4.3; declared_core's existing episode/fact model.
- **Acceptance:** "what did I decide about Y" answers from the log; a superseded fact does not resurface as current.
- **Depends on:** M0. (Independent of M1.)
- ✅ **Shipped 2026-07-11.** `brain remember <text> [--project|--current] [--kind] [--reason]
  [--supersedes] [--no-auto-fact]` — appends a project-scoped episode, crystallizing a fact by
  default (`auto_fact` defaults **True** here, unlike the generic `remember` CLI — the whole
  point of telling the brain to remember something is that a *future* session sees it, and only
  facts, not raw episodes, surface in the artifact). `--supersedes <fact_id>` retires a prior
  standing decision in the same call — required a small core addition,
  `ingest.remember(auto_fact=True, supersedes=...)` forwarding to the inner `record_fact`, since
  that path didn't previously accept it.
  `build_artifact` gained a fifth section, "## Recent memory" — active facts tagged
  `session-memory` for this project, newest first, capped at 8, each showing its fact id (so a
  later `--supersedes` call is directly actionable without a separate lookup). A superseded fact
  is filtered by `status='active'` and never resurfaces — the acceptance bar, met by construction
  since facts already carried supersession before M2 (CLAUDE.md invariant #2); M2's job was
  surfacing that in the artifact, not building it.
  **`session_memory.py`** ingests Claude Code's own per-project `~/.claude/projects/<slug>/memory/*.md`
  files as episodes tagged `corpus=memory` (`brain ingest-memory --memory-dir|--project|--current
  [--types]`). Two decisions made concrete against real data while building this, both discovered
  by inspecting an actual memory directory rather than assuming the format:
  1. **Only `metadata.type == "project"` is ingested by default.** Claude Code's own auto-memory
     system declares four types (`user`/`feedback`/`project`/`reference`); the other three are
     about Eyal and how Claude should work with him, not a project's technical state — ingesting
     them would leak personal/behavioral notes into a portfolio artifact injected into unrelated
     repos' sessions. `--types` overrides this if a caller explicitly wants more.
  2. **`batch` is an explicit, optional flag, never auto-derived from the directory.** A real
     memory directory (`~/.claude/projects/-root-projects-ubuntu/memory/`) was found to hold notes
     about several different, unrelated projects at once — Claude Code doesn't scope one memory
     directory to one repo as tightly as this brain's own portfolio does. Tagging the whole
     directory's contents to a single guessed project would have mis-tagged most of them.
     Ingesting unscoped (`batch=None`, the default) still makes everything fully
     `recall`/`ask`-able across the whole brain; it just doesn't surface in any one project's
     `build_artifact`.
  `default_claude_memory_dir(project_root)` infers the `~/.claude/projects/<slug>/memory` path
  from a project's root (both `/` and `_` become `-` — confirmed against this repo's own real
  directory naming, not from official documentation — flagged as inferred, not guaranteed-stable).
  **Verified live**: ingested the real, unmodified `-root-projects-ubuntu` memory directory (14 of
  its ~19 files are `type=project`) into a scratch copy of `portfolio.db`, then asked
  `project-memory ask "what is the graph memory context system decision"` against it — real,
  correct episodes surfaced (`post-compact-plan-and-brain-upgrade`, `nlke-ecosystem-extraction-plan`,
  …), confirming the acceptance bar end to end against actual, not synthetic, data.
  38 new tests (`tests/test_session_memory.py`, plus `test_store_ingest.py`/`test_artifact.py`/
  `test_cli.py` additions), 257 total (up from 219 at the end of M1).
  **Not built — M2's own "forgetting = decay + archival" component**: this round shipped
  accretion (`brain remember`/`ingest-memory`), crystallization (`auto_fact`), and supersession
  (already existed, now surfaced in the artifact) — but nothing decays or archives yet; a fact
  stays in "Recent memory" indefinitely until explicitly superseded or invalidated. Folded into
  M8's maintenance floor (90/180-day archival) instead of being solved here.

### M3 · The TUI (for Eyal) — 3 tabs *(SoT P4)*
- **Goal:** Browse / Graph / Dashboard over the store.
- **Components:** `project_memory/tui.py` (curses or textual) — Browse (repo list + detail + ask box) · Graph (walk edges — rides M1) · Dashboard (health/clusters).
- **Acceptance:** open TUI → browse a repo → walk its graph → read the dashboard, all from `portfolio.db`.
- **Depends on:** M1 (for a real Graph tab); M0.

### M4 · Provenance + functional-journey *(SoT injection layer, provenance half)*
- **Goal:** know what was loaded, when, why — and whether it was used.
- **Components:** `brain-loads.log` (jsonl: `{ts, scope, kind, trigger}`) + a `used/unused` marker · functional-journey capture (narrative of a session's loads/actions).
- **Mine from:** `controll-interface/Functional Journey Reporting.md`; `Background studio` `fixed.html` (`sliderJourneys`/`systemOutcomes`).
- **Acceptance:** report packs loaded-but-never-used; reconstruct a session's journey as a story.
- **Depends on:** M0 (CLI) — richer with M2.
- ✅ **Shipped 2026-07-12.** `project_memory/provenance.py` — pure functions
  over an open `ProjectMemory`, reading the episode log directly (via
  `mem.schema.episode_table`, never a hardcoded name — same discipline as
  `query.py::recent`). **The `brain-loads.log` jsonl in the component list was
  not built as a side-file, by an already-documented design decision:**
  `cli.py::cmd_brain_load` had *already* chosen (pre-M4) to record every load as
  an episode (`kind="brain_load"`) in the brain's own store rather than a
  disconnected log, so `recall`/`ask`/`recent` already see loads. M4 builds the
  provenance *reports* on that existing log instead of introducing a second sink:
  `record_use` appends a `kind="brain_use"` episode (the `used`/`unused` marker,
  append-only — not a mutable flag, honoring "episodes are append-only");
  `unused_loads` folds loads against uses to answer "loaded but never used"
  (`--packs` restricts to packs — the acceptance bar's exact phrasing);
  `journey(session)` reconstructs a session's ordered load/use/export events as a
  readable story (`JourneyReport.story()` / `.to_dict()`). Sessions ride the
  episode table's *existing* `session_id` column (no schema change) —
  `cmd_brain_load`/`menu`/`export` now stamp it, and the `SessionStart` hook
  passes Claude Code's own `session_id` through `--session`; pre-M4 loads
  (`session_id = NULL`) fold into the all-sessions view. CLI: `brain used
  <scope>` (rejects a scope that was never loaded — a `used` marker only makes
  sense for pulled context), `brain journey [--session]`, `brain unused
  [--packs] [--session]`, all `--json`-able. **Declared over inferred
  (CLAUDE.md):** a load is treated as used only when *explicitly* marked, never
  guessed from later scoped activity — that heuristic is a deliberate non-goal.
  One new episode kind, `brain_use`, added to `PORTFOLIO_KINDS` (schema
  validation fails loud on unknown kinds; Python-side, so backward-compatible
  with the existing `portfolio.db` — no migration). **Verified live** against
  the real `portfolio.db`: read-only `brain journey`/`unused` reconstructed 7
  real historical events and correctly reported both scopes as loaded-but-never-
  used; a full load→used→journey→unused write cycle (run against a *copy*, so no
  false `used` marker was written into the real store) folded correctly — the
  used scope dropped from the unused report, the note surfaced in the story, and
  marking a never-loaded scope was cleanly rejected. 24 new tests
  (`test_provenance.py`, 14; `test_cli.py`, 9; `test_session_start_hook.py`, 1),
  325 total. **Acceptance bar met:** packs-loaded-but-never-used report + a
  session's journey reconstructed as a story.

### M5 · Reach expansion — termux + the app-builder pack *(SoT "Later" reach)*
- **Goal:** index cross-filesystem projects; light up the driving pack.
- **Components:** a declared cross-fs roots list (add termux: `voice-graph-rag`, `gemini-KG-RAG-coding-expert`, `nlke-declarum-model-01-coding`, `jewelry-current`, `canvas-os`) · run `index_portfolio` over them · author `packs/aria-app-builder.pack.md` (members now exist).
- **Acceptance:** `brain load aria-app-builder` emits the full app-builder context bundle (voice-graph-rag + gemini-KG-RAG-coding-expert + nlke-declarum-model-01 + jewelry-current) + its prompt.
- **Depends on:** M0 (ingest + pack format).
- ✅ **Shipped 2026-07-11.** Hit a real gap before "add a roots list" was even possible: the five
  termux repos don't share one parent directory with `~/projects` *or* with each other — they sit
  under three distinct filesystem regions (termux home directly, a `kg-factory/` subdirectory, and
  shared storage under `/sdcard/`). `index_portfolio()`/`verify_edge()` both hardcoded
  `root / repo.name`, a single shared root for the *entire* scope — a cross-fs "roots list" alone
  couldn't have worked, and per-call `--root` reruns couldn't either, since `verify_edge` needs both
  sides of an edge resolvable in the same call. Fixed with an optional `RepoSpec.path` (absolute
  location override) and a shared `_repo_path()` resolution helper used by `extract_atoms`,
  `index_portfolio`, and `verify_edge` alike — `path=None` (every pre-M5 repo) is byte-identical to
  the old `root / name` behavior. Real paths verified on disk before indexing, not assumed from the
  spec's names: a same-named `voice-graph-rag` under `~/projects/future/` turned out to be a stray
  `gemini/` notes folder (ignored); a same-named `nlke-declarum-model-01-coding` there was confirmed
  byte-identical (README hash + git `HEAD` both match) to the termux copy, so the termux path was
  kept canonical. `packs/aria-app-builder.pack.md` bundles the spec's four named members (not
  `canvas-os`, which is indexed but not a pack member), each "why" line grounded in that repo's own
  README/CLAUDE.md.
  **Verified live**: `index_portfolio` went from 21 to 26 repos, 771 interface atoms (up from
  ~495); all five new repos ingested with zero atom warnings (`nlke-declarum-model-01-coding` via
  495 real `.ngf.md` cards, the rest via the `ngfify` fallback). `brain load aria-app-builder`
  emits all four members' full artifacts plus the pack's prompt, matching the acceptance bar
  exactly. 9 new tests (`test_portfolio.py`, `test_pack.py` additions), 260 total.
  **Follow-up — ✅ Shipped 2026-07-13**: the deferred termux-edge work is done.
  `portfolio-edges.yaml` now declares four `composes` edges involving the termux repos, each
  grounded in one side's own edge-docs so each survives `verify_edge`:
  `nlke-declarum-model-01-coding → gemini-KG-RAG-coding-expert` (ingests its Graph-RAG KG as a
  corpus source — the one intra-termux/intra-pack edge), and three that wire the app-builder
  spine `voice-graph-rag` into the existing fleet graph —
  `Aisle-demo`, `aisle-wedding-copilot`, and `sag-declarum-atlas-framework` each name it (co-pilot
  spine / aria-core substrate). Two doc-mentions were deliberately **not** declared, because a name
  co-occurrence isn't a composition: `declared_repo_factory` names `canvas-os` only to note where
  `aria-core` is vendored, and the atlas framework names `jewelry-current` only as a `file:`-ref
  packaging precedent. Edge set went **24 → 28 kept** (18 dropped, unchanged); the live
  `portfolio.db` was updated with `index_portfolio --no-fresh` (append — *not* a `--fresh` rebuild,
  which would wipe M4's 9 provenance episodes), preserving 771 atoms + 9 provenance episodes.
  `graph.walk` now reaches voice-graph-rag's three composers and nlke ⟷ gemini-KG-RAG. Full suite
  green at 325 (no new tests — the edge path is already covered by synthetic fixtures).

### M6 · Provider-agnostic export — one brain, many tools *(the north-star realization; SoT "Later" adapters)*
- **Goal:** the same store injects into any agent.
- **Components:** `project_memory/export/` adapters: neutral artifact → `CLAUDE.md` · `AGENTS.md` (Codex) · `GEMINI.md` · Antigravity · **MCP breadth** (resources = snapshot pull · prompts · a bulk-reindex tool) — match game-engine pgm.
- **Mine from:** `examples/mcp_server.py`; game-engine pgm MCP surface; canvas-os `context/{promptBuilder,contextEngine}.ts`.
- **Acceptance:** one store → verified injection in Claude, Codex, and Gemini from a single artifact; an MCP resource pull returns a repo/project snapshot.
- **Depends on:** M0 (the payload is already neutral — this is mostly adapters).
- ✅ **Shipped 2026-07-12.** Built the MCP leg first, then the file-export
  adapters. `project_memory/export/mcp_portfolio.py` —
  pure functions over an already-open `ProjectMemory`, no stdio in the library
  code itself: `list_resources`/`read_resource` (one `portfolio://project/<name>`
  resource per known project + one `portfolio://pack/<id>` per declared pack;
  reading either returns `build_artifact`/`build_pack_artifact`'s exact text —
  the same snapshot `brain load` prints), `list_prompts`/`get_prompt`
  (`load_context(scope, kind?)` — wraps the artifact as a conversation-turn
  message, matching the MCP breadth item's "prompts"), and `list_tools`/
  `call_tool` (one tool, `brain_reindex(name?, root?)` — matching the item's
  "a bulk-reindex tool"). `examples/mcp_portfolio_server.py` is the thin JSON-RPC
  stdio transport, a second server distinct from the existing per-project
  `examples/mcp_server.py`, adding `resources/list`, `resources/read`,
  `prompts/list`, `prompts/get` methods to that server's existing
  `initialize`/`tools/list`/`tools/call`/`ping` shape.
  **A deliberate design call not in the original spec text:** `brain_reindex`
  is idempotent, never destructive — unlike `scripts/index_portfolio.py`'s
  default (delete `--db` and rebuild fresh), the MCP tool always calls
  `index_portfolio` in place. An agent calling a live tool mid-session must
  never be able to wipe the store out from under itself; `remember`/
  `record_fact`'s existing `INSERT OR IGNORE` already makes in-place reruns
  safe (the same guarantee `cmd_brain_reindex` relies on), so this was a
  reuse, not new machinery.
  **This also closes a second open item** — ROADMAP.md's "mid-session
  recall" gap (the `SessionStart` hook was the only "wake up" moment; nothing
  let Claude pull another project's or pack's artifact without restarting the
  session). The `portfolio://` resources + `load_context` prompt are exactly
  that on-demand pull.
  **Verified live** against the real `portfolio.db`: `resources/list` returned
  29 resources; `resources/read` on `portfolio://project/project_memory` and
  `portfolio://pack/aria-app-builder` both returned correct artifact text;
  `prompts/get` on `load_context` returned a well-formed message; `tools/list`
  returned `brain_reindex`; an unknown-scheme URI round-tripped to a clean
  JSON-RPC error instead of crashing the pipe. 17 new tests
  (`test_export_mcp_portfolio.py`), 277 total at that point.
  **The file-export leg, same day:** `project_memory/export/files.py` — pure
  functions, no CLI coupling beyond a target directory. `render_block(scope,
  mem, *, hops=1, kind="project")` wraps `build_artifact` in
  `<!-- project_memory:begin/end -->` markers; `apply_block(existing, block)`
  is the idempotent insert/replace — if the markers are already present in a
  file, only that span is replaced, so any hand-written instructions
  elsewhere in the same file survive a rerun untouched; applying the same
  block twice is a no-op the second time. `write_provider_file`/
  `write_all_provider_files` map `PROVIDER_FILES` (`claude`→`CLAUDE.md`,
  `codex`→`AGENTS.md`, `gemini`→`GEMINI.md`, `antigravity`→`AGENTS.md`) onto
  that primitive. **A finding, not an assumption:** Google Antigravity's own
  docs say it reads `AGENTS.md` — the same file Codex reads, falling back to
  `GEMINI.md` only if `AGENTS.md` is absent — so there is no fourth,
  Antigravity-specific file; `ALL_FILENAMES` (what `--provider all` writes)
  has three entries, and `test_export_files.py` asserts `codex` and
  `antigravity` produce byte-identical `AGENTS.md` content rather than just
  claiming it. `cli.py::cmd_brain_export` (`project-memory brain export <name>
  --provider {claude,codex,gemini,antigravity,all}`) resolves the target
  directory via `--into` or the project's own resolved location (`_repo_path`,
  the same resolution `brain reindex` already uses), rejects packs (no single
  directory to write into) and unknown projects, and supports `--dry-run`
  (prints the block, writes nothing) — same idempotent-by-design discipline
  `brain_reindex` established for this layer, applied somewhere higher-stakes:
  a real project's own context file can carry hand-authored rules a naive
  overwrite would destroy. **Verified live** against the real `portfolio.db`,
  writing only to a scratch directory (never a real sibling repo): `--dry-run`
  wrote nothing; a real `--provider all` run produced correct `CLAUDE.md`/
  `AGENTS.md`/`GEMINI.md` content; hand-written content added to `CLAUDE.md`
  survived a rerun untouched, with only the marker-delimited block replaced.
  24 new tests (`test_export_files.py`, 14; `test_cli.py` additions, 10), 301
  total. **Acceptance bar now fully met:** one store → verified injection in
  Claude (`CLAUDE.md`), Codex/Antigravity (`AGENTS.md`), and Gemini
  (`GEMINI.md`) from a single artifact, plus the MCP resource pull.

### M7 · Dense + retrieval quality *(SoT P5 dense leg — Sunday/GPU, optional)*
- **Goal:** better recall without breaking the lexical floor.
- **Components:** turn on `dense.py` `http_embedder` → local llama.cpp/Ollama `/v1/embeddings` (degrades to lexical) · ONE model, versioned, `normalize=True` · drift detection (>0.15 centroid) + backfill · named-attribute/interpretable embeddings (research Phase-4) · optional CrossEncoder rerank (opt-in).
- **Acceptance:** dense-on beats dense-off on the golden set; lexical fallback still works with the server down.
- **Depends on:** M0. (Parallel to everything; explicitly optional for v1.0.)

### M8 · Budgeted injection + maintenance floor *(SoT §4.4 ContextBudgeter + §maintenance → production)*
- **Goal:** injection respects a token ceiling; the system self-checks.
- **Components:** **`ContextBudgeter`** (net-new — no source system has it): pack to a token ceiling by priority × score, with a pinned always-include set (e.g. the per-repo purpose lines) · a **golden set** (~30 query→expected pairs, >90% pass) as a regression gate · maintenance (crystallization inline/nightly, drift reports, 90/180-day archival, snapshots).
- **Acceptance:** artifacts never exceed the budget; the golden set is green and gates schema/model changes.
- **Depends on:** M0; the golden set spans M1/M2 behavior.

---

## 4. Sequencing

- **Critical spine:** M0 → M1 (graph) → M2 (session memory) are the substance; M8 (budget + golden set) closes v1.0.
- **Parallelizable:** M4 (provenance), M6 (export adapters), M7 (dense) can proceed independently once M0 lands.
- **Gated:** M3's Graph tab needs M1; M5's app-builder pack needs the termux ingest in M5 itself.
- **Optional for v1.0:** M7 (dense) is a booster, not a gate — v1.0 can ship lexical-only.
- **Recommended order:** M0 → M1 → M2 → M5 → M6 → M4 → M3 → (M7) → M8. (Substance first; reach + one-brain-many-tools next; then ergonomics/quality; budget+maintenance last.)

---

## 5. Where to mine each piece (condensed — full map in SoT §1)

| Need | Mine from |
|---|---|
| Scored graph BFS + rescore | nlke `~/projects/kggraph/nlke/core/{graph_expander,reranker,bm25,retrieval}.py` |
| Injection layer (promptBuilder / contextEngine / SessionStart hook / source-filtered recall) | canvas-os `~/kg-factory/canvas-os/src/lib/aria-core/{knowledge,state,context}/` |
| MCP breadth (resources + prompts + reindex) | game-engine pgm MCP surface; `project_memory/examples/mcp_server.py` |
| Event-sourcing / temporal supersession / decay / tuning constants | the research package (SoT §4.3, §7); `declared_core` episode/fact model |
| Functional-journey capture | `controll-interface/Functional Journey Reporting.md`; `Background studio/fixed.html` |
| Right-sizing (stable vs volatile → tier) | jewelry-current `handlers/shopping.ts` (fetch-on-demand); SoT §4.5 |
| Fusion / intent weights / dense / structural | `declared_core/declared_core/retrieval/{fusion,intent,dense,structural,bm25}.py` |

**Tuning constants** (RRF k=60 · dedup 0.95 · BFS≤2 · decay λ≈0.01 · archival 90/180-day · drift >0.15 · golden-set >90% · sqlite-vec ceiling ~500K · one model + normalize) — see SoT §7.

---

## 6. Gates & attribution

- Attribution **Eyal Nof only, no co-author trailer**. **Do NOT push** (internal moat engine; Codebase-Memorizer is its public-simple twin).
- Human-gated milestones: any that touch termux paths (M5), any external-provider export (M6), any push.
- Honesty rule: each shipped milestone documents what's real vs pending vs optional (MVP vs fast-follow vs Sunday vs later), grounded in a real run — never a claimed capability without a runnable check.

---

*v1.0 is reached when the eleven §1 capabilities are all true and green. At that point the Manual
Memory Log (Jun 2025) → Syntax-as-Context (Sep 2025) → this system is one closed arc: declaration over
inference, with the infrastructure finally caught up.*
