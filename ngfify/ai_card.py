"""The 13-slot `ai_card` contract -- matches the ecosystem's canonical shape exactly.

See a real example at
`NLKE-Declarum-game-engine/docs/ecosystem-extraction-plan-2026-07-09.ngf.md`:
its YAML frontmatter is this shape. Scalar slots (`id`, `kind`, `audience`,
`status`, `owner_area`, `last_verified`) are single strings; every other
slot is a list of strings (even when a per-file deriver only ever produces
one item, e.g. `provides`).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Canonical slot order -- also the order slots are emitted in frontmatter.
AI_CARD_SLOTS: tuple[str, ...] = (
    "id",
    "kind",
    "audience",
    "status",
    "owner_area",
    "main_files",
    "public_interfaces",
    "provides",
    "depends_on",
    "safe_edit_points",
    "risk_areas",
    "graph_rag_entities",
    "last_verified",
)

#: Slots whose value is a list of strings (all slots except the six scalars).
LIST_SLOTS: frozenset[str] = frozenset(
    {
        "main_files",
        "public_interfaces",
        "provides",
        "depends_on",
        "safe_edit_points",
        "risk_areas",
        "graph_rag_entities",
    }
)


@dataclass
class AiCard:
    """A single file's derived `ai_card` frontmatter -- the 13-slot contract."""

    id: str
    kind: str
    audience: str
    status: str
    owner_area: str
    main_files: list[str]
    public_interfaces: list[str]
    provides: list[str]
    depends_on: list[str]
    safe_edit_points: list[str]
    risk_areas: list[str]
    graph_rag_entities: list[str]
    last_verified: str

    def to_dict(self) -> dict[str, object]:
        """Convert to a plain dict, in canonical slot order."""
        return {slot: getattr(self, slot) for slot in AI_CARD_SLOTS}
