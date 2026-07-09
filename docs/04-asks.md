# 04 · The asks

An **ask** is a named question type. It maps a question to a retrieval, ranks and
filters the hits, and composes a terse answer with cited evidence. Every ask
returns the same `AnswerShape`, so callers (and the MCP layer) treat them
uniformly.

```python
res = mem.ask("why did timestamps reorder?", name="why_not")
res.answer          # 'known issue: Gotcha: created_at was stored as a naive ...'
res.confidence      # 0.0–0.9
res.evidence        # up to 6 cited rows: {table, id, kind, preview, score, ...}
res.caveats         # what retrieval couldn't resolve
res.suggested_next  # follow-up asks to try
res.to_dict()       # the full contract, JSON-ready
```

## Routing: intent → ask

`mem.ask(question)` with no `name` classifies the intent and routes to an ask:

| intent | → ask |
|---|---|
| `exact_match` | `what_for` |
| `capability_check` | `can_i` |
| `debugging` | `debug` |
| `workflow` | `how_do_i` |
| `comparison` | `how_does_connect` |
| `goal_based` | `recommend` |
| `exploratory` | `snapshot` |
| `semantic` (fallback) | `recommend` |

Force any ask with `name=`. List them with `mem.asks()`.

## The eleven asks

| ask | answers | how it works |
|---|---|---|
| `why_not` | "why not X / why doesn't X work?" | boosts failure terms; prefers `gotcha`/`invariant` evidence |
| `can_i` | "can I / does it X?" | leans yes/no/partial from affirmative vs negative language |
| `how_do_i` | "how do I X?" | prefers crystallized facts over raw episodes |
| `what_for` | "what is X for?" | the closest description |
| `route` | "where does this belong?" | the dominant memory *kind* for the topic |
| `how_does_connect` | "how does X connect to Y?" | the item that bridges two concepts (set intersection) |
| `snapshot` | "give me the lay of the land around X" | aggregates the 12 dimension scores over the top hits |
| `recommend` | "given this context, what's relevant?" | surfaces the top fact + top decision |
| `similar_to` | "what's similar to X?" | nearest memory to an anchor, annotated with shared tags |
| `debug` | "help with this issue" | pairs recorded gotchas with a matching fix |
| `optimize_for` | "best memory for GOAL, optimized for CRITERIA" | re-ranks by one declared dimension |

## optimize_for and criteria

`optimize_for` re-ranks recall by a single dimension chosen from the question:

```python
mem.ask("search notes optimized for durable", name="optimize_for")
# criteria word 'durable' → dimension 'storage_tier'; the top evidence is
# annotated with its storage_tier score.
```

Criteria words map to dimensions (`durable`→`storage_tier`, `precise`→
`match_precision`, `relevant`→`semantic_coverage`, `reliable`→`error_recovery`,
`broad`→`generative_scope`, `connected`→`synthesis_potential`); a literal
dimension name works too; the default is relevance.

## The five roadmapped asks

`learn`, `explore_smart`, `roadmap`, `alternatives`, and `compatible_with` have
reference implementations in the source project but are **not** shipped in v0.1 —
several assume a dependency graph and need real generalization for an episode+fact
memory. See [ROADMAP.md](../ROADMAP.md).

## Adding your own ask

```python
from project_memory.asks import register, AnswerShape

@register("blamestorm")
def blamestorm(question, retrieve, u):
    hits = retrieve(question + " regression broke", limit=8)
    ...
    return AnswerShape("blamestorm", question, answer, confidence, evidence)
```

Then add it to `ASK_NAMES` and, if it should auto-route, to `_INTENT_ROUTES`.

Next: [05 · Dimensions](05-dimensions.md).
