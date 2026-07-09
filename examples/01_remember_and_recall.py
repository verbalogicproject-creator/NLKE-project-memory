"""Example 01 — remember episodes + facts, then recall them.

The two write paths (episodes = events, facts = durable claims) and the one read
path (hybrid recall across both, joined by the episode→fact link).

    python examples/01_remember_and_recall.py
"""

from project_memory import ProjectMemory

mem = ProjectMemory.open()  # in-memory; pass a path to persist

# Episodes are events. auto_fact also crystallizes a durable claim from one.
mem.remember("We chose SQLite over Postgres for the local-first store.",
             kind="decision", tags=["storage"], auto_fact=True,
             reason="zero-ops, single-file backups")
mem.remember("FTS5 triggers crash on NULL columns — coalesce every value to ''.",
             kind="gotcha", tags=["fts5", "sqlite"])

# Facts can also be written directly.
mem.record_fact("Search runs fully offline.", reason="FTS5 + BM25, no network",
                tags=["search"])

print("counts:", mem.count())
hits = mem.recall("sqlite storage")
print(f"recall('sqlite storage') → {len(hits)} hits")
for h in hits[:3]:
    print(f"  [{h['table']:>8}] {(h.get('content') or h.get('claim'))[:70]}")

assert mem.count()["episodes"] == 2
assert mem.count()["facts"] == 2          # one auto_fact + one direct
assert any(h["table"] == "facts" for h in hits)

# ── Verify your build ────────────────────────────────────────────────────────
# You should see 2 episodes / 2 facts, and the recall should surface both an
# episode and a fact about SQLite.
print("Verify your build: ok")
