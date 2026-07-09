import json

from project_memory import build_demo
from project_memory.demo import demo_corpus_dir, hash_embedder


def test_demo_counts():
    assert build_demo().count() == {"episodes": 8, "facts": 5}


def test_demo_is_deterministic():
    a = build_demo()
    b = build_demo()
    ra = a.conn.execute("SELECT id, content, kind, created_at FROM episodes ORDER BY id").fetchall()
    rb = b.conn.execute("SELECT id, content, kind, created_at FROM episodes ORDER BY id").fetchall()
    assert ra == rb
    fa = a.conn.execute("SELECT id, claim, created_at FROM facts ORDER BY id").fetchall()
    fb = b.conn.execute("SELECT id, claim, created_at FROM facts ORDER BY id").fetchall()
    assert fa == fb


def test_demo_corpus_json_is_valid():
    data = json.loads((demo_corpus_dir() / "demo_memory.json").read_text())
    assert data["episodes"] and data["facts"]
    assert all("id" in e and "created_at" in e for e in data["episodes"])


def test_demo_recall_deterministic():
    assert [h["id"] for h in build_demo().recall("offline search")] == \
           [h["id"] for h in build_demo().recall("offline search")]


def test_hash_embedder_deterministic():
    e = hash_embedder(32)
    assert e("hello world") == e("hello world")
    assert e("") is None
    assert len(e("some text here")) == 32


def test_demo_has_a_mud_pair():
    # The demo ships a security↔business fact pair for the synthesis-mud demo.
    mem = build_demo()
    r = mem.synthesize(
        "From a security perspective, storing access tokens in plaintext is an unacceptable risk.",
        "From a business perspective, the legacy plaintext token store was cheap and worked fine.")
    assert r.verdict == "refuse"
