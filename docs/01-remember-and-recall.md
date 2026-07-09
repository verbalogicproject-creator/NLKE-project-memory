# 01 · Remember and recall

The running example for these chapters is a small notes app called **Orchard**.
Everything here is what `build_demo()` sets up — you can follow along against the
demo memory or your own.

## Remember an episode

```python
from project_memory import ProjectMemory

mem = ProjectMemory.open()   # in-memory for the tutorial

mem.remember("We chose SQLite FTS5 + BM25 for note search so it works offline.",
             kind="decision", tags=["search", "offline"])
```

`remember` appends an episode. Required: the text. Common options:

| arg | meaning |
|---|---|
| `kind=` | the episode kind; must be in the schema taxonomy (default `general`) |
| `tags=` | a list of labels (structural neighbours share tags) |
| `batch=` | a grouping label (e.g. a sprint / session) |
| `auto_fact=True` | also crystallize this as a fact (with `reason=`) |
| `id=`, `created_at=` | set explicitly for deterministic seeds/tests |

Episodes are **append-only**. Remembering the same event twice records two
episodes — that's correct, it happened twice.

## Recall

```python
for h in mem.recall("offline search"):
    print(h["table"], h["id"], h.get("content") or h.get("claim"))
```

`recall` searches **both** tables and fuses the results. Each hit is a dict with:

- `table` + `id` — where it came from,
- the row's columns (`content` for episodes; `claim`/`reason` for facts),
- `rrf_sources` — which signals surfaced it (`bm25`, `structural`, `dense`, `rules`),
- a fused score (`rrf_score` or `weighted_score`), and `dense_score` if dense ran.

### Narrowing

```python
mem.recall("offline", table="facts")     # only facts
mem.recall("sqlite", limit=5)            # top 5
mem.recall("sqlite", verbose=True)       # keep the per-dimension `dimensions` vector
```

### Recent, count

```python
mem.recent(limit=5)                # newest episodes first
mem.recent(kind="gotcha")          # newest gotchas
mem.count()                        # {'episodes': N, 'facts': M}
```

## Why a match came back

Because retrieval is declared, every hit is explainable. A fact can surface not
because it matched your words but because the *episode it was crystallized from*
matched — the declared episode→fact link expands structurally. That's the payoff
of two linked tables over one flat store.

Next: [02 · Facts and supersession](02-facts-and-supersession.md).
