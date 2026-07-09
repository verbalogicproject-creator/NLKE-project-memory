from project_memory import extract_entities, understand


def test_extract_quoted_phrase():
    assert "reciprocal rank fusion" in extract_entities('what is "reciprocal rank fusion"?')


def test_extract_identifiers():
    ents = extract_entities("how does FTS5 connect to created_at and CamelCase?")
    assert "FTS5" in ents and "created_at" in ents and "CamelCase" in ents


def test_extract_dedupes_case_insensitively():
    ents = extract_entities("FTS5 fts5 Fts5")
    assert len([e for e in ents if e.lower() == "fts5"]) == 1


def test_understand_returns_intent_and_entities():
    u = understand("why did we drop Postgres?")
    assert u.intent
    assert 0.0 <= u.confidence <= 1.0
    assert "Postgres" in u.entities


def test_understand_is_pure():
    a = understand("how do I configure FTS5?")
    b = understand("how do I configure FTS5?")
    assert a.to_dict() == b.to_dict() or (a.intent == b.intent and a.entities == b.entities)
