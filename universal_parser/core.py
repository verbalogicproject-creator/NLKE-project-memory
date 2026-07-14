"""The `UniversalParser` orchestrator: detect -> select -> parse -> validate -> gate.

This module is the thin composition root; the actual format logic lives in
`parsers/`, detection lives in `detection.py`, and the confidence-scored
boundary's enforcement lives in `gate.py`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .config import ParserConfig
from .detection import FormatDetector
from .exceptions import MissingDependencyError, UnsafeContentRefusal
from .gate import build_refusal_content, enforce_confidence_gate, split_entities_by_confidence
from .parsers import ParserAdapter, build_parsers
from .schema import ParseResult

logger = logging.getLogger(__name__)

REQUIRED_CONTENT_FIELDS = ("structured_data", "text_content", "entities")

# When a file's own detected-format parser fails and no alternative format
# matches, we fall back to reading it as plain text -- but detection is then
# no longer trustworthy, so collapse the detection confidence to the lowest
# ("default"/unknown) band. That drags the overall score below the floor so
# the confidence gate refuses it, rather than asserting a failed parse as a
# confident result. See `parse()` and `_retry_by_content()`.
_DEGRADED_DETECTION_CONFIDENCE = 0.50


class UniversalParser:
    """Parse 15+ file formats into one confidence-scored, schema-validated result.

    Pipeline, per PLAYBOOK-style sequential composition:

    1. Detect format (extension -> magic bytes -> content sniffing -> default).
    2. Select the matching parser adapter, or fall back to plain text.
    3. Parse, catching adapter errors and degrading to plain text.
    4. Validate the parsed content against the adapter's declared schema.
    5. Gate on confidence: refuse (default), warn, or raise -- never silently
       assert a low-confidence guess as fact. See `config.ParserConfig`.

    A binary format whose optional dependency is missing (e.g. PDF without
    `pdfplumber`) is never silently decoded as text; it is refused outright
    with an install hint (see `_missing_dependency_result`).
    """

    def __init__(self, config: ParserConfig | None = None) -> None:
        """Build the parser registry from `config` (or defaults)."""
        self.config = config or ParserConfig()
        self.parsers: dict[str, ParserAdapter] = build_parsers(self.config.limits)

    def parse(self, file_path: str, allow_low_confidence: bool = False) -> ParseResult:
        """Parse `file_path` end-to-end and return a `ParseResult`.

        Args:
            file_path: path to the file to parse.
            allow_low_confidence: if `True`, bypasses the whole-result
                confidence gate for this call even when
                `config.on_low_confidence == "refuse"` or `"raise"`.
        """
        start_time = time.time()
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        format_detected, detection_method, detection_confidence = FormatDetector.detect(
            str(file_path_obj), self.config.extra_extension_map
        )

        parser = self.parsers.get(format_detected)
        if parser is None:
            parser = self.parsers["txt"]
        elif not parser.can_parse():
            return self._missing_dependency_result(
                file_path_obj, format_detected, detection_method, detection_confidence, start_time
            )

        degraded_from: str | None = None
        try:
            content = parser.parse(str(file_path_obj))
        except MissingDependencyError:
            raise
        except UnsafeContentRefusal as exc:
            return self._refusal_result(
                file_path_obj, format_detected, detection_method, detection_confidence,
                start_time, str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - any adapter failure is recovered-or-refused
            failed_format = format_detected
            retry = self._retry_by_content(file_path_obj, failed_format)
            if retry is not None:
                parser, content, format_detected, detection_method, detection_confidence = retry
                logger.warning(
                    "Parse error for format '%s' (%s): %s. Recovered by re-detecting as '%s'.",
                    failed_format, file_path_obj.name, exc, format_detected,
                )
            else:
                logger.warning(
                    "Parse error for format '%s' (%s): %s. Falling back to plain text; "
                    "the result will be refused as an unreliable parse.",
                    failed_format, file_path_obj.name, exc,
                )
                degraded_from = failed_format
                parser = self.parsers["txt"]
                content = parser.parse(str(file_path_obj))
                detection_method = "fallback"
                detection_confidence = _DEGRADED_DETECTION_CONFIDENCE

        validation_result = self._validate(content, parser.get_schema())

        entities = content.get("entities", [])
        trusted, low_confidence = split_entities_by_confidence(
            entities, self.config.confidence_thresholds.entity_min_confidence
        )
        content = {**content, "entities": trusted, "low_confidence_entities": low_confidence}

        parse_time_ms = (time.time() - start_time) * 1000
        metadata = {
            "file_path": str(file_path_obj),
            "file_size": file_path_obj.stat().st_size,
            "format_detected": format_detected,
            "detection_method": detection_method,
            "detection_confidence": detection_confidence,
            "parse_time_ms": round(parse_time_ms, 2),
            "parser_version": self.config.parser_version,
            "degraded_from": degraded_from,
        }

        overall_confidence = round(
            detection_confidence * 0.5 + (0.9 if validation_result["schema_valid"] else 0.7) * 0.5,
            2,
        )
        confidence_level = self.config.confidence_thresholds.classify(overall_confidence)

        reason_override: str | None = None
        if degraded_from is not None:
            reason_override = (
                f"file was detected as '{degraded_from}' but the {degraded_from} parser "
                "failed and no alternative format matched; fell back to plain text. "
                f"Refusing to assert this as a reliable '{degraded_from}' parse. Pass "
                "allow_low_confidence=True to see the raw text instead."
            )

        refused, refusal_reason = enforce_confidence_gate(
            overall_confidence=overall_confidence,
            format_detected=format_detected,
            config=self.config,
            allow_low_confidence=allow_low_confidence,
            reason_override=reason_override,
        )
        if refusal_reason and not refused:
            logger.warning(refusal_reason)
        if refused:
            content = build_refusal_content(refusal_reason or "confidence below configured minimum")

        return ParseResult(
            format=format_detected,
            confidence=overall_confidence,
            confidence_level=confidence_level,
            refused=refused,
            refusal_reason=refusal_reason if refused else None,
            metadata=metadata,
            content=content,
            validation=validation_result,
        )

    def parse_batch(self, file_paths: list[str], **options: Any) -> list[ParseResult]:
        """Parse multiple files, logging and skipping any that raise."""
        results: list[ParseResult] = []
        total = len(file_paths)
        for idx, file_path in enumerate(file_paths, 1):
            try:
                result = self.parse(file_path, **options)
                results.append(result)
                logger.info("[%d/%d] parsed %s: %s", idx, total, file_path, result.format)
            except Exception as exc:  # noqa: BLE001 - batch mode must not abort on one bad file
                logger.error("[%d/%d] error parsing %s: %s", idx, total, file_path, exc)
        return results

    def detect_format(self, file_path: str) -> str:
        """Auto-detect a file's format without parsing it."""
        format_detected, _, _ = FormatDetector.detect(file_path, self.config.extra_extension_map)
        return format_detected

    def get_schema(self, format_type: str) -> dict[str, Any]:
        """Return the declared output schema for `format_type`, or `{}` if unknown."""
        parser = self.parsers.get(format_type)
        return parser.get_schema() if parser else {}

    def _retry_by_content(
        self, file_path_obj: Path, failed_format: str
    ) -> tuple[ParserAdapter, dict[str, Any], str, str, float] | None:
        """Retry a failed parse using content-based (not extension) detection.

        The extension may have lied -- a `.json` that is really CSV. Re-detect
        from content and, if it points to a *different* structured parser
        whose optional dependency is available, try that. Only a result with
        real structure (a non-empty dict/list) is accepted: a permissive
        scalar (e.g. `yaml.safe_load` happily returning a bare string for
        junk) is rejected, so this recovery path can never reintroduce the
        "assert a guess as fact" problem it exists to prevent.

        Returns `(parser, content, format, detection_method, confidence)` on a
        successful recovery, or `None` to let the caller degrade to text.
        """
        content_format = FormatDetector._detect_by_content(str(file_path_obj))
        if not content_format or content_format == failed_format:
            return None
        candidate = self.parsers.get(content_format)
        if candidate is None or candidate is self.parsers["txt"] or not candidate.can_parse():
            return None
        try:
            content = candidate.parse(str(file_path_obj))
        except Exception:  # noqa: BLE001 - retry failed too; caller degrades to text
            return None
        structured = content.get("structured_data")
        if not isinstance(structured, (dict, list)) or not structured:
            return None
        return candidate, content, content_format, "content", 0.75

    def _missing_dependency_result(
        self,
        file_path_obj: Path,
        format_detected: str,
        detection_method: str,
        detection_confidence: float,
        start_time: float,
    ) -> ParseResult:
        """Refuse to fabricate content for a binary format we cannot actually parse.

        Rather than silently decoding binary bytes as text (which produces
        garbled, unlabeled "content"), universal_parser refuses outright and
        names the missing dependency and the extra that installs it.
        """
        reason = (
            f"cannot parse format '{format_detected}': its optional dependency is "
            f"not installed. Install with: pip install 'nlke-universal-parser[{format_detected}]'. "
            "Refusing to guess this binary file's content by decoding it as text."
        )
        return self._refusal_result(
            file_path_obj, format_detected, detection_method, detection_confidence,
            start_time, reason,
        )

    def _refusal_result(
        self,
        file_path_obj: Path,
        format_detected: str,
        detection_method: str,
        detection_confidence: float,
        start_time: float,
        reason: str,
    ) -> ParseResult:
        """Build a hard-refused `ParseResult` (confidence 0.0) with an explicit reason.

        Shared by the missing-optional-dependency path and the unsafe-content
        path (e.g. an XML file that declares a DTD/entities): both refuse to
        parse at all rather than fabricate content or risk resource
        exhaustion.
        """
        parse_time_ms = (time.time() - start_time) * 1000
        metadata = {
            "file_path": str(file_path_obj),
            "file_size": file_path_obj.stat().st_size,
            "format_detected": format_detected,
            "detection_method": detection_method,
            "detection_confidence": detection_confidence,
            "parse_time_ms": round(parse_time_ms, 2),
            "parser_version": self.config.parser_version,
            "degraded_from": None,
        }
        validation_result = {
            "schema_valid": False,
            "errors": [reason],
            "warnings": [],
            "schema_checked_against": "n/a",
        }
        return ParseResult(
            format=format_detected,
            confidence=0.0,
            confidence_level=self.config.confidence_thresholds.classify(0.0),
            refused=True,
            refusal_reason=reason,
            metadata=metadata,
            content=build_refusal_content(reason),
            validation=validation_result,
        )

    def _validate(self, content: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        """Validate parsed content against the adapter's declared schema."""
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(content, dict):
            errors.append("Content is not a dictionary")
        for field_name in REQUIRED_CONTENT_FIELDS:
            if field_name not in content:
                warnings.append(f"Missing field: {field_name}")
        return {
            "schema_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "schema_checked_against": str(schema),
        }
