"""project_memory.export.mcp_portfolio — the Portfolio Brain's MCP breadth (M6).

Distinct from `examples/mcp_server.py` (which fronts the *core* per-project
episode/fact memory — ask/recall/synthesize/remember/recent). This module
fronts the *Portfolio Brain* (`project_memory.portfolio`): the cross-repo store
behind `brain load`/`menu`/`reindex`. It closes the "mid-session recall" gap
noted in ROADMAP.md — today the only "wake up" moment is the SessionStart
hook, which injects one project's artifact once, up front; an MCP client can
pull another project's or pack's artifact any time via these resources/
prompts, without restarting the session.

Three surfaces, matching the MCP breadth the M6 spec calls out ("match
game-engine pgm"):
  - **Resources** — one per known project (`portfolio://project/<name>`) and
    per declared pack (`portfolio://pack/<id>`); reading one returns that
    scope's `build_artifact`/`build_pack_artifact` snapshot, verbatim (the
    same text `brain load` prints).
  - **Prompts** — `load_context(scope, kind?)`, so a client can insert a
    project's/pack's artifact as a conversation turn instead of only ever
    reading it as an opaque resource blob.
  - **Tools** — `brain_reindex(name?, root?)`: idempotent (never deletes or
    rebuilds the store — `remember`/`record_fact` are `INSERT OR IGNORE`), so
    an agent can safely call it mid-session. Omit `name` for the whole
    `PORTFOLIO_SCOPE`; pass one repo name to refresh just that repo (mirrors
    the CLI's `brain reindex <name>`).

Pure functions over an already-open `ProjectMemory` — no stdio/JSON-RPC here;
`examples/mcp_portfolio_server.py` is the thin transport wrapper.

Like `portfolio.py`/`artifact.py`/`pack.py`/`graph.py`, this is Portfolio Brain
internal capability: not part of the core library's public surface
(`project_memory.__all__`), and it needs the `portfolio` extra.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .. import ProjectMemory
from ..artifact import build_artifact
from ..graph import known_projects
from ..pack import list_packs
from ..portfolio import DEFAULT_PROJECTS_ROOT, PORTFOLIO_SCHEMA, PORTFOLIO_SCOPE, RepoSpec, index_portfolio

_SCHEME = "portfolio"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EDGES_PATH = _REPO_ROOT / "portfolio-edges.yaml"
DEFAULT_BRAIN_DB = _REPO_ROOT / "portfolio.db"


def open_brain(db: "str | Path | None" = None) -> ProjectMemory:
    """Open the portfolio brain db — same resolution as the CLI's `brain`
    commands: ``db`` arg, else ``PMEM_BRAIN_DB``, else ``<repo>/portfolio.db``."""
    resolved = str(db) if db else os.environ.get("PMEM_BRAIN_DB") or str(DEFAULT_BRAIN_DB)
    return ProjectMemory.open(resolved, PORTFOLIO_SCHEMA)


# ── resources ─────────────────────────────────────────────────────────────

def list_resources(mem: ProjectMemory) -> "list[dict[str, Any]]":
    """One resource per known project + per declared pack."""
    resources = [
        {
            "uri": f"{_SCHEME}://project/{name}",
            "name": name,
            "description": f"Context artifact for project '{name}' (build_artifact, hops=1).",
            "mimeType": "text/markdown",
        }
        for name in sorted(known_projects(mem))
    ]
    resources.extend(
        {
            "uri": f"{_SCHEME}://pack/{pack['id']}",
            "name": pack["name"],
            "description": f"Context artifact for pack '{pack['id']}' (build_pack_artifact).",
            "mimeType": "text/markdown",
        }
        for pack in list_packs()
    )
    return resources


def _parse_uri(uri: str) -> "tuple[str, str]":
    prefix = f"{_SCHEME}://"
    if not uri.startswith(prefix):
        raise ValueError(f"unknown resource URI scheme: {uri!r} (expected {prefix!r}...)")
    kind, _, scope = uri[len(prefix):].partition("/")
    if kind not in ("project", "pack") or not scope:
        raise ValueError(f"malformed resource URI: {uri!r} (expected '{prefix}project|pack/<name>')")
    return kind, scope


def read_resource(mem: ProjectMemory, uri: str) -> str:
    """Read one resource — the same text `brain load` prints for that scope."""
    kind, scope = _parse_uri(uri)
    return build_artifact(scope, mem, kind="pack" if kind == "pack" else "project")


# ── prompts ───────────────────────────────────────────────────────────────

_LOAD_CONTEXT = "load_context"


def list_prompts() -> "list[dict[str, Any]]":
    return [
        {
            "name": _LOAD_CONTEXT,
            "description": "Pull a project's or pack's context artifact as a conversation turn.",
            "arguments": [
                {"name": "scope", "description": "project name or pack id", "required": True},
                {"name": "kind", "description": "'project' (default) or 'pack'", "required": False},
            ],
        }
    ]


def get_prompt(mem: ProjectMemory, name: str, args: "dict[str, Any]") -> "dict[str, Any]":
    if name != _LOAD_CONTEXT:
        raise ValueError(f"unknown prompt: {name!r}")
    scope = args.get("scope")
    if not scope:
        raise ValueError("load_context needs a 'scope' argument")
    kind = args.get("kind", "project")
    artifact = build_artifact(scope, mem, kind=kind)
    return {
        "description": f"Context artifact for {kind} '{scope}'",
        "messages": [{"role": "user", "content": {"type": "text", "text": artifact}}],
    }


# ── tools ─────────────────────────────────────────────────────────────────

_REINDEX_TOOL = "brain_reindex"


def list_tools() -> "list[dict[str, Any]]":
    return [
        {
            "name": _REINDEX_TOOL,
            "description": (
                "Refresh the portfolio brain's atoms/milestones/edges. Idempotent — never "
                "deletes the store, just re-remembers (INSERT OR IGNORE). Omit 'name' to "
                "reindex the whole PORTFOLIO_SCOPE; pass one repo name to refresh just that repo."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "one repo name from PORTFOLIO_SCOPE; omit for all"},
                    "root": {"type": "string", "description": f"~/projects root (default {DEFAULT_PROJECTS_ROOT})"},
                },
            },
        }
    ]


def call_tool(
    mem: ProjectMemory, name: str, args: "dict[str, Any]", *,
    scope: "tuple[RepoSpec, ...]" = PORTFOLIO_SCOPE, edges_path: "Path | None" = DEFAULT_EDGES_PATH,
) -> "dict[str, Any]":
    if name != _REINDEX_TOOL:
        raise ValueError(f"unknown tool: {name!r}")

    root = Path(args["root"]).expanduser() if args.get("root") else DEFAULT_PROJECTS_ROOT
    target_name = args.get("name")
    if target_name:
        spec = next((r for r in scope if r.name == target_name), None)
        if spec is None:
            raise ValueError(f"'{target_name}' is not in PORTFOLIO_SCOPE")
        run_scope: "tuple[RepoSpec, ...]" = (spec,)
    else:
        run_scope = scope

    report = index_portfolio(mem, root=root, edges_path=edges_path, scope=run_scope)
    return report.to_dict()
