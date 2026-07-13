#!/usr/bin/env python3
"""SessionStart hook — injects the current repo's declared context artifact
into a fresh Claude Code session (project_memory's Portfolio Brain,
MEMORY-SYSTEM-MVP-SPEC.md Unit 4).

Reads the hook's stdin JSON for ``cwd`` (the session's working directory —
not necessarily this script's own process cwd), asks ``brain load --current
--json`` for that project's artifact, and prints it as plain text: Claude
Code's plain-text fallback adds unstructured stdout as ``additionalContext``
on exit 0. Must never block session start — any failure degrades to silence,
not an error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
CLI = REPO_DIR / ".venv" / "bin" / "project-memory"


def main() -> int:
    if not CLI.is_file():
        return 0

    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    cwd = hook_input.get("cwd")
    trigger = hook_input.get("source") or "hook"
    session = hook_input.get("session_id")
    cmd = [str(CLI), "brain", "load", "--current", "--json", "--trigger", trigger]
    if cwd:
        cmd += ["--cwd", cwd]
    if session:
        cmd += ["--session", session]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return 0

    if result.returncode != 0:
        return 0

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return 0

    if data.get("loaded"):
        sys.stdout.write(data.get("artifact", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
