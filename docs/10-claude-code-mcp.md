# 10 · Claude Code + MCP

`project_memory` ships a minimal, stdlib-only MCP server
(`examples/mcp_server.py`) that puts a project's memory in front of an agent like
Claude Code. It speaks JSON-RPC 2.0 over stdio (MCP protocol `2024-11-05`) and
needs no dependencies beyond `project_memory` itself.

## Register it

```bash
claude mcp add project-memory -- python "$(pwd)/examples/mcp_server.py"
```

By default it serves the packaged **demo** memory, so it works the moment it's
registered. Point it at your own memory and options with environment variables:

| env var | meaning |
|---|---|
| `PMEM_DB` | path to a memory built with `project-memory remember` (absolute) |
| `PMEM_PRESET` | `generic` \| `agent` \| `research` |
| `PMEM_DENSE_URL` | OpenAI-style `/v1/embeddings` URL for optional dense recall |

```bash
claude mcp add project-memory \
  -e PMEM_DB=/abs/path/memory.db -e PMEM_PRESET=agent \
  -- python "$(pwd)/examples/mcp_server.py"
```

## Tools exposed

| tool | does |
|---|---|
| `memory_recall` | search memory (episodes + facts): `{query, limit?}` |
| `memory_ask` | answer a question → `AnswerShape`: `{question, name?}` |
| `memory_synthesize` | MUD-check merging two facts: `{fact_a, fact_b}` |
| `memory_remember` | append an episode: `{content, kind?, auto_fact?, reason?}` |
| `memory_recent` | recent episodes: `{limit?}` |

Each returns JSON text content. `memory_recall` hits are slimmed to
`{table, id, text, kind, score, sources}`.

## Using it in a session

Once registered, ask Claude Code things like:

- *"Use `memory_ask` to recall why we chose SQLite over Postgres."*
- *"Before you write that down, use `memory_synthesize` to check it against the
  security note — is it clean or MUD?"*
- *"Use `memory_remember` to record this decision with kind=decision."*

The `memory_synthesize` tool is the distinctive one: it lets the agent check
whether a new conclusion is *compatible* with what's already known, and refuse to
record a muddy synthesis — an epistemic guardrail the model can't talk itself past.

