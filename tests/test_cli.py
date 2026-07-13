import json

import pytest

from project_memory.cli import main


def _run(capsys, argv):
    rc = main(argv)
    out = capsys.readouterr().out
    return rc, out


def test_demo_json(capsys):
    rc, out = _run(capsys, ["demo", "--json"])
    d = json.loads(out)
    assert rc == 0
    assert d["counts"] == {"episodes": 8, "facts": 5}
    assert d["synthesize"]["verdict"] == "refuse"


def test_asks_lists_eleven(capsys):
    rc, out = _run(capsys, ["asks", "--json"])
    assert len(json.loads(out)) == 11


def test_kinds(capsys):
    rc, out = _run(capsys, ["kinds", "--json"])
    assert "decision" in json.loads(out)


def test_dims(capsys):
    rc, out = _run(capsys, ["dims", "--json"])
    assert len(json.loads(out)) == 12


def test_synthesize_refuse(capsys):
    rc, out = _run(capsys, [
        "synthesize",
        "From a security perspective, plaintext tokens are unacceptable.",
        "From a business perspective, plaintext tokens were cheap and fine.",
        "--json",
    ])
    assert json.loads(out)["verdict"] == "refuse"


def test_remember_recall_roundtrip(tmp_path, capsys):
    db = str(tmp_path / "m.db")
    _run(capsys, ["remember", "we chose SQLite for storage", "--kind", "decision",
                  "--auto-fact", "--reason", "local-first", "--db", db])
    rc, out = _run(capsys, ["recall", "sqlite storage", "--db", db, "--json"])
    hits = json.loads(out)
    assert rc == 0 and hits
    assert any("SQLite" in (h.get("content") or h.get("claim") or "") for h in hits)


def test_recall_empty_message(tmp_path, capsys):
    db = str(tmp_path / "empty.db")
    rc, out = _run(capsys, ["recall", "nothing here", "--db", db])
    assert "no memory matches" in out


def test_ask_by_name(tmp_path, capsys):
    db = str(tmp_path / "m2.db")
    _run(capsys, ["remember", "created_at must be UTC to avoid reorder bugs",
                  "--kind", "gotcha", "--db", db])
    rc, out = _run(capsys, ["ask", "why did timestamps reorder?", "--name", "why_not",
                            "--db", db, "--json"])
    assert json.loads(out)["ask"] == "why_not"


def test_unknown_kind_exits_nonzero(tmp_path, capsys):
    db = str(tmp_path / "m3.db")
    rc = main(["remember", "x", "--kind", "bogus", "--db", db])
    assert rc == 1


# ── brain (portfolio artifact injection) ─────────────────────────────────────

def _index_tiny_brain(tmp_path):
    pytest.importorskip("yaml")
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


def test_brain_load_explicit_project(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "load", "alpha", "--db", db])
    assert rc == 0
    assert out.startswith("# Context: alpha")


def test_brain_load_unknown_project_exits_nonzero(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "load", "not-a-project", "--db", db])
    assert rc == 1


def test_brain_load_hops_default_is_1(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "load", "alpha", "--db", db])
    assert rc == 0
    assert "hops=" not in out.splitlines()[1]


