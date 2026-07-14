"""The detect -> per-language deriver -> ai_card assembler dispatcher."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from ..ai_card import AI_CARD_SLOTS, AiCard
from ..config import NgfifyConfig
from ..detection import BASE_KIND_MAP, CODE_LANGUAGES, Language, detect_language, refine_kind
from ..frontmatter import parse_ai_card_yaml, split_frontmatter
from ..parsing import parse_source, read_source_text
from ..text_utils import TODO_SENTINEL, kebab_case, mtime_to_iso_date
from .common import DerivedFields
from .css_deriver import derive_css
from .html_deriver import derive_html
from .jsts_deriver import derive_jsts
from .markdown_deriver import derive_markdown
from .python_deriver import derive_python

__all__ = ["derive_ai_card", "DerivedFields"]

_DERIVER_TABLE: dict[Language, Callable[[Path, str, NgfifyConfig], DerivedFields]] = {
    Language.PYTHON: derive_python,
    Language.TYPESCRIPT: derive_jsts,
    Language.JAVASCRIPT: derive_jsts,
    Language.MARKDOWN: derive_markdown,
    Language.HTML: derive_html,
    Language.CSS: derive_css,
}


def derive_ai_card(path: Path, config: NgfifyConfig | None = None) -> tuple[AiCard, dict[str, Any]]:
    """Derive the 13-slot `AiCard` for `path`.

    Returns `(card, extra_keys)`, where `extra_keys` holds any non-ai_card
    keys found in an already-frontmattered markdown file's declared block
    (preserved, never dropped, never merged into the 13 canonical slots).
    """
    config = config or NgfifyConfig()
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ngfify: no such file: {path}")

    language = detect_language(path, config.extra_extension_map)
    parse_result = parse_source(path, config.extra_extension_map)
    full_text = read_source_text(path, parse_result)

    existing: dict[str, Any] = {}
    extra_keys: dict[str, Any] = {}
    derivation_text = full_text
    if language is Language.MARKDOWN:
        raw_frontmatter, body_after = split_frontmatter(full_text)
        if raw_frontmatter is not None:
            existing = parse_ai_card_yaml(raw_frontmatter)
            derivation_text = body_after
            extra_keys = {key: value for key, value in existing.items() if key not in AI_CARD_SLOTS}

    derived = _DERIVER_TABLE[language](path, derivation_text, config)
    kind = refine_kind(language, path, full_text) if language in CODE_LANGUAGES else BASE_KIND_MAP[language]

    card = AiCard(
        id=kebab_case(path.stem),
        kind=kind,
        audience=config.audience_default,
        status=config.status_default,
        owner_area=_owner_area(path, config),
        main_files=[str(path)],
        public_interfaces=derived.public_interfaces,
        provides=derived.provides,
        depends_on=derived.depends_on,
        safe_edit_points=[TODO_SENTINEL],
        risk_areas=derived.risk_areas,
        graph_rag_entities=derived.graph_rag_entities,
        last_verified=mtime_to_iso_date(path),
    )

    if existing:
        card = _merge_declared(card, existing)

    return card, extra_keys


def _owner_area(path: Path, config: NgfifyConfig) -> str:
    """The file's parent-dir name, else `"unassigned"` -- or the declared override."""
    if config.owner_area_override:
        return config.owner_area_override
    parent_name = path.resolve().parent.name
    return parent_name or "unassigned"


def _merge_declared(card: AiCard, existing: dict[str, Any]) -> AiCard:
    """Never clobber an author's declared ai_card value; only fill what's missing."""
    updates: dict[str, Any] = {}
    for slot in AI_CARD_SLOTS:
        if slot in existing:
            value = existing[slot]
            if value not in (None, "", []):
                updates[slot] = value
    return replace(card, **updates)
