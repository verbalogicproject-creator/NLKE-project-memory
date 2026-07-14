# Examples

Runnable, self-verifying scripts. Each ends by printing **`Verify your build: ok`**
— if you see that line, that feature works in your install.

```bash
pip install -e ".[dev]"              # from the repo root (declared_core is vendored)
python examples/01_remember_and_recall.py
```

| File | Shows |
|---|---|
| `01_remember_and_recall.py` | The two write paths (episodes + facts) and hybrid recall. |
| `02_asks.py` | The eleven natural-language asks + intent routing. |
| `03_synthesis_mud.py` | The epistemic guard: clean / bridge / refuse with calibrated confidence. |
| `04_custom_schema.py` | Declaring your own episode taxonomy; presets. |
| `05_dense_optional.py` | The optional dense signal degrading byte-identically to lexical. |
| `mcp_server.py` | Exposing memory to Claude Code over MCP (stdlib JSON-RPC 2.0). |

## MCP quickstart

```bash
claude mcp add project-memory -- python "$(pwd)/mcp_server.py"
```

By default it serves the packaged demo memory. Point it at your own with
`PMEM_DB=/abs/path/memory.db` (and `PMEM_PRESET`, `PMEM_DENSE_URL`). See
[`../docs/10-claude-code-mcp.md`](../docs/10-claude-code-mcp.md).
