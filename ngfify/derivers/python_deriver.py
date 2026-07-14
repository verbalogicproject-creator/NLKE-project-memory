"""Python ai_card derivation via the stdlib `ast` module (precise, not regex).

SPEC-v0.1 explicitly allows bypassing `universal_parser`'s regex code-parser
for Python in favor of `ast`, since `ast` gives exact def/class/import
extraction rather than a heuristic pattern match.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from ..text_utils import TODO_SENTINEL, find_risk_areas
from .common import DerivedFields, build_graph_rag_entities

if TYPE_CHECKING:
    from ..config import NgfifyConfig


def derive_python(path: Path, source_text: str, config: "NgfifyConfig") -> DerivedFields:
    """Derive ai_card fields for a `.py` file.

    `public_interfaces` = public (non-`_`) top-level `def`/`class` names,
    unioned with any `__all__` list. `provides` = the module docstring's
    first line, else the leading block comment's first line. `depends_on` =
    every `import`/`from ... import` target found anywhere in the file
    (including nested scopes -- still literally present in this file).
    """
    risk_areas = find_risk_areas(source_text, config) or [TODO_SENTINEL]

    try:
        tree = ast.parse(source_text, filename=str(path))
    except SyntaxError:
        # Cannot fabricate structure for source that doesn't even parse;
        # declare every AST-dependent slot as not-inferable instead.
        return DerivedFields(
            public_interfaces=[TODO_SENTINEL],
            provides=[TODO_SENTINEL],
            depends_on=[TODO_SENTINEL],
            risk_areas=risk_areas,
            graph_rag_entities=[TODO_SENTINEL],
        )

    public_interfaces = _public_interfaces(tree)
    provides = _provides(tree, source_text)
    depends_on = _depends_on(tree)
    graph_rag_entities = build_graph_rag_entities(public_interfaces, depends_on, config)

    return DerivedFields(
        public_interfaces=public_interfaces,
        provides=provides,
        depends_on=depends_on,
        risk_areas=risk_areas,
        graph_rag_entities=graph_rag_entities,
    )


def _public_interfaces(tree: ast.Module) -> list[str]:
    """Public top-level `def`/`class` names, unioned with `__all__`."""
    names: list[str] = []
    seen: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_") and node.name not in seen:
                names.append(node.name)
                seen.add(node.name)

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                for element in node.value.elts:
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        if element.value not in seen:
                            names.append(element.value)
                            seen.add(element.value)

    return names or [TODO_SENTINEL]


def _provides(tree: ast.Module, source_text: str) -> list[str]:
    """Module docstring first line, else the leading block comment's first line."""
    docstring = ast.get_docstring(tree)
    if docstring:
        first_line = docstring.strip().splitlines()[0].strip()
        if first_line:
            return [first_line]

    comment = _leading_block_comment(source_text)
    return [comment] if comment else [TODO_SENTINEL]


def _leading_block_comment(source_text: str) -> str | None:
    """The first consecutive-`#`-comment line at the top of the file, if any."""
    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            return text or None
        return None
    return None


def _depends_on(tree: ast.Module) -> list[str]:
    """Every `import`/`from ... import` target in the file, in first-seen order."""
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in targets:
                    targets.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            prefix = "." * level
            module = node.module or ""
            target = f"{prefix}{module}" if (prefix or module) else "."
            if target not in targets:
                targets.append(target)
    return targets or [TODO_SENTINEL]
