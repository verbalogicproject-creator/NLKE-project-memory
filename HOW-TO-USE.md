# How to use project_memory

A task-oriented tour. For the *why*, read [`docs/00-mental-model.md`](docs/00-mental-model.md);
for exhaustive references, [`docs/08-api-reference.md`](docs/08-api-reference.md)
and [`docs/09-cli-reference.md`](docs/09-cli-reference.md).

## Install

`project_memory` installs standalone — the `declared_core` engine is vendored in-repo.

```bash
pip install -e .            # project_memory  (add [dense] for numpy dense recall)
```

## Open a memory

```python
from project_memory import ProjectMemory

mem = ProjectMemory.open("memory.db")     # a file; or .open() for in-memory
```

## Remember events, record facts

```python
# An episode is something that happened.
mem.remember("We chose SQLite over Postgres.", kind="decision",
             tags=["storage"], auto_fact=True, reason="local-first, zero-ops")

# A fact is a durable claim. Update one by superseding it — history is kept.
old = mem.record_fact("Search is best-effort.", id="f-search")
mem.record_fact("Search runs fully offline via FTS5.", supersedes="f-search")
```

`kind` must be in your schema's taxonomy (`DEFAULT_KINDS` by default) or the write
raises. Declare your own: `ProjectMemory.open(schema=MemorySchema(kinds=(...)))`.

## Recall

```python
mem.recall("database choice")                 # ranked episodes + facts
mem.recall("offline", table="facts")          # only facts
mem.recall("sqlite", limit=5, verbose=True)   # keep per-dimension scores
```

Each hit carries provenance: `rrf_sources` (which signals found it), a fused
score, and `dense_score` if the optional dense signal ran.

## Ask questions

```python
mem.ask("why not Postgres?")                  # routed by intent
mem.ask("can I search offline?", name="can_i")  # force a specific ask
mem.asks()                                    # the eleven ask names
```

Every ask returns an `AnswerShape`: `answer`, `confidence`, `evidence`, `caveats`,
`suggested_next`. See [`docs/04-asks.md`](docs/04-asks.md).

## Guard a synthesis

```python
r = mem.synthesize(
    "From a security perspective, plaintext tokens are unacceptable.",
    "From a business perspective, plaintext tokens were cheap and worked.")
r.verdict        # 'refuse'  (opposing perspectives — Layer 3)
r.confidence     # 0.0
r.mud_reason     # 'Layer 3 — lighting/perspective conflict (compat=0.40)'
```

`verdict` is `clean` / `bridge` / `refuse`; `confidence` is calibrated (never above
the lower input certainty). See [`docs/06-synthesis-mud.md`](docs/06-synthesis-mud.md).

## From the command line

```bash
project-memory remember "we chose SQLite" --kind decision --auto-fact --reason "..."
project-memory recall "storage" --json
project-memory ask "why not Postgres?"
project-memory synthesize "A ..." "B ..." --json
project-memory recent --limit 5
```

Writes go to `--db` (default `./project-memory.db`, or `PMEM_DB`). Every subcommand
takes `--json`. See [`docs/09-cli-reference.md`](docs/09-cli-reference.md).

## From Claude Code (MCP)

```bash
claude mcp add project-memory -- python "$(pwd)/examples/mcp_server.py"
```

Then: *"Use memory_ask to recall why we chose SQLite."* See
[`docs/10-claude-code-mcp.md`](docs/10-claude-code-mcp.md).

## Optional: semantic recall

```python
from project_memory import ProjectMemory, http_embedder
mem = ProjectMemory.open("memory.db", embedder=http_embedder("http://127.0.0.1:8140/v1/embeddings"))
```

With no embedder, recall is pure lexical and deterministic. A dead embedder
changes nothing. See [`docs/07-optional-dense.md`](docs/07-optional-dense.md).
