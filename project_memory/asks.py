"""Asks — the natural-language question types over project memory.

An *ask* maps a question to a retrieval, ranks + filters the hits, and composes a
terse answer with cited evidence. Every ask returns the same declared
`AnswerShape`:

    {ask, question, answer, confidence, evidence[], caveats[], suggested_next[], trace_id}

so a caller (or an agent, or the MCP layer) can treat them uniformly. Asks never
reach into SQLite themselves — they receive a ``retrieve`` closure from
`ProjectMemory`, which hides the connection, corpus, and optional dense index.
This keeps an ask a *pure declaration of how to answer a kind of question*.

v0.1 ships eleven curated asks:

  why_not · can_i · how_do_i · what_for · route · how_does_connect · snapshot
  recommend · similar_to · debug · optimize_for

Reference implementations for all of them exist in the source project's
``intent_query.py``; here they are generalized to an episode + fact memory (no
tool/dependency graph assumed). Five more (learn / explore_smart / roadmap /
alternatives / compatible_with) are on the ROADMAP.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from declared_core import score_item, score_summary

from .dimensions import MEMORY_DIMENSIONS
from .nl import Understanding, understand

MAX_EVIDENCE = 6

# retrieve(query, *, limit=None, table=None) -> list[projected hit dicts]
Retriever = Callable[..., "list[dict[str, Any]]"]


# ── The uniform return shape ─────────────────────────────────────────────────

@dataclass
class AnswerShape:
    """The declared contract every ask returns."""

    ask: str
    question: str
    answer: str
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    suggested_next: list[str] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ask": self.ask,
            "question": self.question,
            "answer": self.answer,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "caveats": self.caveats,
            "suggested_next": self.suggested_next,
            "trace_id": self.trace_id,
        }


def _score_of(hit: dict[str, Any]) -> float:
    return float(
        hit.get("rrf_score")
        or hit.get("weighted_score")
        or hit.get("rules_score")
        or 0.0
    )


def build_evidence(hits: list[dict[str, Any]], max_items: int = MAX_EVIDENCE) -> list[dict[str, Any]]:
    """Trim recall hits to a compact, uniform evidence list."""
    out: list[dict[str, Any]] = []
    for h in hits[:max_items]:
        preview = (h.get("content") or h.get("claim") or "")[:200]
        out.append({
            "table": h.get("table"),
            "id": h.get("id"),
            "kind": h.get("kind") or h.get("status"),
            "preview": preview,
            "reason": h.get("reason"),
            "score": round(_score_of(h), 4),
            "created_at": h.get("created_at"),
        })
    return out


def confidence_from_hits(hits: list[dict[str, Any]]) -> float:
    """Rough confidence: top-1 fused score, scaled into [0, 0.9]."""
    if not hits:
        return 0.0
    return min(0.9, _score_of(hits[0]) * 10.0)


# ── Registry + dispatch ──────────────────────────────────────────────────────

AskFn = Callable[[str, Retriever, Understanding], AnswerShape]
_REGISTRY: dict[str, AskFn] = {}


def register(name: str) -> Callable[[AskFn], AskFn]:
    def _wrap(fn: AskFn) -> AskFn:
        _REGISTRY[name] = fn
        return fn
    return _wrap


def run_ask(
    name: str,
    question: str,
    retrieve: Retriever,
    *,
    understanding: Understanding | None = None,
) -> AnswerShape:
    """Dispatch to a registered ask. Unknown name → an explicit AnswerShape."""
    fn = _REGISTRY.get(name)
    if fn is None:
        return AnswerShape(
            ask=name, question=question,
            answer=f"unknown ask '{name}'", confidence=0.0,
            caveats=[f"ask '{name}' is not registered; available: {sorted(_REGISTRY)}"],
        )
    u = understanding or understand(question)
    return fn(question, retrieve, u)


# Declared intent → ask routing. `ProjectMemory.ask(question)` uses this when no
# explicit ask name is given. The eight intents are declared_core's; the mapping
# is a small, auditable table — "route, don't search".
_INTENT_ROUTES: dict[str, str] = {
    "exact_match": "what_for",
    "capability_check": "can_i",
    "debugging": "debug",
    "workflow": "how_do_i",
    "comparison": "how_does_connect",
    "goal_based": "recommend",
    "exploratory": "snapshot",
    "semantic": "recommend",
}


def route_intent(intent: str) -> str:
    """Map a classified intent to the ask that best answers it."""
    return _INTENT_ROUTES.get(intent, "recommend")


# ── The eleven asks ──────────────────────────────────────────────────────────

@register("why_not")
def why_not(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Why not X / why doesn't X work?' → recorded failure mode or rationale."""
    hits = retrieve(question + " failure error bug fix gotcha invariant reason because", limit=8)
    ev = build_evidence(hits)
    gotchas = [e for e in ev if e.get("kind") in ("gotcha", "invariant")]
    if gotchas:
        answer = f"known issue: {gotchas[0]['preview'][:180]}"
    elif ev:
        answer = f"closest recorded rationale: {ev[0]['preview'][:180]}"
    else:
        answer = "nothing recorded — this may be new; decide and remember it"
    caveats = []
    if ev and not gotchas:
        caveats.append("no gotcha/invariant matched — evidence is best-effort keyword match")
    if not ev:
        caveats.append("no memory yet; capture the decision with remember(kind='decision')")
    return AnswerShape("why_not", question, answer, confidence_from_hits(hits), ev, caveats,
                       suggested_next=[f"how_do_i fix {question}", f"debug {question}"])


