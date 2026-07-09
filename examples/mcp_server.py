"""Example — expose project_memory as an MCP server (stdlib only).

A minimal JSON-RPC 2.0 stdio server (MCP protocol 2024-11-05) that puts a
project's memory in front of an agent like Claude Code. By default it serves the
packaged demo memory so it runs out of the box. Point it at your own memory with
env vars:

    PMEM_DB=/abs/path/memory.db     # a memory you built with `project-memory remember`
    PMEM_PRESET=generic|agent|research
    PMEM_DENSE_URL=http://127.0.0.1:8140/v1/embeddings   # optional dense recall

Register it:
    claude mcp add project-memory -- python /abs/path/to/examples/mcp_server.py

Then, in a session:
    "Use memory_ask to recall why we chose SQLite."
    "Use memory_synthesize to check if these two facts can be merged cleanly."
"""

import json
import os
import sys

from project_memory import ProjectMemory, build_demo, http_embedder
from project_memory.presets import PRESETS


def _open() -> ProjectMemory:
    db = os.environ.get("PMEM_DB")
    embedder = http_embedder(os.environ["PMEM_DENSE_URL"]) if os.environ.get("PMEM_DENSE_URL") else None
    if not db:
        return build_demo(embedder=embedder)
    schema = PRESETS.get(os.environ.get("PMEM_PRESET", "generic"), PRESETS["generic"])
    return ProjectMemory.open(db, schema, embedder=embedder)


MEM = _open()

TOOLS = [
    {
        "name": "memory_recall",
        "description": "Search project memory (episodes + facts) — BM25 + structural + intent fusion.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 5}},
            "required": ["query"],
        },
    },
    {
        "name": "memory_ask",
        "description": "Answer a question from memory: routes to an ask, returns answer + cited evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "name": {"type": "string", "description": "optional: force a specific ask"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "memory_synthesize",
        "description": "MUD-check merging two facts: returns clean/bridge/refuse + calibrated confidence + reason.",
        "inputSchema": {
            "type": "object",
            "properties": {"fact_a": {"type": "string"}, "fact_b": {"type": "string"}},
            "required": ["fact_a", "fact_b"],
        },
    },
    {
        "name": "memory_remember",
        "description": "Append an episode to memory (optionally crystallizing it as a durable fact).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "kind": {"type": "string", "default": "general"},
                "auto_fact": {"type": "boolean", "default": False},
                "reason": {"type": "string"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_recent",
        "description": "The most recent episodes, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
]


def _slim(hit: dict) -> dict:
    return {
        "table": hit.get("table"),
        "id": hit.get("id"),
        "text": hit.get("content") or hit.get("claim"),
        "kind": hit.get("kind") or hit.get("status"),
        "score": round(hit.get("rrf_score", hit.get("weighted_score", 0.0)), 4),
        "sources": hit.get("rrf_sources", []),
    }


def _call(name, args):
    if name == "memory_recall":
        hits = MEM.recall(args["query"], limit=args.get("limit", 5))
        return {"count": len(hits), "hits": [_slim(h) for h in hits]}
    if name == "memory_ask":
        return MEM.ask(args["question"], name=args.get("name")).to_dict()
    if name == "memory_synthesize":
        return MEM.synthesize(args["fact_a"], args["fact_b"]).to_dict()
    if name == "memory_remember":
        return MEM.remember(args["content"], kind=args.get("kind", "general"),
                            auto_fact=args.get("auto_fact", False), reason=args.get("reason"))
    if name == "memory_recent":
        return {"episodes": MEM.recent(limit=args.get("limit", 10))}
    raise ValueError(f"unknown tool: {name}")


def _handle(req):
    method = req.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "project-memory", "version": "0.1.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = req.get("params", {})
        result = _call(params["name"], params.get("arguments", {}))
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
