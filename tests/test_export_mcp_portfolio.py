"""Tests for `project_memory.export.mcp_portfolio` — the Portfolio Brain's MCP
breadth (M6): resources (snapshot pull), a prompt (mid-session load), and one
idempotent bulk-reindex tool. Needs the `portfolio` extra (PyYAML)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("yaml")

from project_memory import ProjectMemory
from project_memory.artifact import build_artifact
from project_memory.export.mcp_portfolio import (
    call_tool,
    get_prompt,
    list_prompts,
    list_resources,
    list_tools,
    read_resource,
)
from project_memory.pack import list_packs
from project_memory.portfolio import PORTFOLIO_SCHEMA, RepoSpec, index_portfolio


def _write_readme(path: Path, text: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(text, encoding="utf-8")


@pytest.fixture
def mem_with_two_repos(tmp_path):
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n")
    _write_readme(root / "beta", "# beta\n\n## Public API\n\n`OtherThing` does another thing.\n")
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    scope = (RepoSpec("alpha"), RepoSpec("beta"))
    index_portfolio(mem, root=root, edges_path=None, scope=scope)
    yield mem
    mem.close()


# ── resources ────────────────────────────────────────────────────────────────

def test_list_resources_includes_known_projects(mem_with_two_repos):
    uris = {r["uri"] for r in list_resources(mem_with_two_repos)}
    assert "portfolio://project/alpha" in uris
    assert "portfolio://project/beta" in uris


def test_list_resources_includes_real_packs(mem_with_two_repos):
    uris = {r["uri"] for r in list_resources(mem_with_two_repos)}
    real_pack_ids = {p["id"] for p in list_packs()}
    assert real_pack_ids  # sanity: the repo really ships at least one pack
    assert {f"portfolio://pack/{pid}" for pid in real_pack_ids} <= uris


def test_read_resource_project_matches_build_artifact(mem_with_two_repos):
    text = read_resource(mem_with_two_repos, "portfolio://project/alpha")
    assert text == build_artifact("alpha", mem_with_two_repos, kind="project")


def test_read_resource_pack_matches_build_artifact(mem_with_two_repos):
    pack_id = list_packs()[0]["id"]
    text = read_resource(mem_with_two_repos, f"portfolio://pack/{pack_id}")
    assert text == build_artifact(pack_id, mem_with_two_repos, kind="pack")


def test_read_resource_rejects_unknown_scheme(mem_with_two_repos):
    with pytest.raises(ValueError):
        read_resource(mem_with_two_repos, "file:///etc/passwd")


def test_read_resource_rejects_malformed_uri(mem_with_two_repos):
    with pytest.raises(ValueError):
        read_resource(mem_with_two_repos, "portfolio://project/")


# ── prompts ──────────────────────────────────────────────────────────────────

def test_list_prompts_declares_load_context():
    names = {p["name"] for p in list_prompts()}
    assert names == {"load_context"}


def test_get_prompt_load_context_returns_project_artifact(mem_with_two_repos):
    result = get_prompt(mem_with_two_repos, "load_context", {"scope": "alpha"})
    text = result["messages"][0]["content"]["text"]
    assert text == build_artifact("alpha", mem_with_two_repos, kind="project")


def test_get_prompt_load_context_pack_kind(mem_with_two_repos):
    pack_id = list_packs()[0]["id"]
    result = get_prompt(mem_with_two_repos, "load_context", {"scope": pack_id, "kind": "pack"})
    assert result["messages"][0]["content"]["text"].startswith(f"# Context: {pack_id}")


def test_get_prompt_rejects_unknown_name(mem_with_two_repos):
    with pytest.raises(ValueError):
        get_prompt(mem_with_two_repos, "no_such_prompt", {"scope": "alpha"})


def test_get_prompt_requires_scope(mem_with_two_repos):
    with pytest.raises(ValueError):
        get_prompt(mem_with_two_repos, "load_context", {})


# ── tools ────────────────────────────────────────────────────────────────────

def test_list_tools_declares_brain_reindex():
    names = {t["name"] for t in list_tools()}
    assert names == {"brain_reindex"}


def test_call_tool_reindex_single_repo(tmp_path):
    root = tmp_path / "projects"
    _write_readme(root / "gamma", "# gamma\n\n## Public API\n\n`Thing` does a thing.\n")
    scope = (RepoSpec("gamma"),)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    report = call_tool(mem, "brain_reindex", {"name": "gamma", "root": str(root)}, scope=scope, edges_path=None)
    assert report["repos_indexed"] == ["gamma"]
    mem.close()


def test_call_tool_reindex_defaults_to_full_scope(tmp_path):
    root = tmp_path / "projects"
    _write_readme(root / "gamma", "# gamma\n\n## Public API\n\n`Thing` does a thing.\n")
    _write_readme(root / "delta", "# delta\n\n## Public API\n\n`Other` does another thing.\n")
    scope = (RepoSpec("gamma"), RepoSpec("delta"))
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    report = call_tool(mem, "brain_reindex", {"root": str(root)}, scope=scope, edges_path=None)
    assert set(report["repos_indexed"]) == {"gamma", "delta"}
    mem.close()


def test_call_tool_reindex_unknown_repo_raises(tmp_path):
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    with pytest.raises(ValueError):
        call_tool(mem, "brain_reindex", {"name": "ghost-repo-xyz"}, scope=(RepoSpec("gamma"),), edges_path=None)
    mem.close()


def test_call_tool_reindex_is_idempotent(tmp_path):
    root = tmp_path / "projects"
    _write_readme(root / "gamma", "# gamma\n\n## Public API\n\n`Thing` does a thing.\n")
    scope = (RepoSpec("gamma"),)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    call_tool(mem, "brain_reindex", {"name": "gamma", "root": str(root)}, scope=scope, edges_path=None)
    report2 = call_tool(mem, "brain_reindex", {"name": "gamma", "root": str(root)}, scope=scope, edges_path=None)
    assert report2["repos_indexed"] == ["gamma"]  # re-run, no crash, same result
    mem.close()


def test_call_tool_rejects_unknown_tool(tmp_path):
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    with pytest.raises(ValueError):
        call_tool(mem, "no_such_tool", {})
    mem.close()