@register("can_i")
def can_i(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Can I / does it X?' → yes / no / partial from recorded capability."""
    hits = retrieve(question, limit=8)
    ev = build_evidence(hits)
    text = " ".join((e["preview"] or "").lower() for e in ev)
    positive = any(w in text for w in ("supports", "provides", "can ", "yes", "implemented", "shipped", "works"))
    negative = any(w in text for w in ("cannot", "not implemented", "deferred", "not yet", "unsupported", "won't"))
    if positive and not negative:
        verdict = "yes"
    elif negative and not positive:
        verdict = "no"
    elif positive and negative:
        verdict = "partial — some paths yes, some no"
    else:
        verdict = "unknown — no clear signal in memory"
    caveats = [] if ev else ["no evidence in memory; try how_do_i or capture it first"]
    return AnswerShape("can_i", question, verdict, confidence_from_hits(hits), ev, caveats,
                       suggested_next=[f"how_do_i {question}", f"route {question}"])


@register("how_do_i")
def how_do_i(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'How do I X?' → the procedure, preferring crystallized facts."""
    hits = retrieve(question, limit=8)
    ev = build_evidence(hits)
    facts = [e for e in ev if e["table"] == "facts"]
    if facts:
        answer = f"per a recorded fact: {facts[0]['preview'][:160]}"
    elif ev:
        answer = f"nearest procedure in memory: {ev[0]['preview'][:160]}"
    else:
        answer = "no procedure recorded for this"
    caveats = [] if ev else ["nothing in memory; this may live in the docs/code, not memory"]
    return AnswerShape("how_do_i", question, answer, confidence_from_hits(hits), ev, caveats,
                       suggested_next=[f"can_i {question}", f"what_for {question}"])


@register("what_for")
def what_for(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'What is X for / what is X?' → the closest description."""
    hits = retrieve(question, limit=6)
    ev = build_evidence(hits)
    answer = ev[0]["preview"] if ev else "no description found in memory"
    return AnswerShape("what_for", question, answer, confidence_from_hits(hits), ev,
                       suggested_next=[f"how_do_i {question}", f"how_does_connect {question} to X"])


@register("route")
def route(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Where does this belong?' → the dominant memory *kind* for the topic.

    Generalized from the source project's hardcoded path table: instead of naming
    files, it surfaces which recorded *kind* of thinking (decision / gotcha / …)
    the topic most clusters around, plus the strongest pointer.
    """
    hits = retrieve(question, limit=8)
    ev = build_evidence(hits)
    kinds: dict[str, int] = {}
    for e in ev:
        k = e.get("kind")
        if k:
            kinds[k] = kinds.get(k, 0) + 1
    if kinds:
        dominant = max(kinds.items(), key=lambda kv: kv[1])[0]
        answer = f"clusters under '{dominant}' — strongest: {ev[0]['preview'][:150]}"
    elif ev:
        answer = f"closest memory: {ev[0]['preview'][:160]}"
    else:
        answer = "no route match in memory"
    return AnswerShape("route", question, answer,
                       confidence_from_hits(hits) if ev else 0.1, ev,
                       suggested_next=[f"what_for {question}", f"how_do_i {question}"])


_CONNECT_RE = re.compile(r"how does (.+?) connect(?:_?to)? (.+)", re.IGNORECASE)


@register("how_does_connect")
def how_does_connect(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'How does X connect to Y?' → the memory that bridges two concepts."""
    m = _CONNECT_RE.search(question)
    if m:
        a, b = m.group(1).strip().rstrip("?."), m.group(2).strip().rstrip("?.")
    else:
        parts = [p.strip() for p in re.split(r"\s+(?:to|and|vs|<->|→)\s+", question, maxsplit=1) if p.strip()]
        if len(parts) < 2:
            # Fall back to the two extracted entities, if any.
            if len(u.entities) >= 2:
                a, b = u.entities[0], u.entities[1]
            else:
                return AnswerShape("how_does_connect", question,
                                   "need two concepts — e.g. 'how does X connect to Y'", 0.0,
                                   caveats=["couldn't parse two concepts from the question"])
        else:
            a, b = parts
    hits_a, hits_b = retrieve(a, limit=6), retrieve(b, limit=6)
    both = retrieve(f"{a} {b}", limit=6)
    ids_a = {(h.get("table"), h.get("id")) for h in hits_a}
    ids_b = {(h.get("table"), h.get("id")) for h in hits_b}
    bridge_ids = ids_a & ids_b
    bridges = [h for h in (hits_a + hits_b) if (h.get("table"), h.get("id")) in bridge_ids]
    if bridges:
        ev = build_evidence(_dedupe(bridges + both))
        top = bridges[0]
        answer = f"'{a}' ↔ '{b}' bridged via {top.get('kind') or 'a shared item'}: {(top.get('content') or top.get('claim') or '')[:140]}"
    else:
        ev = build_evidence(both)
        answer = (f"no shared item — closest cross-mention: {ev[0]['preview'][:150]}"
                  if ev else f"no memory linking '{a}' and '{b}'")
    return AnswerShape("how_does_connect", question, answer,
                       confidence_from_hits(bridges or both), ev,
                       suggested_next=[f"what_for {a}", f"what_for {b}"])


@register("snapshot")
def snapshot(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """A dimensional summary of the memory around a concept (declared dims)."""
    hits = retrieve(question, limit=12)
    if not hits:
        return AnswerShape("snapshot", question, f"no memory matches '{question}'", 0.0)
    per_dim: dict[str, list[float]] = {}
    for h in hits:
        scores = h.get("dimensions") or score_item(h, question, MEMORY_DIMENSIONS)
        for name, val in scores.items():
            per_dim.setdefault(name, []).append(float(val))
    agg = {name: round(sum(vs) / len(vs), 4) for name, vs in per_dim.items()}
    overall = score_summary(agg)
    strongest = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:3]
    weakest = sorted(agg.items(), key=lambda kv: kv[1])[:3]
    answer = (f"snapshot of '{question}' (n={len(hits)}): overall {overall:.2f}. "
              f"strongest: " + ", ".join(f"{n}={v:.2f}" for n, v in strongest)
              + " · weakest: " + ", ".join(f"{n}={v:.2f}" for n, v in weakest))
    return AnswerShape("snapshot", question, answer, overall, build_evidence(hits),
                       suggested_next=[f"what_for {question}", f"optimize_for {question}"])


@register("recommend")
def recommend(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Given this context, what's relevant?' → top decision + top fact to recall."""
    hits = retrieve(question, limit=10)
    ev = build_evidence(hits, max_items=6)
    top_fact = next((e for e in ev if e["table"] == "facts"), None)
    top_decision = next((e for e in ev if e.get("kind") == "decision"), None)
    lines: list[str] = []
    if top_fact:
        lines.append(f"fact → {top_fact['preview'][:140]}")
    if top_decision and top_decision is not top_fact:
        lines.append(f"decision → {top_decision['preview'][:140]}")
    if not lines and ev:
        lines.append(f"most relevant → {ev[0]['preview'][:140]}")
    answer = (f"[intent={u.intent}] " + " ; ".join(lines)) if lines else "nothing relevant in memory yet"
    return AnswerShape("recommend", question, answer, confidence_from_hits(hits), ev,
                       suggested_next=[f"snapshot {question}", f"how_do_i {question}"])


@register("similar_to")
def similar_to(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'What's similar to X?' → memory near an anchor, ranked, with shared tags.

    The anchor is the quoted phrase / identifier if present, else the whole
    question. 'Similar' = fused retrieval similarity, annotated with tag overlap
    (a lightweight Jaccard cue, generalizing the source's graph-Jaccard).
    """
    anchor = u.entities[0] if u.entities else question
    hits = retrieve(anchor, limit=10)
    anchor_terms = set(re.findall(r"\w+", anchor.lower()))
    ev = build_evidence(hits, max_items=6)
    for e, h in zip(ev, hits):
        tags = h.get("tags") or []
        e["shared_tags"] = [t for t in tags if t.lower() in anchor_terms][:3]
    if ev:
        answer = f"nearest to '{anchor}': {ev[0]['preview'][:150]}"
    else:
        answer = f"nothing similar to '{anchor}' in memory"
    return AnswerShape("similar_to", question, answer, confidence_from_hits(hits), ev,
                       suggested_next=[f"how_does_connect {anchor} to X", f"snapshot {anchor}"])


@register("debug")
def debug(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Help me with this issue' → recorded gotchas paired with any known fix.

    Generalized from the source's limitation+workaround search: it pulls the
    failure-mode memory (gotchas/invariants) and pairs each with the strongest
    fix-shaped fact it can find.
    """
    hits = retrieve(question + " error fail bug crash workaround fix fallback", limit=10)
    ev = build_evidence(hits)
    problems = [e for e in ev if e.get("kind") in ("gotcha", "invariant")]
    fixes = [e for e in ev if e["table"] == "facts" or "fix" in (e["preview"] or "").lower()]
    if problems:
        head = problems[0]
        fix = next((f for f in fixes if f["id"] != head["id"]), None)
        answer = f"issue: {head['preview'][:140]}"
        if fix:
            answer += f" · fix: {fix['preview'][:120]}"
    elif ev:
        answer = f"no recorded gotcha; closest signal: {ev[0]['preview'][:150]}"
    else:
        answer = "no debugging memory for this — capture the gotcha when you solve it"
    caveats = [] if problems else ["no gotcha/invariant matched; this failure may be new"]
    return AnswerShape("debug", question, answer, confidence_from_hits(hits), ev, caveats,
                       suggested_next=[f"why_not {question}", f"how_do_i fix {question}"])


# Which declared dimension a criteria word optimizes for.
_CRITERIA_DIM: dict[str, str] = {
    "durable": "storage_tier", "authoritative": "storage_tier", "durability": "storage_tier",
    "precise": "match_precision", "exact": "match_precision", "precision": "match_precision",
    "relevant": "semantic_coverage", "relevance": "semantic_coverage",
    "reliable": "error_recovery", "safe": "error_recovery", "robust": "error_recovery",
    "broad": "generative_scope", "coverage": "generative_scope",
    "connected": "synthesis_potential", "synthesizable": "synthesis_potential",
}


@register("optimize_for")
def optimize_for(question: str, retrieve: Retriever, u: Understanding) -> AnswerShape:
    """'Best memory for GOAL, optimized for CRITERIA' → dimension-reranked recall.

    Retrieves for the goal, then re-ranks by one declared dimension (the criteria).
    Criteria is read from the question ('... for durable', '... precise ...') or a
    literal dimension name; defaults to relevance (``semantic_coverage``).
    """
    q_lower = question.lower()
    dim = "semantic_coverage"
    criteria = "relevant"
    for word, d in _CRITERIA_DIM.items():
        if re.search(rf"\b{re.escape(word)}\b", q_lower):
            dim, criteria = d, word
            break
    else:
        for name in MEMORY_DIMENSIONS.names:
            if name in q_lower:
                dim, criteria = name, name
                break
    hits = retrieve(question, limit=12)
    scored: list[tuple[float, dict[str, Any]]] = []
    for h in hits:
        dims = h.get("dimensions") or score_item(h, question, MEMORY_DIMENSIONS)
        scored.append((float(dims.get(dim, 0.5)), h))
    scored.sort(key=lambda sh: sh[0], reverse=True)
    ranked = [h for _, h in scored]
    ev = build_evidence(ranked, max_items=6)
    for e, (s, _) in zip(ev, scored):
        e[dim] = round(s, 4)
    if ev:
        answer = f"optimized for {criteria} ({dim}): {ev[0]['preview'][:140]} [{dim}={scored[0][0]:.2f}]"
    else:
        answer = f"no memory to optimize for '{question}'"
    return AnswerShape("optimize_for", question, answer,
                       confidence_from_hits(ranked), ev,
                       suggested_next=[f"snapshot {question}", f"recommend {question}"])


def _dedupe(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for h in hits:
        key = (h.get("table"), h.get("id"))
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


# The registered ask names, in a stable declared order.
ASK_NAMES: tuple[str, ...] = (
    "why_not", "can_i", "how_do_i", "what_for", "route", "how_does_connect",
    "snapshot", "recommend", "similar_to", "debug", "optimize_for",
)
