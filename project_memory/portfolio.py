"""portfolio — the Portfolio Brain: index the whole ``~/projects`` ecosystem into
one `project_memory` store, so the substrate can answer questions about itself
(the "recursive close"). See ``PORTFOLIO-BRAIN-SPEC.md`` for the crystallized
design this module implements.

This is a layer *on* the existing engine, not a new one:

  - **One dimension per repo, flat.** The engine already has a per-item cluster
    column — ``episodes.batch`` (see ``schema.py``'s ``cluster_columns=("kind",
    "batch")``). A repo's "dimension" *is* ``batch=<repo name>``; nothing new is
    added to the schema. No cluster-tag layer, no second table.
  - **One atom per declared interface (finest available).** For each repo, in
    priority order: (1) a committed ``ai_card``-shaped ``*.ngf.md`` (its
    ``public_interfaces`` list, finest and hand-declared), (2) a "Public API"
    section in its own ``README.md`` / ``SPEC-v0.1.md`` / ``CODEBASE-REPORT.md``
    (the backtick-quoted symbol names), or (3) — only if neither exists — an
    ``ngfify`` auto-declared card over its best available markdown doc (headings
    as a coarse ``public_interfaces``; ``ngfify`` is an optional dependency,
    installed via the ``portfolio`` extra). Each atom is one ``remember()``
    episode, ``kind="interface"``, tagged and batched to its repo.
  - **Edges are declared facts, verified before ingest.** ``portfolio-edges.yaml``
    materializes the spec's manifest verbatim. Before a ``source -> target`` edge
    becomes a ``record_fact()`` row, this module checks whether *either* repo's
    own docs (README / SPEC-v0.1.md / CODEBASE-REPORT.md / CLAUDE.md / ROADMAP.md
    / CALIBRATION-NOTES.md / ``arch/*.ngf.md``) actually names the other. An edge
    that neither side asserts is **dropped, not ingested** — refuse-to-fabricate,
    applied to memory — and reported in the returned `IndexReport`.

Optional dependencies (the ``portfolio`` extra): ``pyyaml`` (to read
``portfolio-edges.yaml``) and ``ngfify`` (only exercised by the path-3
auto-declare fallback). Import this module directly — it is intentionally *not*
re-exported from ``project_memory.__init__``, so ``import project_memory`` stays
zero-extra-deps.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .query import ProjectMemory
from .schema import DEFAULT_KINDS, MemorySchema

#: Where a bare repo name resolves to, absent an explicit ``--root``.
DEFAULT_PROJECTS_ROOT = Path.home() / "projects"

#: The episode taxonomy this layer needs on top of the generic default:
#: ``"interface"`` for a declared-interface atom, and ``"brain_load"`` — a
#: `brain load` provenance record (see ``cli.cmd_brain_load``), dogfooding the
#: append-only episode log itself instead of a bespoke jsonl log. Edges are
#: *facts* (no ``kind`` column), so they need no taxonomy entry.
PORTFOLIO_KINDS: tuple[str, ...] = (*DEFAULT_KINDS, "interface", "brain_load", "brain_export", "brain_use")
PORTFOLIO_SCHEMA = MemorySchema(kinds=PORTFOLIO_KINDS)

# A stable namespace for deterministic ids — reruns of the indexer produce the
# same ids for the same (repo, source_file, content), so the store is
# byte-reproducible the way `demo.py`'s seed corpus is.
_ID_NAMESPACE = uuid.UUID("6f6e6520-6461-6d65-6e73-696f6e2e627e")

_EXCLUDE_DIR_NAMES = frozenset({
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__",
    "reference", "dist", "build", ".next", ".pytest_cache", "site-packages",
    # Sample/fixture content describing *fake* demo files, not the repo's own
    # declared interface — e.g. ngfify ships `demo_corpus/expected/*.ngf.md`
    # fixtures whose `public_interfaces` (`greet`, `Greeter`, ...) describe its
    # packaged demo sample, not ngfify itself. Excluded from both atom
    # extraction and edge verification.
    "demo_corpus", "demo-output", "fixtures", "expected", "test", "tests",
})

# Docs consulted (in this order, first found wins) when a repo has no declared
# ai_card and no "Public API" section — the ngfify auto-declare fallback (path 3).
FALLBACK_DOC_CANDIDATES: tuple[str, ...] = (
    "README.md", "SPEC-v0.1.md", "CODEBASE-REPORT.md", "CLAUDE.md", "DESIGN-BRIEF.md",
)

# Docs consulted when verifying whether a repo's own words assert a declared edge.
_EDGE_DOC_CANDIDATES: tuple[str, ...] = (
    "README.md", "SPEC-v0.1.md", "CODEBASE-REPORT.md", "CLAUDE.md",
    "ROADMAP.md", "CALIBRATION-NOTES.md", "INTEGRATION-PLAN.md",
)

# A full repo name shorter than this is never used for case-insensitive
# edge-verification matching — too likely to false-positive on ordinary prose
# if auto-derived ("sag", "kg", ...). Curated `RepoSpec.aliases` get a lower
# floor since they're matched case-sensitively (see `verify_edge`) and hand-picked
# precisely (e.g. "Map"), which is a much narrower false-positive surface.
_MIN_VARIANT_LEN = 4
_MIN_ALIAS_LEN = 3


# ── The scope: one RepoSpec per ~/projects repo this brain indexes ───────────

@dataclass(frozen=True)
class RepoSpec:
    """One repo in the portfolio — the thing that becomes one flat dimension.

    ``name`` is both the repo's directory name *and* its dimension name
    (``batch`` value). ``aliases`` are other names the repo is known by in the
    ecosystem's own prose (e.g. ctx-architecture's product name is "Map") —
    used both for retrieval tags and for edge verification.

    ``path``, if set, is this repo's absolute location, used instead of
    ``root / name`` — for repos that don't live under the shared
    ``~/projects`` root (e.g. termux paths under ``/data/data/com.termux/...``
    or shared storage under ``/sdcard/...``, see M5).
    """

    name: str
    aliases: tuple[str, ...] = ()
    vendored: bool = False
    group: str = "fleet"  # "fleet" | "verbalogix" | "self" | "termux"
    path: Path | None = None


#: The fleet: all current scope repos per PORTFOLIO-BRAIN-SPEC.md, `project_memory`
#: itself included (the brain indexing its own body of work).
PORTFOLIO_SCOPE: tuple[RepoSpec, ...] = (
    RepoSpec("universal_parser"),
    RepoSpec("ngfify"),
    RepoSpec("declared_core"),
    RepoSpec("frontmatter_rag"),
    RepoSpec("kg_toolkit"),
    RepoSpec("declared_rules"),
    RepoSpec("rag_evaluator"),
    RepoSpec("scaffold_kg_rag_agent"),
    RepoSpec("persona_guard"),
    RepoSpec("claude_workload_optimizer"),
    RepoSpec("declared_repo_factory"),
    RepoSpec("declarum-substrate", aliases=("declarum",)),
    RepoSpec("Aisle-demo"),
    RepoSpec("aisle-wedding-copilot"),
    RepoSpec("sag-declarum-atlas-framework"),
    RepoSpec("taste-skill-main", vendored=True),
    RepoSpec("ctx-architecture", aliases=("Map",), group="verbalogix"),
    RepoSpec("codebase-memorizer", group="verbalogix"),
    RepoSpec("vouch", group="verbalogix"),
    RepoSpec("verbalogix", group="verbalogix"),
    RepoSpec("project_memory", group="self"),
    # Reach expansion (M5): repos outside ~/projects, each pinned to its real
    # location (see MEMORY-SYSTEM-MVP-TO-V1.0-SPEC.md's M5) — the app-builder
    # pack's members.
    RepoSpec(
        "voice-graph-rag", group="termux",
        path=Path("/data/data/com.termux/files/home/voice-graph-rag"),
    ),
    RepoSpec(
        "gemini-KG-RAG-coding-expert", group="termux",
        path=Path("/data/data/com.termux/files/home/gemini-KG-RAG-coding-expert"),
    ),
    RepoSpec(
        "nlke-declarum-model-01-coding", group="termux",
        path=Path("/data/data/com.termux/files/home/projects/nlke-declarum-model-01-coding"),
    ),
    RepoSpec(
        "jewelry-current", group="termux",
        path=Path("/sdcard/Download/claude-projects/jewelry-current"),
    ),
    RepoSpec(
        "canvas-os", group="termux",
        path=Path("/data/data/com.termux/files/home/kg-factory/canvas-os"),
    ),
)


def _repo_path(name: str, root: Path, spec: RepoSpec | None) -> Path:
    """Absolute location of repo ``name``: ``spec.path`` if declared, else
    ``root / name`` (the shared-root default every pre-M5 repo still uses)."""
    if spec is not None and spec.path is not None:
        return spec.path
    return root / name


def _det_id(*parts: str) -> str:
    """A deterministic id from stable parts — reruns don't duplicate rows."""
    return uuid.uuid5(_ID_NAMESPACE, "\x1f".join(parts)).hex


