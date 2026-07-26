"""Render an `AiCard` + body summary into a `.ngf.md` file's full text.

Uses a small hand-rolled YAML-frontmatter writer (not a full YAML library)
since the 13-slot shape it needs to emit is fixed and simple: scalars and
lists of strings. Quoting follows conservative YAML-safety rules -- when in
doubt, quote.
"""

from __future__ import annotations

from typing import Any

from .ai_card import AI_CARD_SLOTS, LIST_SLOTS, AiCard
from .text_utils import TODO_SENTINEL

_RESERVED_SCALARS = frozenset({"true", "false", "null", "yes", "no", "~", ""})

#: Every YAML 1.2 c-indicator (spec §5.3). A plain scalar may not begin with any of
#: them, so a value that does must be quoted.
#:
#: This was previously a hand-enumerated list missing six of them -- and the one that
#: mattered was the backtick. Markdown headings routinely open with a code span
#: (`## \`declared_core.schema\``), the markdown deriver lifts headings straight into
#: `public_interfaces`, and the result was frontmatter that no YAML parser would
#: accept. Downstream, `frontmatter_rag` reported those cards as
#: `skipped_no_frontmatter` -- indistinguishable from a file that simply has none --
#: so they vanished from the index without an error. 95 headings across 8 repos in
#: this ecosystem begin with a backtick, nearly all of them in the API- and
#: CLI-reference chapters, which are the densest docs there are.
#:
#: Enumerating by hand is what failed, so `tests/test_ai_card_emitter.py` now
#: round-trips emitted frontmatter through a real YAML parser rather than trusting
#: this tuple.
_SPECIAL_LEADING_CHARS = (
    "-", "?", ":", ",", "[", "]", "{", "}", "#", "&", "*", "!",
    "|", ">", "'", '"', "%", "@", "`",
)


def _needs_quoting(value: str) -> bool:
    """Conservative check for whether a scalar needs double-quoting in our writer."""
    if value == "":
        return True
    if value != value.strip():
        return True
    if value.lower() in _RESERVED_SCALARS:
        return True
    if value.startswith(_SPECIAL_LEADING_CHARS):
        return True
    if any(marker in value for marker in (": ", '"', "\n")) or value.endswith(":"):
        return True
    return False


def _yaml_scalar(value: str) -> str:
    """Render a single YAML scalar, quoting only when necessary."""
    if _needs_quoting(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def render_frontmatter(card: AiCard, extra_keys: dict[str, Any] | None = None) -> str:
    """Render `card` (plus any preserved unknown frontmatter keys) as a `---` block."""
    lines: list[str] = ["---"]
    for slot in AI_CARD_SLOTS:
        value = getattr(card, slot)
        _emit_field(lines, slot, value)
    for key, value in (extra_keys or {}).items():
        _emit_field(lines, key, value)
    lines.append("---")
    return "\n".join(lines) + "\n"


def _emit_field(lines: list[str], key: str, value: Any) -> None:
    """Append one field's rendered lines (scalar or list) to `lines`."""
    if isinstance(value, list):
        lines.append(f"{key}:")
        for item in value:
            lines.append(f"  - {_yaml_scalar(str(item))}")
    else:
        lines.append(f"{key}: {_yaml_scalar(str(value))}")


def render_body(
    card: AiCard,
    source_display_path: str,
    generated_date: str,
    tool_version: str,
) -> str:
    """Render the `.ngf.md` body: the `provides` line, an interfaces bullet list, a trailer."""
    provides_line = "; ".join(card.provides) if card.provides else TODO_SENTINEL

    lines: list[str] = [f"# {card.id}", "", provides_line, "", "## Public interfaces", ""]
    interfaces = card.public_interfaces if card.public_interfaces else [TODO_SENTINEL]
    for item in interfaces:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"> auto-declared by ngfify v{tool_version} from {source_display_path} on {generated_date}")
    lines.append("")
    return "\n".join(lines)


def render_ngf_md(
    card: AiCard,
    source_display_path: str,
    generated_date: str,
    tool_version: str,
    extra_keys: dict[str, Any] | None = None,
) -> str:
    """Render the full `.ngf.md` text: frontmatter + a blank line + the body."""
    frontmatter = render_frontmatter(card, extra_keys)
    body = render_body(card, source_display_path, generated_date, tool_version)
    return f"{frontmatter}\n{body}"
