"""M4 · provenance + functional-journey (project_memory.provenance).

All timestamps/ids are injected so ordering and folding are deterministic —
the load log is provenance/telemetry, not part of the deterministic retrieval
path, so wall-clock is fine in production but pinned here.
"""

import pytest

from project_memory import ProjectMemory
from project_memory import provenance as pv
from project_memory.portfolio import PORTFOLIO_SCHEMA

_T = "2026-07-12T00:00:0"  # + "<n>+00:00" for a stable ascending order


@pytest.fixture
def brain():
    m = ProjectMemory.open(":memory:", PORTFOLIO_SCHEMA)
    yield m
    m.close()


def _load(mem, scope, kind, trigger, *, session=None, id, n):
    mem.remember(
        f"loaded {kind} '{scope}'", kind="brain_load", session_id=session,
        tags=[scope, kind, trigger], metadata={"trigger": trigger},
        method="brain_load", id=id, created_at=f"{_T}{n}+00:00",
    )


def _export(mem, scope, provider, *, session=None, id, n):
    mem.remember(
        f"exported '{scope}' to {provider}", kind="brain_export", session_id=session,
        tags=[scope, provider], metadata={"provider": provider, "paths": ["/x/F.md"]},
        method="brain_export", id=id, created_at=f"{_T}{n}+00:00",
    )


# ── record_use (the declared "used" marker) ──────────────────────────────────

def test_record_use_appends_a_brain_use_episode(brain):
    pv.record_use(brain, "declared_core", session="s1", note="checked its API", id="u1",
                  created_at=f"{_T}1+00:00")
    rows = brain.recent(limit=5, kind="brain_use")
    assert len(rows) == 1
    assert rows[0]["tags"] == ["declared_core", "used"]
    assert rows[0]["content"] == "used 'declared_core'"


def test_record_use_rejects_empty_scope(brain):
    with pytest.raises(ValueError):
        pv.record_use(brain, "   ")


def test_record_use_is_append_only_not_a_flag(brain):
    # two uses of the same scope are two episodes — history, not a toggled bit.
    pv.record_use(brain, "alpha", id="u1", created_at=f"{_T}1+00:00")
    pv.record_use(brain, "alpha", id="u2", created_at=f"{_T}2+00:00")
    assert len(brain.recent(limit=5, kind="brain_use")) == 2


# ── provenance_events (normalization + ordering + filtering) ─────────────────

def test_events_are_ordered_and_normalized(brain):
    _load(brain, "declared_core", "project", "startup", session="s1", id="l1", n=1)
    pv.record_use(brain, "declared_core", session="s1", id="u1", created_at=f"{_T}2+00:00")
    _export(brain, "declared_core", "claude", session="s1", id="x1", n=3)

    events = pv.provenance_events(brain)
    assert [e.event for e in events] == ["load", "use", "export"]
    load, use, exp = events
    assert (load.scope, load.scope_kind, load.trigger) == ("declared_core", "project", "startup")
    assert (use.scope, use.event) == ("declared_core", "use")
    assert (exp.scope, exp.scope_kind, exp.detail) == ("declared_core", "project", "claude")


def test_events_ignore_non_provenance_kinds(brain):
    brain.remember("just an interface atom", kind="interface", tags=["alpha"],
                   id="i1", created_at=f"{_T}1+00:00")
    _load(brain, "alpha", "project", "cli", id="l1", n=2)
    events = pv.provenance_events(brain)
    assert [e.event for e in events] == ["load"]


def test_events_session_filter(brain):
    _load(brain, "alpha", "project", "startup", session="s1", id="l1", n=1)
    _load(brain, "beta", "project", "startup", session="s2", id="l2", n=2)
    assert [e.scope for e in pv.provenance_events(brain, session="s1")] == ["alpha"]
    assert [e.scope for e in pv.provenance_events(brain, session="s2")] == ["beta"]
    # unfiltered view sees both
    assert {e.scope for e in pv.provenance_events(brain)} == {"alpha", "beta"}


