"""Example 04 — declare your own episode taxonomy.

The one project-specific knob is the episode ``kinds`` vocabulary. Declare it and
ingestion validates against it. Presets bundle common vocabularies.

    python examples/04_custom_schema.py
"""

from project_memory import MemorySchema, ProjectMemory
from project_memory.presets import RESEARCH

# A hand-declared taxonomy.
schema = MemorySchema(kinds=("hypothesis", "experiment", "result", "general"))
mem = ProjectMemory.open(schema=schema)
mem.remember("Caching the embedder cut recall latency 4x.", kind="result")

# Unknown kinds fail loud, rather than silently mis-indexing.
try:
    mem.remember("...", kind="decision")   # not in this schema
except ValueError as e:
    print("rejected unknown kind:", str(e)[:60])

# A bundled preset (research log) — note the 'contradiction' kind, a natural
# feed for synthesis-mud.
research = ProjectMemory.open(schema=RESEARCH)
print("research kinds:", ", ".join(research.schema.kinds))

assert mem.count()["episodes"] == 1
assert "contradiction" in research.schema.kinds

# ── Verify your build ────────────────────────────────────────────────────────
# The custom schema should accept 'result' and reject 'decision'.
print("Verify your build: ok")
