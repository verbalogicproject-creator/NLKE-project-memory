# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## What this repo is

`project_memory` — a declared, AI-optional project memory: an append-only
**episode** log + crystallized, supersedable **facts**, with hybrid recall, an
eleven-strong natural-language *ask* surface, and a **synthesis-mud** epistemic
guard that refuses to merge contradictory facts. It is a **thin layer on top of
the `declared_core` engine** (a separate repo); retrieval math lives there.

## Setup (declared_core is vendored in-repo)

`project_memory` installs standalone: the `declared_core` engine is **vendored**
as a byte-identical in-repo copy (see `VENDORED.json`), so there is no sibling
repo to install and no required PyPI dependency. For the portfolio layer,
`ngfify` + `universal_parser` are vendored the same way, so its `[portfolio]`
extra is just PyYAML.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Commands

```bash
pytest                                   # full suite (97 tests, keep green)
python examples/01_remember_and_recall.py  # examples self-verify ("Verify your build: ok")
project-memory demo                      # try the packaged demo memory
project-memory ask "why not X?" --json   # the ask surface, scriptable
```

## Architecture that needs reading more than one file

1. **The schema compiles to declared_core.** `schema.py::MemorySchema` maps two
   tables (episodes + facts) to a `declared_core.CorpusSchema` — two `SourceTable`s
   joined by a `Link` (`facts.source_episode_id → episodes.id`). `store.py` builds
   the physical tables from that schema and calls declared_core's `install_fts`.

2. **The tables are the domain model, not fixed strings.** Table names come from
   the schema (`episode_table`/`fact_table`); nothing hardcodes them. `kinds` is
   the one project-specific knob and is user-declared.

3. **`ProjectMemory` (`query.py`) is the orchestrator.** It owns the conn + schema
   + compiled corpus, delegates recall to `declared_core.hybrid_query`, caches the
   optional dense index (invalidated on any write), and hands the asks a
   `retrieve` closure so they never touch SQLite directly.

4. **Asks are pure declarations of how to answer.** `asks.py` holds `AnswerShape`
   + the eleven asks + `_INTENT_ROUTES`. An ask receives `(question, retrieve, understanding)`
   and returns an `AnswerShape`. `ProjectMemory.ask()` routes intent → ask name.

5. **synthesis-mud is self-contained and deterministic.** `synthesis_mud.py` has
   the `Fact` axes, the assessor, five compatibility matrices, the 6-layer
   detector, and `synthesize()`. It has no retrieval dependency; it is the
   differentiator. Verdicts are checked against the methodology's worked examples.

6. **Dense is optional and must stay that way.** `dense.py` builds a declared_core
   `NumpyVectorIndex` from an injected embedder over episode + fact surfaces. A
   dead embedder / missing numpy / `None` must yield results byte-identical to no
   embedder. See `test_dense.py::test_dead_embedder_is_byte_identical_to_no_dense`.

## Load-bearing invariants (do not break)

1. **BM25 is the floor; dense is a booster.** Never make an embedder a hard dep.
2. **Episodes are append-only; facts supersede, never delete.** Keep history.
3. **Schema validation fails loud** (unknown `kind`). Silent mis-indexing is worse.
4. **The no-embedder path is deterministic.** The demo rows carry explicit ids +
   timestamps precisely to stay reproducible.
5. **synthesis-mud stays deterministic + AI-less.** Typed axes, computed matrices,
   overridable per axis. Its verdicts must keep matching the worked examples.
6. **Retrieval math belongs to declared_core.** BM25 / structural / RRF / intent →
   the engine repo, not here.

## What NOT to do

- Do **not** add a required dependency. The vendored `declared_core` engine adds
  none; numpy stays behind the `[dense]` extra.
- Do **not** commit `*.db`, `.venv/`, or `__pycache__` (all gitignored).
- Do **not** claim a feature in the README that isn't proven — put it in
  `ROADMAP.md` (a documented project value; the audience has real judgment).
- Do **not** edit `demo_corpus/demo_memory.json` casually — the README quickstart,
  the CLI `demo`, and several tests assert on its deterministic output (including
  the security↔business fact pair used to demo a MUD refusal).
- Do **not** add a public symbol without exporting it in `__init__.py.__all__`
  **and** documenting it in `docs/08-api-reference.md`.
- Do **not** change a synthesis-mud compatibility matrix without updating the
  worked-example tests — those values are the contract.

## Authorship

This repo is architected and authored by **Eyal Nof**. Commits carry no co-author
trailer.
