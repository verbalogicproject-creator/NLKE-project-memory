# Roadmap

project_memory 0.1.0 ships a complete, honest core: a two-table episodic + factual
memory, hybrid recall, eleven asks, the synthesis-mud epistemic guard, a curated
dimension palette, a CLI, and an MCP server. This file records what is
deliberately **not** shipped yet, and why — so the README never overclaims.

## What's shipped vs. what's next (the graph memory / context-injection layer)

The internal Portfolio Brain / Graph Memory system (`MEMORY-SYSTEM-MVP-SPEC.md`,
`MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`) has its own, more granular honesty split —
full detail lives in those two files; the categories, condensed:

- **MVP, shipped:** repo indexing + verified edges (`portfolio.py`); the context
  artifact + packs + `brain load`/`menu`/`reindex` + the SessionStart hook (Cuts
  1–3); a real, rescored 1-2 hop graph-walk (M1, `graph.py`, opt-in via `--hops 2`);
  an accreted, project-scoped decision log (M2 — `brain remember` +
  `brain ingest-memory`, `session_memory.py`); reach expansion past `~/projects`
  (M5 — `RepoSpec.path`, five termux repos indexed + wired into the graph with
  four verified `composes` edges, the `aria-app-builder` pack);
  provider-agnostic export for the portfolio store (M6 — `export/mcp_portfolio.py`:
  a resource per project/pack for on-demand snapshot pull, a `load_context` prompt,
  one idempotent `brain_reindex` tool, see `examples/mcp_portfolio_server.py`;
  `export/files.py` + `brain export`: the same artifact as an idempotent
  marker-delimited block in `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` — Codex and
  Google Antigravity share the `AGENTS.md` convention, verified against each
  tool's own docs, not assumed — so three files are written, not four); load/use
  provenance + a session's functional-journey story (M4 — `provenance.py`,
  `brain used`/`journey`/`unused`: the `used`/`unused` marker and the
  loaded-but-never-used report built *on the episode log the loads already write
  to* — not a second `brain-loads.log` sink — session-scoped via the episodes'
  existing `session_id` column; a load counts as used only when *explicitly*
  marked, declared over inferred).
  325 tests, dogfooded live across several repos and against real, unmodified
  Claude Code memory files.
- **Fast-follow (next up, no new capability class needed):** **M2's own
  "decay + archival" component was not built** (only accretion + crystallization
  + supersession were) — forgetting is folded into M8's maintenance floor
  (90/180-day archival) instead of being M2's job alone. *(M5's other
  fast-follow — termux edges — is now ✅ shipped: four verified `composes` edges
  wire the termux repos into the graph, so the `aria-app-builder` pack members
  have a relationship graph. See the M5 note below.)*
- **Sunday / optional:** a dense/embedding pass over the portfolio store (M7) —
  booster, not a gate; lexical-only is a valid v1.0.
