"""project_memory.export — provider-agnostic export adapters (M6).

The neutral `build_artifact`/`build_pack_artifact` payload
(`project_memory.artifact`) is provider-neutral by construction; this package
holds the thin adapters that put it in front of a specific tool. Shipped:
`mcp_portfolio` — MCP resources/prompts/tools for the Portfolio Brain — and
`files` — idempotent `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` block injection for
Claude Code/Codex/Antigravity/Gemini CLI (see `MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md`'s M6).

Like `project_memory.portfolio`/`artifact`/`pack`/`graph`, this is Portfolio
Brain internal capability — not part of the core library's public surface
(`project_memory.__all__`), and it needs the `portfolio` extra.
"""

from __future__ import annotations

from .files import (
    ALL_FILENAMES,
    PROVIDER_FILES,
    apply_block,
    render_block,
    write_all_provider_files,
    write_provider_file,
)
from .mcp_portfolio import (
    call_tool,
    get_prompt,
    list_prompts,
    list_resources,
    list_tools,
    open_brain,
    read_resource,
)

__all__ = [
    "list_resources",
    "read_resource",
    "list_prompts",
    "get_prompt",
    "list_tools",
    "call_tool",
    "open_brain",
    "PROVIDER_FILES",
    "ALL_FILENAMES",
    "render_block",
    "apply_block",
    "write_provider_file",
    "write_all_provider_files",
]
