import pytest

from project_memory import ASK_NAMES, AnswerShape, route_intent
from project_memory.asks import _INTENT_ROUTES, run_ask


def test_eleven_asks_registered():
    assert len(ASK_NAMES) == 11
    assert set(ASK_NAMES) == {
        "why_not", "can_i", "how_do_i", "what_for", "route", "how_does_connect",
        "snapshot", "recommend", "similar_to", "debug", "optimize_for",
    }


@pytest.mark.parametrize("name", ASK_NAMES)
def test_every_ask_returns_answershape(demo, name):
    res = demo.ask("offline search timestamps storage", name=name)
    assert isinstance(res, AnswerShape)
    d = res.to_dict()
    assert set(d) == {"ask", "question", "answer", "confidence", "evidence",
                      "caveats", "suggested_next", "trace_id"}
    assert d["ask"] == name
    assert 0.0 <= d["confidence"] <= 1.0


def test_intent_routing_covers_eight_intents():
    for intent in ("exact_match", "capability_check", "debugging", "workflow",
                   "comparison", "goal_based", "exploratory", "semantic"):
        assert route_intent(intent) in ASK_NAMES
    # every routed target is a real ask
    assert set(_INTENT_ROUTES.values()) <= set(ASK_NAMES)


def test_ask_auto_routes_by_intent(demo):
    # No explicit name → routed by classified intent.
    res = demo.ask("why did we store timestamps in UTC?")
    assert res.ask in ASK_NAMES


def test_unknown_ask_is_explicit(demo):
    res = demo.ask("anything", name="does_not_exist")
    assert res.confidence == 0.0
    assert "unknown ask" in res.answer


def test_why_not_finds_gotcha(demo):
    res = demo.ask("why did timestamps reorder?", name="why_not")
    assert res.evidence
    assert res.confidence > 0


def test_optimize_for_reranks_by_dimension(demo):
    res = demo.ask("search notes optimized for durable", name="optimize_for")
    # storage_tier annotated onto the top evidence
    assert res.evidence
    assert any("storage_tier" in e for e in res.evidence)


def test_can_i_yields_verdict(demo):
    res = demo.ask("can I search offline?", name="can_i")
    assert res.answer in ("yes", "no", "partial — some paths yes, some no",
                          "unknown — no clear signal in memory")


def test_run_ask_direct(demo):
    res = run_ask("what_for", "what is SQLite for", demo._retriever(6))
    assert res.ask == "what_for"
