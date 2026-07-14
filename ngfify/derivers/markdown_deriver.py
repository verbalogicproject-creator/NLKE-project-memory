"""Markdown ai_card derivation.

Operates on the file's body text -- if the file already has YAML
frontmatter, the dispatcher (`ngfify.derivers.derive_ai_card`) strips it
before calling this deriver, so headings/links are never derived from the
author's own declared frontmatter block.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL, find_risk_areas
from .common import DerivedFields, build_graph_rag_entities

if TYPE_CHECKING:
    from ..config import NgfifyConfig

_HEADING_2_3 = re.compile(r"^(#{2,3})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_H1 = re.compile(r"^#[ \t]+\S")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def derive_markdown(path: Path, source_text: str, config: "NgfifyConfig") -> DerivedFields:
    """Derive ai_card fields for a `.md` file.

    `public_interfaces` = `##`/`###` heading text. `provides` = the first
    paragraph after the H1. `depends_on` = local (non-URL, non-anchor)
    markdown link targets.
    """
    public_interfaces = _headings(source_text)
    provides = _first_paragraph_after_h1(source_text)
    depends_on = _local_links(source_text)
    risk_areas = find_risk_areas(source_text, config) or [TODO_SENTINEL]
    graph_rag_entities = build_graph_rag_entities(public_interfaces, depends_on, config)

    return DerivedFields(
        public_interfaces=public_interfaces,
        provides=provides,
        depends_on=depends_on,
        risk_areas=risk_areas,
        graph_rag_entities=graph_rag_entities,
    )


def _headings(source_text: str) -> list[str]:
    headings = [match.group(2).strip() for match in _HEADING_2_3.finditer(source_text)]
    return headings or [TODO_SENTINEL]


def _is_local_link(target: str) -> bool:
    if target.startswith("#") or target.startswith("mailto:"):
        return False
    if _SCHEME.match(target):
        return False
    return True


def _local_links(source_text: str) -> list[str]:
    links: list[str] = []
    for match in _LINK.finditer(source_text):
        target = match.group(1)
        if _is_local_link(target) and target not in links:
            links.append(target)
    return links or [TODO_SENTINEL]


def _first_paragraph_after_h1(source_text: str) -> list[str]:
    lines = source_text.splitlines()
    h1_index: int | None = None
    for index, line in enumerate(lines):
        if _H1.match(line):
            h1_index = index
            break
    if h1_index is None:
        return [TODO_SENTINEL]

    cursor = h1_index + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1

    paragraph_lines: list[str] = []
    while cursor < len(lines) and lines[cursor].strip() and not lines[cursor].lstrip().startswith("#"):
        paragraph_lines.append(lines[cursor].strip())
        cursor += 1

    paragraph = " ".join(paragraph_lines).strip()
    return [paragraph] if paragraph else [TODO_SENTINEL]
