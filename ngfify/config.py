"""User-declared configuration for `ngfify` -- every strip-listed constant lives here.

Nothing project-specific (audience labels, owner-area fallback, risk-scan
path patterns, output naming, extension routing) is a hardcoded literal
elsewhere in the package; callers override what they need via
`NgfifyConfig` or a TOML file read by `load_config`, and get parity
defaults for everything else. Mirrors the pattern used by
`universal_parser.config` for consistency across the ecosystem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import toml as _toml
except ImportError:  # pragma: no cover - exercised via load_config tests
    _toml = None

#: Generic OS-convention absolute-path prefixes, not any one project's
#: paths. Override via `NgfifyConfig.hardcoded_path_patterns` (or the
#: `[hardcoded_path_patterns]` TOML list) to add project-specific ones.
DEFAULT_HARDCODED_PATH_PATTERNS: tuple[str, ...] = (
    r"/root/",
    r"/home/[^/\s\"']+/",
    r"/Users/[^/\s\"']+/",
    r"/data/data/com\.termux/",
    r"[A-Za-z]:\\\\",
)


@dataclass(frozen=True)
class NgfifyConfig:
    """Top-level, user-declared configuration for ngfify.

    Attributes:
        audience_default: default `audience` slot value (spec default: `"engineer"`).
        status_default: default `status` slot value (spec default: `"active"`).
        owner_area_override: if set, used for every file's `owner_area`
            instead of the derived parent-directory name -- an explicit
            user declaration, not a fabrication.
        extra_extension_map: additional `".ext" -> "format"` entries merged
            into `universal_parser`'s extension map for the shared parse
            front-end (e.g. to route an unusual extension through a
            specific format).
        hardcoded_path_patterns: regexes flagged by the `risk_areas` heuristic.
        max_graph_rag_entities: cap on `graph_rag_entities` list length.
        output_suffix: appended to the input filename for the default
            output path (spec default: `.ngf.md`, giving `<file>.ngf.md`).
    """

    audience_default: str = "engineer"
    status_default: str = "active"
    owner_area_override: str | None = None
    extra_extension_map: dict[str, str] = field(default_factory=dict)
    hardcoded_path_patterns: tuple[str, ...] = DEFAULT_HARDCODED_PATH_PATTERNS
    max_graph_rag_entities: int = 40
    output_suffix: str = ".ngf.md"


def load_config(path: str | Path | None) -> NgfifyConfig:
    """Load an `NgfifyConfig` from a TOML file, or return defaults.

    Degrades gracefully: if `path` is `None`, the file does not exist, or
    the optional `toml` dependency is not installed, this returns
    `NgfifyConfig()` defaults rather than raising. Expected shape::

        audience_default = "engineer"
        status_default = "active"
        owner_area_override = "ecosystem"
        max_graph_rag_entities = 40
        output_suffix = ".ngf.md"

        [extra_extension_map]
        ".mjs" = "javascript"

        hardcoded_path_patterns = ["/root/", "/srv/myapp/"]
    """
    if path is None:
        return NgfifyConfig()

    config_path = Path(path)
    if not config_path.exists() or _toml is None:
        return NgfifyConfig()

    try:
        raw = _toml.load(config_path)
    except Exception as exc:  # noqa: BLE001 - a malformed config degrades, never crashes the caller
        logger.warning("Could not read config '%s': %s. Using defaults.", config_path, exc)
        return NgfifyConfig()

    return NgfifyConfig(
        audience_default=raw.get("audience_default", "engineer"),
        status_default=raw.get("status_default", "active"),
        owner_area_override=raw.get("owner_area_override"),
        extra_extension_map=_as_str_map(raw.get("extra_extension_map", {})),
        hardcoded_path_patterns=_as_str_tuple(
            raw.get("hardcoded_path_patterns"), DEFAULT_HARDCODED_PATH_PATTERNS
        ),
        max_graph_rag_entities=_as_positive_int(raw.get("max_graph_rag_entities"), 40),
        output_suffix=raw.get("output_suffix", ".ngf.md"),
    )


def _as_str_map(value: object) -> dict[str, str]:
    """Coerce a config value to a ``{str: str}`` map, or `{}` with a warning."""
    if not isinstance(value, dict):
        logger.warning("Config extra_extension_map is not a table; ignoring it.")
        return {}
    return {str(k): str(v) for k, v in value.items()}


def _as_str_tuple(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    """Coerce a config value to a tuple of strings, or `default` with a warning."""
    if value is None:
        return default
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        logger.warning("Config hardcoded_path_patterns is not a list; using defaults.")
        return default
    return tuple(str(item) for item in value)


def _as_positive_int(value: object, default: int) -> int:
    """Coerce a config value to a positive int, or `default` with a warning.

    A typo'd or wrong-typed `max_graph_rag_entities` (e.g. a string) previously
    raised `ValueError` straight through the CLI's `--config`; now it degrades.
    """
    if value is None:
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        logger.warning("Config max_graph_rag_entities=%r is not an integer; using %d.", value, default)
        return default
    if result < 1:
        logger.warning("Config max_graph_rag_entities=%d must be >= 1; using %d.", result, default)
        return default
    return result
