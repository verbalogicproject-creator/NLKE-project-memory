"""project_memory — declared, AI-optional memory for agents and projects.

Give it a folder-free SQLite memory of two things — **episodes** (what happened)
and **facts** (durable claims crystallized from episodes) — and it answers
questions about them: BM25 + structural expansion (episode→fact) + intent-adaptive
fusion, an eleven-strong natural-language *ask* surface, and a MUD *epistemic
guard* that refuses to synthesize contradictory facts.

It is a thin, opinionated layer over the `declared_core` engine (retrieval math
lives there). Local-first, deterministic, $0. A dense signal is optional and
degrades byte-identically to lexical.

    from project_memory import ProjectMemory

    mem = ProjectMemory.open("memory.db")
    mem.remember("we chose SQLite over Postgres", kind="decision", auto_fact=True,
                 reason="local-first, zero-ops")

    mem.recall("database choice")            # → ranked episode + fact hits
    mem.ask("why not Postgres?")             # → composed answer + cited evidence
    mem.synthesize(                          # → refuse / bridge / clean, calibrated
        "From a security perspective, plaintext tokens are unacceptable.",
        "From a business perspective, plaintext tokens were cheap and worked.",
    )

See `project_memory.demo.build_demo()` for a runnable, zero-setup memory.
"""

from __future__ import annotations

from .asks import (
    ASK_NAMES,
    AnswerShape,
    build_evidence,
    register as register_ask,
    route_intent,
    run_ask,
)
from .demo import build_demo, demo_corpus_dir, hash_embedder
from .dense import Embedder, dense_available, http_embedder
from .dimensions import MEMORY_DIMENSIONS, custom as custom_dimensions
from .ingest import invalidate_fact, record_fact, remember
from .nl import Understanding, extract_entities, understand
from .presets import AGENT, GENERIC, PRESETS, RESEARCH
from .query import ProjectMemory
from .schema import DEFAULT_KINDS, FACT_STATUSES, SCHEMA_VERSION, MemorySchema
from .store import connect
from .synthesis_mud import (
    AXES,
    Fact,
    MudVerdict,
    SynthesisResult,
    compatibilities,
    detect_mud,
    install_synthesis_tables,
    record_synthesis,
    synthesize,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # the main object
    "ProjectMemory",
    # schema
    "MemorySchema",
    "DEFAULT_KINDS",
    "FACT_STATUSES",
    "SCHEMA_VERSION",
    # presets
    "GENERIC",
    "AGENT",
    "RESEARCH",
    "PRESETS",
    # writing (functional form)
    "remember",
    "record_fact",
    "invalidate_fact",
    # natural-language front door + asks
    "understand",
    "extract_entities",
    "Understanding",
    "AnswerShape",
    "ASK_NAMES",
    "run_ask",
    "route_intent",
    "register_ask",
    "build_evidence",
    # dimensions
    "MEMORY_DIMENSIONS",
    "custom_dimensions",
    # synthesis-mud
    "synthesize",
    "detect_mud",
    "compatibilities",
    "Fact",
    "SynthesisResult",
    "MudVerdict",
    "AXES",
    "install_synthesis_tables",
    "record_synthesis",
    # optional dense
    "Embedder",
    "http_embedder",
    "dense_available",
    # demo + store
    "build_demo",
    "demo_corpus_dir",
    "hash_embedder",
    "connect",
]
