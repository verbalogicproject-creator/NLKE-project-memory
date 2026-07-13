"""Example — expose the Portfolio Brain as a second MCP server (stdlib only).

Distinct from `examples/mcp_server.py` (which fronts the *core* per-project
episode/fact memory). This one fronts `project_memory.portfolio` — the
cross-repo store behind `brain load`/`menu`/`reindex` — as MCP **resources**
(one per known project/pack; reading pulls that scope's context artifact), a
**prompt** (`load_context`, to insert an artifact as a conversation turn
mid-session — closing the "mid-session recall" gap noted in ROADMAP.md), and
**one tool** (`brain_reindex`, idempotent — never deletes the store).

Point it at your own portfolio db with an env var (defaults to
``<repo>/portfolio.db``, same resolution as the CLI's `brain` commands):

    PMEM_BRAIN_DB=/abs/path/portfolio.db python examples/mcp_portfolio_server.py

Register it:
    claude mcp add project-memory-portfolio -- python /abs/path/to/examples/mcp_portfolio_server.py

Then, in a session:
    "List the portfolio resources and read the one for project_memory."
    "Use the load_context prompt with scope=aria-app-builder, kind=pack."
    "Call brain_reindex with name=project_memory to refresh its own atoms."
"""

import json
import sys

from project_memory.export.mcp_portfolio import (
    call_tool,
    get_prompt,
    list_prompts,
    list_resources,
    list_tools,
    open_brain,
    read_resource,
)

MEM = open_brain()


def _handle(req):
    method = req.get("method")
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"resources": {}, "prompts": {}, "tools": {}},
            "serverInfo": {"name": "project-memory-portfolio", "version": "0.1.0"},
        }
    if method == "resources/list":
        return {"resources": list_resources(MEM)}
    if method == "resources/read":
        uri = req["params"]["uri"]
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": read_resource(MEM, uri)}]}
    if method == "prompts/list":
        return {"prompts": list_prompts()}
    if method == "prompts/get":
        params = req.get("params", {})
        return get_prompt(MEM, params["name"], params.get("arguments", {}))
    if method == "tools/list":
        return {"tools": list_tools()}
    if method == "tools/call":
        params = req.get("params", {})
        result = call_tool(MEM, params["name"], params.get("arguments", {}))
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    if method == "ping":
        return {}
    raise ValueError(f"unknown method: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        if req.get("method", "").startswith("notifications/"):
            continue  # notifications get no response
        try:
            result = _handle(req)
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
        except Exception as e:  # noqa: BLE001 — report as JSON-RPC error, never crash
            resp = {"jsonrpc": "2.0", "id": req.get("id"),
                    "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
