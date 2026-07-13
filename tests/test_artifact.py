"""Tests for `project_memory.artifact.build_artifact` (MVP Unit 1).

`build_artifact` reads `mem.conn` directly (exact `batch`/`tags` membership),
not `recall`/`ask` (fuzzy BM25/RRF) — these tests exercise that read path
against a tiny synthetic portfolio, mirroring `test_portfolio.py`'s harness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_memory import ProjectMemory
from project_memory import pack as pack_module
from project_memory.artifact import build_artifact, build_pack_artifact
from project_memory.portfolio import PORTFOLIO_SCHEMA, RepoSpec, index_portfolio

pytest.importorskip("yaml")

_SECTIONS = ("## Identity", "## Interfaces", "## Related (1-hop, with reason)", "## What to do")


def _write_readme(repo_path: Path, text: str) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / "README.md").write_text(text, encoding="utf-8")


def _tiny_portfolio(tmp_path: Path) -> ProjectMemory:
    """alpha composes/depends on beta; both have a Public API section."""
    root = tmp_path / "projects"
    _write_readme(
        root / "alpha",
        "# alpha\n\n**Alpha turns raw input into structured output.**\n\n"
        "## Public API\n\n`DoThing` does the thing.\n\nDepends on beta.\n",
    )
    _write_readme(root / "beta", "# beta\n\n## Public API\n\n`OtherThing` does another thing.\n")
    (root / "edges.yaml").write_text(
        "composes_depends_on:\n  - source: alpha\n    targets: [beta]\n"
        "public_twin_of: []\nbuilt_by: []\n",
        encoding="utf-8",
    )
    scope = (RepoSpec("alpha"), RepoSpec("beta"))
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    index_portfolio(mem, root=root, edges_path=root / "edges.yaml", scope=scope)
    return mem


def test_build_artifact_has_all_four_sections(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    assert all(s in artifact for s in _SECTIONS)
    assert artifact.startswith("# Context: alpha")
    mem.close()


def test_build_artifact_identity_from_readme_summary(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    identity = artifact.split("## Identity", 1)[1].split("## Interfaces", 1)[0]
    assert "Alpha turns raw input into structured output" in identity
    assert "Group: fleet · Kind: project" in identity
    mem.close()


def test_build_artifact_lists_interface_atoms(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    assert "DoThing" in artifact
    assert "OtherThing" not in artifact  # beta's interface must not leak into alpha's artifact
    mem.close()


def test_build_artifact_forward_edge(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    assert "composes → beta" in related
    mem.close()


def test_build_artifact_reverse_edge(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("beta", mem)
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    assert "depended-on-by ← alpha" in related
    mem.close()


def test_build_artifact_marks_pending_edge(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    # A fact naming a target that was never indexed (no batch of that name) —
    # the seed's "phantom edge" case: a valid pending edge, not an error.
    mem.record_fact(
        "alpha composes / depends on gamma.",
        reason="alpha's own docs name 'gamma'",
        tags=["alpha", "gamma", "edge", "composes"],
    )
    artifact = build_artifact("alpha", mem)
    lines = {line for line in artifact.splitlines() if line.startswith("- composes")}
    beta_line = next(l for l in lines if "beta" in l)
    gamma_line = next(l for l in lines if "gamma" in l)
    assert "(pending)" not in beta_line
    assert "(pending)" in gamma_line
    mem.close()


def test_build_artifact_excludes_superseded_facts(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    old = mem.record_fact(
        "alpha composes / depends on delta.",
        tags=["alpha", "delta", "edge", "composes"],
    )["id"]
    # Retire the edge claim outright — the replacement fact carries no edge
    # tags, so the alpha->delta relationship should vanish from Related.
    mem.record_fact(
        "alpha no longer depends on delta; the dependency was removed.",
        tags=["alpha", "retired-dependency"],
        supersedes=old,
    )
    artifact = build_artifact("alpha", mem)
    assert "delta" not in artifact
    mem.close()


def test_build_artifact_graceful_for_unknown_scope(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("never-indexed", mem)
    assert all(s in artifact for s in _SECTIONS)
    assert "(no declared summary found)" in artifact
    assert "(none declared)" in artifact
    assert "(no verified edges)" in artifact
    mem.close()


def test_build_artifact_edge_query_handles_underscore_in_scope_name(tmp_path: Path):
    """`_project_edges`'s SQL-side LIKE pre-filter treats `_` as a wildcard —
    it must still find the real edge for a scope whose name contains one
    (only false positives are possible from that, never a false negative;
    the exact Python-side tags check is what actually decides membership)."""
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    mem.remember("declared_core: does the thing.", kind="interface", batch="declared_core",
                 tags=["declared_core", "interface"], id="dc-atom")
    mem.record_fact(
        "frontmatter_rag composes / depends on declared_core.",
        reason="frontmatter_rag's own docs name 'declared_core' (== declared_core)",
        tags=["frontmatter_rag", "declared_core", "edge", "composes"],
    )
    artifact = build_artifact("declared_core", mem)
    assert "depended-on-by ← frontmatter_rag" in artifact
    mem.close()


def test_build_artifact_unknown_pack_raises(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    with pytest.raises(ValueError, match="no pack named"):
        build_artifact("not-a-real-pack", mem, kind="pack")
    mem.close()


def test_build_artifact_rejects_hops_beyond_2(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    with pytest.raises(NotImplementedError):
        build_artifact("alpha", mem, hops=3)
    mem.close()


def test_build_artifact_pack_rejects_hops_2(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    with pytest.raises(NotImplementedError, match="pack artifacts only support hops=1"):
        build_artifact("alpha", mem, kind="pack", hops=2)
    mem.close()


def test_build_artifact_shows_indexed_date(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    identity = build_artifact("alpha", mem).split("## Identity", 1)[1].split("## Interfaces", 1)[0]
    assert "Indexed: " in identity and "Indexed: never" not in identity
    mem.close()


def test_build_artifact_shows_never_indexed_for_unknown_scope(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    identity = build_artifact("never-indexed", mem).split("## Identity", 1)[1].split("## Interfaces", 1)[0]
    assert "Indexed: never" in identity
    mem.close()


def test_build_artifact_picks_latest_milestone(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    # Simulate a re-index after the README summary changed: a second milestone
    # row for the same batch, deliberately older *and* newer than reality to
    # prove selection is by created_at, not insertion order.
    mem.remember(
        "alpha: a stale summary from before a rewrite.", kind="milestone", batch="alpha",
        tags=["alpha", "repo-summary", "fleet"], id="old-milestone",
        created_at="2020-01-01T00:00:00+00:00",
    )
    mem.remember(
        "alpha: the current, freshest summary.", kind="milestone", batch="alpha",
        tags=["alpha", "repo-summary", "fleet"], id="new-milestone",
        created_at="2099-01-01T00:00:00+00:00",
    )
    identity = build_artifact("alpha", mem).split("## Identity", 1)[1].split("## Interfaces", 1)[0]
    assert "the current, freshest summary" in identity
    assert "stale summary" not in identity
    mem.close()


def test_build_artifact_compresses_formulaic_reason(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    # The real reason produced by verify_edge for this fixture is the full
    # formulaic sentence; the artifact should show the compressed form.
    assert "docs name 'beta'" in related
    assert "(== beta)" not in related  # the verbatim sentence must not survive


def test_build_artifact_passes_through_nonformulaic_reason(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    mem.record_fact(
        "alpha composes / depends on gamma.",
        reason="a hand-written reason that doesn't match the template",
        tags=["alpha", "gamma", "edge", "composes"],
    )
    artifact = build_artifact("alpha", mem)
    assert "a hand-written reason that doesn't match the template" in artifact
    mem.close()


def test_build_artifact_caps_interfaces_with_truncation_note(tmp_path: Path):
    mem = ProjectMemory.open(schema=PORTFOLIO_SCHEMA)
    for i in range(20):
        mem.remember(f"gamma: symbol_{i} — declared public interface.", kind="interface", batch="gamma",
                     tags=["gamma", "interface"], id=f"gamma-atom-{i}")
    artifact = build_artifact("gamma", mem)
    interfaces = artifact.split("## Interfaces", 1)[1].split("## Related", 1)[0]
    assert interfaces.count("symbol_") == 15
    assert "…and 5 more (truncated for context budget)" in interfaces
    mem.close()


# ── hops=2 graph-walk (M1) ───────────────────────────────────────────────────

def test_build_artifact_hops1_is_the_default_and_unheaded_by_hops(tmp_path: Path):
    """hops=1's output must stay exactly as before M1 — no `hops=` in the
    header meta line, same heading text."""
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    header_meta = artifact.splitlines()[1]
    assert "hops=" not in header_meta
    assert "## Related (1-hop, with reason)" in artifact
    mem.close()


def test_build_artifact_hops2_includes_second_hop_neighbor(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)  # alpha composes/depends on beta
    mem.record_fact(
        "beta composes / depends on gamma.",
        reason="beta's own docs name 'gamma'",
        tags=["beta", "gamma", "edge", "composes"],
    )
    artifact = build_artifact("alpha", mem, hops=2)
    assert "## Related (1-2 hops, scored)" in artifact
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    assert "composes → beta" in related  # still shows the 1-hop neighbor
    assert "→ gamma" in related  # and the 2-hop one, reached via beta
    mem.close()


def test_build_artifact_hops2_marks_pending_at_second_hop(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    mem.record_fact(
        "beta composes / depends on gamma.",
        reason="beta's own docs name 'gamma'",
        tags=["beta", "gamma", "edge", "composes"],
    )
    artifact = build_artifact("alpha", mem, hops=2)
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    beta_line = next(l for l in related.splitlines() if "→ beta" in l and "beta →" not in l)
    gamma_line = next(l for l in related.splitlines() if l.rstrip().endswith("gamma") or "(pending)" in l and "gamma" in l)
    assert "(pending)" not in beta_line  # beta was indexed by _tiny_portfolio
    assert "(pending)" in gamma_line  # gamma was never indexed
    mem.close()


def test_build_artifact_hops2_shows_a_score(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem, hops=2)
    related = artifact.split("## Related", 1)[1].split("## What to do", 1)[0]
    assert "(score " in related
    mem.close()


def test_build_artifact_hops2_header_notes_hops(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem, hops=2)
    header_meta = artifact.splitlines()[1]
    assert "hops=2" in header_meta
    mem.close()


# ── Recent memory (M2) ───────────────────────────────────────────────────────

def test_build_artifact_recent_memory_empty_by_default(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert "none yet" in memory
    mem.close()


def test_build_artifact_recent_memory_shows_crystallized_fact(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    mem.remember("we chose SQLite for the store", kind="decision", batch="alpha",
                 tags=["alpha", "session-memory"], auto_fact=True, reason="zero-ops")
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert "we chose SQLite for the store" in memory
    assert "zero-ops" in memory
    mem.close()


def test_build_artifact_recent_memory_excludes_other_projects(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    mem.remember("beta's own decision", kind="decision", batch="beta",
                 tags=["beta", "session-memory"], auto_fact=True)
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert "beta's own decision" not in memory
    mem.close()


def test_build_artifact_recent_memory_excludes_non_crystallized_episodes(tmp_path: Path):
    """A `brain remember --no-auto-fact` episode stays queryable via
    recall/ask but must not clutter the at-a-glance artifact section."""
    mem = _tiny_portfolio(tmp_path)
    mem.remember("the build broke again", kind="gotcha", batch="alpha",
                 tags=["alpha", "session-memory"], auto_fact=False)
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert "the build broke again" not in memory
    assert "none yet" in memory
    mem.close()


def test_build_artifact_recent_memory_excludes_superseded_facts(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    old = mem.remember("we use SQLite", kind="decision", batch="alpha",
                        tags=["alpha", "session-memory"], auto_fact=True)
    mem.remember("we migrated to Postgres", kind="decision", batch="alpha",
                 tags=["alpha", "session-memory"], auto_fact=True, supersedes=old["fact_id"])
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert "we migrated to Postgres" in memory
    assert "we use SQLite" not in memory  # superseded — must not resurface as current
    mem.close()


def test_build_artifact_recent_memory_shows_newest_first(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    mem.remember("older decision", kind="decision", batch="alpha", tags=["alpha", "session-memory"],
                 auto_fact=True, id="e-old", created_at="2020-01-01T00:00:00+00:00")
    mem.remember("newer decision", kind="decision", batch="alpha", tags=["alpha", "session-memory"],
                 auto_fact=True, id="e-new", created_at="2099-01-01T00:00:00+00:00")
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert memory.index("newer decision") < memory.index("older decision")
    mem.close()


def test_build_artifact_recent_memory_caps_with_truncation_note(tmp_path: Path):
    mem = _tiny_portfolio(tmp_path)
    for i in range(12):
        mem.remember(f"decision {i}", kind="decision", batch="alpha",
                     tags=["alpha", "session-memory"], auto_fact=True, id=f"mem-{i}")
    artifact = build_artifact("alpha", mem)
    memory = artifact.split("## Recent memory", 1)[1].split("## What to do", 1)[0]
    assert memory.count('"decision ') == 8
    assert "…and 4 more (truncated for context budget)" in memory
    mem.close()


# ── pack composition (Unit 2) ────────────────────────────────────────────────

_PACK_PROMPT = "When loaded: ground answers in the pack members' declared interfaces."


def _write_pack(packs_dir: Path, pack_id: str, members: list[str], prompt: str = _PACK_PROMPT) -> None:
    packs_dir.mkdir(parents=True, exist_ok=True)
    member_lines = "\n".join(f"  - {m}" for m in members)
    (packs_dir / f"{pack_id}.pack.md").write_text(
        f"---\nkind: pack\nid: {pack_id}\nmembers:\n{member_lines}\n---\n{prompt}\n",
        encoding="utf-8",
    )


def test_build_artifact_pack_composes_both_members(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", ["alpha: the main flow", "beta: a dependency"])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    assert "DoThing" in artifact  # alpha's interface
    assert "OtherThing" in artifact  # beta's interface
    mem.close()


def test_build_artifact_pack_appends_prompt_exactly_once(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", ["alpha: the main flow", "beta: a dependency"])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    assert artifact.count("## What to do") == 1
    assert artifact.rstrip().endswith(_PACK_PROMPT)
    mem.close()


def test_build_artifact_pack_members_become_related_reasons(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", ["alpha: the main flow", "beta: a dependency"])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    assert "member → alpha — the main flow" in artifact
    assert "member → beta — a dependency" in artifact
    mem.close()


def test_build_pack_artifact_works_without_any_pack_file(tmp_path: Path):
    """`build_pack_artifact` is decoupled from `.pack.md` files entirely — a
    future ad-hoc/computed grouping can call it directly with its own member
    list, no hand-authored pack file required (upgrade: generalize beyond
    static packs)."""
    mem = _tiny_portfolio(tmp_path)
    artifact = build_pack_artifact(
        "ad-hoc-group", mem,
        members=[{"name": "alpha", "why": "computed reason A"},
                 {"name": "beta", "why": "computed reason B"}],
        prompt="an ad-hoc prompt",
    )
    assert "DoThing" in artifact and "OtherThing" in artifact
    assert "member → alpha — computed reason A" in artifact
    assert artifact.count("## What to do") == 1
    assert artifact.rstrip().endswith("an ad-hoc prompt")
    mem.close()


def test_build_artifact_pack_staleness_shows_oldest_member(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", ["alpha: the main flow", "beta: a dependency"])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    header = artifact.split("\n", 2)[1]
    assert "oldest member indexed:" in header
    mem.close()


def test_build_artifact_pack_flags_never_indexed_member(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", ["alpha: the main flow", "never-indexed-repo: not in the store"])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    header = artifact.split("\n", 2)[1]
    assert "oldest member: never indexed" in header
    mem.close()


def test_build_artifact_pack_caps_members_with_truncation_note(tmp_path: Path, monkeypatch):
    mem = _tiny_portfolio(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_pack(packs_dir, "demo", [f"member{i}: reason {i}" for i in range(25)])
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    artifact = build_artifact("demo", mem, kind="pack")
    related = artifact.split("## Related", 1)[1].split("\n\n", 1)[0]
    assert related.count("- member →") == 20
    assert "…and 5 more members (truncated for context budget)" in related
    assert artifact.count("# Context: member") == 20  # only 20 member blocks concatenated
    mem.close()
