"""Tests for `project_memory.pack` — the `.pack.md` file format + loader
(Unit 2's first half)."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_memory.pack import find_pack, list_packs, load_pack

_VALID_PACK = """---
kind: pack
id: demo-pack
name: Demo pack
members:
  - alpha: does the alpha thing
  - beta: does the beta thing
---
When loaded: ground answers in the members' declared interfaces.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_pack_parses_id_name_members_prompt(tmp_path: Path):
    path = _write(tmp_path, "demo-pack.pack.md", _VALID_PACK)
    pack = load_pack(path)
    assert pack["id"] == "demo-pack"
    assert pack["name"] == "Demo pack"
    assert pack["members"] == [
        {"name": "alpha", "why": "does the alpha thing"},
        {"name": "beta", "why": "does the beta thing"},
    ]
    assert pack["prompt"] == "When loaded: ground answers in the members' declared interfaces."


def test_load_pack_defaults_name_to_id(tmp_path: Path):
    text = _VALID_PACK.replace("name: Demo pack\n", "")
    path = _write(tmp_path, "demo-pack.pack.md", text)
    assert load_pack(path)["name"] == "demo-pack"


def test_load_pack_rejects_wrong_kind(tmp_path: Path):
    text = _VALID_PACK.replace("kind: pack", "kind: project")
    path = _write(tmp_path, "bad.pack.md", text)
    with pytest.raises(ValueError, match="kind"):
        load_pack(path)


def test_load_pack_rejects_missing_id(tmp_path: Path):
    text = _VALID_PACK.replace("id: demo-pack\n", "")
    path = _write(tmp_path, "bad.pack.md", text)
    with pytest.raises(ValueError, match="id"):
        load_pack(path)


def test_load_pack_rejects_empty_members(tmp_path: Path):
    text = "---\nkind: pack\nid: demo-pack\nmembers:\n---\nsome prompt\n"
    path = _write(tmp_path, "bad.pack.md", text)
    with pytest.raises(ValueError, match="members"):
        load_pack(path)


def test_load_pack_rejects_missing_prompt_body(tmp_path: Path):
    text = "---\nkind: pack\nid: demo-pack\nmembers:\n  - alpha: why\n---\n"
    path = _write(tmp_path, "bad.pack.md", text)
    with pytest.raises(ValueError, match="body"):
        load_pack(path)


def test_load_pack_rejects_member_without_why(tmp_path: Path):
    text = _VALID_PACK.replace("  - alpha: does the alpha thing\n", "  - alpha\n")
    path = _write(tmp_path, "bad.pack.md", text)
    with pytest.raises(ValueError, match="<name>: <why>"):
        load_pack(path)


def test_load_pack_rejects_no_frontmatter(tmp_path: Path):
    path = _write(tmp_path, "bad.pack.md", "just a markdown file, no frontmatter\n")
    with pytest.raises(ValueError, match="frontmatter"):
        load_pack(path)


def test_find_pack_resolves_by_filename_stem(tmp_path: Path):
    _write(tmp_path, "demo-pack.pack.md", _VALID_PACK)
    pack = find_pack("demo-pack", packs_dir=tmp_path)
    assert pack is not None and pack["id"] == "demo-pack"


def test_find_pack_returns_none_when_file_absent(tmp_path: Path):
    assert find_pack("nope", packs_dir=tmp_path) is None


def test_find_pack_rejects_id_filename_mismatch(tmp_path: Path):
    _write(tmp_path, "wrong-name.pack.md", _VALID_PACK)
    with pytest.raises(ValueError, match="doesn't match"):
        find_pack("wrong-name", packs_dir=tmp_path)


def test_real_aisle_pack_loads():
    pack = find_pack("aisle")
    assert pack is not None
    names = {m["name"] for m in pack["members"]}
    assert names == {"Aisle-demo", "scaffold_kg_rag_agent", "sag-declarum-atlas-framework", "taste-skill-main"}


def test_real_verbalogix_pack_loads():
    # Deliberately *not* id "verbalogix" — that string collides with the
    # "verbalogix" project (one of this pack's own members), and a project
    # batch name always wins over a pack id in `brain load`'s resolution
    # order, which would make the pack permanently unreachable by id.
    pack = find_pack("verbalogix-suite")
    assert pack is not None
    names = {m["name"] for m in pack["members"]}
    assert names == {"ctx-architecture", "codebase-memorizer", "vouch", "verbalogix"}


def test_real_aria_app_builder_pack_loads():
    pack = find_pack("aria-app-builder")
    assert pack is not None
    names = {m["name"] for m in pack["members"]}
    assert names == {
        "voice-graph-rag", "gemini-KG-RAG-coding-expert",
        "nlke-declarum-model-01-coding", "jewelry-current",
    }


# ── list_packs (Cut 3, brain menu) ──────────────────────────────────────────

def test_list_packs_sorted_by_id(tmp_path: Path):
    _write(tmp_path, "zeta.pack.md", _VALID_PACK.replace("id: demo-pack", "id: zeta"))
    _write(tmp_path, "alpha.pack.md", _VALID_PACK.replace("id: demo-pack", "id: alpha"))
    packs = list_packs(packs_dir=tmp_path)
    assert [p["id"] for p in packs] == ["alpha", "zeta"]
    assert packs[0]["name"] == "Demo pack"


def test_list_packs_empty_dir_returns_empty_list(tmp_path: Path):
    assert list_packs(packs_dir=tmp_path) == []


def test_list_packs_missing_dir_returns_empty_list(tmp_path: Path):
    assert list_packs(packs_dir=tmp_path / "does-not-exist") == []


def test_list_packs_raises_on_id_filename_mismatch(tmp_path: Path):
    _write(tmp_path, "wrong-name.pack.md", _VALID_PACK)
    with pytest.raises(ValueError, match="doesn't match"):
        list_packs(packs_dir=tmp_path)


def test_list_packs_finds_the_real_packs():
    packs = list_packs()
    ids = {p["id"] for p in packs}
    assert {"aisle", "verbalogix-suite", "aria-app-builder"} <= ids
