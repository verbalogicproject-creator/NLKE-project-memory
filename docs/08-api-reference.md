# 08 · API reference

Every public symbol exported from `project_memory`. Import them from the top-level
package (`from project_memory import …`).

---

## `ProjectMemory`

The object most callers use. Owns a SQLite connection + a `MemorySchema` + the
compiled corpus.

### Constructors

- **`ProjectMemory.open(path=":memory:", schema=None, *, embedder=None, dimensions=None) -> ProjectMemory`**
  Open (or create) a memory. `path` is a SQLite file or `":memory:"`. `schema`
  defaults to `MemorySchema()`. `embedder` enables optional dense recall.
  `dimensions` is a custom `DimensionSchema` (default: the 12-dim palette).
- **`ProjectMemory(conn, schema=None, *, embedder=None, dimensions=None)`** — the
  same, from an existing connection.

### Writing

- **`.remember(content, *, kind="general", session_id=None, batch=None, tags=None, metadata=None, method="manual", id=None, created_at=None, auto_fact=False, reason=None) -> dict`**
  Append an episode. Returns `{"id", "kind", "fact_id"}`. Raises `ValueError` on an
  unknown `kind` or empty content. With `auto_fact=True`, also records a fact.
- **`.record_fact(claim, *, reason=None, source_episode_id=None, tags=None, method="manual", id=None, created_at=None, supersedes=None) -> dict`**
  Write a fact; optionally supersede another. Returns `{"id", "supersedes"}`.
- **`.invalidate_fact(fact_id, *, updated_at=None) -> bool`** — mark a fact
  invalidated. Returns whether a row changed.

### Reading

- **`.recall(text, *, limit=10, table=None, use_intent=True, hybrid=True, verbose=False) -> list[dict]`**
  Search memory. `table` restricts to `"episodes"`/`"facts"`. Hits carry
  `table`, `id`, the row columns, `rrf_sources`, a fused score, and `dense_score`
  if dense ran. `verbose` keeps the per-dimension `dimensions` vector.
- **`.ask(question, *, name=None, limit=8) -> AnswerShape`** — answer a question.
  `name` forces an ask; `None` routes by intent.
- **`.understand(question) -> Understanding`** — classify intent + extract entities
  (pure).
- **`.synthesize(a, b, *, persist=False) -> SynthesisResult`** — MUD-check a merge.
  `a`/`b` are strings or `Fact`s. `persist` writes to the audit table.
- **`.recent(limit=10, *, kind=None) -> list[dict]`** — most recent episodes,
  newest first.
- **`.count() -> dict`** — `{"episodes": N, "facts": M}` (active facts only).
- **`.asks() -> list[str]`** — the available ask names.
- **`.close()`** — close the connection.

---

## Schema

- **`MemorySchema(kinds=DEFAULT_KINDS, episode_table="episodes", fact_table="facts", small_corpus_threshold=100, schema_version=1)`**
  The declaration. Compiles to a two-table `declared_core.CorpusSchema`.
  - `.validate_kind(kind)` — raise if not declared.
  - `.episode_source()` / `.fact_source()` → `declared_core.SourceTable`.
  - `.fact_link()` → the `declared_core.Link`.
  - `.corpus_schema(*, dimensions=None)` → the compiled `CorpusSchema`.
- **`DEFAULT_KINDS`** — `("decision", "gotcha", "insight", "invariant", "task", "milestone", "general")`.
- **`FACT_STATUSES`** — `("active", "superseded", "invalidated")`.
- **`SCHEMA_VERSION`** — the current on-disk schema version (int).

### Presets

- **`GENERIC`**, **`AGENT`**, **`RESEARCH`** — ready `MemorySchema` values.
- **`PRESETS`** — `{"generic": …, "agent": …, "research": …}`.

---

## Writing (functional form)

The same operations as the `ProjectMemory` methods, as free functions taking
`(conn, schema, …)`: **`remember`**, **`record_fact`**, **`invalidate_fact`**. Use
these when you manage the connection yourself.

---

## Natural language

- **`understand(question) -> Understanding`** — intent + entities (pure).
- **`extract_entities(text) -> list[str]`** — quoted phrases + identifiers +
  proper nouns.
- **`Understanding`** — dataclass `{question, intent, confidence, entities}` +
  `.to_dict()`.

---

## Asks

- **`AnswerShape`** — the uniform ask result: `{ask, question, answer, confidence,
  evidence, caveats, suggested_next, trace_id}` + `.to_dict()`.
- **`ASK_NAMES`** — the eleven registered ask names, in order.
- **`run_ask(name, question, retrieve, *, understanding=None) -> AnswerShape`** —
  dispatch to an ask directly.
- **`route_intent(intent) -> str`** — the intent → ask-name mapping.
- **`register_ask(name)`** — decorator to register a new ask.
- **`build_evidence(hits, max_items=6) -> list[dict]`** — trim hits to evidence.

---

## Dimensions

- **`MEMORY_DIMENSIONS`** — the curated 12-dim `DimensionSchema`.
- **`custom_dimensions(*dims) -> DimensionSchema`** — build a custom palette.
- (`project_memory.dimensions` also exposes `score`, `overall`, `DimensionDef`,
  `register_dimension_scorer`.)

---

## synthesis-mud

- **`synthesize(a, b, *, synthesis_threshold=0.4, multi_dim_threshold=0.6) -> SynthesisResult`**
  Assess and merge (or refuse). `a`/`b` are `str` or `Fact`.
- **`detect_mud(a, b, *, synthesis_threshold=0.4, multi_dim_threshold=0.6) -> MudVerdict`**
  The 6-layer check over two `Fact`s.
- **`compatibilities(a, b) -> dict`** — the five axis compatibilities.
- **`Fact`** — dataclass with the 5+1 axes; **`Fact.assess(statement, **overrides)`**
  infers them (overridable per axis).
- **`SynthesisResult`** — `{verdict, fact_a, fact_b, synthesized, confidence,
  mud_reason, compatibilities, certainty_preserved, bridging_axes}` +
  `.is_mud`, `.to_dict()`.
- **`MudVerdict`** — `{is_mud, reasons, compatibilities, failing_layer}` + `.to_dict()`.
- **`AXES`** — `("texture", "lighting", "composition", "contrast", "method")`.
- **`install_synthesis_tables(conn)`** / **`record_synthesis(conn, result, *, created_at=None, id=None) -> str`**
  Optional persistence of the audit trail.

---

## Optional dense

- **`Embedder`** — the type alias `Callable[[str], Sequence[float] | None]`.
- **`http_embedder(url=None, *, model=None, query_prefix=None, timeout=15.0) -> Embedder`**
  A stdlib embedder for an OpenAI-style endpoint.
- **`dense_available() -> bool`** — is numpy importable?

---

## Demo + store

- **`build_demo(path=":memory:", *, embedder=None) -> ProjectMemory`** — the
  packaged, deterministic demo memory.
- **`demo_corpus_dir() -> Path`** — where the demo JSON lives.
- **`hash_embedder(dim=64) -> Embedder`** — a deterministic offline embedder.
- **`connect(path=":memory:") -> sqlite3.Connection`** — a configured connection.

Next: [09 · CLI reference](09-cli-reference.md).
