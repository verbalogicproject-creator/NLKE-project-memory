"""A minimal, dependency-free parser for the ai_card YAML frontmatter shape.

This is deliberately NOT a general-purpose YAML engine: it understands
exactly the shape ai_cards use (top-level `key: scalar` and `key:` followed
by indented `  - item` lists, values optionally double-quoted) because that
is the only shape ngfify needs to MERGE with (see SPEC-v0.1.md: "if the
source is markdown that already has frontmatter, MERGE ... never clobber
an author's declaration"). Anything outside that shape (nested maps,
multi-line block scalars, YAML anchors, ...) is not supported -- an
existing key whose value doesn't parse cleanly is simply left out of the
merge dict, and the deriver's own value is used for that slot instead of
guessing at a malformed one.
"""

from __future__ import annotations

import re
from typing import Any

_KEY_LINE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_LIST_ITEM_LINE = re.compile(r"^\s+-\s?(.*)$")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split `text` into `(raw_frontmatter_block, body)`.

    Returns `(None, text)` unchanged if `text` does not open with a `---`
    frontmatter delimiter on its very first line.
    """
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None, text

    lines = text.splitlines(keepends=True)
    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return None, text

    raw_block = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    return raw_block, body


def parse_ai_card_yaml(raw_block: str) -> dict[str, Any]:
    """Parse an ai_card-shaped frontmatter block into `{key: str | list[str]}`.

    Unrecognized lines are skipped rather than raised on -- a best-effort,
    conservative parse. See the module docstring for the exact shape
    supported.
    """
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for raw_line in raw_block.splitlines():
        if not raw_line.strip():
            continue

        list_match = _LIST_ITEM_LINE.match(raw_line)
        if list_match and current_key is not None and current_list is not None:
            current_list.append(_unquote(list_match.group(1).strip()))
            continue

        key_match = _KEY_LINE.match(raw_line)
        if not key_match:
            continue

        key, value = key_match.group(1), key_match.group(2).strip()
        if value == "":
            current_key = key
            current_list = []
            result[key] = current_list
        else:
            current_key = None
            current_list = None
            result[key] = _unquote(value)

    return result


def _unquote(value: str) -> str:
    """Strip a matching pair of double quotes, unescaping `\\"` inside."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value
