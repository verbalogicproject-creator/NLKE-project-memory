# project_memory — User Manual

**As of:** 2026-07-11 · **Version:** 0.1.0 · **Tests:** 260 passing

This is a practical, day-to-day manual: what the system does, every command it
ships, and how to actually use it. For design rationale see the `docs/`
chapters and the spec files listed at the bottom; this file is the "how do I
do X" reference.

---

## 1. What this is

`project_memory` is a **declared project memory**: an append-only log of
episodes (things that happened) plus crystallized, supersedable facts (things
believed), with hybrid recall (BM25 + structure + an optional dense booster)
and a natural-language `ask` surface — all running on the `declared_core`
engine, no LLM in the retrieval loop.

On top of that core library sits the **Portfolio Brain / Graph Memory
system** — an *internal* capability (not part of the published package) that
indexes this machine's whole `~/projects` ecosystem into one store and
injects live context into Claude Code sessions. Section 5 covers it
separately since it's a different audience (you, running this repo) than
Sections 2–4 (anyone using `project_memory` as a library/CLI in their own
project).

```
   episode  ─────────────────────────►  fact
   "we chose SQLite over Postgres"      "SQLite is the store of record"
   kind=decision                        reason="local-first, zero-ops"
   (append-only, what happened)         (supersedable, what we believe)
```

---

