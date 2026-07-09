"""synthesis-mud — the epistemic guard that refuses to muddy your memory.

Most retrieval systems answer *"what is similar to my query?"*. project_memory
also answers *"would merging these two facts be **clean** or **muddy**?"* — and
refuses to muddy. This is the layer that makes it "not just another RAG".

The metaphor is colour theory. Two *primary* colours mix into a clean *secondary*
(blue + yellow → green). Mix everything and you get **MUD** — a brown that looks
like a result but has lost all coherence. Facts are the same: two facts whose
*qualities* clash produce a synthesis that *looks* like progress but smuggles in
opinion-as-fact, collides incompatible perspectives, or inflates certainty.

Each fact is assessed along **5 + 1 axes** (Eyal Nof's colour-theory synthesis
methodology, 2026-05-23):

  texture      factual quality      smooth / rough / grainy
  lighting     perspective/framing  a viewpoint (security, business, general, …)
  composition  argument structure   premise_conclusion / cause_effect / …
  contrast     how difference reads  binary / spectrum / implicit
  method       how it was reasoned  deduction / induction / analogy / abduction
  (+recursion  derivation depth — how many layers of synthesis deep it sits)

`synthesize(a, b)` assesses both facts, runs a **6-layer** compatibility check
(cheap checks first, short-circuit on the first failure), and returns one of
three verdicts with a *calibrated* confidence and a human-readable ``mud_reason``:

  clean   — merge freely; confidence ≈ the lower input certainty
  bridge  — compatible but frictional; the merge must *say* the bridge; lower confidence
  refuse  — incompatible; no merge, and the reason tells you why

It is deterministic, AI-less, ~1 file, and domain-portable. The axis *assessment*
here is a transparent marker-word heuristic — good enough to catch the common MUD
patterns automatically, and every axis can be overridden explicitly on a `Fact`
when you want precision. As the methodology says: it flags structural
incompatibility patterns; it does not prove correctness, and it is not a
replacement for human review.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

# The five compatibility axes (recursion depth is lineage metadata, not a matrix).
AXES = ("texture", "lighting", "composition", "contrast", "method")

# Tunable thresholds (methodology §5). A single axis below ``SYNTHESIS_THRESHOLD``
# is MUD; two or more axes below ``MULTI_DIM_THRESHOLD`` is also MUD.
SYNTHESIS_THRESHOLD = 0.4
MULTI_DIM_THRESHOLD = 0.6
# Below this minimum compatibility (but not MUD) a merge needs an explicit bridge.
BRIDGE_THRESHOLD = 0.7


# ── The fact and its axes ────────────────────────────────────────────────────

@dataclass
class Fact:
    """A statement assessed along the 5+1 epistemic-aesthetic axes.

    Use `Fact.assess(text)` for the deterministic heuristic, or construct one
    directly (or pass overrides to ``assess``) when you already know an axis.
    """

    statement: str
    is_fact: bool = True
    texture: str = "smooth"                 # smooth / rough / grainy
    lighting: str = "general"               # the perspective / framing
    composition: str = "parallel"           # argument structure
    contrast: str = "implicit"              # binary / spectrum / implicit
    method: str = "induction"               # reasoning method
    certainty: float = 0.8                  # method certainty [0, 1]
    recursion_depth: int = 1                # derivation depth

    @classmethod
    def assess(cls, statement: str, **overrides: Any) -> "Fact":
        """Infer the axes of ``statement`` with transparent marker-word rules.

        Any keyword override replaces the inferred value — e.g.
        ``Fact.assess(text, lighting="security")``.
        """
        low = statement.lower()
        is_fact = not _has(low, _OPINION)
        texture = (
            "rough" if (_has(low, _ROUGH) or not is_fact)
            else "grainy" if _has(low, _GRAINY) or _PCT.search(statement)
            else "smooth"
        )
        method, certainty = _assess_method(low)
        fact = cls(
            statement=statement,
            is_fact=is_fact,
            texture=texture,
            lighting=_assess_lighting(low),
            composition=_assess_composition(low),
            contrast=_assess_contrast(low),
            method=method,
            certainty=certainty,
        )
        for k, v in overrides.items():
            setattr(fact, k, v)
        return fact


# ── Marker-word tables for the deterministic assessor ────────────────────────

_OPINION = ("i think", "i believe", "i feel", "in my opinion", "imho", "my favorite",
            "i love", "i hate", "the best", "the worst", "should be", "obviously better")
_ROUGH = ("arguably", "debatable", "controversial", "some say", "it depends",
          "probably", "might be", "seems", "i think")
_GRAINY = ("most ", "many ", "often", "usually", "tend to", "on average", "n=")
_PCT = re.compile(r"\d+\s*%")

_PERSPECTIVES = ("security", "business", "user", "technical", "ethical", "practical",
                 "performance", "legal", "financial", "design")
# Perspectives that pull in opposite directions — a naive merge smuggles one as universal.
_OPPOSING = {
    frozenset({"security", "business"}),
    frozenset({"user", "technical"}),
    frozenset({"ethical", "practical"}),
    frozenset({"performance", "security"}),
}


def _has(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _assess_lighting(low: str) -> str:
    m = re.search(r"from an? ([a-z]+) (?:perspective|standpoint|point of view)", low)
    if m and m.group(1) in _PERSPECTIVES:
        return m.group(1)
    for p in _PERSPECTIVES:
        if re.search(rf"\b{p}(?:-wise| perspective| standpoint)\b", low):
            return p
    return "general"


def _assess_composition(low: str) -> str:
    if _has(low, ("therefore", "thus", "hence", " so ")):
        return "premise_conclusion"
    if _has(low, ("because", "since ", "due to", "results in", "leads to", "causes")):
        return "cause_effect"
    if _has(low, ("first ", "then ", "finally", "after ", "before ")):
        return "chronological"
    if _has(low, ("unlike", "whereas", "compared to", "differs", "versus", " vs ")):
        return "compare_contrast"
    if _has(low, ("most importantly", "primarily", "secondarily", "above all")):
        return "hierarchical"
    return "parallel"


def _assess_contrast(low: str) -> str:
    if _has(low, ("either ", " or ", "black and white", "all or nothing")):
        return "binary"
    if _has(low, ("ranges from", "spectrum", "continuum", "varying degrees",
                  "trade-off", "tradeoff", "more or less", "to weak")):
        return "spectrum"
    return "implicit"


def _assess_method(low: str) -> tuple[str, float]:
    if _has(low, ("all ", "every ", "must ", "necessarily", "by definition")):
        return "deduction", 1.0
    if _has(low, ("best explanation", "likely because", "probably due", "suggests that")):
        return "abduction", 0.6
    if _has(low, ("like ", "similar to", "worked for", "analogous", "just as")):
        return "analogy", 0.7
    if _has(low, ("most ", "generally", "observed", "tend to", "usually", "typically")):
        return "induction", 0.8
    if _has(low, ("given ", "combining", "building on", "together")):
        return "composition", 0.75
    return "induction", 0.8


# ── The five compatibility matrices (methodology §5, ported verbatim) ─────────

def texture_compatibility(a: str, b: str) -> float:
    # Keys are stored pre-sorted so the sorted-pair lookup below always hits.
    matrix = {
        ("smooth", "smooth"): 1.0, ("rough", "smooth"): 0.6, ("grainy", "smooth"): 0.7,
        ("rough", "rough"): 0.8, ("grainy", "rough"): 0.7, ("grainy", "grainy"): 0.9,
    }
    return matrix.get(tuple(sorted((a, b))), 0.5)


def lighting_compatibility(a: str, b: str) -> float:
    if a == b:
        return 0.95
    if frozenset({a, b}) in _OPPOSING:
        return 0.4  # opposing perspectives — MUD-likely
    return 0.7


def composition_compatibility(a: str, b: str) -> float:
    if a == b:
        return 0.95
    similar = {
        ("cause_effect", "premise_conclusion"): 0.85,
        ("compare_contrast", "parallel"): 0.85,
        ("cause_effect", "chronological"): 0.85,
    }
    return similar.get(tuple(sorted((a, b))), 0.7 if "parallel" in (a, b) else 0.5)


def contrast_compatibility(a: str, b: str) -> float:
    if a == "binary" and b == "binary":
        return 0.7  # compounded false-dichotomy risk
    if a == "spectrum" and b == "spectrum":
        return 0.95
    if {a, b} == {"binary", "spectrum"}:
        return 0.6
    return 0.75


def method_compatibility(a: str, b: str, cert_a: float, cert_b: float) -> float:
    if a == b:
        return 0.95
    if abs(cert_a - cert_b) > 0.3:
        return 0.5  # significant certainty mismatch
    return 0.75


def compatibilities(a: Fact, b: Fact) -> dict[str, float]:
    """All five axis compatibilities between two facts."""
    return {
        "texture": texture_compatibility(a.texture, b.texture),
        "lighting": lighting_compatibility(a.lighting, b.lighting),
        "composition": composition_compatibility(a.composition, b.composition),
        "contrast": contrast_compatibility(a.contrast, b.contrast),
        "method": method_compatibility(a.method, b.method, a.certainty, b.certainty),
    }


# ── MUD detection ────────────────────────────────────────────────────────────

@dataclass
class MudVerdict:
    is_mud: bool
    reasons: list[str]
    compatibilities: dict[str, float]
    failing_layer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_mud": self.is_mud,
            "reasons": self.reasons,
            "compatibilities": {k: round(v, 4) for k, v in self.compatibilities.items()},
            "failing_layer": self.failing_layer,
        }


# Layer order (cheap → expensive); Layer 1 is the boolean fact check.
_LAYERS = (
    ("texture", "Layer 2 — texture incompatible"),
    ("lighting", "Layer 3 — lighting/perspective conflict"),
    ("composition", "Layer 4 — composition incompatible"),
    ("contrast", "Layer 5 — contrast/nuance lost"),
    ("method", "Layer 6 — method/certainty mismatch"),
)


def detect_mud(
    a: Fact,
    b: Fact,
    *,
    synthesis_threshold: float = SYNTHESIS_THRESHOLD,
    multi_dim_threshold: float = MULTI_DIM_THRESHOLD,
) -> MudVerdict:
    """The 6-layer check. Layer 1 (each input is a validated fact) first, then the
    five axis layers cheap→expensive, short-circuiting on the first failure —
    while still recording every axis compatibility for the audit trail."""
    compat = compatibilities(a, b)

    # Layer 1 — base validation.
    if not a.is_fact or not b.is_fact:
        which = "A" if not a.is_fact else "B"
        return MudVerdict(
            True,
            [f"Layer 1 — input {which} is opinion, not a validated fact; "
             "reformulate as an observation or supply evidence"],
            compat, failing_layer="Layer 1",
        )

    # Layers 2-6 — the axis matrices, short-circuit on first sub-threshold axis.
    # "At or below" the threshold is MUD: the canonical trigger is opposing
    # perspectives (lighting compat 0.4), which the methodology's worked example
    # 9.3 refuses. A method certainty-mismatch of 0.5 stays above it (example 9.4).
    for axis, label in _LAYERS:
        if compat[axis] <= synthesis_threshold:
            return MudVerdict(
                True, [f"{label} (compat={compat[axis]:.2f})"],
                compat, failing_layer=label.split(" —")[0],
            )

    # Multi-dimensional rule — several simultaneously-weak axes muddy the whole.
    weak = [ax for ax, c in compat.items() if c < multi_dim_threshold]
    if len(weak) >= 2:
        return MudVerdict(
            True, [f"multiple axes weak simultaneously: {weak}"],
            compat, failing_layer="multi-dim",
        )

    return MudVerdict(False, [], compat)


# ── Synthesis ────────────────────────────────────────────────────────────────

@dataclass
class SynthesisResult:
    """The outcome of a MUD-checked synthesis attempt."""

    verdict: str                             # "clean" | "bridge" | "refuse"
    fact_a: str
    fact_b: str
    synthesized: str | None                  # the merged statement, or None if refused
    confidence: float                        # calibrated [0, 1]
    mud_reason: str                          # why refused / why bridged / "clean"
    compatibilities: dict[str, float]
    certainty_preserved: bool = True
    bridging_axes: list[str] = field(default_factory=list)

    @property
    def is_mud(self) -> bool:
        return self.verdict == "refuse"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "fact_a": self.fact_a,
            "fact_b": self.fact_b,
            "synthesized": self.synthesized,
            "confidence": round(self.confidence, 4),
            "mud_reason": self.mud_reason,
            "compatibilities": {k: round(v, 4) for k, v in self.compatibilities.items()},
            "certainty_preserved": self.certainty_preserved,
            "bridging_axes": self.bridging_axes,
        }


def synthesize(
    a: "str | Fact",
    b: "str | Fact",
    *,
    synthesis_threshold: float = SYNTHESIS_THRESHOLD,
    multi_dim_threshold: float = MULTI_DIM_THRESHOLD,
) -> SynthesisResult:
    """Attempt to merge two facts, refusing (or bridging) when it would be MUD.

    ``a``/``b`` may be raw strings (assessed with the heuristic) or `Fact`s you
    assessed/overrode yourself. Returns a `SynthesisResult` whose ``verdict`` is
    ``clean`` / ``bridge`` / ``refuse`` and whose ``confidence`` is *calibrated*:
    never higher than the lower input certainty, and lowered further when the
    merge needs a bridge.
    """
    fa = a if isinstance(a, Fact) else Fact.assess(a)
    fb = b if isinstance(b, Fact) else Fact.assess(b)
    verdict = detect_mud(fa, fb, synthesis_threshold=synthesis_threshold,
                         multi_dim_threshold=multi_dim_threshold)
    compat = verdict.compatibilities
    base = min(fa.certainty, fb.certainty)
    avg = sum(compat.values()) / len(compat)
    cert_preserved = abs(fa.certainty - fb.certainty) <= 0.3

    if verdict.is_mud:
        return SynthesisResult(
            "refuse", fa.statement, fb.statement, None, 0.0,
            "; ".join(verdict.reasons), compat, cert_preserved,
        )

    bridging = [ax for ax, c in compat.items() if c < BRIDGE_THRESHOLD]
    if bridging:
        merged = (f"{_strip(fa.statement)} — bridged with the constraint that "
                  f"{_lower(fb.statement)} (state both; do not collapse one into the other)")
        return SynthesisResult(
            "bridge", fa.statement, fb.statement, merged,
            round(base * avg * 0.85, 4),
            f"compatible but frictional on {bridging}; the merge must carry the bridge",
            compat, cert_preserved, bridging_axes=bridging,
        )

    merged = f"{_strip(fa.statement)}; and {_lower(fb.statement)}"
    return SynthesisResult(
        "clean", fa.statement, fb.statement, merged,
        round(base * avg, 4),
        "clean synthesis across all 6 layers", compat, cert_preserved,
    )


def _strip(s: str) -> str:
    return s.strip().rstrip(".")


def _lower(s: str) -> str:
    s = s.strip()
    return (s[0].lower() + s[1:]) if s else s


# ── Optional persistence (methodology §4 minimum-viable schema) ───────────────

SYNTHESIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS synthesis_facts (
  synthesis_id       TEXT PRIMARY KEY,
  fact_a             TEXT NOT NULL,
  fact_b             TEXT NOT NULL,
  synthesized_fact   TEXT,
  verdict            TEXT NOT NULL,
  confidence         REAL DEFAULT 0.0,
  is_mud             INTEGER DEFAULT 0,
  mud_reason         TEXT,
  certainty_preserved INTEGER DEFAULT 1,
  compatibilities    TEXT,                    -- JSON {axis: score}
  created_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_synthesis_is_mud ON synthesis_facts(is_mud);
"""


def install_synthesis_tables(conn: sqlite3.Connection) -> None:
    """Create the ``synthesis_facts`` audit table (idempotent). Optional — the
    ``mud_detected_count`` over this table is a signal of where the system's
    epistemic discipline is engaging."""
    conn.executescript(SYNTHESIS_SCHEMA)
    conn.commit()


def record_synthesis(
    conn: sqlite3.Connection,
    result: SynthesisResult,
    *,
    created_at: str | None = None,
    id: str | None = None,
) -> str:
    """Persist a synthesis attempt (clean, bridge, or refusal) for the audit
    trail. Returns the ``synthesis_id``."""
    import json
    from .store import now_iso

    install_synthesis_tables(conn)
    sid = id or uuid.uuid4().hex
    conn.execute(
        "INSERT INTO synthesis_facts (synthesis_id, fact_a, fact_b, synthesized_fact, "
        "verdict, confidence, is_mud, mud_reason, certainty_preserved, compatibilities, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sid, result.fact_a, result.fact_b, result.synthesized, result.verdict,
            result.confidence, int(result.is_mud), result.mud_reason,
            int(result.certainty_preserved), json.dumps(result.compatibilities),
            created_at or now_iso(),
        ),
    )
    conn.commit()
    return sid
