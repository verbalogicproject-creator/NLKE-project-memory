"""universal_parser -- parse 15+ file formats into one confidence-scored result.

Every parse returns a `ParseResult` carrying an explicit `confidence` float
*and* a `ConfidenceLevel` label -- never an implicit one. Results below the
configured floor are refused outright rather than emitted as if verified;
see `ParserConfig.on_low_confidence`. Optional heavy dependencies (PyYAML,
toml, pdfplumber, python-docx) degrade gracefully: without them, the
affected format is refused with an install hint instead of being silently
misparsed.

Quickstart::

    from universal_parser import UniversalParser

    parser = UniversalParser()
    result = parser.parse("notes.json")
    print(result.confidence, result.confidence_level, result.content)

Or the packaged demo corpus::

    from universal_parser import build_demo

    for result in build_demo():
        print(result.format, result.confidence_level, result.refused)
"""

from __future__ import annotations

from .config import (
    ConfidenceLevel,
    ConfidenceThresholds,
    ParserConfig,
    ParserLimits,
    load_config,
)
from .core import UniversalParser
from .demo import build_demo, demo_corpus_dir
from .detection import FormatDetector
from .exceptions import LowConfidenceRefusal, MissingDependencyError, UniversalParserError
from .schema import ParseMetadata, ParseResult, ValidationResult

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "UniversalParser",
    "ParserConfig",
    "ParserLimits",
    "ConfidenceThresholds",
    "ConfidenceLevel",
    "load_config",
    "FormatDetector",
    "ParseResult",
    "ParseMetadata",
    "ValidationResult",
    "UniversalParserError",
    "MissingDependencyError",
    "LowConfidenceRefusal",
    "build_demo",
    "demo_corpus_dir",
]
