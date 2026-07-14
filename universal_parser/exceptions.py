"""Exceptions raised by universal_parser."""

from __future__ import annotations


class UniversalParserError(Exception):
    """Base class for all universal_parser errors."""


class MissingDependencyError(UniversalParserError):
    """Raised when a required optional dependency is not installed.

    Used by adapters (e.g. PDF/DOCX) that cannot degrade to a text-based
    fallback without fabricating content; the message always names the
    missing package and the extra to install.
    """


class UnsafeContentRefusal(UniversalParserError):
    """Raised when a file's content is structurally unsafe to fully parse.

    Used when parsing *could* succeed but only by doing something dangerous
    -- e.g. expanding XML entities declared in a DTD, where a crafted file
    ('billion laughs') would exhaust memory. The adapter refuses rather than
    risk resource exhaustion; `core.UniversalParser` turns this into an
    explicit, confidence-refused result. The message always names why the
    content was judged unsafe.
    """


class LowConfidenceRefusal(UniversalParserError):
    """Raised when a result's confidence is below the configured floor.

    This is the hard-failure mode of the confidence-scored boundary:
    with `ParserConfig.on_low_confidence == "raise"`, universal_parser
    never returns a low-confidence guess dressed up as a fact -- it raises
    instead. See `config.ParserConfig` and `gate.enforce_confidence_gate`.
    """

    def __init__(self, message: str, confidence: float, format_detected: str) -> None:
        """Store the message plus the confidence/format that triggered it."""
        super().__init__(message)
        self.confidence = confidence
        self.format_detected = format_detected
