"""session_memory.py — ingest Claude Code's own per-project auto-memory files
into this brain's episode log (M2, MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md).

Claude Code's auto-memory system already writes small markdown files with
YAML frontmatter (``name``, ``description``, ``metadata.type``) + a body under
``~/.claude/projects/<slug>/memory/*.md``. Rather than being a second,
disconnected memory Claude has to separately know to go read, this ingests
them as episodes tagged ``corpus=memory`` — into the SAME store `brain load`
already injects from.

**Scoping decision (confirmed against a real directory while building this):**
only ``metadata.type == "project"`` memories are ingested by default. The
other three types Claude Code declares — ``user``, ``feedback``,
``reference`` — are about *Eyal and how Claude should work with him*, not a
project's technical state; ingesting them would leak personal/behavioral
notes into a portfolio artifact that gets injected into unrelated repos'
sessions.

**Why ``batch`` is an explicit override, not auto-derived from the
directory:** a real ``~/.claude/projects/.../memory/`` directory was found
(while building this) to hold notes about *several different projects at
once* — Claude Code doesn't scope one memory directory to one repo as
tightly as this brain's own portfolio does. Guessing a single project for
the whole directory would mis-tag most of its contents, so ``batch`` must be
passed explicitly (or left ``None`` for an unscoped, still-`recall`/`ask`-able
ingest) rather than inferred.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

#: The four memory types Claude Code's own auto-memory system declares. Only
#: "project" is ingested by default — see the module docstring.
_KNOWN_MEMORY_TYPES = ("user", "feedback", "project", "reference")

#: Claude Code's own convention: every memory dir has exactly one index file
#: named literally this, listing (not declaring) the other files — never
#: itself a memory to ingest.
_INDEX_FILENAME = "MEMORY.md"

# A stable namespace for deterministic ids — matches portfolio.py's own
# `_det_id` discipline (a rerun is a benign no-op, not a duplicate row).
_ID_NAMESPACE = uuid.UUID("6f6e6520-6461-6d65-6e73-696f6e2e627e")


def _det_id(*parts: str) -> str:
    return uuid.uuid5(_ID_NAMESPACE, "\x1f".join(parts)).hex


def _split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter_raw, body) — line-scanning, not string-searching: returns
    at the first *bare* ``---`` line found scanning from the second line on,
    so a markdown horizontal rule inside the body never gets mistaken for the
    closing delimiter (same discipline as `pack._split_pack_file`)."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        raise ValueError("memory file must open with a '---' frontmatter block")
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1:]).strip()
    raise ValueError("memory file frontmatter block is never closed with '---'")


def _read_memory_file(path: Path) -> dict[str, Any]:
    """Parse one memory `.md` file's frontmatter + body. Fails loud on
    anything malformed (CLAUDE.md: "Schema validation fails loud")."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "ingesting memory files needs PyYAML — install the `portfolio` extra: "
            "pip install 'project-memory[portfolio]'"
        ) from exc

    raw_fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    fm = yaml.safe_load(raw_fm) or {}
    if not fm.get("name"):
        raise ValueError(f"{path}: frontmatter is missing required 'name'")
    mem_type = (fm.get("metadata") or {}).get("type")
    if mem_type not in _KNOWN_MEMORY_TYPES:
        raise ValueError(
            f"{path}: metadata.type must be one of {_KNOWN_MEMORY_TYPES} (got {mem_type!r})"
        )
    return {"name": fm["name"], "description": fm.get("description") or "", "type": mem_type, "body": body}


def default_claude_memory_dir(project_root: Path) -> Path:
    """Where Claude Code keeps a project's own memory files, given that
    project's root directory.

    **Inferred, not documented:** observed from this repo's own
    ``~/.claude/projects/-root-projects-project-memory/memory/`` — the
    absolute path with both ``/`` and ``_`` replaced by ``-``. Verify this
    resolves correctly on a given machine before relying on it; it is not
    Claude Code's official, guaranteed-stable naming contract.
    """
    slug = str(project_root.resolve()).replace("/", "-").replace("_", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def ingest_memory_dir(
    mem: Any, memory_dir: Path, *, batch: str | None = None, types: tuple[str, ...] = ("project",),
) -> int:
    """Ingest every memory file in `memory_dir` (skipping the index,
    `MEMORY.md`) whose `metadata.type` is in `types`, as one episode each,
    tagged `corpus=memory`. Returns the count ingested.

    `batch` tags every ingested episode to one project so it surfaces in that
    project's `build_artifact` reads (via `batch`-scoped queries) — pass it
    only when `memory_dir` is genuinely single-project-scoped. Left `None`
    (default), episodes are ingested unscoped: still fully `recall`/`ask`-able
    across the whole brain, just not tied to any one project's artifact. See
    the module docstring for why this isn't auto-derived from the directory.
    """
    if not memory_dir.is_dir():
        return 0
    count = 0
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == _INDEX_FILENAME:
            continue
        record = _read_memory_file(path)
        if record["type"] not in types:
            continue
        tags = ["corpus=memory", record["type"], record["name"]]
        if batch:
            tags.append(batch)
        content = f"{record['name']}: {record['description']}\n\n{record['body']}".strip()
        mem.remember(
            content, kind="general", batch=batch, tags=tags,
            metadata={"source_file": str(path), "memory_type": record["type"]},
            method="session_memory_ingest",
            id=_det_id("memory", str(path), content),
        )
        count += 1
    return count
