"""Example 05 — the optional dense signal degrades to nothing.

Dense (semantic) recall is a booster, never a dependency. With no embedder — or a
dead one, or no numpy — recall is byte-identical to pure lexical. This is the
"AI-optional, degrades to AI-less" contract, shared across the whole family.

    python examples/05_dense_optional.py
    python examples/05_dense_optional.py   # (install .[dense] to exercise the live path)
"""

from project_memory import build_demo, dense_available, hash_embedder

QUERY = "timezone bug"

no_embedder = [h["id"] for h in build_demo().recall(QUERY)]
dead_embedder = [h["id"] for h in build_demo(embedder=lambda t: None).recall(QUERY)]

print("numpy available:", dense_available())
print("no-embedder    top:", no_embedder[:3])
print("dead-embedder  top:", dead_embedder[:3])
assert no_embedder == dead_embedder, "a dead embedder must not change results"

if dense_available():
    live = [h["id"] for h in build_demo(embedder=hash_embedder()).recall(QUERY)]
    print("live-embedder  top:", live[:3])
    assert live, "the live dense path should still return hits"
else:
    print("(install project-memory[dense] to exercise the live dense path)")

# ── Verify your build ────────────────────────────────────────────────────────
# The no-embedder and dead-embedder result orders must be identical.
print("Verify your build: ok")
