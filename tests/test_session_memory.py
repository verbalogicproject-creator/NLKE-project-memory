"""Tests for `project_memory.session_memory` (M2 — ingesting Claude Code's
own auto-memory files).

Fixtures mirror the real observed format (frontmatter with a nested
``metadata:`` mapping), not a simplified stand-in — see the module docstring
for where that format was confirmed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_memory import ProjectMemory
from project_memory.portfolio import PORTFOLIO_SCHEMA
from project_memory.session_memory import (
    default_claude_memory_dir,
    ingest_memory_dir,
    _read_memory_file,
)

pytest.importorskip("yaml")

_PROJECT_MEMORY = """---
name: aisle-10-deployed-live
description: "Aisle wedding co-pilot is deployed live on Vercel"
metadata:
  node_type: memory
  type: project
  originSessionId: 8d4281f1-485b-4ec8-909b-a9bcf8fc4556
---

**Aisle went live 2026-07-10.**

- Live URL: https://aisle-demo-two.vercel.app
- A horizontal rule inside the body, for parser robustness:

---

More body text after an embedded rule.
"""

_USER_MEMORY = """---
name: eyal-orchestrator-working-style
description: "Eyal doesn't hand-write code"
metadata:
  node_type: memory
  type: user
  originSessionId: 8d4281f1-485b-4ec8-909b-a9bcf8fc4556
---

Eyal routes tasks across providers rather than writing code by hand.
"""

_FEEDBACK_MEMORY = """---
name: eyal-sole-author
description: "no co-author trailer on commits"
metadata:
  node_type: memory
  type: feedback
---

Attribute extracted repos to Eyal Nof only.
"""


def _write(dir_path: Path, name: str, text: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_read_memory_file_parses_real_format(tmp_path: Path):
    path = _write(tmp_path, "aisle-10-deployed-live.md", _PROJECT_MEMORY)
    record = _read_memory_file(path)
    assert record["name"] == "aisle-10-deployed-live"
    assert record["description"] == "Aisle wedding co-pilot is deployed live on Vercel"
    assert record["type"] == "project"
    assert "went live 2026-07-10" in record["body"]


def test_read_memory_file_embedded_horizontal_rule_does_not_truncate_body(tmp_path: Path):
    path = _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    record = _read_memory_file(path)
    assert "More body text after an embedded rule." in record["body"]


def test_read_memory_file_rejects_missing_name(tmp_path: Path):
    text = _PROJECT_MEMORY.replace("name: aisle-10-deployed-live\n", "")
    path = _write(tmp_path, "bad.md", text)
    with pytest.raises(ValueError, match="name"):
        _read_memory_file(path)


def test_read_memory_file_rejects_unknown_type(tmp_path: Path):
    text = _PROJECT_MEMORY.replace("type: project", "type: bogus")
    path = _write(tmp_path, "bad.md", text)
    with pytest.raises(ValueError, match="metadata.type"):
        _read_memory_file(path)


def test_read_memory_file_rejects_no_frontmatter(tmp_path: Path):
    path = _write(tmp_path, "bad.md", "just markdown, no frontmatter\n")
    with pytest.raises(ValueError, match="frontmatter"):
        _read_memory_file(path)


def test_default_claude_memory_dir_matches_observed_convention():
    """Confirmed against this repo's own real
    `~/.claude/projects/-root-projects-project-memory/memory/` directory —
    both `/` and `_` become `-`."""
    result = default_claude_memory_dir(Path("/root/projects/project_memory"))
    assert str(result) == str(Path.home() / ".claude/projects/-root-projects-project-memory/memory")


def test_ingest_memory_dir_only_ingests_project_type_by_default(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    _write(tmp_path, "user-note.md", _USER_MEMORY)
    _write(tmp_path, "feedback-note.md", _FEEDBACK_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)

    count = ingest_memory_dir(mem, tmp_path)

    assert count == 1
    assert mem.count()["episodes"] == 1
    hits = mem.recall("Aisle", table="episodes")
    assert any("went live" in (h.get("content") or "") for h in hits)
    assert not mem.recall("orchestrator", table="episodes")
    mem.close()


def test_ingest_memory_dir_skips_the_index_file(tmp_path: Path):
    _write(tmp_path, "MEMORY.md", "# Memory Index\n\n- [x](x.md) — a note.\n")
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    count = ingest_memory_dir(mem, tmp_path)
    assert count == 1  # MEMORY.md itself never counted
    mem.close()


def test_ingest_memory_dir_types_override_includes_more(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    _write(tmp_path, "user-note.md", _USER_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    count = ingest_memory_dir(mem, tmp_path, types=("project", "user"))
    assert count == 2
    mem.close()


def test_ingest_memory_dir_batch_none_by_default(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    ingest_memory_dir(mem, tmp_path)
    row = mem.conn.execute("SELECT batch FROM episodes").fetchone()
    assert row[0] is None
    mem.close()


def test_ingest_memory_dir_batch_tags_a_project_when_given(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    ingest_memory_dir(mem, tmp_path, batch="Aisle-demo")
    row = mem.conn.execute("SELECT batch, tags FROM episodes").fetchone()
    assert row[0] == "Aisle-demo"
    assert "Aisle-demo" in row[1]
    mem.close()


def test_ingest_memory_dir_tags_corpus_and_type(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    ingest_memory_dir(mem, tmp_path)
    tags_json = mem.conn.execute("SELECT tags FROM episodes").fetchone()[0]
    assert '"corpus=memory"' in tags_json
    assert '"project"' in tags_json
    mem.close()


def test_ingest_memory_dir_rerun_is_idempotent(tmp_path: Path):
    _write(tmp_path, "aisle.md", _PROJECT_MEMORY)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    ingest_memory_dir(mem, tmp_path)
    ingest_memory_dir(mem, tmp_path)  # must not raise or duplicate
    assert mem.count()["episodes"] == 1
    mem.close()


def test_ingest_memory_dir_missing_directory_returns_zero(tmp_path: Path):
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    count = ingest_memory_dir(mem, tmp_path / "does-not-exist")
    assert count == 0
    mem.close()


def test_ingest_memory_dir_raises_loud_on_malformed_file(tmp_path: Path):
    _write(tmp_path, "bad.md", "no frontmatter at all\n")
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    with pytest.raises(ValueError):
        ingest_memory_dir(mem, tmp_path)
    mem.close()
