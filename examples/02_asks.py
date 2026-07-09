"""Example 02 — the natural-language ask surface.

`ask(question)` classifies the intent, routes to one of eleven asks, and composes
a terse answer with cited evidence. `ask(question, name=...)` forces a specific
ask. Every ask returns the same AnswerShape.

    python examples/02_asks.py
"""

from project_memory import build_demo

mem = build_demo()  # the packaged Orchard demo memory

# Intent-routed: "why ..." → the why_not ask.
a = mem.ask("why did we store timestamps in UTC?", name="why_not")
print(f"[{a.ask}] {a.answer[:90]}")
print(f"  confidence={a.confidence:.2f}  evidence={len(a.evidence)}")

# A few asks by name.
for name, q in [
    ("can_i", "can I search offline?"),
    ("optimize_for", "search notes optimized for durable"),
    ("how_does_connect", "how does FTS5 connect to offline search"),
]:
    r = mem.ask(q, name=name)
    print(f"[{r.ask}] {r.answer[:90]}")

print("\navailable asks:", ", ".join(mem.asks()))

assert a.ask == "why_not"
assert len(mem.asks()) == 11
assert a.confidence > 0

# ── Verify your build ────────────────────────────────────────────────────────
# You should see the why_not ask surface the UTC/timezone gotcha, and eleven asks
# listed.
print("Verify your build: ok")
