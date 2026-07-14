"""The confidence-scored boundary's enforcement mechanics.

universal_parser never emits an inferred or low-confidence value dressed up
as a fact. This module holds the two gates that make that real rather than
cosmetic:

1. `split_entities_by_confidence` -- the per-entity gate. Every extracted
   entity already carries its own `confidence` float; entities below the
   configured floor (`ConfidenceThresholds.entity_min_confidence`) are moved
   to a separate `low_confidence_entities` list instead of being mixed,
   unlabeled, into the main `entities` list.
2. `enforce_confidence_gate` / `build_refusal_content` -- the whole-result
   gate. If the *overall* parse confidence falls below
   `ConfidenceThresholds.minimum_acceptable`, the parsed content is withheld
   (never returned as if verified) unless the caller explicitly opts in via
   `allow_low_confidence=True`, or the configured action says otherwise.
"""

from __future__ import annotations

from typing import Any

from .config import ParserConfig
from .exceptions import LowConfidenceRefusal


def split_entities_by_confidence(
    entities: list[dict[str, Any]], threshold: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split entities into `(trusted, low_confidence)` by their own confidence.

    An entity with no `confidence` key is treated as `0.0` (never silently
    trusted by default) rather than assumed reliable.
    """
    trusted: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []
    for entity in entities:
        score = float(entity.get("confidence", 0.0))
        (trusted if score >= threshold else unverified).append(entity)
    return trusted, unverified


def build_refusal_content(reason: str) -> dict[str, Any]:
    """Build the structured content payload used when a result is refused.

    Fields are explicitly `None`/empty rather than omitted, so consumers
    can tell "withheld" apart from "genuinely empty document" by shape
    alone, without needing to also check `ParseResult.refused`.
    """
    return {
        "structured_data": None,
        "text_content": None,
        "entities": [],
        "low_confidence_entities": [],
        "withheld_due_to_low_confidence": True,
        "refusal_reason": reason,
    }


def enforce_confidence_gate(
    *,
    overall_confidence: float,
    format_detected: str,
    config: ParserConfig,
    allow_low_confidence: bool,
    reason_override: str | None = None,
) -> tuple[bool, str | None]:
    """Decide whether a parse result should be refused.

    Returns `(refused, refusal_reason)`. `refusal_reason` is populated
    whenever confidence is below the floor, even in "warn" mode where
    `refused` stays `False` -- the caller can still see why the value is
    shaky. Raises `LowConfidenceRefusal` when
    `config.on_low_confidence == "raise"` and the caller has not overridden
    it with `allow_low_confidence=True`.

    `reason_override` lets the caller supply a more specific explanation
    (e.g. "the json parser failed and we fell back to text") that is used
    verbatim in place of the generic below-the-floor message, across all
    three `on_low_confidence` modes.
    """
    threshold = config.confidence_thresholds.minimum_acceptable
    if allow_low_confidence or overall_confidence >= threshold:
        return False, None

    reason = reason_override or (
        f"confidence {overall_confidence:.2f} for format '{format_detected}' is "
        f"below the configured minimum {threshold:.2f}; refusing to assert this "
        "result as reliable. Pass allow_low_confidence=True to override, or "
        "relax ParserConfig.confidence_thresholds.minimum_acceptable."
    )

    if config.on_low_confidence == "raise":
        raise LowConfidenceRefusal(reason, overall_confidence, format_detected)
    if config.on_low_confidence == "warn":
        return False, reason
    return True, reason
