"""load_pack — read one ``.pack.md`` file: frontmatter (id/name/members) + a
markdown body (the pack's "when loaded" prompt).

A pack is a per-pack meta-index node — the same primitive as a project, just
declared instead of indexed: annotated links to member projects (``members:``,
each ``<name>: <why>``) + a prompt. See Unit 2, ``MEMORY-SYSTEM-MVP-SPEC.md``.

Reuses ``portfolio.py``'s hand-rolled flat-YAML frontmatter parser (the same
restricted ``key: scalar`` / ``key:`` + ``- item`` shape ai_cards use) rather
than adding a PyYAML dependency for something this simple.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .portfolio import _parse_flat_yaml

#: Where a bare pack id resolves to, absent an explicit ``packs_dir`` —
#: convention: ``<packs_dir>/<id>.pack.md``, id-in-filename doubling as a
#: cheap existence check before the frontmatter is even parsed.
DEFAULT_PACKS_DIR = Path(__file__).resolve().parent / "packs"


def _split_pack_file(text: str) -> tuple[str, str]:
    """(frontmatter_raw, body) — body is everything after the closing ``---``."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        raise ValueError("pack file must open with a '---' frontmatter block")
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1:]).strip()
    raise ValueError("pack file frontmatter block is never closed with '---'")


def load_pack(path: str | Path) -> dict[str, Any]:
    """Load one ``.pack.md`` file.

    Returns ``{"id", "name", "members": [{"name", "why"}], "prompt"}``. Fails
    loud (``ValueError``) on anything malformed — a pack silently missing a
    member is worse than a pack that refuses to load (CLAUDE.md: "Schema
    validation fails loud").
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    raw_fm, body = _split_pack_file(text)
    fm = _parse_flat_yaml(raw_fm)

    if fm.get("kind") != "pack":
        raise ValueError(f"{path}: frontmatter 'kind' must be 'pack' (got {fm.get('kind')!r})")
    if not fm.get("id"):
        raise ValueError(f"{path}: frontmatter is missing required 'id'")
    if not isinstance(fm.get("members"), list) or not fm["members"]:
        raise ValueError(f"{path}: frontmatter 'members' must be a non-empty list")
    if not body:
        raise ValueError(f"{path}: missing a body (the pack's when-loaded prompt)")

    members: list[dict[str, str]] = []
    for raw_member in fm["members"]:
        name, sep, why = raw_member.partition(": ")
        if not sep:
            raise ValueError(f"{path}: member '{raw_member}' must be '<name>: <why>'")
        members.append({"name": name.strip(), "why": why.strip()})

    return {"id": fm["id"], "name": fm.get("name", fm["id"]), "members": members, "prompt": body}


def find_pack(pack_id: str, packs_dir: Path | None = None) -> dict[str, Any] | None:
    """Resolve a bare pack id to its loaded pack, or ``None`` if no such file
    exists — the not-found case a caller (``build_artifact``, `brain load`)
    needs to distinguish from a malformed one (which still raises loud).

    ``packs_dir`` defaults to ``DEFAULT_PACKS_DIR``, re-read from the module
    global on every call (not bound at def time) so tests can point it at a
    tmp_path via ``monkeypatch.setattr(pack, "DEFAULT_PACKS_DIR", ...)``
    without needing every caller (``build_artifact``, `cli.cmd_brain_load`) to
    thread a ``packs_dir`` parameter through.
    """
    packs_dir = packs_dir or DEFAULT_PACKS_DIR
    path = packs_dir / f"{pack_id}.pack.md"
    if not path.is_file():
        return None
    pack = load_pack(path)
    if pack["id"] != pack_id:
        raise ValueError(
            f"{path}: frontmatter id {pack['id']!r} doesn't match its filename-derived id {pack_id!r}"
        )
    return pack


def list_packs(packs_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every pack declared under ``packs_dir`` (default ``DEFAULT_PACKS_DIR``),
    sorted by id — the enumeration `brain menu` needs to list packs without
    hardcoding which ones exist. Returns ``[{"id", "name"}, ...]``.

    Resolves each discovered file through ``find_pack`` (by its filename-
    derived id), not a direct ``load_pack`` — so a listed pack is guaranteed
    loadable by the very id it's listed under; a file whose declared id
    doesn't match its filename would otherwise show up in the menu under a
    name that can't actually be resolved.
    """
    packs_dir = packs_dir or DEFAULT_PACKS_DIR
    if not packs_dir.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(packs_dir.glob("*.pack.md")):
        pack_id = path.name[: -len(".pack.md")]
        pack = find_pack(pack_id, packs_dir=packs_dir)
        result.append({"id": pack["id"], "name": pack["name"]})
    return result
