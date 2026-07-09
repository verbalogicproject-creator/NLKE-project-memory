# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-09

First release. A declared, AI-optional project memory over `declared_core`.

### Added

- **Two-table memory model** — `episodes` (append-only events) + `facts`
  (durable, supersedable claims), compiled to a `declared_core.CorpusSchema`
  (two `SourceTable`s joined by a `Link`) via `MemorySchema`.
- **Writing** — `remember()` (kind-validated, append-only), `record_fact()` with
  a supersession chain, `auto_fact`, `invalidate_fact()`.
- **Hybrid recall** — `ProjectMemory.recall()` over both tables with optional
  single-table filtering, delegating to `declared_core.hybrid_query`.
- **Natural-language front door** — `understand()` (intent + entity extraction).
- **Eleven asks** — `why_not`, `can_i`, `how_do_i`, `what_for`, `route`,
  `how_does_connect`, `snapshot`, `recommend`, `similar_to`, `debug`,
  `optimize_for`, all returning one `AnswerShape`, with declared intent routing.
- **synthesis-mud** — the epistemic guard: `Fact.assess`, the five compatibility
  matrices, a 6-layer MUD detector, and `synthesize()` returning
  clean / bridge / refuse with a calibrated confidence. Optional persistence to a
  `synthesis_facts` audit table.
- **Dimensions** — the curated 12-dimension `MEMORY_DIMENSIONS` palette (the
  proven `declared_core.DEFAULT`), with a `custom()` builder.
- **Optional dense recall** — inject any `str -> Sequence[float] | None` embedder;
  `http_embedder()` for a local OpenAI-style endpoint. Degrades byte-identically
  to lexical when absent.
- **CLI** — `project-memory {demo,remember,record,recall,ask,synthesize,recent,asks,kinds,dims}`,
  every subcommand with `--json`.
- **Presets** — `generic`, `agent`, `research` schemas.
- **MCP server** — a stdlib JSON-RPC 2.0 example exposing memory to Claude Code.
- **Docs + examples** — numbered chapters `00–10`, five self-verifying examples,
  a zero-setup demo memory, and 97 tests.

### Known limits (see [ROADMAP.md](ROADMAP.md))

- The five "learn / explore_smart / roadmap / alternatives / compatible_with"
  asks are roadmapped, not shipped.
- The synthesis-mud axis assessor is a transparent heuristic (override any axis
  explicitly for precision); a persistent/ANN dense index is future work.

[0.1.0]: https://github.com/verbalogicproject-creator/NLKE-project-memory/releases/tag/v0.1.0
