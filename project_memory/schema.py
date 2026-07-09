"""MemorySchema — declare how a project's memory becomes a searchable corpus.

`project_memory` stores two kinds of thing:

  - **episodes** — an append-only log of what happened ("we chose SQLite over
    Postgres", "the FTS trigger fired twice"). Verbatim or paraphrased, keyed by
    a stable id, tagged, and grouped by ``kind`` (decision / gotcha / …).
  - **facts** — durable claims *crystallized* from episodes ("SQLite is the
    store of record"). A fact has a ``claim`` + optional ``reason`` and a
    supersession chain, so memory updates without losing history.

You don't re-implement retrieval. A `MemorySchema` *declares* these two tables
and compiles down to a `declared_core.CorpusSchema` — two `SourceTable`s joined
by a `Link` — so recall rides the same declared engine every repo in this family
uses: BM25 + structural expansion + reciprocal-rank fusion + intent-adaptive
weighting, with an optional dense signal on top.

The one thing that is genuinely project-specific — the **episode taxonomy** — is
user-declared (``kinds=``), with a generic default. Nothing about your game, app,
or domain is baked into the engine.

    from project_memory import MemorySchema

    schema = MemorySchema(kinds=("decision", "gotcha", "insight", "todo"))

The structural join is the interesting part: because ``facts.source_episode_id``
references ``episodes.id``, a query that matches an *episode* structurally
expands to the *facts* crystallized from it (and vice-versa). Memory recall is
therefore never just keyword matching — it follows the declared graph.
"""

from __future__ import annotations

from dataclasses import dataclass

from declared_core import CorpusSchema, Link, SourceTable

# The generic default episode taxonomy. Deliberately domain-neutral — override
# ``kinds=`` with whatever vocabulary your project actually uses. The engine
# treats every kind as an opaque structural cluster; these are just the sensible
# starting set for "remembering how a project's thinking evolved".
DEFAULT_KINDS: tuple[str, ...] = (
    "decision",   # "we chose X because Y"
    "gotcha",     # a surprise / bug found in the wild
    "insight",    # a realization worth keeping
    "invariant",  # a rule that must keep holding
    "task",       # something to do / a TODO worth remembering
    "milestone",  # a boundary or checkpoint
    "general",    # anything else worth remembering
)

# Facts move through a small, fixed lifecycle. This is structural (it drives the
# ``where`` filter and the supersession chain), not a user taxonomy.
FACT_STATUSES: tuple[str, ...] = ("active", "superseded", "invalidated")

# The current on-disk schema version. Stamped onto every row (the ``method`` +
# ``schema_version`` columns) so a future migration can tell old rows from new —
# the source project's #1 lesson: version the schema from day one.
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemorySchema:
    """A full declaration: how a project's episodes + facts map to two tables.

    kinds        the allowed episode-``kind`` vocabulary. User-declared;
                 ingestion validates against it. Defaults to ``DEFAULT_KINDS``.
    episode_table / fact_table
                 physical table names. Rarely changed, but nothing hardcodes
                 them — set them to namespace two memories in one database.
    small_corpus_threshold
                 passed through to ``declared_core``: below this many candidates,
                 fuse by intent-weighted RRF; at/above it, weighted sum.
    schema_version
                 stamped onto rows; bump only alongside a migration.
    """

    kinds: tuple[str, ...] = DEFAULT_KINDS
    episode_table: str = "episodes"
    fact_table: str = "facts"
    small_corpus_threshold: int = 100
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.kinds:
            raise ValueError("MemorySchema needs at least one episode kind")
        if len(self.kinds) != len(set(self.kinds)):
            raise ValueError(f"duplicate episode kinds: {self.kinds}")
        if self.episode_table == self.fact_table:
            raise ValueError("episode_table and fact_table must differ")

    # ── kind validation ────────────────────────────────────────────────────
    def validate_kind(self, kind: str) -> None:
        if kind not in self.kinds:
            raise ValueError(
                f"unknown episode kind {kind!r}; declared kinds are "
                f"{sorted(self.kinds)}. Add it to MemorySchema(kinds=...)."
            )

    # ── compile to the declared_core engine ────────────────────────────────
    def episode_source(self) -> SourceTable:
        """Episodes: prose in ``content``; ``kind``/``batch`` cluster; ``tags`` overlap."""
        return SourceTable(
            name=self.episode_table,
            id_column="id",
            text_columns=("content",),
            carry_columns=("session_id", "created_at"),
            cluster_columns=("kind", "batch"),
            tag_columns=("tags",),
            order_by="created_at DESC",
        )

    def fact_source(self) -> SourceTable:
        """Facts: ``claim`` + ``reason`` are prose; only *active* facts are searchable."""
        return SourceTable(
            name=self.fact_table,
            id_column="id",
            text_columns=("claim", "reason"),
            carry_columns=("source_episode_id", "status", "created_at"),
            tag_columns=("tags",),
            where="status = 'active'",
            order_by="created_at DESC",
        )

    def fact_link(self) -> Link:
        """The declared join: a matched episode expands to its crystallized facts."""
        return Link(child=self.fact_table, parent=self.episode_table, key="source_episode_id")

    def corpus_schema(self, *, dimensions: object | None = None) -> CorpusSchema:
        """Compile to a `declared_core.CorpusSchema` (what `hybrid_query` needs)."""
        return CorpusSchema(
            sources=(self.episode_source(), self.fact_source()),
            links=(self.fact_link(),),
            dimensions=dimensions,
            small_corpus_threshold=self.small_corpus_threshold,
        )
