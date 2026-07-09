# 03 · The natural-language front door

Before project_memory retrieves anything, it *understands* the question: what kind
of question is it (the **intent**), and what concrete things does it name (the
**entities**). Both are regex — no model, no network, fully explainable. This is
"route, don't search": the intent picks *how* to recall; the entities show *what*
was understood.

## understand()

```python
from project_memory import understand

u = understand("why did we drop Postgres?")
u.intent       # e.g. 'debugging'  (one of declared_core's eight intents)
u.confidence   # 0.9 / 0.5 / 0.3 depending on how it matched
u.entities     # ['Postgres']
```

`Understanding` is a small dataclass (`question`, `intent`, `confidence`,
`entities`) with `.to_dict()`. It is **pure** — no I/O, deterministic.

## The eight intents

The classifier lives in `declared_core`. The intents are: `exact_match`,
`capability_check`, `debugging`, `workflow`, `comparison`, `goal_based`,
`exploratory`, and `semantic` (the fallback). Each maps to a different set of
fusion weights, so *how* your memory is ranked adapts to *what you asked*.

## Entity extraction

`extract_entities(text)` pulls the concrete things a question names, in three
passes, de-duplicated case-insensitively:

1. **Quoted phrases** — `"reciprocal rank fusion"`, `` `created_at` ``.
2. **Code-ish identifiers** — `snake_case`, `dotted.paths`, `CamelCase`, `ACRONYM`,
   `FTS5`.
3. **Capitalized proper nouns** — `Postgres`, `Redis`, `Python` — *skipping* the
   sentence-initial word and question stopwords, so "Why did we drop Postgres?"
   yields `Postgres`, not `Why`.

```python
from project_memory import extract_entities
extract_entities('how does "rank fusion" use FTS5 in created_at with Postgres?')
# ['rank fusion', 'FTS5', 'created_at', 'Postgres']
```

## Where it's used

The `ask` layer (next chapter) sits on this front door: it classifies the intent,
routes to the matching ask, and some asks (e.g. `how_does_connect`, `similar_to`)
use the extracted entities directly. You can also call `understand` yourself to
build custom routing.

Next: [04 · The asks](04-asks.md).
