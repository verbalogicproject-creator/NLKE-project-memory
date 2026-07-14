"""Shared parser adapter contract and small extraction helpers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from ..config import ParserLimits

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
URL_PATTERN = re.compile(r"https?://[^\s]+")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class ParserAdapter(ABC):
    """Base class for format-specific parsers.

    Concrete adapters accept a `ParserLimits` (default: `ParserLimits()`)
    so every "first N items" cap that used to be a hardcoded literal in
    the original script is now user-declared instead.
    """

    def __init__(self, limits: ParserLimits | None = None) -> None:
        """Store the limits to apply while extracting entities/structure."""
        self.limits = limits or ParserLimits()

    @abstractmethod
    def can_parse(self) -> bool:
        """Whether this adapter's dependencies are satisfied right now."""

    @abstractmethod
    def parse(self, file_path: str) -> dict[str, Any]:
        """Parse `file_path` into `{structured_data, text_content, entities}`."""

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """Return the declared output schema shape for this adapter."""

    def get_confidence(self) -> float:
        """Default per-adapter confidence when no finer signal is available."""
        return 0.90


def extract_text_entities(text: str, limits: ParserLimits) -> list[dict[str, Any]]:
    """Extract emails / URLs / IP addresses from free text (shared helper).

    Confidence values (0.90 for email/URL, 0.95 for IP addresses) match the
    original script's hardcoded scores; they reflect how unambiguous each
    pattern is, not how much text was scanned.
    """
    entities: list[dict[str, Any]] = []

    emails = sorted(set(EMAIL_PATTERN.findall(text)))
    for email in emails[: limits.max_text_entities_per_type]:
        entities.append({"name": email, "type": "email", "confidence": 0.90})

    urls = sorted(set(URL_PATTERN.findall(text)))
    for url in urls[: limits.max_text_entities_per_type]:
        entities.append({"name": url, "type": "url", "confidence": 0.90})

    ips = sorted(set(IP_PATTERN.findall(text)))
    for ip in ips[: limits.max_text_entities_per_type]:
        entities.append({"name": ip, "type": "ip_address", "confidence": 0.95})

    return entities