def _iter_files(repo_path: Path, pattern: str) -> Iterator[Path]:
    if not repo_path.is_dir():
        return
    for p in repo_path.rglob(pattern):
        if p.is_file() and not any(part in _EXCLUDE_DIR_NAMES for part in p.parts):
            yield p


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


# ── A minimal, self-contained ai_card frontmatter reader ─────────────────────
# (Deliberately not imported from ngfify: path 1/2 below must work even when the
# optional `ngfify` dependency isn't installed — only path 3 needs it.)

_FM_KEY = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_FM_LIST_ITEM = re.compile(r"^\s+-\s?(.*)$")


def _split_frontmatter(text: str) -> str | None:
    """The raw frontmatter block if `text` opens with a `---` delimiter, else `None`."""
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "".join(lines[1:index])
    return None


def _parse_flat_yaml(raw_block: str) -> dict[str, Any]:
    """Parse the restricted ``key: scalar`` / ``key:`` + ``- item`` shape
    ai_cards use. Anything outside that shape is simply skipped."""
    result: dict[str, Any] = {}
    current_list: list[str] | None = None
    for raw_line in raw_block.splitlines():
        if not raw_line.strip():
            continue
        list_match = _FM_LIST_ITEM.match(raw_line)
        if list_match and current_list is not None:
            current_list.append(_unquote(list_match.group(1).strip()))
            continue
        key_match = _FM_KEY.match(raw_line)
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip()
        if value == "":
            current_list = []
            result[key] = current_list
        else:
            current_list = None
            result[key] = _unquote(value)
    return result


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def find_declared_cards(repo_path: Path) -> list[Path]:
    """Every ``*.ngf.md`` under ``repo_path`` whose frontmatter declares a
    ``public_interfaces`` key — the ai_card signal (path 1, the finest atoms)."""
    cards: list[Path] = []
    for p in sorted(_iter_files(repo_path, "*.ngf.md")):
        text = _read_text(p)
        if text is None:
            continue
        raw = _split_frontmatter(text)
        if raw is None:
            continue
        fm = _parse_flat_yaml(raw)
        if isinstance(fm.get("public_interfaces"), list) and fm["public_interfaces"]:
            cards.append(p)
    return cards


