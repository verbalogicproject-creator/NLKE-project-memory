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
