"""HTML ai_card derivation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL, find_risk_areas
from .common import DerivedFields, build_graph_rag_entities

if TYPE_CHECKING:
    from ..config import NgfifyConfig

# Match a real `id` attribute only. `\b` also sits at the hyphen in
# `data-row-id="..."`, so a bare `\bid` would misread data-/aria- attribute
# values as element ids; require the char before `id` to be neither a word
# char nor a hyphen (i.e. an actual attribute boundary: space, `<`, quote).
_ID_ATTR = re.compile(r"""(?<![\w-])id\s*=\s*["']([^"']+)["']""")
_CUSTOM_TAG = re.compile(r"</?([a-z][a-z0-9]*-[a-z0-9-]*)\b")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_SRC = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_LINK_HREF = re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def derive_html(path: Path, source_text: str, config: "NgfifyConfig") -> DerivedFields:
    """Derive ai_card fields for an `.html` file.

    `public_interfaces` = elements with an `id` attribute (`#the-id`) plus
    custom-element tags (`<my-tag>`). `provides` = `<title>` text.
    `depends_on` = local `<script src>` / `<link href>` targets.
    """
    public_interfaces = _public_interfaces(source_text)
    provides = _provides(source_text)
    depends_on = _depends_on(source_text)
    risk_areas = find_risk_areas(source_text, config) or [TODO_SENTINEL]
    graph_rag_entities = build_graph_rag_entities(public_interfaces, depends_on, config)

    return DerivedFields(
        public_interfaces=public_interfaces,
        provides=provides,
        depends_on=depends_on,
        risk_areas=risk_areas,
        graph_rag_entities=graph_rag_entities,
    )


def _public_interfaces(source_text: str) -> list[str]:
    entries: list[str] = []
    for match in _ID_ATTR.finditer(source_text):
        token = f"#{match.group(1)}"
        if token not in entries:
            entries.append(token)
    for match in _CUSTOM_TAG.finditer(source_text):
        token = f"<{match.group(1)}>"
        if token not in entries:
            entries.append(token)
    return entries or [TODO_SENTINEL]


def _provides(source_text: str) -> list[str]:
    match = _TITLE.search(source_text)
    if not match:
        return [TODO_SENTINEL]
    title_text = re.sub(r"\s+", " ", match.group(1)).strip()
    return [title_text] if title_text else [TODO_SENTINEL]


def _is_local(target: str) -> bool:
    if target.startswith("//"):
        return False
    if _SCHEME.match(target):
        return False
    return True


def _depends_on(source_text: str) -> list[str]:
    """Local `<script src>` / `<link href>` targets, in document order."""
    matches = list(_SCRIPT_SRC.finditer(source_text)) + list(_LINK_HREF.finditer(source_text))
    matches.sort(key=lambda match: match.start())

    targets: list[str] = []
    for match in matches:
        target = match.group(1)
        if _is_local(target) and target not in targets:
            targets.append(target)
    return targets or [TODO_SENTINEL]