def _card_frontmatter(card_path: Path) -> dict[str, Any]:
    text = _read_text(card_path) or ""
    raw = _split_frontmatter(text) or ""
    return _parse_flat_yaml(raw)


# ── Path 2: a declared "Public API" section in the repo's own docs ──────────

_PUBLIC_API_HEADING = re.compile(r"^#{1,6}[ \t]*Public API.*$", re.IGNORECASE | re.MULTILINE)
_ANY_HEADING = re.compile(r"^#{1,6}[ \t]", re.MULTILINE)
_BACKTICK_IDENT = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")
_FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_BARE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _section_symbols(section: str) -> list[str]:
    """Symbol names in a "Public API" section: single-backtick-quoted idents
    (``the prose-list style``), plus, if present, every comma/whitespace
    -separated bare identifier inside a fenced code block (the plain-list
    style some CODEBASE-REPORT.md's use instead of individual backticks)."""
    seen: set[str] = set()
    names: list[str] = []

    def add(ident: str) -> None:
        if ident not in seen:
            seen.add(ident)
            names.append(ident)

    for ident in _BACKTICK_IDENT.findall(section):
        add(ident)
    for block in _FENCED_BLOCK.findall(section):
        for token in re.split(r"[,\s]+", block.strip()):
            if token and _BARE_IDENT.match(token):
                add(token)
    return names


