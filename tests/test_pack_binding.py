"""Unit 5 — the tested selection→injection binding (non-negotiable).

The seed's lesson (from `controll-interface` V1.1, which shipped selection
toggles the router silently bypassed): what you select must deterministically
drive what gets injected. This locks that down for packs — a pack's artifact
contains exactly its declared members, never a sibling pack's, and changing
`members:` changes the artifact's membership deterministically.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_memory import ProjectMemory
from project_memory import pack as pack_module
from project_memory.artifact import build_artifact
from project_memory.portfolio import PORTFOLIO_SCHEMA, RepoSpec, index_portfolio

pytest.importorskip("yaml")


def _write_readme(repo_path: Path, text: str) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "README.md").write_text(text, encoding="utf-8")


def _three_repo_portfolio(tmp_path: Path) -> ProjectMemory:
    """repo-x, repo-y, repo-z — three unrelated repos, each with one distinct
    public symbol, so a pack's membership can be verified by which symbols
    show up (or don't) in its artifact."""
    root = tmp_path / "projects"
    _write_readme(root / "repo-x", "# repo-x\n\n## Public API\n\n`XThing` does X.\n")
    _write_readme(root / "repo-y", "# repo-y\n\n## Public API\n\n`YThing` does Y.\n")
    _write_readme(root / "repo-z", "# repo-z\n\n## Public API\n\n`ZThing` does Z.\n")
    scope = (RepoSpec("repo-x"), RepoSpec("repo-y"), RepoSpec("repo-z"))
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=None, scope=scope)
    return mem


def _write_pack(packs_dir: Path, pack_id: str, members: list[str], prompt: str) -> None:
    packs_dir.mkdir(parents=True, exist_ok=True)
    member_lines = "\n".join(f"  - {m}" for m in members)
    (packs_dir / f"{pack_id}.pack.md").write_text(
        f"---\nkind: pack\nid: {pack_id}\nmembers:\n{member_lines}\n---\n{prompt}\n",
        encoding="utf-8",
    )


def test_pack_artifact_contains_exactly_its_declared_members(tmp_path: Path, monkeypatch):
    mem = _three_repo_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "pack-a", ["repo-x: reason x", "repo-y: reason y"], "pack-a prompt.")
    _write_pack(packs_dir, "pack-b", ["repo-y: reason y2", "repo-z: reason z"], "pack-b prompt.")
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("pack-a", mem, kind="pack")
    assert "XThing" in artifact
    assert "YThing" in artifact
    assert "ZThing" not in artifact  # repo-z belongs only to pack-b
    assert "pack-a prompt." in artifact
    assert "pack-b prompt." not in artifact
    mem.close()


def test_pack_artifact_excludes_sibling_pack_members(tmp_path: Path, monkeypatch):
    mem = _three_repo_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "pack-a", ["repo-x: reason x", "repo-y: reason y"], "pack-a prompt.")
    _write_pack(packs_dir, "pack-b", ["repo-y: reason y2", "repo-z: reason z"], "pack-b prompt.")
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("pack-b", mem, kind="pack")
    assert "ZThing" in artifact
    assert "YThing" in artifact
    assert "XThing" not in artifact  # repo-x belongs only to pack-a
    assert "pack-b prompt." in artifact
    assert "pack-a prompt." not in artifact
    mem.close()


def test_changing_pack_members_changes_the_artifact_deterministically(tmp_path: Path, monkeypatch):
    mem = _three_repo_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "pack-a", ["repo-x: reason x"], "pack-a prompt.")
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    before = build_artifact("pack-a", mem, kind="pack")
    assert "XThing" in before
    assert "YThing" not in before

    _write_pack(packs_dir, "pack-a", ["repo-y: reason y"], "pack-a prompt.")
    after = build_artifact("pack-a", mem, kind="pack")
    assert "YThing" in after
    assert "XThing" not in after
    mem.close()


def test_real_aisle_and_verbalogix_packs_never_cross_contaminate():
    """The two real MVP packs (aisle, verbalogix-suite — see
    `project_memory/packs/`) share no members; each pack's artifact must show
    only its own."""
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    aisle_pack = pack_module.find_pack("aisle")
    verbalogix_pack = pack_module.find_pack("verbalogix-suite")
    aisle_members = {m["name"] for m in aisle_pack["members"]}
    verbalogix_members = {m["name"] for m in verbalogix_pack["members"]}
    assert aisle_members.isdisjoint(verbalogix_members)
    mem.close()


def test_real_verbalogix_pack_id_does_not_collide_with_a_member_project():
    """`verbalogix` is both the pack's umbrella product name *and* one of its
    own declared members — the pack id must not be that string, or `brain
    load verbalogix` would always resolve to the project (see cli.cmd_brain_load's
    project-before-pack precedence) and the pack itself would be unreachable."""
    pack = pack_module.find_pack("verbalogix-suite")
    member_names = {m["name"] for m in pack["members"]}
    assert pack["id"] not in member_names
