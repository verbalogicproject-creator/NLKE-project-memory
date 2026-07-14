"""Extension -> language routing, and the `kind` refinement heuristic.

This is intentionally a thin, suffix-based dispatcher (not a re-implementation
of format sniffing): `ngfify` only ever receives an explicit file path with a
real extension from its CLI, so magic-byte/content sniffing (which
`universal_parser.FormatDetector` already does for the shared parse
front-end) is not needed here. `Language` exists because ngfify supports one
format `universal_parser` does not (CSS) and needs a stable internal bucket
name independent of `universal_parser`'s own format strings.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """The languages ngfify v0.1 knows how to derive an ai_card for."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    MARKDOWN = "markdown"
    HTML = "html"
    CSS = "css"


class UnsupportedFileTypeError(ValueError):
    """Raised when a file's extension has no registered `Language`."""


#: Extension -> Language. Extend per-call via `NgfifyConfig.extra_extension_map`
#: (values must be one of the `Language` enum's string values) rather than
#: editing this constant.
EXTENSION_LANGUAGE_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".md": Language.MARKDOWN,
    ".markdown": Language.MARKDOWN,
    ".html": Language.HTML,
    ".htm": Language.HTML,
    ".css": Language.CSS,
}

#: Base `kind` per language, before the test/cli/config refinement pass.
BASE_KIND_MAP: dict[Language, str] = {
    Language.PYTHON: "code_module",
    Language.TYPESCRIPT: "code_module",
    Language.JAVASCRIPT: "code_module",
    Language.MARKDOWN: "doc",
    Language.HTML: "markup",
    Language.CSS: "stylesheet",
}

#: Languages eligible for the test/cli/config `kind` refinement (code only --
#: refining prose/markup/stylesheet the same way would not be meaningful).
CODE_LANGUAGES: frozenset[Language] = frozenset(
    {Language.PYTHON, Language.TYPESCRIPT, Language.JAVASCRIPT}
)

_TEST_FRAMEWORK_CALL = re.compile(r"\b(?:describe|it|test)\s*\(")
_CONFIG_STEM_SUFFIXES = ("_config", "_settings", ".config")


def detect_language(path: Path, extra_extension_map: dict[str, str] | None = None) -> Language:
    """Detect the `Language` bucket for `path` from its suffix.

    Raises `UnsupportedFileTypeError` for any extension ngfify v0.1 does not
    know how to derive (better an explicit refusal than a silent guess).
    """
    merged: dict[str, Language] = dict(EXTENSION_LANGUAGE_MAP)
    for ext, lang_value in (extra_extension_map or {}).items():
        try:
            merged[ext.lower()] = Language(lang_value)
        except ValueError:
            # A config mapping to an unknown language shouldn't crash every
            # file with a bare ValueError. Drop the bad entry with a warning;
            # a file with that extension then gets the normal, CLI-handled
            # UnsupportedFileTypeError instead of a traceback.
            logger.warning(
                "Ignoring config extra_extension_map[%r]=%r: not a valid ngfify language (%s).",
                ext,
                lang_value,
                ", ".join(member.value for member in Language),
            )

    suffix = path.suffix.lower()
    if suffix not in merged:
        supported = ", ".join(sorted(merged))
        raise UnsupportedFileTypeError(
            f"ngfify v0.1 does not support '{suffix}' files. Supported extensions: {supported}"
        )
    return merged[suffix]


def refine_kind(language: Language, path: Path, source_text: str) -> str:
    """Refine a code file's `kind` to `test` / `cli` / `config` when clearly so.

    Precedence: `test` (most specific/safest signal) > `cli` > `config` >
    the language's base `kind` (`code_module`). Heuristics only look at
    filename conventions and unambiguous top-of-file signals -- never a
    fabricated guess about intent.
    """
    base_kind = BASE_KIND_MAP[language]
    if language not in CODE_LANGUAGES:
        return base_kind

    stem = path.stem.lower()
    name = path.name.lower()
    first_lines = source_text.splitlines()[:1]
    has_shebang = bool(first_lines) and first_lines[0].startswith("#!")

    is_test_name = stem.startswith("test_") or stem.endswith("_test") or ".test." in name or ".spec." in name
    if is_test_name:
        return "test"
    if language is Language.PYTHON and ("import pytest" in source_text or "import unittest" in source_text):
        return "test"
    if language in (Language.TYPESCRIPT, Language.JAVASCRIPT) and _TEST_FRAMEWORK_CALL.search(source_text):
        return "test"

    if has_shebang:
        return "cli"
    if language is Language.PYTHON and "__main__" in source_text and (
        "argparse" in source_text or "sys.argv" in source_text
    ):
        return "cli"

    if stem in ("config", "settings") or stem.endswith(_CONFIG_STEM_SUFFIXES):
        return "config"

    return base_kind
