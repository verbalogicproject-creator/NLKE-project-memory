"""Parsers for plain text and log files."""

from __future__ import annotations

import re
from typing import Any

from .base import ParserAdapter, extract_text_entities


class TextParser(ParserAdapter):
    """Parse plain text (also used for Markdown, HTML, INI, ENV as-is)."""

    def can_parse(self) -> bool:
        """Text parsing uses only the standard library."""
        return True

    def parse(self, file_path: str) -> dict[str, Any]:
        """Read the file and extract line/word counts plus text entities."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        lines = text.split("\n")
        return {
            "structured_data": {
                "lines": lines,
                "line_count": len(lines),
                "word_count": len(text.split()),
            },
            "text_content": text,
            "entities": extract_text_entities(text, self.limits),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for plain text content."""
        return {
            "structured_data": {"lines": "array", "line_count": "number", "word_count": "number"},
            "text_content": "string",
            "entities": "array",
        }


class LogParser(ParserAdapter):
    """Parse log files with structured timestamp/level extraction."""

    _TIMESTAMP_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")
    _LEVEL_PATTERN = re.compile(r"\[(ERROR|WARN|INFO|DEBUG)\]")

    def can_parse(self) -> bool:
        """Log parsing uses only the standard library."""
        return True

    def parse(self, file_path: str) -> dict[str, Any]:
        """Parse each line into a timestamped/leveled event, bounded by limits."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        events = self._parse_log_lines(lines)
        return {
            "structured_data": {
                "events": events,
                "total_lines": len(lines),
                "event_count": len(events),
            },
            "text_content": "".join(lines[: self.limits.max_log_preview_lines]),
            "entities": self._extract_log_entities(events),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for log content."""
        return {
            "structured_data": {"events": "array", "total_lines": "number", "event_count": "number"},
            "text_content": "string",
            "entities": "array",
        }

    def _parse_log_lines(self, lines: list[str]) -> list[dict[str, Any]]:
        """Parse each line into an event dict; confidence rises with each signal found."""
        events: list[dict[str, Any]] = []
        for line in lines[: self.limits.max_log_lines_parsed]:
            event: dict[str, Any] = {"raw": line.strip(), "confidence": 0.70}

            ts_match = self._TIMESTAMP_PATTERN.search(line)
            if ts_match:
                event["timestamp"] = ts_match.group(1)
                event["confidence"] = 0.85

            level_match = self._LEVEL_PATTERN.search(line)
            if level_match:
                event["level"] = level_match.group(1)
                event["confidence"] = 0.90

            events.append(event)
        return events

    def _extract_log_entities(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Summarize the distinct log levels seen, with per-level counts."""
        levels = {event["level"] for event in events if "level" in event}
        entities = []
        for level in sorted(levels):
            count = sum(1 for e in events if e.get("level") == level)
            entities.append({"name": level, "type": "log_level", "count": count, "confidence": 0.95})
        return entities
