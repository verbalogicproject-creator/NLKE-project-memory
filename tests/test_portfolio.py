"""Tests for `project_memory.portfolio` — the Portfolio Brain layer.

Some tests need the optional `portfolio` extra (`pyyaml` for the edge manifest,
`ngfify` for the auto-declare fallback); those are guarded with
`pytest.importorskip` so the base suite stays green without it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_memory import ProjectMemory
from project_memory.portfolio import (
    PORTFOLIO_SCHEMA,
    PORTFOLIO_SCOPE,
    Atom,
    RawEdge,
    RepoSpec,
    _is_decorative_line,
    _visible_text,
    extract_atoms,
    find_declared_cards,
    find_public_api_section,
    index_portfolio,
    repo_summary,
    resolve_edges,
    verify_edge,
)


# ── the scope itself ─────────────────────────────────────────────────────────

def test_scope_names_are_unique():
    names = [r.name for r in PORTFOLIO_SCOPE]
    assert len(names) == len(set(names))


def test_scope_includes_self():
    assert any(r.name == "project_memory" and r.group == "self" for r in PORTFOLIO_SCOPE)


def test_portfolio_schema_declares_interface_kind():
    assert "interface" in PORTFOLIO_SCHEMA.kinds


# ── visible-text / decorative-line stripping ────────────────────────────────

def test_visible_text_strips_plain_link():
    assert _visible_text("See [the docs](./docs) for more.") == "See  for more."


def test_visible_text_strips_nested_badge_link():
    badge = "[![CI](https://x/badge.svg)](https://x/actions)"
    assert _visible_text(badge) == ""


def test_visible_text_strips_html_tags_but_keeps_words():
    assert _visible_text('<p align="center"><em>Hello world</em></p>') == "Hello world"


def test_is_decorative_line_flags_badges_and_blank():
    assert _is_decorative_line("")
    assert _is_decorative_line("[![CI](https://x/badge.svg)](https://x/actions)")
    assert not _is_decorative_line("A real sentence describing the project.")


def test_is_decorative_line_flags_readme_translation_pointer():
    assert _is_decorative_line("**עברית:** [README.he.md](./README.he.md) — draft.")


def test_repo_summary_skips_leading_badges(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "# demo-repo\n\n"
        "[![CI](https://x/badge.svg)](https://x/actions)\n\n"
        "**A tiny demo repo for tests.** It does one thing.\n",
        encoding="utf-8",
    )
    assert repo_summary(tmp_path) == "**A tiny demo repo for tests.** It does one thing."


def test_repo_summary_none_without_readme(tmp_path: Path):
    assert repo_summary(tmp_path) is None


# ── atom extraction: path 1 (declared card) ─────────────────────────────────

def test_find_declared_cards_reads_public_interfaces(tmp_path: Path):
    arch = tmp_path / "arch"
    arch.mkdir()
    (arch / "overview.ngf.md").write_text(
        '---\nid: "demo-overview"\npublic_interfaces:\n  - "DoThing"\n  - "OtherThing"\n---\n# Overview\n',
        encoding="utf-8",
    )
    cards = find_declared_cards(tmp_path)
    assert len(cards) == 1 and cards[0].name == "overview.ngf.md"


def test_find_declared_cards_ignores_demo_corpus_fixtures(tmp_path: Path):
    fixtures = tmp_path / "pkg" / "demo_corpus" / "expected"
    fixtures.mkdir(parents=True)
    (fixtures / "sample.py.ngf.md").write_text(
        '---\nid: "sample"\npublic_interfaces:\n  - "greet"\n---\n# sample\n',
        encoding="utf-8",
    )
    assert find_declared_cards(tmp_path) == []


def test_extract_atoms_prefers_declared_card(tmp_path: Path):
    repo = tmp_path / "demo-repo"
    arch = repo / "arch"
    arch.mkdir(parents=True)
    (arch / "overview.ngf.md").write_text(
        '---\nid: "demo-overview"\npublic_interfaces:\n  - "DoThing"\n---\n# Overview\n',
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# demo-repo\n\n## Public API\n\n`OtherSymbol`\n", encoding="utf-8")
    spec = RepoSpec("demo-repo")
    atoms, warnings = extract_atoms(spec, tmp_path)
    assert warnings == []
    assert len(atoms) == 1
    assert atoms[0].method == "declared_card"
    assert "DoThing" in atoms[0].content


# ── atom extraction: path 2 (Public API section) ────────────────────────────

def test_find_public_api_section_backtick_prose(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "# demo\n\n## Public API\n\n`Foo`, `Bar`, and `Baz` are exported.\n\n## Next\n",
        encoding="utf-8",
    )
    result = find_public_api_section(tmp_path)
    assert result == (["Foo", "Bar", "Baz"], "README.md")


def test_find_public_api_section_fenced_block(tmp_path: Path):
    (tmp_path / "CODEBASE-REPORT.md").write_text(
        "# Codebase report\n\n## Public API surface\n\n"
        "19 symbols:\n\n```\nAlpha, Beta,\nGamma\n```\n\n## Dependencies\n",
        encoding="utf-8",
    )
    result = find_public_api_section(tmp_path)
    assert result == (["Alpha", "Beta", "Gamma"], "CODEBASE-REPORT.md")


def test_find_public_api_section_none_without_heading(tmp_path: Path):
    (tmp_path / "README.md").write_text("# demo\n\nJust prose, no API heading.\n", encoding="utf-8")
    assert find_public_api_section(tmp_path) is None


def test_extract_atoms_falls_back_to_public_api_doc(tmp_path: Path):
    repo = tmp_path / "demo-repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# demo-repo\n\n## Public API\n\n`Thing` does the thing.\n", encoding="utf-8",
    )
    spec = RepoSpec("demo-repo")
    atoms, warnings = extract_atoms(spec, tmp_path)
    assert warnings == []
    assert len(atoms) == 1 and atoms[0].method == "public_api_doc"


def test_extract_atoms_warns_when_nothing_declared(tmp_path: Path):
    repo = tmp_path / "bare-repo"
    repo.mkdir()
    spec = RepoSpec("bare-repo")
    atoms, warnings = extract_atoms(spec, tmp_path)
    assert atoms == []
    assert len(warnings) == 1 and "bare-repo" in warnings[0]


def test_extract_atoms_uses_path_override_outside_root(tmp_path: Path):
    # M5: a repo that doesn't live under the shared root at all (e.g. a
    # termux path) — `RepoSpec.path` must be used verbatim, `root` ignored.
    elsewhere = tmp_path / "elsewhere" / "actual-repo"
    elsewhere.mkdir(parents=True)
    (elsewhere / "README.md").write_text(
        "# actual-repo\n\n## Public API\n\n`Thing` does the thing.\n", encoding="utf-8",
    )
    root = tmp_path / "projects"
    root.mkdir()
    spec = RepoSpec("outside-repo", path=elsewhere)
    atoms, warnings = extract_atoms(spec, root)
    assert warnings == []
    assert len(atoms) == 1 and atoms[0].method == "public_api_doc"


# ── atom extraction: path 3 (ngfify fallback), optional dependency ─────────

def test_extract_atoms_ngfify_fallback(tmp_path: Path):
    pytest.importorskip("ngfify")
    repo = tmp_path / "demo-repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# demo-repo\n\n## First Section\n\nSome prose.\n\n## Second Section\n\nMore prose.\n",
        encoding="utf-8",
    )
    spec = RepoSpec("demo-repo")
    atoms, warnings = extract_atoms(spec, tmp_path)
    assert warnings == []
    assert atoms and all(a.method == "ngfify_auto" for a in atoms)
    assert {"First Section", "Second Section"} <= {
        a.content.split(": ", 1)[1].split(" — ")[0] for a in atoms
    }


# ── edge verification ────────────────────────────────────────────────────────

def _write_readme(repo_path: Path, text: str) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "README.md").write_text(text, encoding="utf-8")


def test_verify_edge_true_when_source_names_target(tmp_path: Path):
    _write_readme(tmp_path / "alpha", "# alpha\n\nAlpha composes beta directly.\n")
    _write_readme(tmp_path / "beta", "# beta\n\nJust beta.\n")
    kept, reason = verify_edge(tmp_path, "alpha", "beta", {})
    assert kept and "alpha" in reason


def test_verify_edge_true_when_target_names_source(tmp_path: Path):
    _write_readme(tmp_path / "alpha", "# alpha\n\nNo mention of the other repo.\n")
    _write_readme(tmp_path / "beta", "# beta\n\nBuilt on top of alpha.\n")
    kept, reason = verify_edge(tmp_path, "alpha", "beta", {})
    assert kept and "beta" in reason


def test_verify_edge_false_when_neither_asserts(tmp_path: Path):
    _write_readme(tmp_path / "alpha", "# alpha\n\nNo relation mentioned.\n")
    _write_readme(tmp_path / "beta", "# beta\n\nAlso no relation mentioned.\n")
    kept, reason = verify_edge(tmp_path, "alpha", "beta", {})
    assert not kept


def test_verify_edge_uses_curated_alias_case_sensitively(tmp_path: Path):
    _write_readme(tmp_path / "alpha", "# alpha\n\nReads Zed's output file.\n")
    _write_readme(tmp_path / "zed-project", "# zed-project\n\nNothing about alpha.\n")
    scope = {"zed-project": RepoSpec("zed-project", aliases=("Zed",))}
    kept, reason = verify_edge(tmp_path, "alpha", "zed-project", scope)
    assert kept and "Zed" in reason


def test_verify_edge_alias_does_not_match_lowercase_common_word(tmp_path: Path):
    # "zed" (lowercase, generic) must NOT satisfy the "Zed" (proper-noun) alias,
    # and neither repo's own docs otherwise name the other.
    _write_readme(tmp_path / "alpha", "# alpha\n\nDraw a zed shape on the canvas.\n")
    _write_readme(tmp_path / "zed-project", "# zed-project\n\nUnrelated content here.\n")
    scope = {"zed-project": RepoSpec("zed-project", aliases=("Zed",))}
    kept, _ = verify_edge(tmp_path, "alpha", "zed-project", scope)
    assert not kept


def test_verify_edge_uses_path_override_for_either_side(tmp_path: Path):
    # M5: one or both sides of an edge may live outside the shared root.
    _write_readme(tmp_path / "alpha", "# alpha\n\nNo mention of the other repo.\n")
    elsewhere = tmp_path / "elsewhere" / "beta"
    _write_readme(elsewhere, "# beta\n\nBuilt on top of alpha.\n")
    scope = {"beta": RepoSpec("beta", path=elsewhere)}
    kept, reason = verify_edge(tmp_path, "alpha", "beta", scope)
    assert kept and "beta" in reason


def test_resolve_edges_expands_targets(tmp_path: Path):
    _write_readme(tmp_path / "alpha", "# alpha\n\nComposes beta and gamma.\n")
    _write_readme(tmp_path / "beta", "# beta\n")
    _write_readme(tmp_path / "gamma", "# gamma\n")
    raw = [RawEdge("composes", "alpha", ("beta", "gamma"))]
    scope = (RepoSpec("alpha"), RepoSpec("beta"), RepoSpec("gamma"))
    decisions = resolve_edges(tmp_path, raw, scope)
    assert len(decisions) == 2
    assert all(d.kept for d in decisions)


# ── load_edge_manifest (needs PyYAML) ────────────────────────────────────────

def test_load_edge_manifest(tmp_path: Path):
    pytest.importorskip("yaml")
    from project_memory.portfolio import load_edge_manifest

    manifest = tmp_path / "edges.yaml"
    manifest.write_text(
        "composes_depends_on:\n"
        "  - source: alpha\n"
        "    targets: [beta]\n"
        "    note: test note\n"
        "public_twin_of:\n"
        "  - source: gamma\n"
        "    targets: [delta]\n"
        "built_by:\n"
        "  - source: factory\n"
        "    targets: [alpha, beta]\n",
        encoding="utf-8",
    )
    edges = load_edge_manifest(manifest)
    categories = {e.category for e in edges}
    assert categories == {"composes", "public_twin_of", "built_by"}
    composes = next(e for e in edges if e.category == "composes")
    assert composes.source == "alpha" and composes.targets == ("beta",) and composes.note == "test note"


# ── end-to-end index_portfolio on a tiny synthetic scope ───────────────────

def test_index_portfolio_end_to_end(tmp_path: Path):
    pytest.importorskip("yaml")
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n\nDepends on beta.\n")
    _write_readme(root / "beta", "# beta\n\n## Public API\n\n`OtherThing` does another thing.\n")
    (root / "edges.yaml").write_text(
        "composes_depends_on:\n"
        "  - source: alpha\n"
        "    targets: [beta]\n"
        "public_twin_of: []\n"
        "built_by: []\n",
        encoding="utf-8",
    )
    scope = (RepoSpec("alpha"), RepoSpec("beta"))

    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    report = index_portfolio(mem, root=root, edges_path=root / "edges.yaml", scope=scope)

    assert report.repos_indexed == ["alpha", "beta"]
    assert report.atom_count == 2
    assert report.milestone_count == 2
    assert len(report.edges_kept) == 1
    assert report.edges_kept[0].source == "alpha" and report.edges_kept[0].target == "beta"

    counts = mem.count()
    assert counts["episodes"] == 4  # 2 interface atoms + 2 milestones
    assert counts["facts"] == 1     # the one composes edge

    hits = mem.recall("beta", table="facts")
    assert any("alpha composes" in (h.get("claim") or "") for h in hits)
    mem.close()


def test_index_portfolio_skips_missing_repo(tmp_path: Path):
    root = tmp_path / "projects"
    root.mkdir()
    scope = (RepoSpec("ghost"),)
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    report = index_portfolio(mem, root=root, edges_path=None, scope=scope)
    assert report.repos_indexed == []
    assert any("ghost" in w for w in report.atom_warnings)
    mem.close()


def test_index_portfolio_is_deterministic(tmp_path: Path):
    """Same corpus, two fresh stores -> identical atom content (ids derived
    from stable parts, not randomness) — the same discipline `demo.py` uses."""
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n")
    scope = (RepoSpec("alpha"),)

    mem1 = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem1, root=root, edges_path=None, scope=scope)
    ids1 = sorted(r[0] for r in mem1.conn.execute("SELECT id FROM episodes").fetchall())
    mem1.close()

    mem2 = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem2, root=root, edges_path=None, scope=scope)
    ids2 = sorted(r[0] for r in mem2.conn.execute("SELECT id FROM episodes").fetchall())
    mem2.close()

    assert ids1 == ids2


def test_atom_is_a_frozen_dataclass():
    a = Atom(repo="x", content="y", method="declared_card", source_file="z.md")
    assert a.tags == ()


# ── idempotent re-index (a real crash found while building the brain CLI) ───

def test_index_portfolio_rerun_does_not_crash(tmp_path: Path):
    """Re-running the indexer into the same (unchanged) db used to raise
    sqlite3.IntegrityError on the very first duplicate id — deterministic ids
    plus a plain INSERT. `remember`/`record_fact` now use INSERT OR IGNORE."""
    pytest.importorskip("yaml")
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\n## Public API\n\n`DoThing` does the thing.\n")
    scope = (RepoSpec("alpha"),)

    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=None, scope=scope)
    index_portfolio(mem, root=root, edges_path=None, scope=scope)  # must not raise

    counts = mem.count()
    assert counts["episodes"] == 2  # 1 interface atom + 1 milestone, not duplicated
    mem.close()


def test_reindex_after_readme_change_updates_milestone(tmp_path: Path):
    """A changed summary must produce a fresh milestone row (content-derived
    id), not crash on the old, content-blind id."""
    root = tmp_path / "projects"
    _write_readme(root / "alpha", "# alpha\n\nFirst summary.\n")
    scope = (RepoSpec("alpha"),)

    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=None, scope=scope)

    _write_readme(root / "alpha", "# alpha\n\nSecond, updated summary.\n")
    index_portfolio(mem, root=root, edges_path=None, scope=scope)  # must not raise

    milestones = mem.conn.execute(
        "SELECT content FROM episodes WHERE batch = 'alpha' AND kind = 'milestone'"
    ).fetchall()
    assert len(milestones) == 2
    assert any("Second, updated summary" in m[0] for m in milestones)
    mem.close()