def find_public_api_section(repo_path: Path) -> tuple[list[str], str] | None:
    """The declared symbols under the first "## Public API..." heading in the
    repo's own README / SPEC-v0.1.md / CODEBASE-REPORT.md, in that order."""
    for name in ("README.md", "SPEC-v0.1.md", "CODEBASE-REPORT.md"):
        doc = repo_path / name
        text = _read_text(doc) if doc.is_file() else None
        if not text:
            continue
        heading = _PUBLIC_API_HEADING.search(text)
        if not heading:
            continue
        nxt = _ANY_HEADING.search(text, heading.end())
        section = text[heading.end(): nxt.start() if nxt else len(text)]
        names = _section_symbols(section)
        if names:
            return names, name
    return None


# ── Path 3: ngfify auto-declare fallback (optional dependency) ───────────────

def _ngfify_fallback(repo_path: Path) -> tuple[list[str], str] | None:
    """`ngfify`-derive ``public_interfaces`` from the repo's best available doc.
    Returns ``None`` if ``ngfify`` isn't installed or no candidate doc exists."""
    try:
        from ngfify import TODO_SENTINEL, ngfify_file
    except ImportError:
        return None
    for name in FALLBACK_DOC_CANDIDATES:
        doc = repo_path / name
        if not doc.is_file():
            continue
        result = ngfify_file(doc, write=False, display_path=str(doc))
        items = [i for i in result.card.public_interfaces if i and i != TODO_SENTINEL]
        if items:
            return items, name
    return None


#: Matches only an *innermost*, non-nested `[text](url)` / `![alt](url)` —
#: excluding `[`/`]` from the "text" class forces a link-wrapped badge
#: (`[![CI](img)](url)`) to be cleared from the inside out, one iteration at a
#: time (see `_visible_text`), instead of leaving a hollow `](url)` behind.
_MD_LINK_IMG = re.compile(r"!?\[[^\[\]]*\]\([^()]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_README_POINTER = re.compile(r"\[[^\]]*\]\([^)]*readme[^)]*\)", re.IGNORECASE)


def _visible_text(line: str) -> str:
    """A markdown line with badges/links and raw HTML tags stripped.

    Applied to a fixed point: a link-wrapped badge (``[![CI](img)](url)``) is
    two nested constructs, so one pass leaves a hollow ``[](url)`` behind —
    repeat until nothing more is removed.
    """
    s = line
    while True:
        stripped = _MD_LINK_IMG.sub("", s)
        if stripped == s:
            break
        s = stripped
    return _HTML_TAG.sub("", s).strip()


def _is_decorative_line(line: str) -> bool:
    """Badge rows (``[![CI](...)]``), bare image/HTML banners, and
    "see the translated README" pointers carry no summary content — skip them
    when hunting for a repo's real tagline."""
    stripped = line.strip()
    if not stripped:
        return True
    if _README_POINTER.search(stripped):
        return True
    return not _visible_text(stripped)


def _first_paragraph_after_h1(text: str) -> str | None:
    """A tiny, self-contained "repo tagline" extractor for the milestone episode.

    Skips badge rows / translation pointers right after the H1 (common in this
    ecosystem's READMEs) rather than mistaking them for the summary."""
    lines = text.splitlines()
    h1 = next((i for i, ln in enumerate(lines) if re.match(r"^#[ \t]+\S", ln)), None)
    if h1 is None:
        return None
    cursor = h1 + 1
    while cursor < len(lines) and _is_decorative_line(lines[cursor]):
        cursor += 1
    para: list[str] = []
    while (
        cursor < len(lines) and lines[cursor].strip()
        and not lines[cursor].lstrip().startswith("#")
        and not _is_decorative_line(lines[cursor])
    ):
        para.append(_visible_text(lines[cursor]))
        cursor += 1
    joined = " ".join(p for p in para if p).strip()
    return joined or None


def repo_summary(repo_path: Path) -> str | None:
    """The repo's own one-line self-description (README's first paragraph)."""
    text = _read_text(repo_path / "README.md")
    return _first_paragraph_after_h1(text) if text else None


