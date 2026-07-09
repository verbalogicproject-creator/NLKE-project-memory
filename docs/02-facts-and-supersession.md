# 02 · Facts and supersession

Episodes are what happened. **Facts** are what you concluded — and conclusions
change. project_memory updates a belief without destroying the record of the old
one.

## Record a fact

```python
mem.record_fact("Search is best-effort.", reason="no ranking yet",
                tags=["search"], id="f-search")
```

A fact has a `claim`, an optional `reason`, and optional `tags`. It may point back
at the episode it came from (`source_episode_id`) — `remember(..., auto_fact=True)`
sets that link for you.

## Supersede, don't delete

When the belief changes, write the new fact and mark the old one superseded:

```python
mem.record_fact("Search runs fully offline via FTS5 + BM25.",
                supersedes="f-search")
```

Now:

- the **new** fact is `active` and searchable,
- the **old** fact is `status='superseded'`, with `superseded_by` pointing at the
  new one — retained, but out of recall.

```python
mem.count()["facts"]     # counts only active facts
mem.recall("search")     # returns the new fact, never the superseded one
```

The `facts` source declares `where = "status = 'active'"`, so retrieval only ever
sees live facts — the history stays in the table for audit, not for search.

## Invalidate (it was wrong, not merely outdated)

```python
mem.invalidate_fact("f-old")     # status → 'invalidated'
```

Use `invalidate` when a fact was *mistaken* (distinct from being *superseded* by a
newer truth). Both drop it out of recall; the distinction is recorded for you.

## The lifecycle

```
              record_fact(claim)
                     │
                     ▼
                 [active] ──── supersedes=X ────►  X becomes [superseded]
                     │                              (superseded_by → new id)
                     └──── invalidate_fact ─────►  [invalidated]
```

Only `active` facts are ever returned by recall or the asks. This is what lets a
long-lived memory stay *correct* without becoming *lossy*.

Next: [03 · The natural-language front door](03-natural-language-front-door.md).