## Verifying the server by hand

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 | python examples/mcp_server.py
```

You should see an `initialize` result naming `project-memory`, then the five tools.

## Protocol notes

- Methods handled: `initialize`, `tools/list`, `tools/call`, `ping`.
- `notifications/*` receive no response (per spec).
- Errors are returned as JSON-RPC error objects — the server never crashes the
  pipe on a bad request.

## A second server: the Portfolio Brain (`examples/mcp_portfolio_server.py`, M6)

The server above fronts *one project's* memory. `project_memory` also has an
internal capability — the **Portfolio Brain** (`project_memory.portfolio`) — a
cross-repo store behind `brain load`/`menu`/`reindex`. `examples/mcp_portfolio_server.py`
fronts *that* store, over the same stdlib JSON-RPC transport, but with a wider
MCP surface: resources, a prompt, and one tool — not just tools.

```bash
claude mcp add project-memory-portfolio -- python "$(pwd)/examples/mcp_portfolio_server.py"
```

It opens `PMEM_BRAIN_DB` (same resolution as the CLI's `brain` commands: env
var, else `<repo>/portfolio.db`).

| surface | name | does |
|---|---|---|
| resource | `portfolio://project/<name>` | read → that project's `build_artifact` snapshot |
| resource | `portfolio://pack/<id>` | read → that pack's `build_pack_artifact` snapshot |
| prompt | `load_context` | `{scope, kind?}` → the artifact as a conversation-turn message |
| tool | `brain_reindex` | `{name?, root?}` → idempotent refresh, `IndexReport` as JSON |

**Why this exists:** the SessionStart hook injects one project's artifact once,
at the start of a session — the only "wake up" moment before this. If mid-session
the agent realizes it needs *another* project's or a pack's context (e.g. it
hits an edge naming a repo it hasn't loaded), it previously had no way to pull
that in without restarting the session. The `portfolio://` resources and the
`load_context` prompt are exactly that on-demand pull — this is the "mid-session
recall" gap `ROADMAP.md` had flagged as not-yet-built.

`brain_reindex` is deliberately **idempotent, never destructive**: unlike
`scripts/index_portfolio.py --fresh` (the default there — delete and rebuild),
this tool only ever calls `index_portfolio` in place. `remember`/`record_fact`
are `INSERT OR IGNORE`, so re-running it live, mid-session, on an already-indexed
repo is a safe no-op; a changed README picks up a new milestone row instead of
crashing on a stale id.

Verify it by hand the same way as the core server:

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"resources/list"}' \
 | python examples/mcp_portfolio_server.py
```

## File-based export: `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` (`brain export`, M6)

The MCP server above is an *on-demand pull* — it needs an MCP client. Codex and
Google Antigravity don't speak MCP resources the way Claude Code does; the way
they actually pick up standing context is a file in the repo root, read at
session start. `project-memory brain export` writes the same
`build_artifact` snapshot into that file, closing M6's other half: **one
store → verified injection in Claude, Codex, and Gemini from a single
artifact.**

```bash
project-memory brain export declared_core --provider claude    # -> CLAUDE.md
project-memory brain export declared_core --provider codex     # -> AGENTS.md
project-memory brain export declared_core --provider gemini    # -> GEMINI.md
project-memory brain export declared_core --provider all       # -> all three
project-memory brain export declared_core --provider claude --dry-run  # preview, no write
```

Researched, not assumed: Google Antigravity's own docs say it reads
`AGENTS.md` as its standing-instructions file — the **same convention Codex
uses**, not a fourth file. So `--provider antigravity` and `--provider codex`
both target `AGENTS.md`; `--provider all` writes exactly three files
(`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`), not four. `write_provider_file`
(`export/files.py`) writing `codex` and `antigravity` into two directories
produces byte-identical `AGENTS.md` content — asserted by
`test_export_files.py`, not just claimed.

**Idempotent, marker-delimited, never destructive** — the same discipline as
`brain_reindex`. Each write wraps the artifact in
`<!-- project_memory:begin/end -->` markers (`export/files.py::apply_block`):
a rerun replaces only that span, leaving any hand-written instructions
elsewhere in the same `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` untouched. Writing
into a real project's own context file is higher-stakes than the portfolio
db writes `brain_reindex` does — a full-file overwrite could destroy a
developer's own hand-authored rules, so this was a hard requirement, not a
nicety.

By default the target directory is the project's own resolved location
(`RepoSpec.path` if declared, else `--root/<name>`, same resolution
`brain reindex` uses) — pass `--into <dir>` to write somewhere else instead
(e.g. a scratch directory, for previewing before touching a real repo).
Packs are out of scope: unlike a project, a pack has no single directory to
write into — `brain load <pack>` / the MCP `portfolio://pack/<id>` resource
are still the way to pull a pack's artifact.

Verify it by hand:

```bash
mkdir -p /tmp/export-preview
project-memory brain export declared_core --provider all --into /tmp/export-preview --dry-run
project-memory brain export declared_core --provider all --into /tmp/export-preview
cat /tmp/export-preview/CLAUDE.md
```

## Provenance: what was loaded, and was it used? (`brain journey`/`unused`, M4)

Every injection above leaves a trace. `brain load` (and the `SessionStart` hook,
and `brain menu`/`export`) records each load as a `kind="brain_load"` episode in
the store itself — *not* a side-file — so the brain remembers its own use.
M4 turns that log into two reports plus a marker:

- **`brain used <scope>`** marks a load as actually used — one append-only
  `brain_use` episode (the `used`/`unused` marker). It refuses a scope that was
  never loaded: a "used" marker only means something for context that was pulled.
- **`brain journey [--session <id>]`** reconstructs a session's ordered
  load/use/export events as a readable story.
- **`brain unused [--packs] [--session <id>]`** reports loads that were never
  marked used — `--packs` answers "which packs did I load and never use?"

Sessions ride the episodes' existing `session_id` column — the `SessionStart`
hook passes Claude Code's own `session_id` through `brain load --session`, so a
whole session's loads group together. Pre-M4 loads (no session) fold into the
all-sessions view.

**Declared, not inferred:** a load is only "used" when you (or the agent) say so
with `brain used`. The system never guesses use from later activity — that would
fabricate a signal the log doesn't carry.

```bash
S=$(uuidgen)                                             # or Claude Code's own session id
project-memory brain load declared_core --session "$S" --trigger startup
project-memory brain used declared_core --session "$S" --note "read its retrieval-math API"
project-memory brain journey --session "$S"             # the story
project-memory brain unused --packs                      # packs loaded but never used (all sessions)
```

The reports are read-only — safe to run against the live `portfolio.db`. Only
`brain used` writes (one benign, append-only marker episode).
