"""Universal parse-result schema (schema-first, per the original design).

Every parse -- regardless of format -- returns a `ParseResult` with the
same shape: the detected format, a numeric `confidence` *and* an explicit
`ConfidenceLevel` label, metadata about how detection/parsing happened,
the parsed content, and a validation report. Confidence is never implicit,
and `refused` / `refusal_reason` make withholding a first-class, inspectable
outcome rather than a value quietly downgraded in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import ConfidenceLevel


@dataclass
class ParseMetadata:
    """Metadata describing how a file was detected and parsed."""

    file_path: str
    file_size: int
    format_detected: str
    detection_method: str  # "extension" | "magic" | "content" | "default" | "fallback"
    detection_confidence: float
    parse_time_ms: float
    parser_version: str = "1.0"
    # Set to the originally-detected format when its parser failed and we fell
    # back to plain text (which forces a refusal); `None` on a normal parse.
    degraded_from: str | None = None


@dataclass
class ValidationResult:
    """Schema-validation outcome for a parsed file's content."""

    schema_valid: bool
    errors: list[str]
    warnings: list[str]
    schema_checked_against: str


@dataclass
class ParseResult:
    """Universal, confidence-scored parse result.

    `confidence_level` and `refused` are the enforcement surface of the
    parsing -> confidence-scored boundary: a caller can always tell,
    programmatically, whether a value is asserted or withheld -- never
    both at once. When `refused` is `True`, `content` holds an explicit
    withholding marker (see `gate.build_refusal_content`), never a
    best-effort guess mixed in with genuine data.
    """

    format: str
    confidence: float
    confidence_level: ConfidenceLevel
    refused: bool
    refusal_reason: str | None
    metadata: dict[str, Any]
    content: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain, JSON-serializable dictionary."""
        return {
            "format": self.format,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "metadata": self.metadata,
            "content": self.content,
            "validation": self.validation,
        }
