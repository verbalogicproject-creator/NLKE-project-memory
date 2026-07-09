"""Optional dense (semantic) recall — a booster, never a dependency.

project_memory is fully useful with zero embeddings: BM25 over episode content +
fact claims/reasons, plus structural expansion along the episode→fact link, plus
intent-adaptive fusion. Dense retrieval adds paraphrase recall (matches that
share *meaning* but few words) by embedding each row's *surface* and fusing a
cosine-similarity list as declared_core's fourth signal.

It degrades cleanly in every failure mode — identical contract to the rest of the
family:
  - no embedder passed            → pure lexical (byte-identical determinism)
  - ``numpy`` not installed       → pure lexical (install ``[dense]`` to enable)
  - embedder returns ``None``     → pure lexical (server down / disabled)

Bring any ``str -> Sequence[float] | None`` callable. ``http_embedder()`` is a
convenience for an OpenAI-style local embeddings endpoint (llama.cpp, Ollama,
etc.) — stdlib only, returns ``None`` on any failure.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from typing import Any, Callable, Sequence

from .schema import MemorySchema

Embedder = Callable[[str], "Sequence[float] | None"]


def dense_available() -> bool:
    """Is the optional ``numpy`` dependency importable? (dense needs it)."""
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def _tags(raw: Any) -> list[str]:
    if isinstance(raw, str) and raw.startswith("["):
        try:
            val = json.loads(raw)
            return [str(x) for x in val] if isinstance(val, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _surface(parts: "list[str | None]") -> str:
    """Join the non-empty parts of a row into its embedded semantic surface,
    de-duplicated and order-preserving."""
    seen: set[str] = set()
    uniq: list[str] = []
    for p in parts:
        if not p:
            continue
        s = str(p).strip()
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return "\n\n".join(uniq)


def _iter_items(conn: sqlite3.Connection, schema: MemorySchema) -> list[dict[str, Any]]:
    """Load every episode + active fact as a dense-index item.

    Each item carries ``table`` + ``id`` (so a dense-only hit still fuses and can
    be displayed) and the ``_text`` surface that gets embedded.
    """
    items: list[dict[str, Any]] = []

    ep = schema.episode_table
    for r in conn.execute(f"SELECT id, content, kind, tags FROM {ep}").fetchall():
        row = {"id": r[0], "content": r[1], "kind": r[2], "tags": r[3]}
        text = _surface([row["content"], row["kind"], *_tags(row["tags"])])
        items.append({**row, "table": ep, "_text": text})

    ft = schema.fact_table
    for r in conn.execute(
        f"SELECT id, claim, reason, tags FROM {ft} WHERE status = 'active'"
    ).fetchall():
        row = {"id": r[0], "claim": r[1], "reason": r[2], "tags": r[3]}
        text = _surface([row["claim"], row["reason"], *_tags(row["tags"])])
        items.append({**row, "table": ft, "_text": text})

    return items


def build_dense_index(
    conn: sqlite3.Connection,
    schema: MemorySchema,
    embedder: Embedder,
) -> Any | None:
    """Build a `declared_core.NumpyVectorIndex` over episodes + facts, or ``None``
    if numpy is unavailable (→ recall degrades to lexical). The index is passed as
    ``dense=`` to `hybrid_query`."""
    if not dense_available():
        return None
    from declared_core import NumpyVectorIndex

    items = _iter_items(conn, schema)
    return NumpyVectorIndex.from_items(embedder, items, text_of=lambda it: it["_text"])


# ── A ready-made stdlib embedder for an OpenAI-style local endpoint ───────────

def http_embedder(
    url: str | None = None,
    *,
    model: str | None = None,
    query_prefix: str | None = None,
    timeout: float = 15.0,
) -> Embedder:
    """Return an embedder that POSTs to an OpenAI-style ``/v1/embeddings`` endpoint.

    Defaults (overridable via args or the ``PMEM_EMBED_*`` env vars) target a
    local llama.cpp / Ollama embeddings server. Returns ``None`` on *any* failure
    so recall degrades to pure lexical — the same non-blocking discipline the rest
    of the stack uses. No pip dependency (stdlib ``urllib``).

    ``query_prefix`` is prepended to queries only (some models, e.g. bge-v1.5, are
    asymmetric and want a retrieval instruction on the query side).
    """
    url = url or os.environ.get("PMEM_EMBED_URL", "http://127.0.0.1:8140/v1/embeddings")
    model = model or os.environ.get("PMEM_EMBED_MODEL", "local-embed")
    if query_prefix is None:
        query_prefix = os.environ.get("PMEM_EMBED_QUERY_PREFIX", "")

    def embed(text: str) -> "list[float] | None":
        body = json.dumps({"model": model, "input": [text or ""]}).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list) and data:
                vec = data[0].get("embedding")
                if isinstance(vec, list) and vec:
                    return [float(x) for x in vec]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            pass
        return None

    return embed
