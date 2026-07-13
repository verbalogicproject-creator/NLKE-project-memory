# project_memory → the Portfolio Brain (#13) — upgrade SPEC

## Purpose
Turn the existing `project_memory` engine into a **declared memory of the whole `~/projects` ecosystem**, so
you (and Claude, via the CLI) can ask the portfolio about itself — the **"recursive close"**: the substrate
indexing its own body of work. Internal tool, built to publishable grade. It is the **private moat engine**
that the free **Codebase-Memorizer** product is the public-simple twin of.

## Build ON the existing engine — read it first, compose, do NOT reinvent
The engine at `/root/projects/project_memory/project_memory/` already provides declared **dimensions**
(`dimensions.py`), **ingest** (`ingest.py`), the SQLite **store** (`schema.py`/`store.py`), the graph /
relationship layer (`synthesis_mud.py`), and query via **`asks.py`/`query.py`/`cli.py`** (+ `presets.py`,
`demo.py`, `examples/mcp_server.py`). **Read these to learn the real API**, then add the portfolio layer on
top. Do not rebuild the engine.

## Crystallized design (LOCKED)
- **Structure — flat: repo = dimension.** One declared dimension per `~/projects` repo, named after the repo.
  No cluster-tag layer.
- **Atoms — per ai_card / declared interface (finest).** For each repo, ingest one atom per declared card /
  public interface: from `arch/*.ngf.md` + ai_cards + the `public_interfaces`/public-API lists in
  `SPEC-v0.1.md` / `CODEBASE-REPORT.md`. Repos still in plain markdown are **auto-declared with ngfify first**
  (`nlke-ngfify`, now shipped — dogfood) to produce ai_cards, then ingested.
- **Edges — composition + open-core twins + built-by** (declared, not inferred; see the manifest below).
- **Query front — CLI `ask` now** (MCP is the follow-up, not tonight).

## Scope (all current `~/projects` repos; exclude `/future`, `~/revenue`)
Fleet: `universal_parser` `ngfify` `declared_core` `frontmatter_rag` `kg_toolkit` `declared_rules`
`rag_evaluator` `scaffold_kg_rag_agent` `persona_guard` `claude_workload_optimizer` `declared_repo_factory`
`declarum-substrate` `Aisle-demo` `aisle-wedding-copilot` `sag-declarum-atlas-framework` `taste-skill-main`.
Verbalogix line: `ctx-architecture` `codebase-memorizer` `vouch` `verbalogix`.
Plus `project_memory` **itself** (the brain indexes itself — the ultimate recursive close).
Skip `.git`/`.venv`/`node_modules`/`reference/`/build artifacts. (taste-skill-main is third-party — index it,
mark it `vendored`.)

## The declared edge manifest (materialize as `portfolio-edges.yaml`; declared, not inferred)
```
composes/depends_on:
  ngfify -> universal_parser
  frontmatter_rag -> declared_core
  kg_toolkit -> declared_core
  declared_rules -> declared_core
  rag_evaluator -> declared_core, frontmatter_rag, kg_toolkit        # "scores"
  scaffold_kg_rag_agent -> declared_core, frontmatter_rag, kg_toolkit, declared_rules, rag_evaluator, persona_guard, declarum-substrate  # capstone-of
  aisle-wedding-copilot -> Aisle-demo                                # recipe-for
  Aisle-demo -> scaffold_kg_rag_agent, sag-declarum-atlas-framework, taste-skill-main
  codebase-memorizer -> ctx-architecture                            # reads Map's architecture.ctx
  vouch -> ctx-architecture, codebase-memorizer                     # optional KG compose
  verbalogix -> ctx-architecture, codebase-memorizer, vouch         # orchestrates
public-twin-of:
  codebase-memorizer -> project_memory                              # public-simple twin of the moat engine
  vouch -> persona_guard                                            # public "refuse-to-fabricate" twin
  ctx-architecture -> ngfify                                        # both derive declared docs from source
built-by:
  declared_repo_factory -> universal_parser, ngfify, declared_core, frontmatter_rag, kg_toolkit, declared_rules, rag_evaluator, scaffold_kg_rag_agent, persona_guard, claude_workload_optimizer, declarum-substrate, ctx-architecture, codebase-memorizer, vouch, verbalogix
```
Confirm each edge against the repos' own READMEs during ingest; drop any the repo doesn't actually assert,
and note it (declared-and-verified, not assumed).

## Deliverables (publishable grade)
- A **portfolio indexer** (`project_memory/portfolio.py` + a `scripts/index_portfolio.py` entry) that:
  enumerate scope repos → declare a dimension per repo → extract declared-interface atoms (ngfify
  auto-declare for plain-markdown repos) → ingest under the repo dimension → load `portfolio-edges.yaml` as
  declared edges → build/refresh the store.
- **`portfolio-edges.yaml`** (the manifest above, materialized).
- A **recursive-close demo** (`examples/recursive_close.py` or a doc) running REAL CLI `ask` queries and
  pasting real output: e.g. *"what composes Map?"*, *"show the Verbalogix line"*, *"what is project_memory's
  public twin?"*, *"what did declared_repo_factory build?"*, *"what's in the retrieval cluster around
  declared_core?"*.
- Docs update (README/CHANGELOG) noting the portfolio-brain capability + the recursive-close demo. Keep it
  honest about what's tonight (BM25/FTS floor, CLI) vs follow-up (dense booster, MCP).
- Attribution **Eyal Nof only, no co-author trailer**. Do **NOT** push (internal moat tool — human gates it).

## Tonight's scope guard
Indexer + ingest + edges + the CLI demo, on the existing engine. NO dense-embedding pass (BM25/FTS floor is
enough tonight; dense is the GPU follow-up), NO MCP server (follow-up), NO TUI. Ground every claim in a real
`ask` run.
