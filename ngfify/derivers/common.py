"""Shared container + helper reused by every per-language deriver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL

if TYPE_CHECKING:
    from ..config import NgfifyConfig


@dataclass
class DerivedFields:
    """The per-language-derived slots; the dispatcher fills in the rest of `AiCard`."""

    public_interfaces: list[str]
    provides: list[str]
    depends_on: list[str]
    risk_areas: list[str]
    graph_rag_entities: list[str]


def build_graph_rag_entities(
    public_interfaces: list[str],
    depends_on: list[str],
    config: "NgfifyConfig",
) -> list[str]:
    """`graph_rag_entities` = defined public symbols + salient imported names.

    Per SPEC-v0.1: "the file's defined public symbols + salient imported
    names (the nouns a graph would link)." Every entity here is either a
    `public_interfaces` value verbatim or a short name derived from a
    `depends_on` value -- never an invented noun.
    """
    if public_interfaces == [TODO_SENTINEL] and depends_on == [TODO_SENTINEL]:
        return [TODO_SENTINEL]

    entities: list[str] = []
    for name in public_interfaces:
        if name != TODO_SENTINEL and name not in entities:
            entities.append(name)
    for dependency in depends_on:
        if dependency == TODO_SENTINEL:
            continue
        short = dependency.strip(".").split(".")[0].split("/")[-1].strip("#.<>")
        if short and short not in entities:
            entities.append(short)

    entities = entities[: config.max_graph_rag_entities]
    return entities or [TODO_SENTINEL]
