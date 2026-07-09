"""ProjectMemory — the one object most callers use.

It owns a SQLite connection + a `MemorySchema`, writes episodes/facts, and
answers questions by delegating retrieval to `declared_core.hybrid_query` (BM25 +
structural expansion along the episode→fact link + intent-adaptive fusion, with
an optional dense signal). Three read entry points:

    mem = ProjectMemory.open("memory.db")     # or .open() for in-memory
    mem.remember("we chose SQLite over Postgres", kind="decision", auto_fact=True)

    mem.recall("database choice")              # → ranked episode + fact hits
    mem.ask("why not Postgres?")               # → a composed answer + evidence
    mem.synthesize(fact_a, fact_b)             # → MUD-checked merge (or refusal)

Everything is declared and explainable: each hit carries which signals found it
(``rrf_sources``), its fused score, and — if the dense booster ran — its
``dense_score``. Nothing is embedded, learned, or guessed unless you opt in.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from declared_core import HybridResult, hybrid_query

from . import ingest as _ingest
from .asks import AnswerShape, ASK_NAMES, route_intent, run_ask
from .dense import Embedder, build_dense_index
from .nl import Understanding, understand
from .schema import MemorySchema
from .store import connect, create_store
from .synthesis_mud import Fact, SynthesisResult
from .synthesis_mud import record_synthesis as _record_synthesis
from .synthesis_mud import synthesize as _synthesize

# Reserved scorer internals stripped from every projected hit.
_RESERVED = ("_text", "_tags")


class ProjectMemory:
    """A project's episodic + factual memory, recalled in natural language."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        schema: MemorySchema | None = None,
        *,
        embedder: Embedder | None = None,
        dimensions: object | None = None,
    ) -> None:
        self.schema = schema or MemorySchema()
        self.conn = conn
        self.corpus = create_store(conn, self.schema, dimensions=dimensions)
        self._embedder = embedder
        self._dense: Any | None = None
        self._dense_built = False

    @classmethod
    def open(
        cls,
        path: str = ":memory:",
        schema: MemorySchema | None = None,
        *,
        embedder: Embedder | None = None,
        dimensions: object | None = None,
    ) -> "ProjectMemory":
        """Open (or create) a memory at ``path`` (``:memory:`` for ephemeral)."""
        return cls(connect(path), schema, embedder=embedder, dimensions=dimensions)

    # ── writing ──────────────────────────────────────────────────────────────
    def remember(self, content: str, **kw: Any) -> dict[str, Any]:
        """Append an episode (see ``ingest.remember`` for kwargs)."""
        res = _ingest.remember(self.conn, self.schema, content, **kw)
        self._invalidate_dense()
        return res

    def record_fact(self, claim: str, **kw: Any) -> dict[str, Any]:
        """Write a durable fact (see ``ingest.record_fact`` for kwargs)."""
        res = _ingest.record_fact(self.conn, self.schema, claim, **kw)
        self._invalidate_dense()
        return res

    def invalidate_fact(self, fact_id: str, **kw: Any) -> bool:
        res = _ingest.invalidate_fact(self.conn, self.schema, fact_id, **kw)
        self._invalidate_dense()
        return res

    # ── reading ──────────────────────────────────────────────────────────────
    def recall(
        self,
        text: str,
        *,
        limit: int = 10,
        table: str | None = None,
        use_intent: bool = True,
        hybrid: bool = True,
        verbose: bool = False,
    ) -> list[dict[str, Any]]:
        """Search memory; return ranked, projected hits (episodes + facts).

        table       restrict to one source (``"episodes"`` / ``"facts"``); ``None``
                    searches both and fuses.
        use_intent  route fusion weights by query intent (declared_core).
        hybrid      include the optional dense signal (if an embedder is set).
        verbose     keep the full per-dimension ``dimensions`` vector in each hit.
        """
        _, hits = self._run(text, limit=limit, table=table, use_intent=use_intent, hybrid=hybrid)
        return [self._project(h, verbose) for h in hits[:limit]]

    def ask(
        self,
        question: str,
        *,
        name: str | None = None,
        limit: int = 8,
    ) -> AnswerShape:
        """Answer a question: understand it, route to an *ask*, compose an answer.

        ``name`` forces a specific ask (see ``asks()``); ``None`` routes by the
        classified intent. The result carries a terse answer, ranked evidence,
        caveats, and suggested follow-ups — the declared `AnswerShape` contract.
        """
        u = understand(question)
        chosen = name or route_intent(u.intent)
        return run_ask(chosen, question, self._retriever(limit), understanding=u)

    def understand(self, question: str) -> Understanding:
        """Classify intent + extract entities without retrieving. Pure."""
        return understand(question)

    def synthesize(
        self,
        a: "str | Fact",
        b: "str | Fact",
        *,
        persist: bool = False,
    ) -> SynthesisResult:
        """MUD-check a merge of two facts; refuse / bridge / clean with a calibrated
        confidence. ``a``/``b`` are raw statements (or pre-assessed `Fact`s). With
        ``persist=True`` the outcome is written to the ``synthesis_facts`` audit
        table. See ``project_memory.synthesis_mud``."""
        result = _synthesize(a, b)
        if persist:
            _record_synthesis(self.conn, result)
        return result

    def asks(self) -> list[str]:
        """The names of the available asks."""
        return list(ASK_NAMES)

    def recent(self, limit: int = 10, *, kind: str | None = None) -> list[dict[str, Any]]:
        """The most recent episodes, newest first (optionally filtered by kind)."""
        sql = f"SELECT id, content, kind, batch, tags, created_at FROM {self.schema.episode_table}"
        params: list[Any] = []
        if kind is not None:
            self.schema.validate_kind(kind)
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        import json

        return [
            {
                "id": r[0], "content": r[1], "kind": r[2], "batch": r[3],
                "tags": json.loads(r[4]) if r[4] else [], "created_at": r[5],
            }
            for r in self.conn.execute(sql, params).fetchall()
        ]

    def count(self) -> dict[str, int]:
        """How many episodes and (active) facts are stored."""
        ep = int(self.conn.execute(
            f"SELECT COUNT(*) FROM {self.schema.episode_table}").fetchone()[0])
        ft = int(self.conn.execute(
            f"SELECT COUNT(*) FROM {self.schema.fact_table} WHERE status = 'active'").fetchone()[0])
        return {"episodes": ep, "facts": ft}

    def close(self) -> None:
        self.conn.close()

    # ── internals ──────────────────────────────────────────────────────────────
    def _retriever(self, default_limit: int):
        """A closure the asks use to retrieve — hides conn/corpus/dense."""
        def retrieve(query: str, *, limit: int | None = None, table: str | None = None) -> list[dict[str, Any]]:
            _, hits = self._run(
                query, limit=limit or default_limit, table=table,
                use_intent=True, hybrid=True,
            )
            return [self._project(h, verbose=False) for h in hits]
        return retrieve

    def _run(
        self, text: str, *, limit: int, table: str | None, use_intent: bool, hybrid: bool
    ) -> tuple[HybridResult, list[dict[str, Any]]]:
        dense = self._dense_index() if hybrid else None
        # Over-fetch when filtering to a single table so a filter can't starve the result.
        fetch = max(limit * 3, limit + 10) if table else limit
        result = hybrid_query(
            text, self.corpus, self.conn,
            limit=fetch, dense=dense, use_intent=use_intent,
        )
        hits = result.hits
        if table is not None:
            hits = [h for h in hits if h.get("table") == table]
        return result, hits

    def _dense_index(self) -> Any | None:
        if self._embedder is None:
            return None
        if not self._dense_built:
            self._dense = build_dense_index(self.conn, self.schema, self._embedder)
            self._dense_built = True
        return self._dense

    def _invalidate_dense(self) -> None:
        self._dense_built = False
        self._dense = None

    def _project(self, hit: dict[str, Any], verbose: bool) -> dict[str, Any]:
        out = {k: v for k, v in hit.items() if k not in _RESERVED}
        if not verbose:
            out.pop("dimensions", None)
        return out