def mentions_verbalogix(repo_path: Path) -> bool:
    """Does this repo's own README call itself a Verbalogix product?"""
    text = _read_text(repo_path / "README.md") or ""
    return re.search(r"\bverbalogix\b", text, re.IGNORECASE) is not None


# ── Atoms ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Atom:
    """One ingestible unit: a repo's declared interface item."""

    repo: str
    content: str
    method: str  # "declared_card" | "public_api_doc" | "ngfify_auto"
    source_file: str
    tags: tuple[str, ...] = field(default_factory=tuple)


def extract_atoms(repo: RepoSpec, root: Path) -> tuple[list[Atom], list[str]]:
    """The repo's declared-interface atoms, finest source first. Returns
    ``(atoms, warnings)`` — a warning means every path (1, 2, 3) came up empty.

    Note: an ``Atom.content`` string is injected verbatim into *other* repos'
    sessions (via `artifact.build_artifact`), so it deliberately avoids this
    ecosystem's own jargon ("declared", "substrate", …) — that vocabulary
    reads as unfamiliar/suspicious insider-speak outside this family of repos
    (caught dogfooding against `vouch`, whose own brand rules ban exactly
    those words). ``method=`` values are internal categorization, never
    rendered into an artifact, so they're unaffected.
    """
    repo_path = _repo_path(repo.name, root, repo)
    base_tags = (repo.name, *repo.aliases, "interface", *(("vendored",) if repo.vendored else ()))

    cards = find_declared_cards(repo_path)
    if cards:
        atoms: list[Atom] = []
        for card_path in cards:
            fm = _card_frontmatter(card_path)
            card_id = fm.get("id", card_path.stem)
            rel = str(card_path.relative_to(repo_path))
            for item in fm.get("public_interfaces", []):
                if not item or item.startswith("<derive:"):
                    continue
                atoms.append(Atom(
                    repo=repo.name,
                    content=f"{repo.name}: {item} — public interface ({card_id}, {rel}).",
                    method="declared_card", source_file=rel,
                    tags=(*base_tags, card_id),
                ))
        return atoms, []

    api = find_public_api_section(repo_path)
    if api:
        names, doc_used = api
        atoms = [
            Atom(
                repo=repo.name,
                content=f"{repo.name}: `{name}` — public API symbol (from {doc_used}).",
                method="public_api_doc", source_file=doc_used, tags=base_tags,
            )
            for name in names
        ]
        return atoms, []

    fallback = _ngfify_fallback(repo_path)
    if fallback:
        items, doc_used = fallback
        atoms = [
            Atom(
                repo=repo.name,
                content=f"{repo.name}: {item} — auto-detected section (ngfify over {doc_used}).",
                method="ngfify_auto", source_file=doc_used, tags=(*base_tags, "ngfify-auto"),
            )
            for item in items
        ]
        return atoms, []

    return [], [f"{repo.name}: no declared card, no Public API section, and no ngfify "
                f"fallback available (install the `portfolio` extra, or the repo has "
                f"no README/SPEC-v0.1.md/CODEBASE-REPORT.md) — 0 interface atoms"]


# ── Edges: the declared manifest, verified against the repos' own docs ───────

@dataclass(frozen=True)
class RawEdge:
    """One ``source -> targets`` line as it appears in ``portfolio-edges.yaml``,
    before per-target verification."""

    category: str  # "composes" | "public_twin_of" | "built_by"
    source: str
    targets: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class EdgeDecision:
    """The verification outcome for one ``(source, target)`` pair."""

    category: str
    source: str
    target: str
    kept: bool
    reason: str


_MANIFEST_CATEGORY_KEYS: dict[str, str] = {
    "composes_depends_on": "composes",
    "public_twin_of": "public_twin_of",
    "built_by": "built_by",
}