def test_brain_load_hops2_shows_second_hop_neighbor(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    mem.record_fact(
        "alpha composes / depends on gamma.",
        reason="alpha's own docs name 'gamma'",
        tags=["alpha", "gamma", "edge", "composes"],
    )
    mem.close()

    rc, out = _run(capsys, ["brain", "load", "alpha", "--hops", "2", "--db", db])
    assert rc == 0
    assert "hops=2" in out.splitlines()[1]
    assert "→ gamma" in out


def test_brain_load_pack_with_hops2_errors_cleanly(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    (packs_dir / "demo.pack.md").write_text(
        "---\nkind: pack\nid: demo\nmembers:\n  - alpha: the only member\n---\ndo the thing.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    rc, out = _run(capsys, ["brain", "load", "demo", "--hops", "2", "--db", db])
    assert rc == 1


def test_brain_load_rejects_invalid_hops_choice(tmp_path):
    db, _ = _index_tiny_brain(tmp_path)
    with pytest.raises(SystemExit):
        main(["brain", "load", "alpha", "--hops", "3", "--db", db])


def test_brain_load_resolves_a_pack_id(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    (packs_dir / "demo.pack.md").write_text(
        "---\nkind: pack\nid: demo\nmembers:\n  - alpha: the only member\n---\ndo the thing.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    rc, out = _run(capsys, ["brain", "load", "demo", "--db", db])
    assert rc == 0
    assert out.startswith("# Context: demo")
    assert "scope=pack" in out
    assert "DoThing" in out


def test_brain_load_records_a_provenance_episode(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    rc, _ = _run(capsys, ["brain", "load", "alpha", "--db", db, "--trigger", "startup"])
    assert rc == 0

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    loads = mem.recent(limit=5, kind="brain_load")
    assert len(loads) == 1
    assert loads[0]["tags"] == ["alpha", "project", "startup"]
    mem.close()


def test_brain_load_current_walks_parent_dirs(tmp_path, capsys, monkeypatch):
    db, root = _index_tiny_brain(tmp_path)
    nested = root / "alpha" / "src" / "deeply" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    rc, out = _run(capsys, ["brain", "load", "--current", "--db", db])
    assert rc == 0
    assert out.startswith("# Context: alpha")


def test_brain_load_current_unknown_dir(tmp_path, capsys, monkeypatch):
    db, _ = _index_tiny_brain(tmp_path)
    unknown = tmp_path / "totally-unrelated-dir"
    unknown.mkdir()
    monkeypatch.chdir(unknown)
    rc, out = _run(capsys, ["brain", "load", "--current", "--db", db])
    assert rc == 0
    assert "no known project here" in out


def test_brain_reindex_rejects_unknown_project(tmp_path, capsys):
    db, root = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, [
        "brain", "reindex", "not-in-portfolio-scope", "--root", str(root), "--edges", "", "--db", db,
    ])
    assert rc == 1


def test_brain_reindex_updates_after_readme_change(tmp_path, capsys):
    pytest.importorskip("yaml")
    db = str(tmp_path / "brain2.db")
    root = tmp_path / "projects2"
    (root / "declared_core").mkdir(parents=True)
    (root / "declared_core" / "README.md").write_text(
        "# declared_core\n\nFirst summary.\n", encoding="utf-8",
    )
    rc, _ = _run(capsys, [
        "brain", "reindex", "declared_core", "--root", str(root), "--edges", "", "--db", db,
    ])
    assert rc == 0

    (root / "declared_core" / "README.md").write_text(
        "# declared_core\n\nSecond, updated summary.\n", encoding="utf-8",
    )
    rc, _ = _run(capsys, [
        "brain", "reindex", "declared_core", "--root", str(root), "--edges", "", "--db", db,
    ])
    assert rc == 0

    rc, out = _run(capsys, ["brain", "load", "declared_core", "--db", db])
    assert rc == 0 and "Second, updated summary" in out


# ── brain export (M6 file adapters) ─────────────────────────────────────────

def test_brain_export_unknown_project_exits_nonzero(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, [
        "brain", "export", "not-a-project", "--provider", "claude",
        "--into", str(tmp_path), "--db", db,
    ])
    assert rc == 1


def test_brain_export_into_explicit_dir(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude", "--into", str(target), "--db", db,
    ])
    assert rc == 0
    written = target / "CLAUDE.md"
    assert f"wrote {written}" in out
    assert written.read_text(encoding="utf-8").startswith("<!-- project_memory:begin -->")
    assert "# Context: alpha" in written.read_text(encoding="utf-8")


def test_brain_export_missing_target_dir_exits_nonzero(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude",
        "--into", str(tmp_path / "does-not-exist"), "--db", db,
    ])
    assert rc == 1


def test_brain_export_resolves_default_dir_from_root(tmp_path, capsys):
    db, root = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude", "--root", str(root), "--db", db,
    ])
    assert rc == 0
    assert (root / "alpha" / "CLAUDE.md").exists()


def test_brain_export_all_writes_three_files(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "all", "--into", str(target), "--db", db,
    ])
    assert rc == 0
    assert (target / "CLAUDE.md").exists()
    assert (target / "AGENTS.md").exists()
    assert (target / "GEMINI.md").exists()


