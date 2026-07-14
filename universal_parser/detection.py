"""Format detection: extension -> magic bytes -> content sniffing -> default.

Mirrors the three-phase strategy of the original script, in descending
confidence order. Detection confidence values feed directly into the
overall confidence-scored gate in `core.UniversalParser`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Magic byte signatures for binary formats.
DEFAULT_MAGIC_BYTES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # ZIP header
    "xlsx": b"PK\x03\x04",
    "zip": b"PK\x03\x04",
}

# File extension -> format name. Extend per-call via
# `ParserConfig.extra_extension_map` rather than editing this constant.
DEFAULT_EXTENSION_MAP: dict[str, str] = {
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".xml": "xml",
    ".toml": "toml",
    ".txt": "txt",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".log": "log",
    ".ini": "ini",
    ".env": "env",
    ".js": "javascript",
    ".ts": "typescript",
    ".py": "python",
    ".pdf": "pdf",
    ".docx": "docx",
}


class FormatDetector:
    """Detect a file's format using a multi-phase, confidence-ordered approach."""

    @staticmethod
    def detect(
        file_path: str,
        extra_extension_map: dict[str, str] | None = None,
    ) -> tuple[str, str, float]:
        """Detect `(format, detection_method, confidence)` for `file_path`.

        Strategy, in order:
          1. Extension match (fastest, highest confidence: 0.95).
          2. Magic bytes (accurate for binary formats: 0.90).
          3. Content pattern sniffing (slower fallback: 0.75).
          4. Default: assume plain text (0.50) -- deliberately the lowest
             confidence band, so a genuinely unrecognizable file does not
             get treated as a confident "txt" parse downstream.
        """
        extension_map = DEFAULT_EXTENSION_MAP
        if extra_extension_map:
            extension_map = {**DEFAULT_EXTENSION_MAP, **extra_extension_map}

        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()
        if suffix in extension_map:
            return extension_map[suffix], "extension", 0.95

        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
            for fmt, magic in DEFAULT_MAGIC_BYTES.items():
                if header.startswith(magic):
                    if fmt in ("docx", "xlsx"):
                        office_fmt = FormatDetector._check_office_format(file_path)
                        if office_fmt:
                            return office_fmt, "magic", 0.90
                    return fmt, "magic", 0.90
        except OSError as exc:
            logger.warning("Error reading magic bytes for %s: %s", file_path, exc)

        content_format = FormatDetector._detect_by_content(file_path)
        if content_format:
            return content_format, "content", 0.75

        return "txt", "default", 0.50

    @staticmethod
    def _check_office_format(file_path: str) -> str | None:
        """Disambiguate a ZIP-based file as DOCX or XLSX."""
        try:
            with open(file_path, "rb") as f:
                data = f.read(200)
            if b"_rels" in data or b"word/" in data:
                return "docx"
            if b"xl/" in data or b"worksheets" in data:
                return "xlsx"
        except OSError:
            pass
        return None

    @staticmethod
    def _detect_by_content(file_path: str) -> str | None:
        """Detect format by analyzing content patterns in the first 1 KB."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(1000)
        except OSError as exc:
            logger.warning("Error detecting format by content for %s: %s", file_path, exc)
            return None

        if content.strip().startswith("{") or content.strip().startswith("["):
            try:
                json.loads(content)
                return "json"
            except json.JSONDecodeError:
                pass

        if ":" in content or "---" in content:
            return "yaml"

        if content.strip().startswith("<"):
            return "xml"

        if "," in content and "\n" in content:
            return "csv"

        if re.search(r"^\s*\[.+\]", content, re.MULTILINE):
            return "ini"

        if re.search(r"^[A-Z_][A-Z0-9_]*=", content, re.MULTILINE):
            return "env"

        if re.search(r"^#+\s|^\*\*|^##|^-\s", content, re.MULTILINE):
            return "markdown"

        if re.search(r"\d{4}-\d{2}-\d{2}|\[\w+\]|^\d+:", content, re.MULTILINE):
            return "log"

        if re.search(r"\bfunction\s*\(|\bconst\s+|\blet\s+", content):
            return "javascript"
        if re.search(r"\bdef\s+|\bimport\s+|\bfrom\s+", content):
            return "python"
        if re.search(r"\binterface\s+|\btype\s+|\bclass\s+", content):
            return "typescript"

        if re.search(r"<!DOCTYPE|<html|<head|<body", content, re.IGNORECASE):
            return "html"

        return None
