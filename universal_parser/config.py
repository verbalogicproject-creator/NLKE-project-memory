"""User-declared configuration for universal_parser.

Every project-specific constant from the original single-file script --
entity limits, confidence bands, log-line caps, and so on -- lives here as
a dataclass with sane defaults instead of a hardcoded module constant.
Nothing in this module is tied to any one project's kinds, dimensions, or
naming conventions; callers override what they need and get parity
defaults for everything else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

try:
    import toml as _toml
except ImportError:  # pragma: no cover - exercised via load_config tests
    _toml = None


class ConfidenceLevel(str, Enum):
    """An explicit label for how a value was obtained -- never left implicit.

    EXPLICIT : read directly from an unambiguous, well-formed source
               (matched file extension, valid schema, verbatim field).
    HIGH     : strong structural evidence (magic bytes, an exact match).
    INFERRED : derived by heuristic / content-sniffing; plausible, not certain.
    LOW      : weak or fallback evidence; treat as a hint, not a fact.
    REFUSED  : below the configured floor -- universal_parser will not
               assert this value at all. See `ParserConfig.on_low_confidence`.
    """

    EXPLICIT = "explicit"
    HIGH = "high"
    INFERRED = "inferred"
    LOW = "low"
    REFUSED = "refused"


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Score bands (0.0-1.0) used to classify and gate confidence values.

    Defaults reproduce the bands described in the original script's
    docstring (explicit extraction 0.90-1.0, inferred detection 0.70-0.80)
    and add an explicit floor (`minimum_acceptable`) below which a whole
    result is refused, plus a separate floor (`entity_min_confidence`) below
    which an individual extracted entity is set aside as unverified.
    """

    explicit_min: float = 0.90
    high_min: float = 0.85
    inferred_min: float = 0.70
    minimum_acceptable: float = 0.72
    entity_min_confidence: float = 0.92

    def classify(self, value: float) -> ConfidenceLevel:
        """Classify a raw confidence score into a `ConfidenceLevel` band."""
        if value < self.minimum_acceptable:
            return ConfidenceLevel.REFUSED
        if value >= self.explicit_min:
            return ConfidenceLevel.EXPLICIT
        if value >= self.high_min:
            return ConfidenceLevel.HIGH
        if value >= self.inferred_min:
            return ConfidenceLevel.INFERRED
        return ConfidenceLevel.LOW


@dataclass(frozen=True)
class ParserLimits:
    """Caps on how much structure gets extracted per parse.

    Every number here was a hardcoded literal in the original script (e.g.
    "first 10 items", "first 1000 lines"); they are now user-declared, with
    defaults that reproduce the original tool's behavior.
    """

    max_json_list_items: int = 10
    max_csv_preview_rows: int = 50
    max_xml_entities: int = 100
    max_text_entities_per_type: int = 10
    max_log_lines_parsed: int = 1000
    max_log_preview_lines: int = 100
    max_code_functions: int = 50
    max_code_classes: int = 50
    max_code_imports: int = 30


OnLowConfidenceAction = Literal["refuse", "raise", "warn"]


@dataclass(frozen=True)
class ParserConfig:
    """Top-level, user-declared configuration for `UniversalParser`.

    Replaces every project-specific constant from the original script
    (schema shape, confidence bands, extraction caps, extension overrides)
    with a single dataclass callers can override; ships with defaults that
    reproduce the original tool's observable behavior except for the
    documented breaking changes (see the "Changed" section of CHANGELOG.md).

    Attributes:
        confidence_thresholds: score bands used to classify and gate.
        limits: per-format extraction caps.
        on_low_confidence: what happens when overall confidence falls below
            `confidence_thresholds.minimum_acceptable`:
              "refuse" (default) -- withhold content, mark `refused=True`.
              "raise"  -- raise `LowConfidenceRefusal`.
              "warn"   -- log a warning but still emit the content.
        extra_extension_map: additional/overriding `".ext" -> "format"`
            entries merged on top of the built-in extension map.
        parser_version: stamped into `ParseMetadata.parser_version`.
    """

    confidence_thresholds: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    limits: ParserLimits = field(default_factory=ParserLimits)
    on_low_confidence: OnLowConfidenceAction = "refuse"
    extra_extension_map: dict[str, str] = field(default_factory=dict)
    parser_version: str = "1.0"


def load_config(path: str | Path | None) -> ParserConfig:
    """Load a `ParserConfig` from a TOML file, or return defaults.

    Degrades gracefully: if `path` is `None`, the file does not exist, or
    the optional `toml` dependency is not installed, this returns
    `ParserConfig()` defaults rather than raising. Expected TOML shape::

        parser_version = "1.0"
        on_low_confidence = "refuse"

        [confidence_thresholds]
        minimum_acceptable = 0.72
        entity_min_confidence = 0.92

        [limits]
        max_log_lines_parsed = 2000

        [extra_extension_map]
        ".jsonl" = "json"
    """
    if path is None:
        return ParserConfig()

    config_path = Path(path)
    if not config_path.exists():
        return ParserConfig()
    if _toml is None:
        return ParserConfig()

    try:
        raw = _toml.load(config_path)
    except Exception as exc:  # noqa: BLE001 - a malformed config degrades, never crashes the caller
        logger.warning("Could not read config '%s': %s. Using defaults.", config_path, exc)
        return ParserConfig()

    thresholds = _section_or_default(ConfidenceThresholds, raw.get("confidence_thresholds", {}), "confidence_thresholds")
    limits = _section_or_default(ParserLimits, raw.get("limits", {}), "limits")

    on_low_confidence = raw.get("on_low_confidence", "refuse")
    if on_low_confidence not in ("refuse", "raise", "warn"):
        logger.warning(
            "Unknown on_low_confidence=%r in config; using 'refuse'. Valid: refuse, raise, warn.",
            on_low_confidence,
        )
        on_low_confidence = "refuse"

    extra_extension_map = raw.get("extra_extension_map", {})
    if not isinstance(extra_extension_map, dict):
        logger.warning("Config [extra_extension_map] is not a table; ignoring it.")
        extra_extension_map = {}

    return ParserConfig(
        confidence_thresholds=thresholds,
        limits=limits,
        on_low_confidence=on_low_confidence,
        extra_extension_map=dict(extra_extension_map),
        parser_version=str(raw.get("parser_version", "1.0")),
    )


def _section_or_default(cls: type, data: Any, section: str) -> Any:
    """Build a config dataclass from a TOML table, degrading on bad input.

    Keeps only keys that are real fields of `cls` (a typo'd or unknown key is
    ignored with a warning, not raised as `TypeError`), and falls back to
    `cls()` defaults if the section isn't a table or a value is the wrong
    type. This is what makes `load_config` degrade gracefully instead of
    crashing a caller such as the CLI's `--config` on a slightly-wrong file.
    """
    if not isinstance(data, dict):
        logger.warning("Config section [%s] is not a table; using defaults.", section)
        return cls()
    valid = {f.name for f in fields(cls)}
    unknown = sorted(k for k in data if k not in valid)
    if unknown:
        logger.warning(
            "Ignoring unknown [%s] key(s) in config: %s. Valid: %s.",
            section,
            ", ".join(unknown),
            ", ".join(sorted(valid)),
        )
    try:
        return cls(**{k: v for k, v in data.items() if k in valid})
    except Exception as exc:  # noqa: BLE001 - wrong value type in config -> defaults, not a crash
        logger.warning("Invalid [%s] in config (%s); using defaults.", section, exc)
        return cls()