def load_edge_manifest(path: Path) -> list[RawEdge]:
    """Load ``portfolio-edges.yaml`` (the spec's manifest, materialized)."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only if pyyaml absent
        raise RuntimeError(
            "reading portfolio-edges.yaml needs PyYAML — install the `portfolio` "
            "extra: pip install 'project-memory[portfolio]'"
        ) from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    edges: list[RawEdge] = []
    for yaml_key, category in _MANIFEST_CATEGORY_KEYS.items():
        for entry in data.get(yaml_key) or []:
            edges.append(RawEdge(
                category=category,
                source=entry["source"],
                targets=tuple(entry["targets"]),
                note=entry.get("note", ""),
            ))
    return edges


def _name_variant(name: str) -> tuple[str, ...]:
    """The repo's own full name — no fuzzy derivation. A hyphen/underscore-split
    "head" (``declarum-substrate`` -> ``declarum``) was tried and reverted: a
    common word inside a compound repo name (e.g. ``declared_repo_factory`` ->
    ``declared``) false-positives on nearly every doc in this ecosystem, since
    "declared" is the family's own vocabulary. Use `RepoSpec.aliases` instead —
    curated, precise nicknames (``ctx-architecture`` -> ``"Map"``,
    ``declarum-substrate`` -> ``"declarum"``) checked case-sensitively below."""
    return (name,) if len(name) >= _MIN_VARIANT_LEN else ()


def _own_docs_text(repo_path: Path) -> str:
    """Concatenate a repo's own top-level declared docs + its own ``arch/*.ngf.md``
    architecture cards — the corpus an edge must be asserted in to count."""
    chunks = [
        _read_text(repo_path / name) or ""
        for name in _EDGE_DOC_CANDIDATES
    ]
    chunks.extend(_read_text(p) or "" for p in _iter_files(repo_path, "arch/*.ngf.md"))
    return "\n".join(chunks)


def verify_edge(
    root: Path, source: str, target: str, scope_by_name: dict[str, RepoSpec],
) -> tuple[bool, str]:
    """Is this edge asserted by *either* repo's own docs?

    The full repo name is matched case-insensitively (distinctive compound
    names, low collision risk). A declared `RepoSpec.alias` is matched
    case-sensitively (a curated nickname like "Map" is also an ordinary English
    word lowercased, so only its capitalized, proper-noun form counts). Neither
    is used below `_MIN_VARIANT_LEN` (full name) / `_MIN_ALIAS_LEN` (alias)
    characters.
    """
    target_spec, source_spec = scope_by_name.get(target), scope_by_name.get(source)
    source_text = _own_docs_text(_repo_path(source, root, source_spec))
    target_text = _own_docs_text(_repo_path(target, root, target_spec))
    target_aliases = target_spec.aliases if target_spec else ()
    source_aliases = source_spec.aliases if source_spec else ()

    for name in _name_variant(target):
        if re.search(rf"\b{re.escape(name)}\b", source_text, re.IGNORECASE):
            return True, f"{source}'s own docs name '{name}' (== {target})"
    for alias in target_aliases:
        if len(alias) >= _MIN_ALIAS_LEN and re.search(rf"\b{re.escape(alias)}\b", source_text):
            return True, f"{source}'s own docs name the alias '{alias}' (== {target})"
    for name in _name_variant(source):
        if re.search(rf"\b{re.escape(name)}\b", target_text, re.IGNORECASE):
            return True, f"{target}'s own docs name '{name}' (== {source})"
    for alias in source_aliases:
        if len(alias) >= _MIN_ALIAS_LEN and re.search(rf"\b{re.escape(alias)}\b", target_text):
            return True, f"{target}'s own docs name the alias '{alias}' (== {source})"
    return False, f"neither {source}'s nor {target}'s own docs name the other"


def resolve_edges(
    root: Path, raw_edges: Iterable[RawEdge], scope: Iterable[RepoSpec],
) -> list[EdgeDecision]:
    """Expand each `RawEdge`'s target list into per-pair `EdgeDecision`s."""
    scope_by_name = {r.name: r for r in scope}
    decisions: list[EdgeDecision] = []
    for edge in raw_edges:
        for target in edge.targets:
            kept, reason = verify_edge(root, edge.source, target, scope_by_name)
            decisions.append(EdgeDecision(edge.category, edge.source, target, kept, reason))
    return decisions


_EDGE_PHRASING: dict[str, str] = {
    "composes": "{source} composes / depends on {target}{alias}",
    "public_twin_of": "{source} is the public, open-core twin of {target}{alias}",
    "built_by": "{source} built {target}{alias}",
}


