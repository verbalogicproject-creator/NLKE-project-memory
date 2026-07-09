"""A zero-setup demo memory, plus a deterministic embedder for offline dense demos.

`build_demo()` loads a small, fully-deterministic memory (the fictional "Orchard"
notes app — see ``demo_corpus/demo_memory.json``) so the quickstart, the CLI
``demo`` command, and the tests all work with no files and no configuration. Every
row has an explicit id + timestamp, so two ``build_demo()`` calls produce
byte-identical stores.

`hash_embedder()` is a deterministic bag-of-words embedder (no model, no network)
— it lets the dense path be *exercised* and *tested* offline. It is a real
embedder in the interface sense (paraphrases with shared words land nearby); it is
not a semantic model. Point `http_embedder()` at a local server for real semantics.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Sequence

from .dense import Embedder
from .query import ProjectMemory
from .schema import MemorySchema


def demo_corpus_dir() -> Path:
    """Directory holding the packaged demo memory JSON."""
    return Path(__file__).parent / "demo_corpus"


def build_demo(path: str = ":memory:", *, embedder: Embedder | None = None) -> ProjectMemory:
    """Open a `ProjectMemory` seeded with the packaged demo memory.

    Deterministic: the seed rows carry explicit ids + timestamps, so with no
    embedder the resulting store is byte-identical every time.
    """
    data = json.loads((demo_corpus_dir() / "demo_memory.json").read_text(encoding="utf-8"))
    mem = ProjectMemory.open(path, MemorySchema(), embedder=embedder)
    for ep in data.get("episodes", []):
        mem.remember(
            ep["content"], kind=ep.get("kind", "general"),
            tags=ep.get("tags"), batch=ep.get("batch"),
            session_id=ep.get("session_id"),
            id=ep["id"], created_at=ep["created_at"],
        )
    for ft in data.get("facts", []):
        mem.record_fact(
            ft["claim"], reason=ft.get("reason"),
            source_episode_id=ft.get("source_episode_id"), tags=ft.get("tags"),
            id=ft["id"], created_at=ft["created_at"],
        )
    return mem


def hash_embedder(dim: int = 64) -> Embedder:
    """A deterministic, offline bag-of-words embedder (crc32-hashed token buckets).

    Useful for exercising and testing the optional dense path with no model and no
    network. Deterministic across processes; returns ``None`` only for empty text.
    """
    import re

    token_re = re.compile(r"\w+")

    def embed(text: str) -> "list[float] | None":
        toks = token_re.findall((text or "").lower())
        if not toks:
            return None
        vec = [0.0] * dim
        for t in toks:
            vec[zlib.crc32(t.encode("utf-8")) % dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    return embed
