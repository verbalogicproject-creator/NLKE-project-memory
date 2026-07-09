# Release notes — project_memory 0.1.0

*2026-07-09*

`project_memory` is the memory layer of the declared-retrieval family: a
local-first, AI-optional store of a project's **episodes** (what happened) and
**facts** (what you concluded), recalled in natural language — with a
deterministic epistemic guard that **refuses to synthesize contradictory facts**.

## Why it exists

Agents forget between sessions, and the usual fix — dump everything into a vector
store — has two failure modes: it is opaque (why did *that* come back?), and it
will happily merge two facts that contradict each other, laundering opinion into
fact and inflating confidence. `project_memory` takes the other path:

- **Declared, not inferred.** Two plain SQLite tables + FTS5, searched by
  `declared_core` (BM25 + structural + intent fusion). Every hit is explainable.
- **Guarded synthesis.** The colour-theory *MUD* check assesses each fact along
  5+1 axes and refuses (or bridges) a merge that would lose coherence — the one
  thing an LLM can't be trusted to police in its own memory.

## Highlights

- Episodes + facts, joined by a declared link, over one SQLite file.
- Eleven natural-language asks returning a uniform `AnswerShape`.
- **synthesis-mud**: `clean` / `bridge` / `refuse` with calibrated confidence and
  a human-readable reason.
- A `project-memory` CLI (all `--json`) and a stdlib MCP server for Claude Code.
- Optional dense recall that degrades byte-identically to lexical.

## Install

```bash
pip install -e ../declared_core      # the engine (not yet on PyPI)
pip install -e .                     # project_memory
project-memory demo
```

## Verification

- **97 tests**, green in a clean virtualenv.
- All five `examples/` print `Verify your build: ok`.
- The MUD verdicts are checked against the methodology's own worked examples
  (clean / bridge / Layer-1 refusal / Layer-3 refusal).
- The dead-embedder-equals-no-embedder contract is asserted by a test.

## Compatibility

Python ≥ 3.10. One required dependency (`declared_core`); `numpy` only for
`[dense]`. Local-first, offline, `$0`.

## What's next

See [ROADMAP.md](ROADMAP.md): the remaining five asks, a persistent/ANN dense
index, and promoting `synthesis-mud` to its own package once a second consumer
needs it.