- **Later:** a budgeted injector + golden-set regression floor (M8) · a TUI
  for Eyal (M3, gated on M1's graph existing, which it now does).

## Not shipped (by design), candidates for later

### The remaining five asks
v0.1 ships a curated eleven asks. Five more from the source project's
`intent_query.py` are roadmapped: **`learn`** (assemble an ordered learning path),
**`explore_smart`** (guided expansion from an anchor), **`roadmap`** (topologically
ordered steps to a goal), **`alternatives`**, and **`compatible_with`**. The last
three assume a dependency/tool graph; on an episode+fact memory they need real
generalization (and `compatible_with` overlaps synthesis-mud). They land when the
generalization is genuinely useful, not merely present.

### Persistent / ANN dense index
`build_dense_index` builds an in-memory `NumpyVectorIndex` (brute-force cosine),
rebuilt per process and invalidated on write. That is right for the
thousands-of-rows memories this targets. A persisted vector store + ANN backend
(behind the same `DenseIndex` protocol) would avoid re-embedding for large,
long-lived memories.

### Dense over episodes+facts surfaces, chunked
The dense surface embeds each row's title/claim/tags as one text. Long episodes
would benefit from body chunking (multiple vectors per row) once the persistent
index lands.

### Recency as a first-class dimension
Memory is time-shaped: newer episodes often matter more. A deterministic
`recency` dimension (relative to the corpus, not wall-clock) is a natural addition
to the palette. It is intentionally *not* in v0.1 because a naive wall-clock
scorer would break determinism; doing it right needs a corpus-relative reference.

### Ingestion beyond text
Episodes/facts are written programmatically. A future release could ingest from
Markdown/JSON logs via the shared `universal_parser` (the same backend planned for
`frontmatter_rag`), behind the existing `remember`/`record_fact` API.

### synthesis-mud → its own package
The guard is incubated here. On a **second consumer** (e.g. multi-agent knowledge
merge, or a standalone fact-validation service) it graduates to its own repo,
imported by both. Until then it lives in `project_memory.synthesis_mud`.

### Richer axis assessment
The 5+1 axis assessor is a transparent marker-word heuristic — good enough to
catch the common MUD patterns, and every axis is overridable per `Fact`. A future
version could offer an optional LLM-backed assessor (kept behind the same `Fact`
interface, so the deterministic default never regresses).

### Portfolio Brain follow-up (`project_memory.portfolio`)
The portfolio layer ships tonight with the BM25/FTS floor + CLI `ask`/`recall`
only. Explicitly deferred:
- **A dense/embedding pass** over the portfolio store (paraphrase recall across
  repos — "what refuses to fabricate?" finding `vouch`, `persona_guard`, `ngfify`
  without the word "fabricate" appearing verbatim everywhere).
- **An MCP server exposing the portfolio store directly** — ✅ **shipped (M6)**
  via `export/mcp_portfolio.py` / `examples/mcp_portfolio_server.py`: resources
  (snapshot pull), a `load_context` prompt, and a `brain_reindex` tool. What it
  does **not** expose: the raw NL `ask`/`recall` surface — those still go
  through the core `examples/mcp_server.py` or the CLI, not this server.
- **File-based provider-agnostic export** — ✅ **shipped (M6)** via
  `export/files.py` / `project-memory brain export`: the same artifact
  written as an idempotent marker-delimited block into
  `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` — Codex and Google Antigravity share the
  `AGENTS.md` convention (researched, not assumed), so `--provider all` writes
  three files, not four. A rerun replaces only project_memory's own block,
  leaving a project's own hand-written instructions untouched.
- **A graph-shaped ask** (e.g. `what_composes` / `what_built`) — the existing
  eleven asks route by intent classification tuned for episode/fact recall, not
  portfolio-edge traversal; `recall(..., table="facts")` is still the more
  reliable surface for edge questions through the `ask()` intent router.
  **Partially addressed by M1** (`graph.py`'s `walk` + `brain load --hops 2`) —
  but that's a separate CLI command with its own declared rescoring, not a
  natural-language `ask` intent; routing "what composes X" through `ask()` to
  `graph.walk` is still open (see CHANGELOG's "Known limits").
- **Re-verification on drift** — `portfolio-edges.yaml` still carries the full
  original manifest (including edges dropped tonight); re-running
  `scripts/index_portfolio.py` after a repo's docs are updated to assert a
  currently-dropped edge will pick it up automatically, with no manifest change.

### Context-injection follow-up (`project_memory.artifact`, `brain` CLI)

- **Mid-session recall** — ✅ **shipped (M6)**. The `SessionStart` hook is still
  the only *automatic* wake-up (a fresh session gets its repo's artifact once,
  up front), but an on-demand pull now exists: `export/mcp_portfolio.py`'s
  `portfolio://project/<name>` / `portfolio://pack/<id>` resources and its
  `load_context` prompt let an agent fetch another project's or pack's artifact
  mid-session (e.g. it realizes it needs cross-repo context) without restarting
  the session — register `examples/mcp_portfolio_server.py` to use it.
- **Load/use provenance + functional-journey** — ✅ **shipped (M4)** via
  `provenance.py` / `brain used`/`journey`/`unused`. Every load is already an
  episode (`kind="brain_load"`); M4 adds a declared `used` marker
  (`kind="brain_use"`), a `journey(session)` that reconstructs a session's
  ordered load/use/export events as a story, and an `unused_loads` report that
  answers "which packs did I load and never use?" — session-scoped through the
  episodes' `session_id` (which the `SessionStart` hook now passes through from
  Claude Code). **Deliberately declared, not inferred:** a load is treated as
  used only when explicitly marked, never guessed from later scoped activity —
  auto-inference is a documented non-goal, not an oversight.

## Principles for anything we add

- **Optional stays optional.** BM25 + structural must always work offline, no
  extra deps, deterministically.
- **Declared over inferred.** Prefer readable tables and typed axes to learned
  black boxes.
- **Prove before you claim.** A feature reaches the README only when it's
  demonstrable and tested; until then it lives here.
- **Retrieval math goes to `declared_core`.** This repo stays a thin memory layer.
