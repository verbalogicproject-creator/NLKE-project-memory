import json

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