def _edge_claim(decision: EdgeDecision, scope_by_name: dict[str, RepoSpec]) -> str:
    target_spec = scope_by_name.get(decision.target)
    alias = f" (aka {', '.join(target_spec.aliases)})" if target_spec and target_spec.aliases else ""
    template = _EDGE_PHRASING[decision.category]
    return template.format(source=decision.source, target=decision.target, alias=alias) + "."


# ── The orchestrator ──────────────────────────────────────────────────────────

@dataclass
class IndexReport:
    """What `index_portfolio` did — the honest accounting a fresh run produces."""

    repos_indexed: list[str] = field(default_factory=list)
    atom_count: int = 0
    milestone_count: int = 0
    atom_warnings: list[str] = field(default_factory=list)
    edges_kept: list[EdgeDecision] = field(default_factory=list)
    edges_dropped: list[EdgeDecision] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos_indexed": self.repos_indexed,
            "atom_count": self.atom_count,
            "milestone_count": self.milestone_count,
            "atom_warnings": self.atom_warnings,
            "edges_kept": [vars(d) for d in self.edges_kept],
            "edges_dropped": [vars(d) for d in self.edges_dropped],
        }

    def summary(self) -> str:
        lines = [
            f"Portfolio Brain indexed {len(self.repos_indexed)} repos: "
            f"{self.atom_count} interface atoms + {self.milestone_count} repo-summary milestones.",
            f"Edges: {len(self.edges_kept)} kept (verified), {len(self.edges_dropped)} dropped (unverified).",
        ]
        for w in self.atom_warnings:
            lines.append(f"  ! {w}")
        for d in self.edges_dropped:
            lines.append(f"  dropped [{d.category}] {d.source} -> {d.target}: {d.reason}")
        return "\n".join(lines)


def index_portfolio(
    mem: ProjectMemory,
    *,
    root: Path = DEFAULT_PROJECTS_ROOT,
    edges_path: Path | None = None,
    scope: Iterable[RepoSpec] = PORTFOLIO_SCOPE,
) -> IndexReport:
    """Index every repo in ``scope`` into ``mem`` and load the verified edge set.

    ``mem`` must already be open on a `PORTFOLIO_SCHEMA`-compatible store (it
    needs the ``"interface"`` episode kind). Safe to call once per fresh store —
    see ``scripts/index_portfolio.py`` for the idempotent CLI wrapper.
    """
    scope = tuple(scope)
    report = IndexReport()

    for repo in scope:
        repo_path = _repo_path(repo.name, root, repo)
        if not repo_path.is_dir():
            report.atom_warnings.append(f"{repo.name}: not found under {root} — skipped")
            continue
        report.repos_indexed.append(repo.name)

        atoms, warnings = extract_atoms(repo, root)
        report.atom_warnings.extend(warnings)
        for atom in atoms:
            mem.remember(
                atom.content, kind="interface", batch=repo.name,
                tags=list(atom.tags),
                metadata={"source_file": atom.source_file, "method": atom.method},
                method=atom.method,
                id=_det_id("atom", repo.name, atom.source_file, atom.content),
            )
        report.atom_count += len(atoms)

        summary = repo_summary(repo_path)
        tags = [repo.name, *repo.aliases, "repo-summary", repo.group]
        if repo.vendored:
            tags.append("vendored")
        if repo.group == "verbalogix" and mentions_verbalogix(repo_path):
            tags.append("Verbalogix")
        content = f"{repo.name}: {summary}" if summary else f"{repo.name}: (no README summary found)."
        mem.remember(
            content, kind="milestone", batch=repo.name, tags=tags,
            metadata={"source_file": "README.md"}, method="repo_summary",
            id=_det_id("milestone", repo.name, content),
        )
        report.milestone_count += 1

    if edges_path is not None and edges_path.is_file():
        raw_edges = load_edge_manifest(edges_path)
        decisions = resolve_edges(root, raw_edges, scope)
        scope_by_name = {r.name: r for r in scope}
        for decision in decisions:
            if decision.kept:
                report.edges_kept.append(decision)
                claim = _edge_claim(decision, scope_by_name)
                mem.record_fact(
                    claim, reason=decision.reason,
                    tags=[decision.source, decision.target, "edge", decision.category],
                    method="portfolio_edge",
                    id=_det_id("edge", decision.category, decision.source, decision.target),
                )
            else:
                report.edges_dropped.append(decision)

    return report
