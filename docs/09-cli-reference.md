# 09 · CLI reference

The `project-memory` command wraps `ProjectMemory`. Every subcommand accepts
`--json` for scripting. Installed by `pip install -e .` (console script in
`pyproject.toml`).

```
project-memory <command> [args] [--json]
project-memory --version
```

## Shared options

Write/read commands (`remember`, `record`, `recall`, `ask`, `synthesize`, `recent`)
also accept:

| option | default | meaning |
|---|---|---|
| `--db PATH` | `PMEM_DB` env, else `./project-memory.db` | the SQLite memory file |
| `--preset {generic,agent,research}` | `generic` | episode taxonomy |
| `--dense-url URL` | — | OpenAI-style `/v1/embeddings` endpoint (optional booster) |
| `--json` | off | emit JSON instead of text |

## Commands

### `demo`
Explore the packaged demo memory (in-memory; no `--db`). Prints counts, a sample
recall, an ask, and a synthesis refusal.

```bash
project-memory demo
project-memory demo --json
```

### `remember`
Append an episode.

```bash
project-memory remember "we chose SQLite" --kind decision \
  --tag storage --auto-fact --reason "local-first, zero-ops"
```

| option | meaning |
|---|---|
| `content` (positional) | the episode text |
| `--kind` | episode kind (default `general`; must be in the taxonomy) |
| `--tag` | repeatable label |
| `--batch` | grouping label |
| `--auto-fact` | also crystallize a fact |
| `--reason` | the fact's reason (with `--auto-fact`) |

### `record`
Write a durable fact.

```bash
project-memory record "search runs offline" --reason "FTS5 + BM25"
project-memory record "search is offline" --supersedes f-old-id
```

`--reason`, `--tag` (repeatable), `--supersedes FACT_ID`.

### `recall`
Search memory.

```bash
project-memory recall "database choice"
project-memory recall "offline" --table facts --limit 5 --json
```

`--limit N` (default 10), `--table {episodes,facts}`.

### `ask`
Answer a question (routed to an ask).

```bash
project-memory ask "why not Postgres?"
project-memory ask "can I search offline?" --name can_i --json
```

`--name ASK` forces an ask (see `asks`); `--limit N` (default 8). Text output
shows the answer, confidence, up to four evidence lines, and any caveats.

### `synthesize`
MUD-check a merge of two facts.

```bash
project-memory synthesize \
  "From a security perspective, plaintext tokens are unacceptable." \
  "From a business perspective, plaintext tokens were cheap and fine." --json
```

`--persist` writes the outcome to the `synthesis_facts` audit table. Output shows
the verdict, calibrated confidence, per-axis compatibilities, and (if not refused)
the merged statement.

### `recent`
Most recent episodes.

```bash
project-memory recent --limit 5
project-memory recent --kind gotcha --json
```

### `asks` · `kinds` · `dims`
Introspection (no `--db`):

```bash
project-memory asks              # the eleven ask names
project-memory kinds --preset agent   # a preset's episode kinds
project-memory dims              # the 12 dimensions + groups + descriptions
```

## Exit codes

`0` on success; `1` on a user error (e.g. an unknown episode `kind`), with a
message on stderr.

## Environment variables

| var | used by |
|---|---|
| `PMEM_DB` | default `--db` path |
| `PMEM_EMBED_URL` / `PMEM_EMBED_MODEL` / `PMEM_EMBED_QUERY_PREFIX` | `http_embedder` defaults |

Next: [10 · Claude Code + MCP](10-claude-code-mcp.md).
