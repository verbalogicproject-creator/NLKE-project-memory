"""Tests for `scripts/session_start_hook.sh` (Unit 4).

Runs the real hook script as a subprocess (as Claude Code would), with
`PMEM_BRAIN_DB` pointed at a tiny synthetic portfolio built via
`index_portfolio` — the same harness `test_cli.py` uses for `brain load`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "scripts" / "session_start_hook.sh"


def _index_tiny_brain(tmp_path: Path) -> tuple[str, Path]:
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA, RepoSpec, index_portfolio

    root = tmp_path / "projects"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "README.md").write_text(
        "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n", encoding="utf-8",
    )
    db = str(tmp_path / "brain.db")
    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=None, scope=(RepoSpec("alpha"),))
    mem.close()
    return db, root


def _run_hook(db: str, hook_input: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, "PMEM_BRAIN_DB": db}
    return subprocess.run(
        [str(HOOK)], input=json.dumps(hook_input), capture_output=True, text=True,
        env=env, timeout=15,
    )


def test_hook_injects_artifact_for_indexed_cwd(tmp_path):
    db, root = _index_tiny_brain(tmp_path)
    result = _run_hook(db, {"session_id": "t", "cwd": str(root / "alpha"),
                             "hook_event_name": "SessionStart", "source": "startup"})
    assert result.returncode == 0
    assert result.stdout.startswith("# Context: alpha")


def test_hook_is_silent_for_unindexed_cwd(tmp_path):
    db, _ = _index_tiny_brain(tmp_path)
    unrelated = tmp_path / "totally-unrelated"
    unrelated.mkdir()
    result = _run_hook(db, {"session_id": "t", "cwd": str(unrelated),
                             "hook_event_name": "SessionStart", "source": "startup"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_hook_resolves_from_a_subdirectory_of_the_repo(tmp_path):
    db, root = _index_tiny_brain(tmp_path)
    nested = root / "alpha" / "src" / "deep"
    nested.mkdir(parents=True)
    result = _run_hook(db, {"session_id": "t", "cwd": str(nested),
                             "hook_event_name": "SessionStart", "source": "startup"})
    assert result.returncode == 0
    assert result.stdout.startswith("# Context: alpha")


def test_hook_survives_malformed_stdin(tmp_path):
    db, _ = _index_tiny_brain(tmp_path)
    env = {**os.environ, "PMEM_BRAIN_DB": db}
    result = subprocess.run(
        [str(HOOK)], input="not json at all", capture_output=True, text=True,
        env=env, timeout=15,
    )
    assert result.returncode == 0


def test_hook_survives_empty_stdin(tmp_path):
    db, _ = _index_tiny_brain(tmp_path)
    env = {**os.environ, "PMEM_BRAIN_DB": db}
    result = subprocess.run(
        [str(HOOK)], input="", capture_output=True, text=True, env=env, timeout=15,
    )
    assert result.returncode == 0


def test_hook_records_the_session_id_as_provenance(tmp_path):
    """The hook passes Claude Code's own `session_id` through `--session` (M4),
    so `brain journey`/`unused` can group that session's loads."""
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA
    from project_memory.provenance import journey

    db, root = _index_tiny_brain(tmp_path)
    result = _run_hook(db, {"session_id": "sess-xyz", "cwd": str(root / "alpha"),
                             "hook_event_name": "SessionStart", "source": "startup"})
    assert result.returncode == 0

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    report = journey(mem, session="sess-xyz")
    mem.close()
    assert [e.scope for e in report.events] == ["alpha"]
    assert report.events[0].trigger == "startup"


def test_hook_script_is_executable():
    assert os.access(HOOK, os.X_OK)
