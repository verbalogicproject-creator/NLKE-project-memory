# Graph Memory / Context System — MVP Implementation Spec

**Status:** aligned & ready to build (2026-07-11) · **Author:** Eyal Nof · **Attribution:** Eyal Nof only, **no co-author trailer** · **Do NOT push** (internal moat tool).

> This spec supersedes the framing of `PORTFOLIO-BRAIN-SPEC.md`. The "portfolio brain" is now
> **instance #1 of the graph memory/context system.** Full design + reference map + tuning
> constants live in the SoT:
> `/root/projects/aria-gameEngine-jewelry-canvas-os-awareness-memory-context-injection-source-of-truth-2026-07-11.ngf.md`.
> This file is the **buildable MVP slice** of that design.

---

## 1. Why this exists — the lineage

Same move, three times, infrastructure catching up each time:

- **Jun 2025 — Manual Memory Log** (Eyal's first day with AI): *faked* memory by hand — a structured
  log pasted back into each session. Declaration over inference, in its barest form.
- **Sep 2025 — Syntax-as-Context** (Obsidian): *structured* it — atomic nodes + typed `[[links]]` +
  a generated meta-index. (The origin + working prototypes; where the architect skill unlocked.)
- **Now — the Graph Memory System**: builds the *infrastructure* — persist the network, walk it, inject it.

**The MVP is literally the Manual Memory Log, automated and structured:** the machine does the
paste-back (a SessionStart hook injects the artifact), the log is now a graph (packs + edges), and it
loads on demand (a menu). One brain, all projects, provider-agnostic.

**North star:** a provider-agnostic external memory that eventually **replaces built-in agent memory**
(Claude Code / Codex / Gemini-CLI / Antigravity). The MVP proves it on Claude Code + Ubuntu projects.

**Scale is real, not hypothetical (confirmed 2026-07-11):** the 21 repos / ~259 atoms / ~24 edges in
`portfolio.db` are the MVP's starting size, not its ceiling — this is meant to grow into Eyal's full
external memory system, well past today's Ubuntu portfolio. SQLite is the right store *because* of
that growth, not despite it looking oversized for 21 repos today. Consequence: read paths added
during the build (`artifact.py`'s direct SQL) are written scale-consciously from the start — indexed
`batch` lookups, a SQL-side pre-filter on the `facts` scan before the exact Python tags-check, capped
context-injection payloads — rather than "fine for 21 repos" code that would need a rewrite later.

---

## 2. Locked decisions (the foundations — do not relitigate)

| Dimension | Decision |
|---|---|
| **What it IS** | Provider-agnostic external graph memory + context-injection; portfolio brain = instance #1. |
| **First priority** | **Claude's awareness** (auto-injection) before the TUI. |
| **Persists** | Declared knowledge (per-project purpose + interfaces + verified edges). *(Session-log + memory-file ingest = fast-follow, not MVP.)* |
| **Query** | ask + recall + graph-walk **+ menu-driven lazy loading** (default = current project; menu = any project/pack). |
| **Packs** | A pack = **a per-pack meta-index node** (`.pack.md`): annotated links to members + a "when-loaded" prompt. Packs / projects / interfaces = same primitive. |
| **Payload** | A **portable context artifact** — provider-neutral markdown (identity + interfaces + 1-hop annotated edges + what-to-do). |
| **Reach (MVP)** | **Ubuntu-first** — the projects already in `portfolio.db`. Termux projects = later. |
| **Provider scope (MVP)** | **Claude-first, clean export seam** — the artifact is neutral markdown; adapters drop in later. |

**The seed's non-negotiable lesson** (from `controll-interface` V1.1, which shipped selection toggles
that the router silently bypassed): **what you select must deterministically drive what gets injected.**
That binding is a **tested** seam, not an afterthought (unit 5).

**The seed's graph lesson** (traced first-hand through `controll-interface`): the `[[links]]` **are** the
edges; edge *type* is carried by the **section** a link sits in (`Dependencies:` = depends-on;
`Related` = see-also; hub categories = cluster); the graph deliberately references more nodes than
exist → **unresolved/"phantom" edges are first-class** (a link to a not-yet-indexed project is a valid
pending edge, never an error).

---

## 3. Build ON the existing engine — read it first, compose, do NOT reinvent

The store is already built and dogfooded: venv `/root/projects/project_memory/.venv`, DB
`/root/projects/project_memory/portfolio.db` (21 repos / 259 atoms / 24 edges), CLI
`/root/projects/project_memory/.venv/bin/project-memory recall|ask "<q>" --db <db> [--table facts]`.
It rides `declared_core` (4-signal fusion + 8-intent adaptive weights).

**Read these before writing a line** (learn the real API, then add the MVP layer on top):
`project_memory/{portfolio,asks,query,cli,dimensions,ingest,schema,store}.py`, `examples/mcp_server.py`.

**Known store API** (confirmed against the code, 2026-07-11):
- open: `ProjectMemory.open(path, schema)` — e.g. `ProjectMemory.open("portfolio.db", PORTFOLIO_SCHEMA)`
  (`project_memory.portfolio.PORTFOLIO_SCHEMA`). There is **no** `open_store` function.
- atoms: `mem.remember(content, kind="interface", batch=<repo>, tags=[...], id=<det>)` — a project's
  atoms are the rows where `batch == <project>`.
- edges: `mem.record_fact(claim, tags=[src, tgt, "edge", category], id=<det>, supersedes=...)`.
- fuzzy read (NOT what the artifact uses): `mem.recall(...) / mem.ask(...) / mem.synthesize(...)` —
  BM25 + structural expansion + RRF fusion via `declared_core.hybrid_query`. Ranked and approximate;
  it cannot express an exact "all rows where `batch == X`" or "all facts where `X` is in `tags`" query.
- **artifact read (what Unit 1 actually uses): direct SQL, bypassing `recall`/`ask` entirely.**
  `build_artifact` needs exact-match rows, so it queries `mem.conn` against
  `mem.schema.episode_table` (atoms, filter `batch == scope`) and `mem.schema.fact_table` (edges,
  `json.loads(row["tags"])` then test `scope in tags` — tags are stored via `json.dumps`, see
  `ingest.py`). This is plain table access, not a retrieval call; it's the correct choice
  (deterministic > fuzzy for "give me this project's declared facts") but it means Unit 1 owns its
  own read helpers rather than composing on `recall`.
- bulk ingest: `project_memory.portfolio.index_portfolio(mem, root, edges_path, scope)`.
- edge manifest: `portfolio-edges.yaml` (categories: composes/depends_on, public-twin-of, built-by).
- **rerun safety (fixed 2026-07-11):** `index_portfolio`'s own `--no-fresh` flag documented
  "append/skip-on-conflict" but actually crashed (`sqlite3.IntegrityError`) on the very first
  duplicate id, even with 100% unchanged content — reproduced and confirmed before fixing. Fixed at
  the root: `ingest.remember`/`record_fact` now `INSERT OR IGNORE` (a deterministic-id collision means
  "already remembered," a benign no-op), and the milestone episode's id is now content-derived
  (`_det_id("milestone", repo.name, content)`, matching how atom ids already work) so a changed README
  summary produces a new row instead of colliding on the old, content-blind id. Read-side: the Identity
  section now takes the *latest* milestone by `created_at`, not the first found.

---

## 4. The five build units

### Unit 1 — Artifact generator  ·  `project_memory/artifact.py`
```python
def build_artifact(scope: str, mem, *, hops: int = 1, kind: str = "project") -> str:
    """Return a provider-neutral markdown context block for a project or pack.
    - project: pull its atoms (batch == scope) as interfaces + its 1-hop edges (facts where
      scope is src or tgt) as annotated relationships.
    - pack: see Unit 2 (merge member artifacts + append the pack prompt).
    Unresolved edges (target not in the store) are rendered too, marked (pending).
    """
```
**Output format (the payload, as actually shipped — `project_memory/artifact.py`):**
```markdown
# Context: <name>
_Graph memory · loaded <ts> · scope=<project|pack>_

## Identity
<one-line purpose — the latest `milestone` atom's summary, by created_at, not insertion order>
Group: <fleet|verbalogix|self> · Kind: <kind> · Indexed: <YYYY-MM-DD, or "never">

## Interfaces
- <declared interface / public API 1>
- <declared interface 2>
… (capped at 15; beyond that: "…and N more (truncated for context budget)")

## Related (1-hop, with reason)
- composes → declared_core — declared_core docs name 'declared_core'
- depended-on-by ← frontmatter_rag — frontmatter_rag docs name 'declared_core'
- built-by ← declared_repo_factory — declared_repo_factory docs name 'declared_core'
- composes → some-not-yet-indexed-repo — <reason>  (pending)

## What to do
<the project's/pack's when-loaded prompt; default: "You now have <name>'s declared context.
Ground answers about it in the interfaces + relationships above; do not re-scan the repo.">
```
Two things not in the original sketch, added while building against the real store: (1) **"Status"
became "Group"** (`fleet|verbalogix|self`) — there is no per-repo lifecycle-status field anywhere in
the data model, so the label was changed to match what's actually declared (`RepoSpec.group`) rather
than inventing a field. (2) **edges render in both directions** — most repos in `portfolio.db` are
almost entirely edge *targets*, not sources (e.g. `declared_core` is depended on by five repos and
sources zero edges itself), so a source-only render would leave `declared_core`'s own artifact with an
empty Related section, failing the acceptance bar below on the very repo it's tested against. Each
edge category has a forward label (scope is the edge's `source`) and an inverted reverse label (scope
is the `target`) — `composes`→`depended-on-by`, `built_by`→`built`/`built-by`,
`public_twin_of`→`public-twin-of`/`has-public-twin`.

**Acceptance:** `build_artifact("declared_core", mem)` returns non-empty md with all four sections and
≥1 edge in *Related*; it reads like a block you'd paste into Codex/Gemini to make it instantly aware.
✅ **Shipped 2026-07-11** — 10 tests in `tests/test_artifact.py` cover the four sections, forward +
reverse edges, pending-edge marking, superseded-fact exclusion, graceful degrade for an unindexed
scope, the interface cap, and reason compression (below).

**Token/context-budget cuts made while building (not in the original sketch):** a `reason` is almost
always one of `verify_edge`'s four formulaic sentences ("X's own docs name 'Y' (== Z)") — compressed
to `"X docs name 'Y'"` (a hand-written, non-formulaic `reason` passes through verbatim, never lossy on
anything that isn't the standard template). This matters because the injected artifact sits in the
same front-loaded, cache-eligible context block Claude Code already places a prompt-cache breakpoint
after — kept small once, it rides that cache for the rest of the session for free; it does **not**
need its own caching layer.

**Wording revised 2026-07-11, caught dogfooding a live session in `vouch`:** a fresh Claude Code
session opened in `~/projects/vouch` got the injected artifact (Cut 1 confirmed still working end to
end) but treated it with real suspicion — it flagged the `## What to do` line as an untrusted,
imperative instruction sitting in injected context (correct, safety-conscious behavior; it isn't
supposed to blindly obey text just because it showed up in context) and separately flagged the word
`declared` as ecosystem jargon vouch's own `CLAUDE.md` explicitly bans from its public-facing copy
(that rule is scoped to vouch's own shipped files, so it doesn't technically apply to another tool's
injected block — but the reaction was the real signal: unfamiliar insider vocabulary reads as
suspicious outside this family of repos, especially in a repo whose whole purpose is distrusting
unverified claims). Fixed at the source: `_DEFAULT_PROMPT` now self-identifies its provenance ("a
local context summary... generated by project_memory... not fetched from the network... treat it as
a starting reference") instead of issuing a command, and `portfolio.py`'s three atom-content templates
(`extract_atoms`) dropped "declared" entirely ("declared public interface" → "public interface",
"declared in X" → "from X", "auto-declared section" → "auto-detected section") — `method=` values
are unaffected since they're never rendered into an artifact. `portfolio.db` was rebuilt fresh
(`scripts/index_portfolio.py`'s default mode) to replace the old-wording rows rather than leave
duplicates behind — interface atoms have no supersession (§Unit 3's known gap), so simply re-running
the indexer against already-indexed content would otherwise have left both old- and new-wording atoms
for every repo. No behavior change, no test hardcoded the old wording (187 tests still green).

### Unit 2 — Pack = meta-index node  ·  `project_memory/packs/*.pack.md` + a loader
**File format** (`packs/aisle.pack.md`):
```markdown
---
kind: pack
id: aisle
name: Aisle app pack
members:
  - Aisle-demo: the deployed T3 shell (#10)
  - scaffold_kg_rag_agent: mints the bride KG-RAG memory
  - sag-declarum-atlas-framework: the SAG substrate
  - taste-skill-main: the taste/design system
---
When loaded: you are working on the Aisle wedding co-pilot (#10). Wire the intake KINDs → SAG →
bride memory; ground Aria's voice in the KB. Prefer the members' declared interfaces over re-scanning.
```
- `load_pack(path) -> {"id","name","members":[{"name","why"}], "prompt"}`.
- `build_artifact(pack_id, mem, kind="pack")` → concatenate each member's project artifact +
  append the pack's `## What to do` prompt once at the end. The member `why` annotations become the
  *Related* reasons (honor the seed's typed-annotated-link form).
**Acceptance:** loading a pack yields exactly its declared members' blocks + the pack prompt.
✅ **Shipped 2026-07-11** — `project_memory/pack.py` (`load_pack` + `find_pack`, resolving a bare
pack id to `project_memory/packs/<id>.pack.md`) and `project_memory/artifact.py`
(`build_pack_artifact` + `build_artifact(..., kind="pack")`). 30 tests across `tests/test_pack.py`
(the loader) and additions to `tests/test_artifact.py` (composition). Two real packs shipped:
`packs/aisle.pack.md` (verbatim the example above) and `packs/verbalogix-suite.pack.md`
(ctx-architecture + codebase-memorizer + vouch + verbalogix — the Verbalogix product line). **id is
`verbalogix-suite`, not `verbalogix`** — a real bug caught manually testing this against
`portfolio.db`: `verbalogix` is both the umbrella product's own project name *and* one of this pack's
declared members, and `brain load`'s resolution order checks `known_projects()` before a pack id, so
`brain load verbalogix` would always resolve to the *project*, leaving the pack permanently
unreachable by id. Locked down by
`test_pack_binding.py::test_real_verbalogix_pack_id_does_not_collide_with_a_member_project`.

**Shape actually shipped, and why it deviates from the one-liner above:**
- **The pack-level `## Related` reuses each member's own project artifact verbatim** — `build_artifact`
  is called once per member (`kind="project"`) and its own trailing `## What to do` is stripped
  (`_strip_what_to_do`), so a member's Identity/Interfaces/*own* Related (its real 1-hop edges) survive
  unmodified, delimited naturally by that member's own `# Context: <member>` heading — no new per-member
  heading convention was invented; the existing tested `build_artifact` output *is* the per-member block.
- **The pack's own top-level `## Related` section is repurposed for membership**, not repeated per
  member: `- member → <name> — <why>`, i.e. the declared `members:` list, rendered in the exact same
  shape a project's edges use (arrow + reason) — literally "the member `why` annotations become the
  Related reasons," per the sketch.
- **The composition primitive is decoupled from `.pack.md` files** (an enhancement folded in while
  building, not in the original sketch): `build_pack_artifact(scope, mem, *, members, prompt)` takes an
  already-resolved member list + prompt and doesn't care where they came from.
  `build_artifact(pack_id, mem, kind="pack")` is a thin wrapper that resolves `pack_id` via
  `pack.find_pack` and delegates. This matters because static, hand-authored `.pack.md` files won't be
  the only way to group projects once the brain is well past 21 repos — a future ad-hoc/computed
  grouping (e.g. "everything tagged X") can call `build_pack_artifact` directly, no pack file required.
- **Staleness propagates to the pack header, not just per-member** (another folded-in enhancement):
  `_pack_staleness_note` surfaces the *oldest* member's `Indexed:` date (or "never indexed" if any
  member has no atoms at all) in the pack's own top-line header — `members=N · oldest member indexed:
  <date>` — so a stale pack is visible at a glance instead of requiring a scan of every member's own
  Identity section.
- **Pack membership is capped the same way Interfaces is** (`_MAX_PACK_MEMBERS = 20`, same truncate-
  and-say-so idiom as Unit 1's `_MAX_INTERFACE_BULLETS`) — today's two real packs have 4 members each;
  this only bites once packs, like the portfolio itself, grow well past MVP size.

### Unit 3 — `brain` CLI  ·  extend `project_memory/cli.py`
- `brain load <name>` — `<name>` is a project (dimension/batch) **or** a pack id → prints the artifact.
  **As shipped:** `<name>` is looked up against `known_projects()` first (the common case); if that
  misses, `pack.find_pack(name)` is tried before erroring — a project batch name always wins if a
  project and a pack somehow shared an id.
- **Added while building, not in the original sketch — every load is recorded as provenance:** each
  successful `brain load` (`--current` or explicit) writes a `kind="brain_load"` episode
  (`tags=[name, kind, trigger]`), via a new `--trigger` flag (default `"cli"`; the SessionStart hook
  passes the hook's own `source` field — `startup`/`clear`/…). This **replaces** the Cut 3 sketch of a
  bespoke `brain-loads.log` jsonl file: the episode table is already an append-only log, so provenance
  rides the existing `remember`/`recall`/`recent` surface instead of inventing a second one — `mem.recent
  (kind="brain_load")` *is* the provenance log. `batch` is deliberately left unset on these episodes (a
  pack id is not an indexed project; setting it would corrupt `known_projects()`).
- `brain load --current` — detect the cwd repo. **As shipped:** checks the cwd's basename, then walks
  up each parent directory's basename against `known_projects()`, so a session opened *below* a repo's
  root (e.g. `declared_core/src/`) still resolves — not just the exact root. Degrades gracefully to a
  "no known project here" note (exit 0, never an error) when no ancestor matches.
- `brain menu` — interactive picker listing **projects + packs**; select → print the artifact.
  ✅ **Shipped 2026-07-11** — `pack.list_packs` (id/name pairs, resolved through `find_pack` so a
  listed pack is guaranteed loadable by the id it's listed under) + `cli.cmd_brain_menu`. Prints a
  numbered `Projects:` / `Packs:` listing, then `input()`s a selection — a typed number **or** an
  exact name, either resolves. **`--select`** (a number or name) skips the prompt entirely — the
  scriptable/testable path, and what a caller building its own picker UI would use instead of the raw
  `input()` loop. `--json` without `--select` dumps the raw item list (no prompt); with `--select`, the
  chosen artifact as JSON. Selecting records the same `kind="brain_load"` provenance episode `brain
  load` does, tagged `trigger="menu"`.
- Output: the artifact markdown to stdout (so a hook or a human can capture it).
- **Added while building, not in the original sketch — `brain reindex <name>`:** refreshes one
  project's atoms/milestone in place against the existing db (`name` must be in `PORTFOLIO_SCOPE`).
  Exists because the crash described above meant there was previously *no* safe way to refresh a
  single project without deleting and rebuilding the entire `portfolio.db` — a real gap once the store
  is meant to grow far past 21 repos and get refreshed incrementally, not rebuilt from scratch each
  time. Note: it re-verifies the *whole* edge manifest as a side effect (`index_portfolio` doesn't
  filter `portfolio-edges.yaml` by scope) — harmless, just not narrowly scoped to one project's edges.
  **Known residual gap, deliberately not solved here:** interface atoms have no supersession
  mechanism (unlike facts) — a symbol renamed or removed from a repo's Public API section leaves its
  old atom row behind forever after a reindex, since the atom's id is content-derived (old content →
  old id → never revisited). Solving this needs either a `superseded` concept for episodes (a schema
  change) or a `session_id`-scoped "latest reindex run wins" read filter — bigger than this fix, and
  flagged rather than silently worked around.
**Acceptance:** `brain load --current` run from inside a repo dir (or a subdirectory of one) prints
that repo's artifact. ✅ **Shipped 2026-07-11** — 17 tests in `tests/test_cli.py` cover explicit load,
unknown-project exit code, the parent-dir walk, the unknown-cwd note, reindex rejecting a name outside
`PORTFOLIO_SCOPE`, reindex actually updating a changed summary end-to-end, resolving a pack id, and the
provenance episode being recorded with the right tags.

### Unit 4 — SessionStart hook  ·  `scripts/session_start_hook.sh` + Claude Code `settings.json`
- The hook runs `<.venv>/bin/… brain load --current` and returns stdout as `additionalContext`.
- Degrade gracefully: unknown cwd → emit nothing (never break session start).
- **Locked decision (2026-07-11): fire on `startup`/`clear` only, not `resume`.** Claude Code's
  SessionStart hook has three sub-events; the injected artifact becomes part of the same stable,
  front-loaded block Claude Code already places a prompt-cache breakpoint after, so it rides that
  cache for free *as long as it's injected exactly once per session*. Re-injecting on every `resume`
  would duplicate the block mid-transcript — wasted tokens and a broken cache prefix from that point
  on, for no benefit (a resumed session already has the artifact from its `startup`).
**Acceptance:** a new Claude Code session opened in an indexed repo wakes up already carrying that
repo's artifact (verify: ask "what is this project?" answered from the artifact, no repo scan).

### Unit 5 — The tested selection→injection binding  ·  `tests/test_pack_binding.py`  *(non-negotiable)*
- `build_artifact("aisle", mem, kind="pack")` contains **exactly** aisle's declared members + its
  prompt, and **none** of another pack's members.
- Changing a pack's `members:` changes the artifact's membership deterministically.
**Acceptance:** the assertion above is green. This is the V1.1 lesson made load-bearing.
✅ **Shipped 2026-07-11** — 4 tests in `tests/test_pack_binding.py`: two sibling packs sharing one
member each never leak the other's exclusive member; rewriting a pack's `members:` changes the next
`build_artifact` call's membership deterministically; the two *real* shipped packs (`aisle`,
`verbalogix`) are asserted to share zero members.

---

## 5. Build order — three shippable cuts

- **Cut 1 — the core (awareness):** Unit 1 + `brain load <project>` + `--current` (Unit 3, projects
  only) + the SessionStart hook (Unit 4). → *wake up aware + load any project on demand.* Kills
  re-scout for single projects. **This is the MVP's heart; ship it first.**
- **Cut 2 — packs:** Unit 2 + `build_artifact(pack)` + **two real Ubuntu-indexed packs** —
  `aisle` (above) and `verbalogix-suite` (ctx-architecture + codebase-memorizer + vouch + verbalogix) —
  + the binding test (Unit 5). **Folded in while building** (four enhancements, confirmed against the
  north-star growth vision, not in the original sketch): the pack-composition primitive decoupled from
  `.pack.md` files (`build_pack_artifact`), staleness propagated to the pack header, pack membership
  capped like Interfaces is, and **provenance via the episode log** (`kind="brain_load"`) — which
  absorbs the Cut 3 provenance-log item below into Cut 2, since it turned out to be a few lines on the
  existing `remember()` path, not a new log format.
- **Cut 3 — ergonomics:** `brain menu` interactive picker (Unit 3). *(The provenance log originally
  scoped here shipped early, folded into Cut 2 — see above.)* ✅ **Shipped 2026-07-11.**

**First command to run right now** (proves the thesis on today's store):
```bash
/root/projects/project_memory/.venv/bin/python -c \
"from project_memory import ProjectMemory; from project_memory.portfolio import PORTFOLIO_SCHEMA; \
 from project_memory.artifact import build_artifact; \
 mem = ProjectMemory.open('portfolio.db', PORTFOLIO_SCHEMA); \
 print(build_artifact('declared_core', mem))"
```
If that block reads like something you'd happily paste into any agent to make it instantly aware of
`declared_core` — the MVP thesis is proven, and everything else is scale.

---

## 6. Explicitly OUT of the MVP (post-MVP, already specced in the SoT)

Dense embeddings (`dense.py` http_embedder — Sunday/GPU) · the 3-tab TUI (Browse/Graph/Dashboard) ·
multi-hop interactive graph-walk · multi-provider export adapters (Codex/Gemini/Antigravity) ·
auto-capture session log · curated session-log + `~/.claude .../memory/*.md` ingest ·
**termux reach** — so the `aria-app-builder` pack (voice-graph-rag + gemini-KG-RAG-coding-expert +
nlke-declarum-model-01 + jewelry-current) is the **first fast-follow after termux ingest**, not MVP.
MVP packs are Ubuntu-indexed only, so they work on `portfolio.db` as it stands today.

---

## 7. Definition of done (MVP)

1. `build_artifact` emits the four-section portable block for any indexed project.
   ✅ **shipped 2026-07-11** — `project_memory/artifact.py`, 15 tests in `tests/test_artifact.py`.
2. A pack loads exactly its declared members + prompt (Unit 5 green).
   ✅ **shipped 2026-07-11** — `project_memory/pack.py` + `build_pack_artifact`, 4 tests in
   `tests/test_pack_binding.py` (plus 30 more across `tests/test_pack.py` and `tests/test_artifact.py`
   covering the loader and composition).
3. `brain load --current` + the SessionStart hook make a fresh Claude session wake up aware.
   ✅ **shipped 2026-07-11** — `brain load`/`--current`/`reindex` (17 tests, `tests/test_cli.py`) +
   the hook (`scripts/session_start_hook.{sh,py}`, 6 tests, `tests/test_session_start_hook.py`) +
   `~/.claude/settings.json` wired for `startup`/`clear`. **Live end-to-end proof obtained 2026-07-11**
   — a real, fresh Claude Code session opened in `~/projects/declared_core` answered a cross-repo
   dependency question purely from the injected artifact, zero repo-scanning tool calls.
4. Two real Ubuntu packs (`aisle`, `verbalogix-suite`) load cleanly.
   ✅ **shipped 2026-07-11** — `project_memory/packs/{aisle,verbalogix-suite}.pack.md`; membership
   verified disjoint (Unit 5).
5. Honest docs: what's MVP (this) vs fast-follow (session log, termux) vs Sunday (dense) vs later (TUI, adapters).
   ✅ **shipped 2026-07-11** — `README.md` (a new section covering the artifact/pack/`brain`/hook/
   graph-walk layer, with a runnable example and an explicit "not in this layer yet" list, test badge
   corrected to 219), `CHANGELOG.md` (the [Unreleased] section expanded to actually cover Cuts 1–3 and
   M1 — it had silently stopped at the original `portfolio.py` indexing work despite everything built
   since), and `ROADMAP.md` (a condensed MVP/fast-follow/Sunday/later split pointing at the two spec
   docs for detail, plus the stale "graph-shaped ask" bullet corrected now that M1's `graph.walk`
   partially — not fully — addresses it).
6. Attribution Eyal Nof only, no co-author trailer. Not pushed. ✅ holding.

**Cut 1 status (2026-07-11): built and verified end-to-end.** Unit 1, Unit 3's project-only slice
(plus `--current`'s parent-dir walk and `brain reindex`, both additions found necessary while
building — see §3's rerun-crash fix), and Unit 4's hook are all in place, tested, and confirmed live
in a real fresh Claude Code session.

**Cut 2 status (2026-07-11): built, then dogfooded and corrected.** Unit 2 (pack file format + loader
+ `build_pack_artifact` composition) and Unit 5 (the binding test) are in place, plus all four
folded-in enhancements (decoupled composition primitive, pack-header staleness, member cap,
episode-log provenance — see §5). Both real MVP packs (`aisle`, `verbalogix-suite`) load cleanly
against `portfolio.db` as it stands today. Manually testing Cut 1+2 in live sessions across three
different repos (`vouch`, `kg_toolkit`) turned up one real naming bug (the `verbalogix`/pack-id
collision, fixed) and one real wording issue (the injected artifact reading as an untrusted command
+ ecosystem jargon in an unrelated repo — fixed, see Unit 1's revision note); a second dogfood round
confirmed both fixes hold and the pack-loading + honest-degrade behavior work as designed. 187 tests
passing at the end of this round.

**Cut 3 status (2026-07-11): built.** `pack.list_packs` + `cli.cmd_brain_menu` — a numbered
`Projects:`/`Packs:` listing, select by typed number or name (interactive `input()`, or `--select` to
skip it), printing the chosen artifact and recording the same `brain_load` provenance episode `brain
load` does (`trigger="menu"`). This was the only item left in Cut 3 (the provenance log moved into
Cut 2 — see §5). 200 tests passing (up from 187).

**MVP status (2026-07-11): all six Definition-of-done items shipped.** The honest-docs pass
(#5) landed after M1 — README/CHANGELOG/ROADMAP now actually describe the artifact/pack/`brain`/
hook/graph-walk layer built across Cuts 1–3 and M1, which CHANGELOG in particular had silently
never documented. The MVP itself is done; work continues on the v1.0 ladder
(`MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`), M1 already shipped, M2 next per the recommended order.
