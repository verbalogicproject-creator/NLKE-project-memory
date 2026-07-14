"""A zero-setup demo corpus so you can try universal_parser immediately.

`build_demo()` parses every file in the packaged `demo_corpus/` directory,
covering the major format families (JSON, YAML, CSV, XML, TOML, Markdown,
ENV, log, Python) plus one deliberately unrecognizable file with no
extension and no distinguishing content pattern. That last file exists
specifically to exercise the whole-result confidence-refusal gate: with the
default `ConfidenceThresholds`, its "default" detection method (confidence
0.50) combines with a valid-but-generic text schema to land at an overall
confidence of 0.70 -- below `minimum_acceptable` (0.72) -- so `refused=True`
is not a merely theoretical code path.
"""

from __future__ import annotations

from pathlib import Path

from .config import ParserConfig
from .core import UniversalParser
from .schema import ParseResult


def demo_corpus_dir() -> Path:
    """Filesystem path to the packaged demo corpus."""
    return Path(__file__).parent / "demo_corpus"


def build_demo(config: ParserConfig | None = None) -> list[ParseResult]:
    """Parse every file in the packaged demo corpus and return the results."""
    parser = UniversalParser(config)
    corpus_dir = demo_corpus_dir()
    file_paths = sorted(str(p) for p in corpus_dir.iterdir() if p.is_file())
    return parser.parse_batch(file_paths)