def test_brain_export_dry_run_writes_nothing(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude", "--into", str(target),
        "--dry-run", "--db", db,
    ])
    assert rc == 0
    assert not (target / "CLAUDE.md").exists()
    assert "# Context: alpha" in out


def test_brain_export_dry_run_json(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude", "--into", str(target),
        "--dry-run", "--json", "--db", db,
    ])
    assert rc == 0
    d = json.loads(out)
    assert d == {
        "exported": False,
        "dry_run": True,
        "scope": "alpha",
        "provider": "claude",
        "files": [str(target / "CLAUDE.md")],
        "block": d["block"],
    }
    assert not (target / "CLAUDE.md").exists()


def test_brain_export_json_output(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, out = _run(capsys, [
        "brain", "export", "alpha", "--provider", "codex", "--into", str(target),
        "--json", "--db", db,
    ])
    assert rc == 0
    d = json.loads(out)
    assert d == {
        "exported": True,
        "dry_run": False,
        "scope": "alpha",
        "provider": "codex",
        "files": [str(target / "AGENTS.md")],
    }


def test_brain_export_records_a_provenance_episode(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    rc, _ = _run(capsys, [
        "brain", "export", "alpha", "--provider", "claude", "--into", str(target), "--db", db,
    ])
    assert rc == 0

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    exports = mem.recent(limit=5, kind="brain_export")
    assert len(exports) == 1
    assert exports[0]["tags"] == ["alpha", "claude"]
    mem.close()


def test_brain_export_rerun_preserves_hand_written_content(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (target / "CLAUDE.md").write_text("# My own notes\n\nDon't lose me.\n", encoding="utf-8")

    _run(capsys, ["brain", "export", "alpha", "--provider", "claude", "--into", str(target), "--db", db])
    _run(capsys, ["brain", "export", "alpha", "--provider", "claude", "--into", str(target), "--db", db])

    final = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Don't lose me." in final
    assert final.count("<!-- project_memory:begin -->") == 1


# ── brain menu (Cut 3) ───────────────────────────────────────────────────────

def _write_demo_pack(packs_dir, pack_id="demo", members=("alpha: the only member",)):
    packs_dir.mkdir(parents=True, exist_ok=True)
    member_lines = "\n".join(f"  - {m}" for m in members)
    (packs_dir / f"{pack_id}.pack.md").write_text(
        f"---\nkind: pack\nid: {pack_id}\nname: Demo pack\nmembers:\n{member_lines}\n---\ndo the thing.\n",
        encoding="utf-8",
    )


def test_brain_menu_json_lists_projects_and_packs(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_demo_pack(packs_dir)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    rc, out = _run(capsys, ["brain", "menu", "--db", db, "--json"])
    assert rc == 0
    items = json.loads(out)
    assert {"name": "alpha", "kind": "project", "label": ""} in items
    assert {"name": "demo", "kind": "pack", "label": "Demo pack"} in items


def test_brain_menu_select_by_name_project(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")

    rc, out = _run(capsys, ["brain", "menu", "--select", "alpha", "--db", db])
    assert rc == 0
    assert "# Context: alpha" in out


def test_brain_menu_select_by_name_pack(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    packs_dir = tmp_path / "packs"
    _write_demo_pack(packs_dir)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)

    rc, out = _run(capsys, ["brain", "menu", "--select", "demo", "--db", db])
    assert rc == 0
    assert "# Context: demo" in out and "scope=pack" in out


def test_brain_menu_select_by_number(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")

    rc, out = _run(capsys, ["brain", "menu", "--select", "1", "--db", db])
    assert rc == 0
    assert "# Context: alpha" in out  # the only known project, so item #1


def test_brain_menu_invalid_select_exits_nonzero(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")

    rc, out = _run(capsys, ["brain", "menu", "--select", "not-a-real-thing", "--db", db])
    assert rc == 1


def test_brain_menu_no_items_exits_nonzero(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db = str(tmp_path / "empty.db")
    ProjectMemory.open(db, PORTFOLIO_SCHEMA).close()
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")

    rc, out = _run(capsys, ["brain", "menu", "--db", db])
    assert rc == 1


def test_brain_menu_interactive_prompt(tmp_path, capsys, monkeypatch):
    from project_memory import pack as pack_module

    db, _ = _index_tiny_brain(tmp_path)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")

    rc, out = _run(capsys, ["brain", "menu", "--db", db])
    assert rc == 0
    assert "Projects:" in out and "1. alpha" in out
    assert "# Context: alpha" in out


def test_brain_menu_records_provenance_with_menu_trigger(tmp_path, capsys, monkeypatch):
    from project_memory import ProjectMemory, pack as pack_module
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", tmp_path / "empty-packs")

    rc, _ = _run(capsys, ["brain", "menu", "--select", "alpha", "--db", db])
    assert rc == 0

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    loads = mem.recent(limit=5, kind="brain_load")
    assert len(loads) == 1
    assert loads[0]["tags"] == ["alpha", "project", "menu"]
    mem.close()


# ── brain remember (M2) ──────────────────────────────────────────────────────

def test_brain_remember_requires_project_or_current(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "remember", "some decision", "--db", db])
    assert rc == 1


def test_brain_remember_rejects_unknown_project(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "remember", "x", "--project", "not-a-project", "--db", db])
    assert rc == 1


def test_brain_remember_defaults_to_crystallizing_a_fact(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "remember", "we chose SQLite", "--project", "alpha",
                            "--reason", "zero-ops", "--db", db])
    assert rc == 0
    assert "crystallized as fact" in out

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    assert mem.count()["facts"] == 1
    mem.close()


def test_brain_remember_no_auto_fact_logs_episode_only(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "remember", "the build broke again", "--project", "alpha",
                            "--no-auto-fact", "--db", db])
    assert rc == 0
    assert "episode only" in out

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    assert mem.count()["facts"] == 0
    assert mem.count()["episodes"] >= 1
    mem.close()


def test_brain_remember_current_detects_project(tmp_path, capsys, monkeypatch):
    db, root = _index_tiny_brain(tmp_path)
    monkeypatch.chdir(root / "alpha")
    rc, out = _run(capsys, ["brain", "remember", "a decision", "--current", "--db", db])
    assert rc == 0
    assert "remembered for alpha" in out


def test_brain_remember_supersedes_a_prior_fact(tmp_path, capsys):
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    old = mem.record_fact("we use SQLite", tags=["alpha", "session-memory"])
    mem.close()

    rc, out = _run(capsys, ["brain", "remember", "we migrated to Postgres", "--project", "alpha",
                            "--supersedes", old["id"], "--db", db])
    assert rc == 0

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    statuses = {r[0]: r[1] for r in mem.conn.execute("SELECT id, status FROM facts").fetchall()}
    assert statuses[old["id"]] == "superseded"
    mem.close()


def test_brain_remember_json_output(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "remember", "a decision", "--project", "alpha",
                            "--db", db, "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["remembered"] is True and data["project"] == "alpha" and data["fact_id"]


# ── brain ingest-memory (M2) ─────────────────────────────────────────────────

_MEMORY_FIXTURE = """---
name: aisle-10-deployed-live
description: "Aisle wedding co-pilot is deployed live on Vercel"
metadata:
  node_type: memory
  type: project
---

Aisle went live 2026-07-10 on Vercel.
"""


def _write_memory_fixture(memory_dir, filename="aisle.md", text=_MEMORY_FIXTURE):
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / filename).write_text(text, encoding="utf-8")


def test_brain_ingest_memory_requires_a_way_to_locate_the_dir(tmp_path, capsys):
    pytest.importorskip("yaml")
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "ingest-memory", "--db", db])
    assert rc == 1


def test_brain_ingest_memory_explicit_dir_is_unscoped_by_default(tmp_path, capsys):
    pytest.importorskip("yaml")
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "claude-memory"
    _write_memory_fixture(memory_dir)

    rc, out = _run(capsys, ["brain", "ingest-memory", "--memory-dir", str(memory_dir), "--db", db])
    assert rc == 0
    assert "ingested 1" in out and "unscoped" in out

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    assert mem.conn.execute("SELECT batch FROM episodes WHERE method='session_memory_ingest'").fetchone()[0] is None
    mem.close()


def test_brain_ingest_memory_project_flag_tags_batch(tmp_path, capsys):
    pytest.importorskip("yaml")
    from project_memory import ProjectMemory
    from project_memory.portfolio import PORTFOLIO_SCHEMA

    db, _ = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "claude-memory"
    _write_memory_fixture(memory_dir)

    rc, out = _run(capsys, ["brain", "ingest-memory", "--memory-dir", str(memory_dir),
                            "--project", "alpha", "--db", db])
    assert rc == 0
    assert "batch=alpha" in out

    mem = ProjectMemory.open(db, PORTFOLIO_SCHEMA)
    assert mem.conn.execute("SELECT batch FROM episodes WHERE method='session_memory_ingest'").fetchone()[0] == "alpha"
    mem.close()


def test_brain_ingest_memory_project_infers_dir(tmp_path, capsys, monkeypatch):
    pytest.importorskip("yaml")
    from project_memory import cli as cli_module

    db, _ = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "inferred-memory"
    _write_memory_fixture(memory_dir)
    monkeypatch.setattr(cli_module, "default_claude_memory_dir", lambda root: memory_dir)

    rc, out = _run(capsys, ["brain", "ingest-memory", "--project", "alpha", "--db", db])
    assert rc == 0
    assert "ingested 1" in out


def test_brain_ingest_memory_current_infers_project_and_dir(tmp_path, capsys, monkeypatch):
    pytest.importorskip("yaml")
    from project_memory import cli as cli_module

    db, root = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "inferred-memory"
    _write_memory_fixture(memory_dir)
    monkeypatch.setattr(cli_module, "default_claude_memory_dir", lambda root: memory_dir)
    monkeypatch.chdir(root / "alpha")

    rc, out = _run(capsys, ["brain", "ingest-memory", "--current", "--db", db])
    assert rc == 0
    assert "batch=alpha" in out


def test_brain_ingest_memory_missing_dir_returns_zero_gracefully(tmp_path, capsys):
    pytest.importorskip("yaml")
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "ingest-memory",
                            "--memory-dir", str(tmp_path / "does-not-exist"), "--db", db])
    assert rc == 0
    assert "ingested 0" in out


