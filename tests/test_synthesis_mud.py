"""The synthesis-mud module — verified against the methodology's worked examples."""

from project_memory import Fact, compatibilities, detect_mud, synthesize
from project_memory.store import connect
from project_memory.synthesis_mud import (
    install_synthesis_tables,
    lighting_compatibility,
    record_synthesis,
    texture_compatibility,
)


# ── assessment heuristics ─────────────────────────────────────────────────────

def test_opinion_is_not_a_fact():
    assert Fact.assess("I think Python is the best language.").is_fact is False


def test_statement_is_a_fact():
    assert Fact.assess("Python is widely adopted in industry.").is_fact is True


def test_perspective_extraction():
    f = Fact.assess("From a security perspective, plaintext is risky.")
    assert f.lighting == "security"


def test_statistical_texture_is_grainy():
    assert Fact.assess("70% of users prefer dark mode.").texture == "grainy"


def test_axis_override():
    f = Fact.assess("some text", lighting="business")
    assert f.lighting == "business"


# ── compatibility matrices (verbatim from the methodology) ───────────────────

def test_texture_matrix():
    assert texture_compatibility("smooth", "smooth") == 1.0
    assert texture_compatibility("smooth", "rough") == 0.6
    assert texture_compatibility("grainy", "grainy") == 0.9


def test_opposing_perspectives_low():
    assert lighting_compatibility("security", "business") == 0.4
    assert lighting_compatibility("technical", "technical") == 0.95


# ── the worked examples (methodology §9) ─────────────────────────────────────

def test_clean_synthesis():
    r = synthesize("Most production code is read more than written.",
                   "Explicit naming beats compactness for code read often.")
    assert r.verdict == "clean"
    assert r.synthesized is not None
    assert r.confidence <= 0.9   # never more confident than inputs


def test_bridge_smooth_plus_rough():
    r = synthesize("Comprehensive test coverage is best practice for production code.",
                   "Arguably, this legacy codebase is too fragile to refactor safely without tests.")
    assert r.verdict == "bridge"
    assert "texture" in r.bridging_axes
    assert r.synthesized is not None


def test_bridge_via_explicit_texture_override():
    # The design's canonical example, using the documented axis override.
    a = Fact.assess("Comprehensive test coverage is best practice.", texture="smooth")
    b = Fact.assess("This legacy codebase has 0% test coverage and 200000 lines.", texture="rough")
    r = synthesize(a, b)
    assert r.verdict == "bridge" and "texture" in r.bridging_axes


def test_refuse_layer1_opinion():
    r = synthesize("I think Python is the best language.",
                   "Python is widely adopted in industry.")
    assert r.verdict == "refuse" and r.is_mud
    assert "Layer 1" in r.mud_reason
    assert r.synthesized is None
    assert r.confidence == 0.0


def test_refuse_layer3_perspective_conflict():
    r = synthesize(
        "From a security perspective, storing tokens in plaintext is an unacceptable risk.",
        "From a business perspective, the plaintext token store was cheap and worked fine.")
    assert r.verdict == "refuse" and r.is_mud
    assert "Layer 3" in r.mud_reason
    assert r.compatibilities["lighting"] == 0.4


def test_certainty_preserved_flag():
    # deduction (1.0) + analogy (0.7) → certainty gap > 0.3
    a = Fact.assess("x", method="deduction", certainty=1.0, is_fact=True)
    b = Fact.assess("y", method="analogy", certainty=0.5, is_fact=True)
    r = synthesize(a, b)
    assert r.certainty_preserved is False


def test_detect_mud_records_all_compatibilities():
    v = detect_mud(Fact.assess("A smooth fact."), Fact.assess("Another smooth fact."))
    assert set(v.compatibilities) == {"texture", "lighting", "composition", "contrast", "method"}


def test_compatibilities_helper():
    c = compatibilities(Fact.assess("a"), Fact.assess("b"))
    assert all(0.0 <= v <= 1.0 for v in c.values())


# ── optional persistence ──────────────────────────────────────────────────────

def test_persist_synthesis():
    conn = connect()
    install_synthesis_tables(conn)
    r = synthesize("From a security perspective, X is risky.",
                   "From a business perspective, X is fine.")
    sid = record_synthesis(conn, r, created_at="2026-01-01T00:00:00+00:00", id="s1")
    row = conn.execute("SELECT verdict, is_mud FROM synthesis_facts WHERE synthesis_id='s1'").fetchone()
    assert sid == "s1"
    assert row[0] == "refuse" and row[1] == 1


def test_synthesize_result_to_dict_roundtrip():
    d = synthesize("A fact.", "Another fact.").to_dict()
    assert set(d) >= {"verdict", "confidence", "mud_reason", "compatibilities"}
