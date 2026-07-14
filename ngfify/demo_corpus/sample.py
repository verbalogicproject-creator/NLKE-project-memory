"""Tiny demo module for ngfify's Python deriver.

Provides a couple of public functions and one class, plus a private helper
that should NOT show up in public_interfaces.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["greet"]


def greet(name: str) -> str:
    """Return a friendly greeting for `name`."""
    return f"Hello, {name}!"


def load_greeting_config(path: Path) -> dict[str, str]:
    """Load a `{"name": "..."}`-shaped greeting config from `path`."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _internal_helper() -> None:
    """Private helper -- must never appear in public_interfaces."""


class Greeter:
    """Wraps `greet` with a configurable default name."""

    def __init__(self, default_name: str = "world") -> None:
        self.default_name = default_name

    def greet_default(self) -> str:
        """Greet `self.default_name`."""
        return greet(self.default_name)
