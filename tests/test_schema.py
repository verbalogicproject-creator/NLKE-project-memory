import pytest

from declared_core import CorpusSchema
from project_memory import DEFAULT_KINDS, MemorySchema


def test_default_kinds_present():
    s = MemorySchema()
    assert "decision" in s.kinds and "gotcha" in s.kinds
    assert len(s.kinds) == len(set(s.kinds))


def test_custom_kinds():
    s = MemorySchema(kinds=("a", "b"))
    s.validate_kind("a")
    with pytest.raises(ValueError):
        s.validate_kind("decision")


def test_duplicate_kinds_rejected():
    with pytest.raises(ValueError):
        MemorySchema(kinds=("a", "a"))


def test_empty_kinds_rejected():
    with pytest.raises(ValueError):
        MemorySchema(kinds=())


def test_same_table_names_rejected():
    with pytest.raises(ValueError):
        MemorySchema(episode_table="x", fact_table="x")


def test_compiles_to_two_table_corpus_with_link():
    corpus = MemorySchema().corpus_schema()
    assert isinstance(corpus, CorpusSchema)
    names = {s.name for s in corpus.sources}
    assert names == {"episodes", "facts"}
    assert len(corpus.links) == 1
    link = corpus.links[0]
    assert link.parent == "episodes" and link.child == "facts"
    assert link.key == "source_episode_id"


def test_fact_source_filters_active():
    fact_src = MemorySchema().fact_source()
    assert fact_src.where == "status = 'active'"
    assert "claim" in fact_src.text_columns and "reason" in fact_src.text_columns


def test_episode_source_clusters_and_tags():
    ep = MemorySchema().episode_source()
    assert ep.text_columns == ("content",)
    assert "kind" in ep.cluster_columns
    assert "tags" in ep.tag_columns


def test_custom_table_names_not_hardcoded():
    corpus = MemorySchema(episode_table="ev", fact_table="claims").corpus_schema()
    assert {s.name for s in corpus.sources} == {"ev", "claims"}
    assert corpus.links[0].child == "claims"
