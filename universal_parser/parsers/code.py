"""Heuristic (regex-based) parser for JavaScript/TypeScript/Python source."""

from __future__ import annotations

import re
from typing import Any

from ..config import ParserLimits
from .base import ParserAdapter

_FUNCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "javascript": re.compile(r"(?:function|const|let)\s+(\w+)\s*[=(]"),
    "typescript": re.compile(r"(?:function|const|let)\s+(\w+)\s*[=(]"),
    "python": re.compile(r"def\s+(\w+)\s*\("),
}
_CLASS_PATTERN = re.compile(r"class\s+(\w+)")
_IMPORT_PATTERNS: dict[str, re.Pattern[str]] = {
    "javascript": re.compile(r"import\s+(?:\{[^}]+\}|[\w\s,]+)\s+from\s+['\"]([^'\"]+)['\"]"),
    "typescript": re.compile(r"import\s+(?:\{[^}]+\}|[\w\s,]+)\s+from\s+['\"]([^'\"]+)['\"]"),
    "python": re.compile(r"(?:from|import)\s+(?:(\w+)(?:\s+import)?|([^\s]+))"),
}


class CodeParser(ParserAdapter):
    """Extract functions/classes/imports from code via regex heuristics.

    This is intentionally not a real AST parser -- it is a fast, dependency-free
    heuristic, exactly as in the original script. Confidence values (0.90 for
    functions/imports, 0.95 for classes) reflect that a `class Foo` match is
    less ambiguous than a `const foo =` match, not how much code was scanned.
    """

    def __init__(self, language: str, limits: ParserLimits | None = None) -> None:
        """Store the target language (`javascript` | `typescript` | `python`)."""
        super().__init__(limits)
        self.language = language

    def can_parse(self) -> bool:
        """Code parsing uses only the standard library."""
        return True

    def parse(self, file_path: str) -> dict[str, Any]:
        """Read the source file and extract its function/class/import heuristics."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

        return {
            "structured_data": {
                "language": self.language,
                "functions": self._extract_functions(code),
                "classes": self._extract_classes(code),
                "imports": self._extract_imports(code),
                "line_count": len(code.split("\n")),
            },
            "text_content": code,
            "entities": self._extract_code_entities(code),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for code content."""
        return {
            "structured_data": {
                "language": "string",
                "functions": "array",
                "classes": "array",
                "imports": "array",
                "line_count": "number",
            },
            "text_content": "string",
            "entities": "array",
        }

    def _extract_functions(self, code: str) -> list[dict[str, Any]]:
        """Extract function-like definitions, bounded by `limits.max_code_functions`."""
        pattern = _FUNCTION_PATTERNS.get(self.language)
        if pattern is None:
            return []
        functions = [{"name": m.group(1), "confidence": 0.90} for m in pattern.finditer(code)]
        return functions[: self.limits.max_code_functions]

    def _extract_classes(self, code: str) -> list[dict[str, Any]]:
        """Extract class definitions, bounded by `limits.max_code_classes`."""
        classes = [{"name": m.group(1), "confidence": 0.95} for m in _CLASS_PATTERN.finditer(code)]
        return classes[: self.limits.max_code_classes]

    def _extract_imports(self, code: str) -> list[dict[str, Any]]:
        """Extract import targets, bounded by `limits.max_code_imports`."""
        pattern = _IMPORT_PATTERNS.get(self.language)
        if pattern is None:
            return []
        imports: list[dict[str, Any]] = []
        for match in pattern.finditer(code):
            groups = match.groups()
            import_name = next((g for g in groups if g), "")
            if import_name:
                imports.append({"name": import_name, "confidence": 0.90})
        return imports[: self.limits.max_code_imports]

    def _extract_code_entities(self, code: str) -> list[dict[str, Any]]:
        """Merge functions and classes into a single flat entity list."""
        entities: list[dict[str, Any]] = []
        for func in self._extract_functions(code):
            entities.append({"name": func["name"], "type": "function", "confidence": 0.90})
        for cls in self._extract_classes(code):
            entities.append({"name": cls["name"], "type": "class", "confidence": 0.95})
        return entities