## 2. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../declared_core        # the engine — not on PyPI yet, clone it beside this repo
pip install -e ".[dev]"                # this repo + test deps
```

Optional extras:

```bash
pip install -e ".[dense]"       # numpy + declared-core[dense] — paraphrase recall booster
pip install -e ".[portfolio]"   # PyYAML + ngfify — only for the Portfolio Brain (section 5)
```

Nothing above `declared-core` is a required dependency — `numpy` and
`PyYAML`/`ngfify` stay behind extras. Recall is deterministic without them.

Sanity check:

```bash
project-memory demo
```

Should print `Verify your build: ok`-style deterministic output over the
packaged demo memory (8 episodes, 5 facts) — a recall, an `ask`, and a
`synthesize` refusal, with no network calls.

---

## 3. Core concepts

| Concept | What it is | Lifecycle |
|---|---|---|
| **Episode** | An event, in the project's own words — `kind` (decision/gotcha/insight/…), tags, timestamp | Append-only. Happens twice → recorded twice. |
| **Fact** | A durable claim crystallized from episodes — `claim`, optional `reason`, a supersession chain | Never deleted. Superseded facts stay in history with `status`/`superseded_by`. |
| **Recall** | Hybrid search over both tables — BM25 + structural (kind/tag clusters + the episode→fact link) + an optional dense booster + a curated dimension palette | Deterministic without a dense embedder; byte-identical fallback if one dies mid-session. |
| **Ask** | A natural-language question routed (by intent) to one of eleven composed answers, each citing its evidence | Read-only; never mutates memory. |
| **synthesis-mud** | The epistemic guard: merging two facts scores 5+1 axes, runs a 6-layer compatibility check, returns **clean / bridge / refuse** | Deterministic, AI-less, calibrated against worked examples. |

The eleven asks (`project-memory asks` to list): `why_not`, `can_i`,
`how_do_i`, `what_for`, `route`, `how_does_connect`, `snapshot`, `recommend`,
`similar_to`, `debug`, `optimize_for`.

The twelve-dimension palette (`project-memory dims`) spans four families:
navigation (`spatial_relevance`, `hop_distance`, `traversal_frequency`),
retrieval (`match_precision`, `semantic_coverage`, `keyword_hit_rate`),
synthesis (`synthesis_potential`, `generative_scope`), performance
(`latency_class`, `storage_tier`), and architecture (`modularity`,
`error_recovery`).

Episode kinds are preset-specific (`project-memory kinds --preset agent`):
`decision`, `gotcha`, `insight`, `invariant`, `todo`, `observation`,
`general`. `generic` and `research` presets have their own taxonomies —
`kinds --preset <name>` shows exactly which.

---

## 4. Core CLI reference (`project-memory ...`)

Every subcommand takes `--db PATH` (default: `$PMEM_DB` or
`./project-memory.db`), `--preset {agent,generic,research}` (which kind
taxonomy to validate against), `--dense-url URL` (an OpenAI-style
`/v1/embeddings` endpoint — optional booster, everything works without it),
and `--json` (machine-readable output, for scripting).

### `demo`
Explore the packaged, deterministic demo memory. `--json` for structured
output.
```bash
project-memory demo
project-memory demo --json
```

### `remember <content>`
Append an episode.
```bash
project-memory remember "chose SQLite FTS5 for offline search" --kind decision --tag search
project-memory remember "note search must work offline" --kind invariant --auto-fact
```
- `--kind KIND` — episode kind (validated against the preset's taxonomy).
- `--tag TAG` — repeatable.
- `--batch BATCH` — the cluster/dimension this episode belongs to.
- `--auto-fact` — also crystallize a fact from this episode in the same call.
- `--reason REASON` — used if `--auto-fact` is set.

### `record <claim>`
Write (or supersede) a durable fact directly.
```bash
project-memory record "SQLite is the store of record" --reason "local-first, zero-ops"
project-memory record "Postgres is the store of record" --supersedes <fact-id>
```
- `--supersedes FACT_ID` — retires the prior fact; it is never deleted, just
  marked superseded.
- `--tag TAG` — repeatable.

### `recall <query>`
Hybrid search over episodes and/or facts.
```bash
project-memory recall "offline search"
project-memory recall "SQLite" --table facts --limit 5
```
- `--table {episodes,facts}` — restrict to one table (default: both).
- `--limit N`.

### `ask <question>`
Route a natural-language question to one of the eleven asks and get a
composed, cited answer.
```bash
project-memory ask "why did we store timestamps in UTC?"
project-memory ask "how do I add a new note?" --name how_do_i   # force a specific ask
```
- `--name ASK` — skip intent classification, force a specific ask.
- `--limit N` — evidence items considered.

### `synthesize <fact_a> <fact_b>`
Run the synthesis-mud guard over two raw claim strings (not fact ids) —
returns `clean` / `bridge` / `refuse` with a calibrated confidence and a
reason.
```bash
project-memory synthesize "the API must never log request bodies" "logging request bodies helps debug support tickets"
project-memory synthesize "SQLite is the store of record" "Postgres is the store of record" --persist
```
- `--persist` — also write the outcome to the `synthesis_facts` audit table.

### `recent`
Most recent episodes, optionally filtered by kind.
```bash
project-memory recent --limit 10
project-memory recent --kind decision
```

### `asks` / `kinds` / `dims`
List, don't query: the eleven asks, one preset's kind taxonomy, or the
twelve-dimension palette. All support `--json`.
```bash
project-memory asks
project-memory kinds --preset research
project-memory dims
```

---

## 5. Portfolio Brain & Graph Memory (`project-memory brain ...`)

**Internal capability** — this indexes and injects context for *this
machine's* repo ecosystem (`~/projects` plus a few termux paths), not
something a downstream user of the `project_memory` package gets. Requires
the `portfolio` extra (`pip install -e '.[portfolio]'`) for the edge manifest
and the `ngfify` auto-declare fallback.

### 5.1 Build the index

```bash
python scripts/index_portfolio.py                 # fresh rebuild of portfolio.db over PORTFOLIO_SCOPE
python scripts/index_portfolio.py --json           # emit the IndexReport as JSON
python scripts/index_portfolio.py --no-fresh       # append instead of rebuilding
```

What it does, per repo in `PORTFOLIO_SCOPE` (`project_memory/portfolio.py`):
one flat dimension (`batch=<repo name>`), one episode per declared interface
— preferring (1) a committed `*.ngf.md` `ai_card`, then (2) a "Public API"
doc section, then (3) an `ngfify` auto-declared fallback — and verified
`composes`/`public_twin_of`/`built_by` edges from `portfolio-edges.yaml`
(an edge neither repo's own docs assert is **dropped, not ingested**).

As of today: **26 repos indexed, 771 interface atoms**, 24 edges kept / 18
dropped. Repos normally resolve under `~/projects` via `--root`; five repos
that live elsewhere on this machine (termux paths, shared storage) are
pinned via an explicit `RepoSpec.path` override instead (see
`MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`'s M5 for why that was needed).

### 5.2 `brain load` — print a context artifact on demand

```bash
project-memory brain load declared_core                # one project's artifact
project-memory brain load declared_core --hops 2        # + a rescored 1-2 hop graph-walk
project-memory brain load aisle                          # a pack: bundles 4 member projects
project-memory brain load --current                      # detect the project from cwd's basename
project-memory brain load --current --json                # machine-readable, used by the hook
```
An artifact has five sections: **Identity** (what the repo is, from its own
README), **Interfaces** (its declared public surface, capped at 15),
**Related** (1-hop verified edges, or a rescored 1-2 hop walk with `--hops
2`), **Recent memory** (accreted decisions — see 5.4), and **What to do**
(the pack's prompt, or a generic default). Every load is itself recorded as
a `kind="brain_load"` provenance episode.

`--hops 2` rescoring is a declared (not learned) formula: a fixed weight per
edge category (`composes=1.0`, `public_twin_of=0.7`, `built_by=0.5`) times a
`0.6` decay per hop, so a 2-hop neighbor always ranks below the 1-hop
neighbor it routes through. Cycle-safe — never revisits a node already on
the current path.

### 5.3 `brain menu` — browse everything

```bash
project-memory brain menu                     # list every project + pack, prompt for a pick
project-memory brain menu --select 3          # skip the prompt — a number from the listing
project-memory brain menu --select aisle --json
```

### 5.4 `brain remember` — an accreted decision log

```bash
project-memory brain remember "we chose SQLite for zero-ops" --current --reason "local-first"
project-memory brain remember "the build broke on CI again" --current --no-auto-fact --kind gotcha
project-memory brain remember "Postgres is the store now" --current --supersedes <fact-id>
```
Crystallizes a fact by default (`auto_fact=True` — unlike the generic
`remember` CLI in Section 4, which defaults to episode-only, since the whole
point here is that a *future* session sees it). Shows up under that
project's artifact as "## Recent memory", newest first, capped at 8, each
line showing its fact id so a later `--supersedes` is directly actionable.
Use `--no-auto-fact` for one-off events, not standing decisions.

### 5.5 `brain ingest-memory` — pull in Claude Code's own memory files

```bash
project-memory brain ingest-memory --current
project-memory brain ingest-memory --project declared_core
project-memory brain ingest-memory --memory-dir ~/.claude/projects/<slug>/memory --types project,reference
```
Ingests Claude Code's own per-project `~/.claude/projects/<slug>/memory/*.md`
files as episodes tagged `corpus=memory`. Only `metadata.type == "project"`
memories are ingested by default — `user`/`feedback`/`reference` are about
you, not the project, and would leak personal notes into an artifact
injected into unrelated repos. Pass `--types` to override.

### 5.6 `brain reindex` — refresh one project without a full rebuild

```bash
project-memory brain reindex declared_core
```
Re-extracts one project's atoms + milestone in place, without touching every
other repo in the store.

### 5.7 Packs — hand-curated project bundles

A `.pack.md` file (`project_memory/packs/*.pack.md`) is frontmatter
(`members:`, each `<name>: <why>`) plus a body prompt. `brain load <pack-id>`
concatenates every member's own artifact (each member's own "What to do"
stripped, since the pack's own prompt appears once at the end).

Three ship today:
- **`aisle`** — the Aisle wedding co-pilot (Aisle-demo, scaffold_kg_rag_agent, sag-declarum-atlas-framework, taste-skill-main).
- **`verbalogix-suite`** — the Verbalogix product line (ctx-architecture, codebase-memorizer, vouch, verbalogix). Named `-suite`, not `verbalogix`, deliberately: that id collides with a member project's own name.
- **`aria-app-builder`** — the Aria app-builder toolchain, spanning termux repos (voice-graph-rag, gemini-KG-RAG-coding-expert, nlke-declarum-model-01-coding, jewelry-current).

Write your own by adding a `<id>.pack.md` under `project_memory/packs/` —
`kind: pack` and a non-empty `members:` list are required; `find_pack`/
`list_packs` fail loud on anything malformed.

### 5.8 The `SessionStart` hook — auto-injection into Claude Code

`scripts/session_start_hook.{sh,py}` runs `brain load --current --json` and
returns the artifact as `additionalContext`, so a fresh Claude Code session
in a known repo wakes up already aware of it — no manual `brain load`, no
repo-scanning tool calls. Fires on `startup`/`clear` only. Verified live
against real sessions, including via `claude -p` with tools disabled (to
prove the context arrived by injection, not a tool call).

---

## 6. Common workflows

**Seed a new project's memory and ask it something:**
```bash
project-memory remember "chose SQLite over Postgres" --kind decision --auto-fact --reason "zero-ops"
project-memory ask "why did we choose SQLite?"
```

**Correct a past decision without losing history:**
```bash
project-memory record "Postgres replaces SQLite for multi-writer support" --supersedes <old-fact-id>
```

**Check whether two beliefs are safe to merge:**
```bash
project-memory synthesize "we trust the security team's threat model" "we trust the growth team's usage data"
```

**Log a decision so it surfaces next time this repo is loaded (Portfolio Brain):**
```bash
project-memory brain remember "we chose the RepoSpec.path override over symlinks" --current \
  --reason "no filesystem side effects, edges between termux repos still verify"
```

**Pull today's context for a repo, the way Claude Code sees it:**
```bash
project-memory brain load --current
```

---

## 7. Environment variables

| Variable | Used by | Default |
|---|---|---|
| `PMEM_DB` | core CLI (`remember`/`record`/`recall`/`ask`/…) | `./project-memory.db` |
| `PMEM_BRAIN_DB` | all `brain ...` subcommands | `<repo>/portfolio.db` |

`--db` on any command overrides both.

---

## 8. Known limits (see `ROADMAP.md` for the full, honest list)

- No mid-session recall — the only "wake up" moment is `SessionStart`;
  pulling another project's/pack's artifact mid-session needs an MCP tool
  that doesn't exist yet.
- No provenance tracking (loaded-but-never-used markers, functional-journey
  narrative) — planned as M4.
- No decay/archival — a "Recent memory" fact stays until explicitly
  superseded; planned as part of M8's maintenance floor.
- No provider-agnostic export (Codex/Gemini/Antigravity adapters, MCP
  breadth) yet — planned as M6.
- No TUI yet (planned as M3) and no dense/embedding pass over the portfolio
  store yet (optional, planned as M7).
- `aria-app-builder`'s members have no verified edges *between* them yet —
  `portfolio-edges.yaml` doesn't declare any pairs involving the termux repos,
  so the pack bundles them without a relationship graph.

---

## 9. Where to go deeper

- `docs/00-mental-model.md` through `docs/10-claude-code-mcp.md` — numbered
  teaching chapters (mental model, remember/recall, facts/supersession, the
  NL front door, asks, dimensions, synthesis-mud, optional dense, API
  reference, CLI reference, MCP).
- `examples/` — runnable, self-verifying scripts (`01_remember_and_recall.py`
  … `05_dense_optional.py`, plus `mcp_server.py` and `recursive_close.py`).
- `PORTFOLIO-BRAIN-SPEC.md` — the indexing-layer design.
- `MEMORY-SYSTEM-MVP-SPEC.md` — the context-injection MVP (Cuts 1–3).
- `MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md` — the M0–M8 upgrade ladder past the
  MVP, with each shipped milestone's implementation notes inline.
- `CHANGELOG.md` — dated, detailed history of what actually shipped, found,
  and was deliberately left out, each entry with its test count.
- `ROADMAP.md` — what's shipped vs. deliberately not-yet, and why.
