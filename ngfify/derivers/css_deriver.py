"""CSS ai_card derivation.

The selector scan is a deterministic regex heuristic, not a real CSS
parser: it walks `selector-list {` blocks and skips any block whose
selector text starts with `@` (an at-rule like `@media`/`@keyframes`), but
does not fully model at-rule nesting scope -- a class/id selector nested
inside `@media { ... }` is still picked up as a top-level-ish selector.
This is a known, documented v0.1 limitation (still fully traceable to the
source, never fabricated); see `docs/SPEC-v0.1.md` and `ROADMAP.md`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL, find_risk_areas
from .common import DerivedFields, build_graph_rag_entities

if TYPE_CHECKING:
    from ..config import NgfifyConfig

_SELECTOR_BLOCK = re.compile(r"([^{}]+)\{")
_CLASS_TOKEN = re.compile(r"\.([A-Za-z_-][\w-]*)")
_ID_TOKEN = re.compile(r"#([A-Za-z_-][\w-]*)")
_CUSTOM_PROPERTY = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?["']?([^"');]+)["']?\)?\s*;""")
_LEADING_COMMENT = re.compile(r"\A\s*/\*(.*?)\*/", re.DOTALL)
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_SEMICOLON_AT_STATEMENT = re.compile(r"@(?:import|charset|namespace)\b[^;{}]*;")


def _strip_noise(source_text: str) -> str:
    """Remove comments + semicolon-terminated at-statements before selector scanning.

    Without this, a leading `/* comment */` or `@import "./tokens.css";`
    line gets swept into the *first* `{`-terminated "selector group" match
    (there is no earlier `{`/`}` to bound it), and a literal filename
    substring like `.css` would otherwise be misread as a class selector.
    `depends_on`/`provides` are derived from the original, un-stripped text
    -- only selector/custom-property scanning uses this.
    """
    without_comments = _COMMENT_BLOCK.sub(" ", source_text)
    return _SEMICOLON_AT_STATEMENT.sub(" ", without_comments)


def derive_css(path: Path, source_text: str, config: "NgfifyConfig") -> DerivedFields:
    """Derive ai_card fields for a `.css` file.

    `public_interfaces` = top-level class/id selectors + `--custom-properties`.
    `provides` = the leading comment's first line. `depends_on` = `@import` targets.
    """
    public_interfaces = _public_interfaces(_strip_noise(source_text))
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
    selectors: list[str] = []
    for block_match in _SELECTOR_BLOCK.finditer(source_text):
        selector_group = block_match.group(1)
        if selector_group.strip().startswith("@"):
            continue
        for part in selector_group.split(","):
            for class_match in _CLASS_TOKEN.finditer(part):
                token = f".{class_match.group(1)}"
                if token not in selectors:
                    selectors.append(token)
            for id_match in _ID_TOKEN.finditer(part):
                token = f"#{id_match.group(1)}"
                if token not in selectors:
                    selectors.append(token)

    custom_properties: list[str] = []
    for property_match in _CUSTOM_PROPERTY.finditer(source_text):
        name = property_match.group(1)
        if name not in custom_properties:
            custom_properties.append(name)

    return selectors + custom_properties or [TODO_SENTINEL]


def _provides(source_text: str) -> list[str]:
    match = _LEADING_COMMENT.match(source_text)
    if not match:
        return [TODO_SENTINEL]
    first_line = next((line.strip() for line in match.group(1).splitlines() if line.strip()), "")
    return [first_line] if first_line else [TODO_SENTINEL]


def _depends_on(source_text: str) -> list[str]:
    targets: list[str] = []
    for match in _IMPORT.finditer(source_text):
        target = match.group(1)
        if target not in targets:
            targets.append(target)
    return targets or [TODO_SENTINEL]
