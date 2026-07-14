"""TypeScript/JavaScript ai_card derivation via targeted export/import regex.

`universal_parser.parsers.code.CodeParser` matches any function/class/const/
let declaration regardless of the `export` keyword -- useful for a generic
code overview, but not precise enough for SPEC-v0.1's `public_interfaces`
rule ("ts/js: exported names"), which requires the `export` keyword
specifically. Using CodeParser's broader match set here would emit names
that are real symbols in the file but not actually part of its public
surface, so this module scans the raw source directly for `export`
statements instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL, find_risk_areas
from .common import DerivedFields, build_graph_rag_entities

if TYPE_CHECKING:
    from ..config import NgfifyConfig

_EXPORT_NAMED = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|interface|type)\s+"
    r"([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
_EXPORT_CONST = re.compile(r"^export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)
_EXPORT_DEFAULT_IDENT = re.compile(r"^export\s+default\s+([A-Za-z_$][\w$]*)\s*;", re.MULTILINE)
_EXPORT_DEFAULT_ANON_FUNC = re.compile(
    r"^export\s+default\s+(?:async\s+)?function\*?\s*\(", re.MULTILINE
)
_EXPORT_DEFAULT_ANON_CLASS = re.compile(r"^export\s+default\s+class\s*\{", re.MULTILINE)
_EXPORT_BRACE = re.compile(
    r"^export\s+\{([^}]*)\}(?:\s*from\s*['\"]([^'\"]+)['\"])?", re.MULTILINE
)
_EXPORT_STAR = re.compile(r"^export\s+\*\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)

_IMPORT_FROM = re.compile(
    r"""^import\s+(?:type\s+)?(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE
)
_REQUIRE_CALL = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")

_LEADING_BLOCK_COMMENT = re.compile(r"\A\s*/\*+(.*?)\*/", re.DOTALL)
_LEADING_LINE_COMMENT = re.compile(r"\A\s*//[ \t]?(.*)")


def derive_jsts(path: Path, source_text: str, config: "NgfifyConfig") -> DerivedFields:
    """Derive ai_card fields for a `.ts`/`.tsx`/`.js`/`.jsx` file."""
    public_interfaces = _public_interfaces(source_text)
    depends_on = _depends_on(source_text)
    provides = _provides(source_text)
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
    """Exported names: `export function/class/interface/type/const/let/var/default`."""
    names: list[str] = []

    def _add(name: str) -> None:
        if name and name not in names:
            names.append(name)

    for match in _EXPORT_NAMED.finditer(source_text):
        _add(match.group(1))
    for match in _EXPORT_CONST.finditer(source_text):
        _add(match.group(1))
    for match in _EXPORT_DEFAULT_IDENT.finditer(source_text):
        _add(match.group(1))
    if _EXPORT_DEFAULT_ANON_FUNC.search(source_text) or _EXPORT_DEFAULT_ANON_CLASS.search(source_text):
        _add("default")
    for match in _EXPORT_BRACE.finditer(source_text):
        for raw_name in match.group(1).split(","):
            raw_name = raw_name.strip()
            if not raw_name:
                continue
            if " as " in raw_name:
                _, alias = raw_name.split(" as ", 1)
                _add(alias.strip())
            else:
                _add(raw_name)

    return names or [TODO_SENTINEL]


def _depends_on(source_text: str) -> list[str]:
    """Import targets: `import ... from`, `export ... from`, `export * from`, `require(...)`."""
    targets: list[str] = []

    def _add(target: str) -> None:
        if target and target not in targets:
            targets.append(target)

    for match in _IMPORT_FROM.finditer(source_text):
        _add(match.group(1))
    for match in _EXPORT_BRACE.finditer(source_text):
        reexport_target = match.group(2)
        if reexport_target:
            _add(reexport_target)
    for match in _EXPORT_STAR.finditer(source_text):
        _add(match.group(1))
    for match in _REQUIRE_CALL.finditer(source_text):
        _add(match.group(1))

    return targets or [TODO_SENTINEL]


def _provides(source_text: str) -> list[str]:
    """Module docstring / leading block comment first line, per SPEC-v0.1."""
    block_match = _LEADING_BLOCK_COMMENT.match(source_text)
    if block_match:
        for raw_line in block_match.group(1).splitlines():
            candidate = raw_line.strip().lstrip("*").strip()
            if candidate:
                return [candidate]
        return [TODO_SENTINEL]

    line_match = _LEADING_LINE_COMMENT.match(source_text)
    if line_match:
        candidate = line_match.group(1).strip()
        return [candidate] if candidate else [TODO_SENTINEL]

    return [TODO_SENTINEL]
