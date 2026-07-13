#!/usr/bin/env bash
# SessionStart hook entry point (Claude Code's `hooks.command` needs a bare
# shell command). The real logic lives in session_start_hook.py, next to this
# file, so it's independently testable (pipe a fake stdin JSON straight into
# it) without going through bash at all.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"

# Never block session start: a missing venv is silence, not an error.
[ -x "$PYTHON" ] || exit 0

exec "$PYTHON" "$REPO_DIR/scripts/session_start_hook.py"