def test_brain_ingest_memory_types_override(tmp_path, capsys):
    pytest.importorskip("yaml")
    db, _ = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "claude-memory"
    _write_memory_fixture(memory_dir, "aisle.md", _MEMORY_FIXTURE)
    _write_memory_fixture(memory_dir, "user-note.md", _MEMORY_FIXTURE.replace("type: project", "type: user"))

    rc, out = _run(capsys, ["brain", "ingest-memory", "--memory-dir", str(memory_dir),
                            "--types", "project,user", "--db", db])
    assert rc == 0
    assert "ingested 2" in out


def test_brain_ingest_memory_json_output(tmp_path, capsys):
    pytest.importorskip("yaml")
    db, _ = _index_tiny_brain(tmp_path)
    memory_dir = tmp_path / "claude-memory"
    _write_memory_fixture(memory_dir)

    rc, out = _run(capsys, ["brain", "ingest-memory", "--memory-dir", str(memory_dir),
                            "--db", db, "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["ingested"] == 1 and data["project"] is None


# ── brain provenance: used / journey / unused (M4) ───────────────────────────

def _mount_pack(tmp_path, monkeypatch):
    """A one-member 'demo' pack, wired via DEFAULT_PACKS_DIR (as in the load tests)."""
    from project_memory import pack as pack_module
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    (packs_dir / "demo.pack.md").write_text(
        "---\nkind: pack\nid: demo\nmembers:\n  - alpha: the only member\n---\ndo the thing.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pack_module, "DEFAULT_PACKS_DIR", packs_dir)


def test_brain_load_stamps_session_visible_in_journey(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    _run(capsys, ["brain", "load", "alpha", "--db", db, "--session", "s1", "--trigger", "startup"])
    rc, out = _run(capsys, ["brain", "journey", "--session", "s1", "--db", db, "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["session"] == "s1"
    assert data["events"][0]["scope"] == "alpha"
    assert data["events"][0]["trigger"] == "startup"


def test_brain_used_marks_a_loaded_scope(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    _run(capsys, ["brain", "load", "alpha", "--db", db, "--session", "s1"])
    rc, out = _run(capsys, ["brain", "used", "alpha", "--db", db, "--session", "s1"])
    assert rc == 0
    assert "marked 'alpha' used" in out
    # now it's no longer in the unused report
    rc, out = _run(capsys, ["brain", "unused", "--db", db, "--session", "s1"])
    assert rc == 0
    assert "no unused loads" in out


def test_brain_used_rejects_a_never_loaded_scope(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "used", "alpha", "--db", db])
    assert rc == 1  # alpha exists as a project but was never loaded → nothing to mark used


def test_brain_used_requires_scope_or_current(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, _ = _run(capsys, ["brain", "used", "--db", db])
    assert rc == 1


def test_brain_used_current_detects_and_marks(tmp_path, capsys, monkeypatch):
    db, root = _index_tiny_brain(tmp_path)
    monkeypatch.chdir(root / "alpha")
    _run(capsys, ["brain", "load", "--current", "--db", db, "--session", "s1"])
    rc, out = _run(capsys, ["brain", "used", "--current", "--db", db, "--session", "s1"])
    assert rc == 0
    assert "marked 'alpha' used" in out


def test_brain_unused_reports_loaded_but_never_used(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    _run(capsys, ["brain", "load", "alpha", "--db", db, "--session", "s1"])
    rc, out = _run(capsys, ["brain", "unused", "--db", db, "--session", "s1", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert [u["scope"] for u in data["unused"]] == ["alpha"]


def test_brain_unused_packs_only(tmp_path, capsys, monkeypatch):
    db, _ = _index_tiny_brain(tmp_path)
    _mount_pack(tmp_path, monkeypatch)
    _run(capsys, ["brain", "load", "alpha", "--db", db, "--session", "s1"])   # a project
    _run(capsys, ["brain", "load", "demo", "--db", db, "--session", "s1"])    # a pack
    rc, out = _run(capsys, ["brain", "unused", "--packs", "--db", db, "--session", "s1", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert [u["scope"] for u in data["unused"]] == ["demo"]
    assert data["unused"][0]["scope_kind"] == "pack"


def test_brain_journey_story_output(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    _run(capsys, ["brain", "load", "alpha", "--db", db, "--session", "s1", "--trigger", "startup"])
    _run(capsys, ["brain", "used", "alpha", "--db", db, "--session", "s1"])
    rc, out = _run(capsys, ["brain", "journey", "--session", "s1", "--db", db])
    assert rc == 0
    assert "# Journey — session s1" in out
    assert "loaded project 'alpha'  (via startup)" in out
    assert "used 'alpha'" in out


def test_brain_journey_empty_all_sessions(tmp_path, capsys):
    db, _ = _index_tiny_brain(tmp_path)
    rc, out = _run(capsys, ["brain", "journey", "--db", db])
    assert rc == 0
    assert "all sessions" in out
    assert "No load/use/export provenance recorded" in out