# ── unused_loads ("loaded but never used") ───────────────────────────────────

def test_unused_reports_loaded_not_used(brain):
    _load(brain, "declared_core", "project", "startup", session="s1", id="l1", n=1)
    _load(brain, "aria-app-builder", "pack", "menu", session="s1", id="l2", n=2)
    pv.record_use(brain, "declared_core", session="s1", id="u1", created_at=f"{_T}3+00:00")

    unused = pv.unused_loads(brain, session="s1")
    assert [e.scope for e in unused] == ["aria-app-builder"]


def test_unused_packs_filter(brain):
    _load(brain, "alpha", "project", "startup", session="s1", id="l1", n=1)
    _load(brain, "aria-app-builder", "pack", "menu", session="s1", id="l2", n=2)
    # nothing marked used → both are unused, but --packs keeps only the pack
    packs = pv.unused_loads(brain, session="s1", scope_kind="pack")
    assert [e.scope for e in packs] == ["aria-app-builder"]
    assert {e.scope for e in pv.unused_loads(brain, session="s1")} == {"alpha", "aria-app-builder"}


def test_unused_dedups_to_earliest_load(brain):
    _load(brain, "alpha", "project", "startup", session="s1", id="l1", n=1)
    _load(brain, "alpha", "project", "menu", session="s1", id="l2", n=2)
    unused = pv.unused_loads(brain, session="s1")
    assert len(unused) == 1
    assert unused[0].trigger == "startup"  # the earliest load kept


def test_unused_use_in_another_session_does_not_count(brain):
    _load(brain, "alpha", "project", "startup", session="s1", id="l1", n=1)
    # marked used only in a *different* session → still unused within s1
    pv.record_use(brain, "alpha", session="s2", id="u1", created_at=f"{_T}2+00:00")
    assert [e.scope for e in pv.unused_loads(brain, session="s1")] == ["alpha"]
    # but the all-sessions view sees it as used
    assert pv.unused_loads(brain) == []


# ── journey (the story) ──────────────────────────────────────────────────────

def test_journey_story_renders_the_narrative(brain):
    _load(brain, "declared_core", "project", "startup", session="s1", id="l1", n=1)
    _load(brain, "aria-app-builder", "pack", "menu", session="s1", id="l2", n=2)
    pv.record_use(brain, "declared_core", session="s1", id="u1", created_at=f"{_T}3+00:00")

    story = pv.journey(brain, session="s1").story()
    assert "# Journey — session s1" in story
    assert "3 events:" in story
    assert "1. loaded project 'declared_core'  (via startup)" in story
    assert "used 'declared_core'" in story
    assert "Loaded but never used (1):" in story
    assert "· pack 'aria-app-builder'" in story


def test_journey_empty_is_explicit(brain):
    story = pv.journey(brain, session="ghost").story()
    assert "_No load/use/export provenance recorded for session ghost._" in story


def test_journey_to_dict_shape(brain):
    _load(brain, "alpha", "project", "startup", session="s1", id="l1", n=1)
    d = pv.journey(brain, session="s1").to_dict()
    assert d["session"] == "s1"
    assert d["events"][0]["event"] == "load"
    assert d["events"][0]["scope"] == "alpha"
    assert [u["scope"] for u in d["unused"]] == ["alpha"]


def test_provevent_phrase_variants():
    load = pv.ProvEvent("t", "load", "alpha", "project", "startup")
    use = pv.ProvEvent("t", "use", "alpha", detail="checked API")
    exp = pv.ProvEvent("t", "export", "alpha", "project", detail="claude")
    assert load.phrase() == "loaded project 'alpha'  (via startup)"
    assert use.phrase() == "used 'alpha' — checked API"
    assert exp.phrase() == "exported project 'alpha' → claude"
