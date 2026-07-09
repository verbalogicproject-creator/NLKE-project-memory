"""The natural-language front door: understand a question before searching.

`declared_core` already classifies a query's *intent* (a small, auditable regex
table → one of eight intents → fusion weights). project_memory adds light,
declared **entity extraction** on top, so a question like

    "why did we drop the Postgres plan?"

is understood as ``intent=debugging`` with entities ``["Postgres"]`` before it
ever touches the store. This is "route, don't search": the classifier picks *how*
to recall; the entities show *what* was understood. Both are regex — no model, no
network, fully explainable.

The `ask` layer (see ``project_memory.asks``) builds on this front door: it maps
a question to an intent, shapes the retrieval, and composes a terse answer with
cited evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from declared_core import classify_intent

# Quoted spans: "...", '...', or `...` — an explicit signal of a key phrase.
_QUOTED = re.compile(r"[\"'`]([^\"'`]{2,})[\"'`]")
# Code-ish identifiers: dotted / snake_case / CamelCase — the words that name
# concrete things (functions, flags, files, classes, tools).
_IDENT = re.compile(
    r"\b("
    r"[A-Za-z_][A-Za-z0-9_]*(?:[._][A-Za-z0-9_]+)+"   # a.b, snake_case.dotted
    r"|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]+"               # CamelCase
    r"|[A-Z]{2,}[0-9]*"                                # ACRONYM, FTS5
    r")\b"
)
# Capitalized proper nouns (Postgres, Redis, Python) — central to a memory of
# decisions. Guarded below: sentence-initial words and question stopwords are
# skipped so "Why did we drop Postgres?" yields "Postgres", not "Why".
_TITLECASE = re.compile(r"\b([A-Z][a-z]{2,})\b")
_STOP = frozenset({
    "why", "what", "how", "when", "where", "who", "which", "the", "this", "that",
    "these", "those", "does", "did", "can", "could", "should", "would", "will",
    "was", "were", "are", "and", "but", "for", "with", "from", "into", "our",
})


def extract_entities(text: str) -> list[str]:
    """Pull likely key entities from a question (quoted phrases + identifiers).

    Deterministic and order-preserving; de-duplicated case-insensitively.
    """
    found: list[str] = []
    seen: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.strip()
        if len(tok) >= 2 and tok.lower() not in seen:
            seen.add(tok.lower())
            found.append(tok)

    for m in _QUOTED.finditer(text):
        add(m.group(1))
    for m in _IDENT.finditer(text):
        add(m.group(1))
    for m in _TITLECASE.finditer(text):
        if m.start() == 0 or m.group(1).lower() in _STOP:
            continue  # sentence-initial or a question stopword — not an entity
        add(m.group(1))
    return found


@dataclass
class Understanding:
    """What the front door made of a question, before retrieval."""

    question: str
    intent: str
    confidence: float
    entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": self.entities,
        }


def understand(question: str) -> Understanding:
    """Classify intent (via declared_core) and extract entities. Pure, no I/O."""
    intent = classify_intent(question)
    return Understanding(
        question=question,
        intent=intent.intent,
        confidence=intent.confidence,
        entities=extract_entities(question),
    )
