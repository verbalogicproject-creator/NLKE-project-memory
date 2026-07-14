"""Small, dependency-free text helpers shared across every deriver.

Nothing here is project-specific: the risk-scanning patterns and the
kebab-case rules are pure functions of their inputs, with defaults supplied
by `ngfify.config.NgfifyConfig` rather than hardcoded literals.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import NgfifyConfig

#: The one and only sentinel ngfify ever emits for a slot it cannot derive
#: from a single file. Never invent a value instead of this string -- see
#: SPEC-v0.1.md's "derivation-with-provenance, never fabrication" boundary.
TODO_SENTINEL = "<derive: not inferable from a single file>"

_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
_REPEAT_HYPHEN = re.compile(r"-{2,}")


def kebab_case(name: str) -> str:
    """Convert a filename stem (or any identifier) to kebab-case.

    `"myModule"` -> `"my-module"`, `"SPEC-v0.1"` -> `"spec-v0-1"`,
    `"sample_component.test"` -> `"sample-component-test"`.
    """
    if not name:
        return "unnamed"
    spaced = _CASE_BOUNDARY.sub("-", name)
    spaced = _NON_ALNUM.sub("-", spaced)
    spaced = _REPEAT_HYPHEN.sub("-", spaced)
    result = spaced.strip("-").lower()
    return result or "unnamed"


def mtime_to_iso_date(path: Path) -> str:
    """The file's mtime as a UTC ISO date -- deterministic per file, per SPEC-v0.1."""
    timestamp = path.stat().st_mtime
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def today_iso() -> str:
    """Today's UTC date as an ISO string -- used for the emitted body trailer."""
    return datetime.now(tz=timezone.utc).date().isoformat()


#: Generic, language-agnostic risk heuristics. Each is a `(label, pattern)`
#: pair; the label names what was found, the pattern locates it. These are
#: intentionally broad (not project-specific) -- extend via
#: `NgfifyConfig.hardcoded_path_patterns` for the path-shaped ones rather
#: than editing this tuple.
_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uses eval()", re.compile(r"\beval\s*\(")),
    ("uses exec()", re.compile(r"\bexec\s*\(")),
    ("bare except clause", re.compile(r"^[ \t]*except\s*:\s*$", re.MULTILINE)),
    ("uses subprocess", re.compile(r"\bsubprocess\b")),
)


def find_risk_areas(text: str, config: "NgfifyConfig") -> list[str]:
    """Heuristically flag eval/exec/bare-except/subprocess/hardcoded abs paths.

    Every finding names the pattern and the 1-based line number of its
    *first* occurrence in `text` -- derived and traceable, never invented.
    Returns `[]` (the caller substitutes `TODO_SENTINEL`) when nothing is
    found, per the "refuse to fabricate" boundary: an empty risk scan is
    reported as "not inferable", never as an unfounded "no risks".
    """
    findings: list[str] = []
    for label, pattern in _RISK_PATTERNS:
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{label} (line {line})")
    for raw_pattern in config.hardcoded_path_patterns:
        match = re.search(raw_pattern, text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"hardcoded absolute path matching {raw_pattern!r} (line {line})")
    return findings
