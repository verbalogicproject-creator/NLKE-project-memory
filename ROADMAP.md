# Roadmap

project_memory 0.1.0 ships a complete, honest core: a two-table episodic + factual
memory, hybrid recall, eleven asks, the synthesis-mud epistemic guard, a curated
dimension palette, a CLI, and an MCP server. This file records what is
deliberately **not** shipped yet, and why — so the README never overclaims.

## Not shipped (by design), candidates for later

### The remaining five asks
v0.1 ships a curated eleven asks. Five more from the source project's
`intent_query.py` are roadmapped: **`learn`** (assemble an ordered learning path),
**`explore_smart`** (guided expansion from an anchor), **`roadmap`** (topologically
ordered steps to a goal), **`alternatives`**, and **`compatible_with`**. The last
three assume a dependency/tool graph; on an episode+fact memory they need real
generalization (and `compatible_with` overlaps synthesis-mud). They land when the
generalization is genuinely useful, not merely present.

### Persistent / ANN dense index
`build_dense_index` builds an in-memory `NumpyVectorIndex` (brute-force cosine),
rebuilt per process and invalidated on write. That is right for the
thousands-of-rows memories this targets. A persisted vector store + ANN backend
(behind the same `DenseIndex` protocol) would avoid re-embedding for large,
long-lived memories.

### Dense over episodes+facts surfaces, chunked
The dense surface embeds each row's title/claim/tags as one text. Long episodes
would benefit from body chunking (multiple vectors per row) once the persistent
index lands.

### Recency as a first-class dimension
Memory is time-shaped: newer episodes often matter more. A deterministic
`recency` dimension (relative to the corpus, not wall-clock) is a natural addition
to the palette. It is intentionally *not* in v0.1 because a naive wall-clock
scorer would break determinism; doing it right needs a corpus-relative reference.

### Ingestion beyond text
Episodes/facts are written programmatically. A future release could ingest from
Markdown/JSON logs via the shared `universal_parser` (the same backend planned for
`frontmatter_rag`), behind the existing `remember`/`record_fact` API.

### synthesis-mud → its own package
The guard is incubated here. On a **second consumer** (e.g. multi-agent knowledge
merge, or a standalone fact-validation service) it graduates to its own repo,
imported by both. Until then it lives in `project_memory.synthesis_mud`.

### Richer axis assessment
The 5+1 axis assessor is a transparent marker-word heuristic — good enough to
catch the common MUD patterns, and every axis is overridable per `Fact`. A future
version could offer an optional LLM-backed assessor (kept behind the same `Fact`
interface, so the deterministic default never regresses).

## Principles for anything we add

- **Optional stays optional.** BM25 + structural must always work offline, no
  extra deps, deterministically.
- **Declared over inferred.** Prefer readable tables and typed axes to learned
  black boxes.
- **Prove before you claim.** A feature reaches the README only when it's
  demonstrable and tested; until then it lives here.
- **Retrieval math goes to `declared_core`.** This repo stays a thin memory layer.
