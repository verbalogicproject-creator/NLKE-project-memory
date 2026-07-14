"""Parsers for binary document formats: PDF and DOCX.

Both optional dependencies (`pdfplumber`, `python-docx`) are imported
defensively at module load time, exactly like the other optional parsers in
this package. `can_parse()` reports whether the dependency is present, and
`parse()` raises `MissingDependencyError` with an install hint if it is
called anyway -- it never falls back to reading the binary file as text,
which would silently fabricate garbled "content". See `core.UniversalParser`
for how the orchestrator turns a missing dependency into an explicit,
confidence-refused result instead of calling `parse()` at all.
"""

from __future__ import annotations

from typing import Any

from ..exceptions import MissingDependencyError
from .base import ParserAdapter, extract_text_entities

try:
    import pdfplumber
except ImportError:  # pragma: no cover - exercised when pdfplumber is absent
    pdfplumber = None

try:
    import docx
except ImportError:  # pragma: no cover - exercised when python-docx is absent
    docx = None


class PDFParser(ParserAdapter):
    """Extract text per page from a PDF. Requires the optional `pdfplumber` dependency."""

    def can_parse(self) -> bool:
        """Only usable when `pdfplumber` is installed."""
        return pdfplumber is not None

    def parse(self, file_path: str) -> dict[str, Any]:
        """Extract per-page text via `pdfplumber` and derive text entities from it."""
        if pdfplumber is None:
            raise MissingDependencyError(
                "PDF parsing requires the optional 'pdfplumber' dependency. "
                "Install with: pip install 'nlke-universal-parser[pdf]'"
            )

        pages: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = "\n".join(pages)

        return {
            "structured_data": {"page_count": len(pages), "pages": pages},
            "text_content": text,
            "entities": extract_text_entities(text, self.limits),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for PDF content."""
        return {
            "structured_data": {"page_count": "number", "pages": "array"},
            "text_content": "string",
            "entities": "array",
        }


class DOCXParser(ParserAdapter):
    """Extract paragraph text from a DOCX. Requires the optional `python-docx` dependency."""

    def can_parse(self) -> bool:
        """Only usable when `python-docx` is installed."""
        return docx is not None

    def parse(self, file_path: str) -> dict[str, Any]:
        """Extract paragraph text via `python-docx` and derive text entities from it."""
        if docx is None:
            raise MissingDependencyError(
                "DOCX parsing requires the optional 'python-docx' dependency. "
                "Install with: pip install 'nlke-universal-parser[docx]'"
            )

        document = docx.Document(file_path)
        paragraphs = [p.text for p in document.paragraphs]
        text = "\n".join(paragraphs)

        return {
            "structured_data": {"paragraph_count": len(paragraphs), "paragraphs": paragraphs},
            "text_content": text,
            "entities": extract_text_entities(text, self.limits),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for DOCX content."""
        return {
            "structured_data": {"paragraph_count": "number", "paragraphs": "array"},
            "text_content": "string",
            "entities": "array",
        }
