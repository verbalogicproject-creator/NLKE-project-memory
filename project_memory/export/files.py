"""project_memory.export.files — file-based context injection adapters (M6).

Writes the same neutral `build_artifact` snapshot into the on-disk convention
each agentic coding tool actually reads at session start, as an idempotent,
marker-delimited block: a rerun replaces only that block, never touching a
project's own hand-written instructions elsewhere in the file — the same
non-destructive-by-default discipline `mcp_portfolio.py`'s `brain_reindex`
already established for this layer.

Three underlying files, not four: Codex and Google Antigravity both read
`AGENTS.md` as their standing-instructions convention (verified against each
tool's own docs, not assumed) — so there is no separate "antigravity" file,
only a shared alias for it in `PROVIDER_FILES`.

Like `portfolio.py`/`artifact.py`/`pack.py`/`graph.py`/`mcp_portfolio.py`, this
is Portfolio Brain internal capability — not part of the core library's public
surface (`project_memory.__all__`), and it needs the `portfolio` extra.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..artifact import build_artifact
from ..query import ProjectMemory

_BEGIN = "<!-- project_memory:begin -->"
_END = "<!-- project_memory:end -->"
_BLOCK_RE = re.compile(re.escape(_BEGIN) + r".*?" + re.escape(_END), re.DOTALL)

#: provider name -> the file that tool reads at session start.
PROVIDER_FILES = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "antigravity": "AGENTS.md",  # shares Codex's convention, not its own file
    "gemini": "GEMINI.md",
}

#: distinct on-disk filenames `--provider all` writes, in a fixed order —
#: `codex`/`antigravity` alias to the same file, so this has 3 entries, not 4.
ALL_FILENAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")


def render_block(scope: str, mem: ProjectMemory, *, hops: int = 1, kind: str = "project") -> str:
    """The marker-delimited block for ``scope`` — what gets inserted into a
    provider file. Delegates entirely to `build_artifact`; adds nothing of
    its own besides the markers a rerun uses to find and replace it."""
    body = build_artifact(scope, mem, hops=hops, kind=kind)
    return f"{_BEGIN}\n{body}\n{_END}\n"


def apply_block(existing: str, block: str) -> str:
    """Insert/replace ``block`` in ``existing`` file text.

    If the markers are already present, only that span is replaced — any
    hand-written content before or after it is untouched. Otherwise the block
    is appended (or, for an empty/absent file, becomes the whole content).
    Idempotent: applying the same block twice yields the same result as
    applying it once.
    """
    block = block.strip("\n")
    if _BLOCK_RE.search(existing):
        return _BLOCK_RE.sub(lambda _: block, existing, count=1)
    if not existing.strip():
        return block + "\n"
    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block + "\n"


def _write_block_to(path: Path, block: str) -> Path:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(apply_block(existing, block), encoding="utf-8")
    return path


def write_provider_file(
    provider: str,
    scope: str,
    mem: ProjectMemory,
    target_dir: "str | Path",
    *,
    hops: int = 1,
    kind: str = "project",
) -> Path:
    """Write/update ``scope``'s artifact as a marker-delimited block in
    ``target_dir/<provider's file>``. Creates the file if absent; otherwise
    preserves everything outside the markers. Raises ``ValueError`` for an
    unknown ``provider``."""
    filename = PROVIDER_FILES.get(provider)
    if filename is None:
        raise ValueError(f"unknown provider {provider!r} (know: {sorted(set(PROVIDER_FILES))})")
    block = render_block(scope, mem, hops=hops, kind=kind)
    return _write_block_to(Path(target_dir) / filename, block)


def write_all_provider_files(
    scope: str,
    mem: ProjectMemory,
    target_dir: "str | Path",
    *,
    hops: int = 1,
    kind: str = "project",
) -> "list[Path]":
    """Write ``scope``'s artifact into every distinct provider file
    (`ALL_FILENAMES`) under ``target_dir`` — one write per underlying file,
    not per provider alias, so `codex`/`antigravity` don't produce a
    duplicate write of the same `AGENTS.md`."""
    target_dir = Path(target_dir)
    block = render_block(scope, mem, hops=hops, kind=kind)
    return [_write_block_to(target_dir / filename, block) for filename in ALL_FILENAMES]
