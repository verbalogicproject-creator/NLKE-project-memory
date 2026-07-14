"""Thin composition wrapper around `universal_parser` -- the shared parse front-end.

ngfify delegates file reading, encoding handling, and format detection to
`universal_parser.UniversalParser` rather than reimplementing them; the
per-language derivers in `ngfify.derivers` then map its output (primarily
`text_content`) onto the 13 ai_card slots. Narrow, ai_card-specific
extraction that has no equivalent field in `ParseResult` -- exported names,
markdown headings, CSS selectors, and so on -- is ngfify's own
responsibility per SPEC-v0.1 ("Compose, don't reinvent").
"""

from __future__ import annotations

from pathlib import Path

from universal_parser import ParserConfig as UniversalParserConfig
from universal_parser import UniversalParser
from universal_parser.schema import ParseResult

#: universal_parser has no CSS format of its own (see its
#: `DEFAULT_EXTENSION_MAP`); without this override, ".css" would fall
#: through to content-sniffing, which misdetects CSS as YAML (its own
#: sniffing considers any ":" in the content a YAML signal, and CSS
#: declarations are full of them). Routing it to "txt" gets us a plain,
#: confidence-scored text read -- exactly what the CSS deriver needs.
_NGFIFY_EXTRA_EXTENSION_MAP: dict[str, str] = {".css": "txt"}


def parse_source(path: Path, extra_extension_map: dict[str, str] | None = None) -> ParseResult:
    """Run `path` through `universal_parser` and return its `ParseResult`.

    Always passes `allow_low_confidence=True`: ngfify's own boundary
    (derivation-with-provenance) governs what it *asserts* about a file's
    structure; it still needs the file's actual text to derive from, even
    for a file `universal_parser`'s own confidence gate would otherwise
    withhold as a guess. ngfify never treats a withheld/refused
    `universal_parser` result as a substitute for reading the file -- see
    `read_source_text`, which falls back to a direct read if needed.
    """
    merged_map = {**_NGFIFY_EXTRA_EXTENSION_MAP, **(extra_extension_map or {})}
    config = UniversalParserConfig(extra_extension_map=merged_map)
    parser = UniversalParser(config)
    return parser.parse(str(path), allow_low_confidence=True)


def read_source_text(path: Path, parse_result: ParseResult | None = None) -> str:
    """Return `path`'s raw text, preferring `universal_parser`'s decoded `text_content`."""
    if parse_result is not None:
        text = parse_result.content.get("text_content")
        if isinstance(text, str):
            return text
    return path.read_text(encoding="utf-8", errors="ignore")
