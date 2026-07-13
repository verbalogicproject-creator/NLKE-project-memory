"""Tests for `project_memory.export.files` — the file-based half of M6:
idempotent, marker-delimited `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` block
injection. Needs the `portfolio` extra (PyYAML)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("yaml")

from project_memory import ProjectMemory
from project_memory.artifact import build_artifact
from project_memory.export.files import (
    ALL_FILENAMES,
    PROVIDER_FILES,
    apply_block,
    render_block,
    write_all_provider_files,
    write_provider_file,
)
from project_memory.portfolio import PORTFOLIO_SCHEMA, RepoSpec, index_portfolio


def _write_readme(path: Path, text: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(text, encoding="utf-8")


@pytest.fixture
def mem_with_alpha(tmp_path):
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n")
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=None, scope=(RepoSpec("alpha"),))
    yield mem
    mem.close()


# ── render_block ─────────────────────────────────────────────────────────────

def test_render_block_wraps_build_artifact(mem_with_alpha):
    block = render_block("alpha", mem_with_alpha)
    artifact = build_artifact("alpha", mem_with_alpha, kind="project")
    assert block.startswith("<!-- project_memory:begin -->\n")
    assert block.rstrip("\n").endswith("<!-- project_memory:end -->")
    assert artifact in block


# ── apply_block ──────────────────────────────────────────────────────────────

def test_apply_block_on_empty_file_is_just_the_block():
    block = "<!-- project_memory:begin -->\nhello\n<!-- project_memory:end -->\n"
    assert apply_block("", block) == block


def test_apply_block_appends_when_no_markers_present():
    existing = "# My hand-written AGENTS.md\n\nDo the thing carefully.\n"
    block = "<!-- project_memory:begin -->\nhello\n<!-- project_memory:end -->\n"
    result = apply_block(existing, block)
    assert result.startswith(existing.rstrip("\n"))
    assert result.rstrip("\n").endswith("<!-- project_memory:end -->")
    assert result.count("<!-- project_memory:begin -->") == 1


def test_apply_block_replaces_existing_block_only(mem_with_alpha):
    hand_written = "# My hand-written AGENTS.md\n\nDo the thing carefully.\n"
    old_block = "<!-- project_memory:begin -->\nold content\n<!-- project_memory:end -->\n"
    trailer = "\n## Trailing hand-written section\n\nDon't touch this.\n"
    existing = hand_written + "\n" + old_block + trailer

    new_block = "<!-- project_memory:begin -->\nnew content\n<!-- project_memory:end -->"
    result = apply_block(existing, new_block)

    assert hand_written.strip() in result
    assert trailer.strip() in result
    assert "old content" not in result
    assert "new content" in result
    assert result.count("<!-- project_memory:begin -->") == 1


def test_apply_block_is_idempotent():
    existing = "# Hand-written\n\nStuff.\n"
    block = "<!-- project_memory:begin -->\nhello\n<!-- project_memory:end -->"
    once = apply_block(existing, block)
    twice = apply_block(once, block)
    assert once == twice


# ── write_provider_file ──────────────────────────────────────────────────────

def test_write_provider_file_claude(tmp_path, mem_with_alpha):
    path = write_provider_file("claude", "alpha", mem_with_alpha, tmp_path)
    assert path == tmp_path / "CLAUDE.md"
    assert path.read_text(encoding="utf-8").startswith("<!-- project_memory:begin -->")


@pytest.mark.parametrize("provider", ["codex", "antigravity"])
def test_write_provider_file_codex_and_antigravity_share_agents_md(tmp_path, mem_with_alpha, provider):
    path = write_provider_file(provider, "alpha", mem_with_alpha, tmp_path)
    assert path == tmp_path / "AGENTS.md"


def test_write_provider_file_codex_and_antigravity_produce_identical_content(tmp_path, mem_with_alpha):
    codex_dir, anti_dir = tmp_path / "codex", tmp_path / "anti"
    codex_dir.mkdir()
    anti_dir.mkdir()
    codex_path = write_provider_file("codex", "alpha", mem_with_alpha, codex_dir)
    anti_path = write_provider_file("antigravity", "alpha", mem_with_alpha, anti_dir)
    assert codex_path.read_text(encoding="utf-8") == anti_path.read_text(encoding="utf-8")


def test_write_provider_file_unknown_provider_raises(tmp_path, mem_with_alpha):
    with pytest.raises(ValueError):
        write_provider_file("no-such-tool", "alpha", mem_with_alpha, tmp_path)


def test_write_provider_file_preserves_hand_written_content_on_rerun(tmp_path, mem_with_alpha):
    target = tmp_path / "AGENTS.md"
    target.write_text("# Hand-written rules\n\nAlways run tests first.\n", encoding="utf-8")
    write_provider_file("codex", "alpha", mem_with_alpha, tmp_path)
    # simulate a human editing the file after the first export
    text = target.read_text(encoding="utf-8")
    target.write_text(text + "\n## Added by hand later\n\nDon't skip this.\n", encoding="utf-8")

    write_provider_file("codex", "alpha", mem_with_alpha, tmp_path)
    final = target.read_text(encoding="utf-8")
    assert "Always run tests first." in final
    assert "Don't skip this." in final
    assert final.count("<!-- project_memory:begin -->") == 1


# ── write_all_provider_files ─────────────────────────────────────────────────

def test_write_all_provider_files_writes_three_distinct_files(tmp_path, mem_with_alpha):
    paths = write_all_provider_files("alpha", mem_with_alpha, tmp_path)
    assert {p.name for p in paths} == set(ALL_FILENAMES)
    assert len(paths) == len(ALL_FILENAMES) == 3


def test_write_all_provider_files_content_matches_render_block(tmp_path, mem_with_alpha):
    write_all_provider_files("alpha", mem_with_alpha, tmp_path)
    expected = render_block("alpha", mem_with_alpha).strip("\n") + "\n"
    for filename in ALL_FILENAMES:
        assert (tmp_path / filename).read_text(encoding="utf-8") == expected


def test_provider_files_mapping_has_no_stray_fourth_file():
    assert set(PROVIDER_FILES.values()) == set(ALL_FILENAMES)
