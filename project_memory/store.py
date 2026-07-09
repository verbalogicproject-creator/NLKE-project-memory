"""Physical storage: build the ``episodes`` + ``facts`` tables from a
`MemorySchema`, then let `declared_core` attach its FTS index + sync triggers.

`project_memory` brings the base tables (its data model); `declared_core` owns
the search layer. The two tables are the whole domain model:

  episodes ──(source_episode_id)──> facts        (a fact crystallized from an
                                                   episode points back at it)

Both are stamped with ``method`` (how the row was produced) and
``schema_version`` so a future migration can distinguish old rows from new.
Everything is idempotent — safe to call on every connect.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from declared_core import CorpusSchema, install_fts
from declared_core.store import connect as _dc_connect

from .schema import MemorySchema


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection (WAL for files) — thin re-export of declared_core."""
    return _dc_connect(path)


def new_id() -> str:
    """A fresh opaque id. Callers may pass their own id for deterministic seeds."""
    return uuid.uuid4().hex


def now_iso() -> str:
    """UTC timestamp in ISO-8601. Callers may pass their own for deterministic seeds."""
    return datetime.now(timezone.utc).isoformat()


def _episodes_ddl(schema: MemorySchema) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {schema.episode_table} (
  id             TEXT PRIMARY KEY,
  content        TEXT NOT NULL,
  kind           TEXT NOT NULL,
  session_id     TEXT,
  batch          TEXT,
  tags           TEXT DEFAULT '[]',
  metadata       TEXT DEFAULT '{{}}',
  method         TEXT DEFAULT 'manual',
  schema_version INTEGER DEFAULT {schema.schema_version},
  created_at     TEXT NOT NULL
)"""


def _facts_ddl(schema: MemorySchema) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {schema.fact_table} (
  id                TEXT PRIMARY KEY,
  claim             TEXT NOT NULL,
  reason            TEXT,
  source_episode_id TEXT REFERENCES {schema.episode_table}(id),
  status            TEXT DEFAULT 'active' CHECK(status IN ('active', 'superseded', 'invalidated')),
  superseded_by     TEXT REFERENCES {schema.fact_table}(id),
  tags              TEXT DEFAULT '[]',
  method            TEXT DEFAULT 'manual',
  schema_version    INTEGER DEFAULT {schema.schema_version},
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
)"""


def create_store(
    conn: sqlite3.Connection,
    schema: MemorySchema,
    *,
    dimensions: object | None = None,
) -> CorpusSchema:
    """Create the episodes + facts tables (if absent) and install FTS over both.

    Returns the compiled `declared_core.CorpusSchema` — pass it to `hybrid_query`.
    Idempotent: safe to call on every connect.
    """
    conn.execute(_episodes_ddl(schema))
    conn.execute(_facts_ddl(schema))
    ep, ft = schema.episode_table, schema.fact_table
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{ep}_kind ON {ep}(kind)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{ep}_batch ON {ep}(batch)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{ep}_created ON {ep}(created_at)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{ft}_status ON {ft}(status)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{ft}_created ON {ft}(created_at)")
    corpus = schema.corpus_schema(dimensions=dimensions)
    install_fts(conn, corpus)
    conn.commit()
    return corpus
