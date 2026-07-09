# 00 · The mental model

project_memory answers one question well: **"what does this project know, and can
I trust a new conclusion drawn from it?"** To do that it keeps two kinds of thing
and guards one operation.

## Two kinds of thing

**Episodes** are *events* — things that happened, in the project's own words.
"We chose SQLite over Postgres." "The FTS trigger crashed on a NULL." They are
**append-only**: if something happens twice, you record it twice. An episode has a
`kind` (decision, gotcha, insight, …), some `tags`, and a timestamp.

**Facts** are *durable claims* crystallized from episodes. "SQLite is the store of
record." A fact has a `claim`, an optional `reason`, and a **supersession chain**:
when reality changes you write a new fact that supersedes the old one — you never
delete history, you retire it.

```
   episode  ─────────────────────────►  fact
   "we chose SQLite over Postgres"      "SQLite is the store of record"
   kind=decision                        reason="local-first, zero-ops"
   (append-only, what happened)         (supersedable, what we believe)
```

Why two tables? Because events and beliefs have different lifecycles. Merge them
and you lose either the audit trail or the ability to correct a belief. Keeping
them separate — and *linking* them — is what lets recall say "here's the belief,
and here's the event it came from".

## One engine underneath

project_memory doesn't rank anything itself. It compiles those two tables into a
`declared_core` **corpus** (two searchable tables + one link) and hands every
query to that engine: BM25 over the text, structural expansion along the
`kind`/`tag` clusters *and* the episode→fact link, an intent classifier that picks
fusion weights, and a curated dimension signal. All deterministic, all explainable.

> **declared > inferred.** You wrote the structure down (what's an episode, what's
> a fact, how they link, what the kinds are). That declaration *is* the index — so
> you get determinism, speed, offline operation, and `$0` cost, with no model in
> the retrieval loop.

## One guarded operation: synthesis

The thing most memory systems get wrong is **synthesis** — combining two facts into
a third. Naively, synthesis is additive: take A, take B, produce C. But some
combinations are clean (blue + yellow → green) and some are **MUD** (mix
everything → brown). Two facts whose *qualities* clash — an opinion fused with a
fact, a security view fused with a business view, a certain deduction fused with a
shaky analogy — produce a synthesis that *looks* like progress but has lost
coherence.

`synthesize(a, b)` assesses each fact along **5 + 1 axes**, runs a **6-layer**
compatibility check, and returns **clean / bridge / refuse** with a *calibrated*
confidence and a reason. It refuses to muddy your memory. This is the one thing an
LLM can't be trusted to police in its own memory, so a deterministic guard does it.

## The shape of the API

```python
mem = ProjectMemory.open("memory.db")
mem.remember(text, kind=…)      # write an event
mem.record_fact(claim, …)       # write / supersede a belief
mem.recall(query)               # search both, ranked + explainable
mem.ask(question)               # a composed answer with cited evidence
mem.synthesize(a, b)            # the epistemic guard
```

Next: [01 · Remember and recall](01-remember-and-recall.md).
