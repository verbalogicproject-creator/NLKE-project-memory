"""Parser adapter registry.

`build_parsers(limits)` is the single place format names map to adapter
instances -- add a new format by adding one entry here.
"""

from __future__ import annotations

from ..config import ParserLimits
from .base import ParserAdapter
from .code import CodeParser
from .documents import DOCXParser, PDFParser
from .structured import CSVParser, JSONParser, TOMLParser, XMLParser, YAMLParser
from .text import LogParser, TextParser

__all__ = [
    "ParserAdapter",
    "CodeParser",
    "DOCXParser",
    "PDFParser",
    "CSVParser",
    "JSONParser",
    "TOMLParser",
    "XMLParser",
    "YAMLParser",
    "LogParser",
    "TextParser",
    "build_parsers",
]


def build_parsers(limits: ParserLimits | None = None) -> dict[str, ParserAdapter]:
    """Build the default `format -> adapter` mapping used by `UniversalParser`."""
    limits = limits or ParserLimits()
    text_parser = TextParser(limits)
    return {
        "json": JSONParser(limits),
        "csv": CSVParser(limits),
        "yaml": YAMLParser(limits),
        "xml": XMLParser(limits),
        "toml": TOMLParser(limits),
        "txt": text_parser,
        "markdown": text_parser,
        "html": text_parser,
        "log": LogParser(limits),
        "ini": text_parser,
        "env": text_parser,
        "javascript": CodeParser("javascript", limits),
        "typescript": CodeParser("typescript", limits),
        "python": CodeParser("python", limits),
        "pdf": PDFParser(limits),
        "docx": DOCXParser(limits),
    }
