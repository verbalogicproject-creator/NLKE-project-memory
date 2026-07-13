"""project-memory — a command-line front door to a declared project memory.

    project-memory demo                      # explore the packaged demo memory
    project-memory remember "we chose X" --kind decision --auto-fact --reason "..."
    project-memory record "X is the store of record" --reason "..."
    project-memory recall "database choice"
    project-memory ask "why not Postgres?"
    project-memory synthesize "A ..." "B ..."   # MUD-checked merge
    project-memory recent --limit 5
    project-memory asks | kinds | dims
    project-memory brain load declared_core     # a project's context artifact
    project-memory brain load --current         # detect the project from cwd
    project-memory brain menu                   # interactive: list projects + packs, pick one

Every subcommand supports ``--json`` for scripting. Writes go to ``--db`` (default
``project-memory.db`` in the cwd, or the ``PMEM_DB`` env var); ``demo`` uses the
packaged in-memory demo. ``--preset {generic,agent,research}`` picks the episode
taxonomy; ``--dense-url`` enables the optional semantic booster.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .artifact import build_artifact, known_projects
from .demo import build_demo
from .dense import http_embedder
from .dimensions import MEMORY_DIMENSIONS
from .export.files import ALL_FILENAMES, PROVIDER_FILES, render_block, write_all_provider_files, write_provider_file
from .pack import find_pack, list_packs
from .portfolio import (
    DEFAULT_PROJECTS_ROOT,
    PORTFOLIO_SCHEMA,
    PORTFOLIO_SCOPE,
    _repo_path,
    index_portfolio,
)
from .presets import PRESETS
from .provenance import journey as build_journey
from .provenance import record_use, unused_loads
from .query import ProjectMemory
from .session_memory import default_claude_memory_dir, ingest_memory_dir


def _open(args: argparse.Namespace) -> ProjectMemory:
    schema = PRESETS.get(getattr(args, "preset", "generic"), PRESETS["generic"])
    embedder = None
    if getattr(args, "dense_url", None):
        embedder = http_embedder(args.dense_url)
    db = getattr(args, "db", None) or os.environ.get("PMEM_DB", "project-memory.db")
    return ProjectMemory.open(db, schema, embedder=embedder)


def _default_brain_db() -> str:
    """The one portfolio brain db, resolved relative to this package (so `brain
    load` works from any cwd) — overridable via ``PMEM_BRAIN_DB`` or ``--db``."""
    return os.environ.get("PMEM_BRAIN_DB") or str(
        Path(__file__).resolve().parent.parent / "portfolio.db"
    )


def _open_brain(args: argparse.Namespace) -> ProjectMemory:
    db = getattr(args, "db", None) or _default_brain_db()
    return ProjectMemory.open(db, PORTFOLIO_SCHEMA)


def _default_edges_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "portfolio-edges.yaml")


def _emit(obj: Any, as_json: bool, pretty=None) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    elif pretty is not None:
        pretty(obj)
    else:
        print(obj)


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_demo(args: argparse.Namespace) -> int:
    mem = build_demo()
    counts = mem.count()
    recall = mem.recall("offline search", limit=3)
    ask = mem.ask("why did we store timestamps in UTC?", name="why_not")
    synth = mem.synthesize(
        "From a security perspective, storing access tokens in plaintext is an unacceptable risk.",
        "From a business perspective, the legacy plaintext token store was cheap and worked fine.",
    )
    if args.json:
        _emit({"counts": counts, "recall": recall, "ask": ask.to_dict(),
               "synthesize": synth.to_dict()}, True)
        return 0
    print(f"project-memory demo — {counts['episodes']} episodes, {counts['facts']} facts\n")
    print("recall('offline search'):")
    for h in recall:
        print(f"  [{h['table']:>8}] {(h.get('content') or h.get('claim'))[:74]}")
    print(f"\nask('why did we store timestamps in UTC?', why_not):")
    print(f"  → {ask.answer[:110]}")
    print(f"\nsynthesize(security-view, business-view):")
    print(f"  verdict: {synth.verdict.upper()} — {synth.mud_reason[:76]}")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    mem = _open(args)
    res = mem.remember(
        args.content, kind=args.kind, tags=args.tag or None, batch=args.batch,
        auto_fact=args.auto_fact, reason=args.reason,
    )
    _emit(res, args.json, lambda r: print(f"episode {r['id']} [{r['kind']}]"
                                          + (f" + fact {r['fact_id']}" if r["fact_id"] else "")))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    mem = _open(args)
    res = mem.record_fact(args.claim, reason=args.reason, tags=args.tag or None,
                          supersedes=args.supersedes)
    _emit(res, args.json, lambda r: print(f"fact {r['id']}"
                                          + (f" (supersedes {r['supersedes']})" if r["supersedes"] else "")))
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    mem = _open(args)
    hits = mem.recall(args.query, limit=args.limit, table=args.table)
    if args.json:
        _emit(hits, True)
        return 0
    if not hits:
        print(f"no memory matches '{args.query}'")
        return 0
    for h in hits:
        print(f"[{h['table']:>8}] {(h.get('content') or h.get('claim') or '')[:88]}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    mem = _open(args)
    res = mem.ask(args.question, name=args.name, limit=args.limit)
    if args.json:
        _emit(res.to_dict(), True)
        return 0
    print(f"[{res.ask}] {res.answer}")
    print(f"  confidence: {res.confidence:.2f}")
    for e in res.evidence[:4]:
        print(f"  · [{e['table']}] {(e['preview'] or '')[:76]}")
    for c in res.caveats:
        print(f"  ⚠ {c}")
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    mem = _open(args)
    res = mem.synthesize(args.fact_a, args.fact_b, persist=args.persist)
    if args.json:
        _emit(res.to_dict(), True)
        return 0
    print(f"verdict: {res.verdict.upper()}   confidence: {res.confidence:.2f}")
    print(f"reason:  {res.mud_reason}")
    print("compatibilities: " + ", ".join(f"{k}={v:.2f}" for k, v in res.compatibilities.items()))
    if res.synthesized:
        print(f"merged:  {res.synthesized}")
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    mem = _open(args)
    eps = mem.recent(limit=args.limit, kind=args.kind)
    if args.json:
        _emit(eps, True)
        return 0
    for e in eps:
        print(f"[{e['kind']:>10}] {e['content'][:80]}  ({e['created_at'][:10]})")
    return 0


def cmd_asks(args: argparse.Namespace) -> int:
    mem = ProjectMemory.open()
    _emit(mem.asks(), args.json, lambda names: print("\n".join(names)))
    return 0


def cmd_kinds(args: argparse.Namespace) -> int:
    schema = PRESETS.get(args.preset, PRESETS["generic"])
    _emit(list(schema.kinds), args.json, lambda ks: print("\n".join(ks)))
    return 0


def cmd_dims(args: argparse.Namespace) -> int:
    dims = [{"name": d.name, "group": d.group, "description": d.description}
            for d in MEMORY_DIMENSIONS]
    _emit(dims, args.json,
          lambda ds: print("\n".join(f"{d['name']:<22} [{d['group']}]  {d['description']}" for d in ds)))
    return 0


def _detect_current_project(known: set[str], start: Path | None = None) -> str | None:
    """``start``'s basename, or the nearest ancestor directory's basename, that's
    a known project — so a session opened in a subdirectory of an indexed repo
    (e.g. ``declared_core/src/``) still resolves, not just the repo root.
    ``start`` defaults to this process's cwd, but a caller invoking this from
    a hook (whose own working directory isn't guaranteed to match the
    session's) should pass the session's cwd explicitly."""
    start = start or Path.cwd()
    for candidate in (start, *start.parents):
        if candidate.name in known:
            return candidate.name
    return None


def cmd_brain_load(args: argparse.Namespace) -> int:
    if not args.current and not args.name:
        print("error: `brain load` needs a project name or --current", file=sys.stderr)
        return 1

    mem = _open_brain(args)
    known = known_projects(mem)
    kind = "project"

    if args.current:
        start = Path(args.cwd).resolve() if args.cwd else Path.cwd()
        name = _detect_current_project(known, start=start)
        if name is None:
            if args.json:
                _emit({"loaded": False, "cwd": start.name}, True)
            else:
                print(f"# no known project here\n_cwd '{start.name}' is not indexed in the portfolio brain._")
            return 0
    else:
        name = args.name
        if name not in known:
            # `<name>` is a project *or* a pack id (Unit 3) — a pack file is
            # the fallback resolution, not the default, since a project batch
            # name is by far the common case.
            if find_pack(name) is None:
                print(f"error: no known project or pack '{name}' in the portfolio brain", file=sys.stderr)
                return 1
            kind = "pack"

    artifact = build_artifact(name, mem, kind=kind, hops=args.hops)
    # Provenance via the episode log itself (kind="brain_load"), not a bespoke
    # log file — every load becomes a queryable episode (`recall`/`ask`/`recent`
    # already work over it), which is what a memory system that remembers its
    # own use looks like. `batch` is deliberately left unset: a pack id is not
    # an indexed project, and setting it would corrupt `known_projects()`.
    mem.remember(
        f"loaded {kind} '{name}'", kind="brain_load",
        session_id=getattr(args, "session", None),
        tags=[name, kind, args.trigger], metadata={"trigger": args.trigger},
        method="brain_load",
    )
    if args.json:
        _emit({"loaded": True, "scope": name, "kind": kind, "artifact": artifact}, True)
    else:
        print(artifact)
    return 0


def cmd_brain_reindex(args: argparse.Namespace) -> int:
    """Refresh one project's atoms/milestone against the existing brain db.

    Safe to re-run: `remember`/`record_fact` now use ``INSERT OR IGNORE``, so
    unchanged content is a no-op and a changed README summary gets a new
    (content-derived) milestone row rather than crashing on a stale id. Also
    re-verifies the *whole* edge manifest as a side effect (`index_portfolio`
    doesn't filter `portfolio-edges.yaml` by scope) — harmless, just not
    scoped to only this project's edges.
    """
    spec = next((r for r in PORTFOLIO_SCOPE if r.name == args.name), None)
    if spec is None:
        print(f"error: '{args.name}' is not in PORTFOLIO_SCOPE (see project_memory.portfolio)",
              file=sys.stderr)
        return 1

    root = Path(args.root).expanduser()
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return 1

    mem = _open_brain(args)
    edges_path = Path(args.edges) if args.edges else None
    report = index_portfolio(mem, root=root, edges_path=edges_path, scope=(spec,))
    mem.close()

    if args.json:
        _emit(report.to_dict(), True)
    else:
        print(report.summary())
    return 0


def cmd_brain_export(args: argparse.Namespace) -> int:
    """Write a project's context artifact into the on-disk file(s) the given
    provider(s) read at session start (M6's file-adapter leg, next to
    `mcp_portfolio.py`'s on-demand MCP pull).

    Idempotent: a rerun replaces only the marker-delimited block
    `export.files` owns, leaving any hand-written instructions elsewhere in
    the same file untouched (see `export/files.py::apply_block`). Packs are
    out of scope here — unlike a project, a pack has no single directory to
    write into.
    """
    mem = _open_brain(args)
    if args.name not in known_projects(mem):
        print(f"error: '{args.name}' is not a known project in the portfolio brain "
              "(packs aren't supported by `brain export`)", file=sys.stderr)
        return 1

    if args.into:
        target_dir = Path(args.into).expanduser()
    else:
        root = Path(args.root).expanduser()
        spec = next((r for r in PORTFOLIO_SCOPE if r.name == args.name), None)
        target_dir = _repo_path(args.name, root, spec)
    if not target_dir.is_dir():
        print(f"error: target directory {target_dir} does not exist", file=sys.stderr)
        return 1

    filenames = ALL_FILENAMES if args.provider == "all" else (PROVIDER_FILES[args.provider],)

    if args.dry_run:
        block = render_block(args.name, mem, hops=args.hops)
        files = [str(target_dir / f) for f in filenames]
        if args.json:
            _emit({"exported": False, "dry_run": True, "scope": args.name,
                   "provider": args.provider, "files": files, "block": block}, True)
        else:
            for f in files:
                print(f"--- would write {f} ---")
            print(block)
        return 0

    if args.provider == "all":
        paths = write_all_provider_files(args.name, mem, target_dir, hops=args.hops)
    else:
        paths = [write_provider_file(args.provider, args.name, mem, target_dir, hops=args.hops)]

    # Provenance via the episode log itself, matching `cmd_brain_load`'s own
    # pattern — every export becomes a queryable episode, not a bespoke log.
    mem.remember(
        f"exported '{args.name}' to {args.provider}", kind="brain_export",
        session_id=getattr(args, "session", None),
        tags=[args.name, args.provider], metadata={"provider": args.provider,
                                                     "paths": [str(p) for p in paths]},
        method="brain_export",
    )

    if args.json:
        _emit({"exported": True, "dry_run": False, "scope": args.name,
               "provider": args.provider, "files": [str(p) for p in paths]}, True)
    else:
        for p in paths:
            print(f"wrote {p}")
    return 0


def _menu_items(mem: ProjectMemory) -> list[dict[str, str]]:
    """Every known project + declared pack, projects first — the ordered,
    numbered listing `brain menu` presents. A pack's ``label`` is its
    human-facing ``name``; a project has none (its own name is enough)."""
    items = [{"name": n, "kind": "project", "label": ""} for n in sorted(known_projects(mem))]
    items += [{"name": p["id"], "kind": "pack", "label": p["name"]} for p in list_packs()]
    return items


def _print_menu_listing(items: list[dict[str, str]]) -> None:
    seen_pack_header = False
    for idx, item in enumerate(items, start=1):
        if item["kind"] == "pack" and not seen_pack_header:
            print("Packs:")
            seen_pack_header = True
        elif idx == 1:
            print("Projects:")
        label = f' — {item["label"]}' if item["label"] else ""
        print(f"  {idx}. {item['name']}{label}")


def _resolve_menu_choice(choice: str, items: list[dict[str, str]]) -> "tuple[str | None, str | None]":
    """A typed number (1-based, from the printed listing) or an exact name.
    Returns ``(name, kind)``, or ``(None, None)`` if `choice` matches neither."""
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(items):
            item = items[idx - 1]
            return item["name"], item["kind"]
        return None, None
    for item in items:
        if item["name"] == choice:
            return item["name"], item["kind"]
    return None, None


def cmd_brain_menu(args: argparse.Namespace) -> int:
    """List every known project + pack, then print the selected one's artifact.

    ``--select`` (a number from the listing, or an exact name) skips the
    interactive `input()` prompt entirely — the scriptable/testable path.
    Without it: `--json` alone dumps the raw item list (for a caller building
    its own picker UI); with neither, prints the listing and prompts.
    """
    mem = _open_brain(args)
    items = _menu_items(mem)
    if not items:
        print("error: no known projects or packs in the portfolio brain", file=sys.stderr)
        return 1

    choice = args.select
    if choice is None:
        if args.json:
            _emit(items, True)
            return 0
        _print_menu_listing(items)
        choice = input("\nSelect a number or name: ").strip()

    name, kind = _resolve_menu_choice(choice, items)
    if name is None:
        print(f"error: '{choice}' is not a valid selection", file=sys.stderr)
        return 1

    artifact = build_artifact(name, mem, kind=kind)
    mem.remember(
        f"loaded {kind} '{name}'", kind="brain_load",
        session_id=getattr(args, "session", None),
        tags=[name, kind, "menu"], metadata={"trigger": "menu"}, method="brain_load",
    )
    if args.json:
        _emit({"loaded": True, "scope": name, "kind": kind, "artifact": artifact}, True)
    else:
        print("\n" + artifact)
    return 0


def cmd_brain_remember(args: argparse.Namespace) -> int:
    """Append a project-scoped decision/insight episode (M2) — the accreted
    log `build_artifact`'s "Recent memory" section and `ask`/`recall` draw on.

    Defaults to crystallizing a fact (``auto_fact``): the whole point of
    telling the brain to remember something is that a *future* session sees
    it, and only facts (not raw episodes) surface in the artifact. Pass
    ``--no-auto-fact`` for a pure event log entry ("the build broke again")
    that isn't meant to stand as a durable, supersedable claim.
    """
    if not args.current and not args.project:
        print("error: `brain remember` needs --project <name> or --current", file=sys.stderr)
        return 1

    mem = _open_brain(args)
    known = known_projects(mem)

    if args.current:
        start = Path(args.cwd).resolve() if args.cwd else Path.cwd()
        name = _detect_current_project(known, start=start)
        if name is None:
            print(f"error: cwd '{start.name}' is not a known project in the portfolio brain", file=sys.stderr)
            return 1
    else:
        name = args.project
        if name not in known:
            print(f"error: no known project '{name}' in the portfolio brain", file=sys.stderr)
            return 1

    res = mem.remember(
        args.text, kind=args.kind, batch=name, tags=[name, "session-memory"],
        auto_fact=not args.no_auto_fact, reason=args.reason, supersedes=args.supersedes,
    )
    if args.json:
        _emit({"remembered": True, "project": name, **res}, True)
    else:
        fact_note = f" — crystallized as fact {res['fact_id']}" if res["fact_id"] else " (episode only)"
        print(f"remembered for {name}{fact_note}")
    return 0


def cmd_brain_ingest_memory(args: argparse.Namespace) -> int:
    """Ingest Claude Code's own auto-memory `*.md` files (M2) into the brain.

    ``--project`` (with or without ``--memory-dir``) tags every ingested
    episode to that project's `batch` — do this only when the directory is
    genuinely single-project-scoped. Without it, ingestion is unscoped: still
    fully `recall`/`ask`-able, just not tied to any one project's
    `build_artifact` (a real memory directory was found, building this, to
    span several unrelated projects at once — see `session_memory`'s module
    docstring).
    """
    if not args.memory_dir and not args.project and not args.current:
        print("error: `brain ingest-memory` needs --memory-dir, --project, or --current",
              file=sys.stderr)
        return 1

    mem = _open_brain(args)
    project = args.project

    if args.current and not project:
        known = known_projects(mem)
        start = Path.cwd()
        project = _detect_current_project(known, start=start)
        if project is None:
            print(f"error: cwd '{start.name}' is not a known project in the portfolio brain",
                  file=sys.stderr)
            return 1

    if args.memory_dir:
        memory_dir = Path(args.memory_dir)
    elif project:
        memory_dir = default_claude_memory_dir(Path(args.root).expanduser() / project)
    else:
        print("error: could not determine a memory directory — pass --memory-dir explicitly",
              file=sys.stderr)
        return 1

    types = tuple(t.strip() for t in args.types.split(",") if t.strip())
    count = ingest_memory_dir(mem, memory_dir, batch=project, types=types)

    if args.json:
        _emit({"ingested": count, "memory_dir": str(memory_dir), "project": project}, True)
    else:
        scope_note = f" (batch={project})" if project else " (unscoped)"
        print(f"ingested {count} memory file(s) from {memory_dir}{scope_note}")
    return 0


def cmd_brain_used(args: argparse.Namespace) -> int:
    """Mark a previously-loaded scope's context as *used* (M4). One append-only
    ``brain_use`` episode — the declared "used" marker `unused_loads`/`journey`
    fold against loads. Refuses a scope that was never loaded (a typo, or a
    claim to have used context that was never pulled), rather than silently
    recording an orphan marker."""
    mem = _open_brain(args)

    if args.current and not args.scope:
        known = known_projects(mem)
        start = Path(args.cwd).resolve() if args.cwd else Path.cwd()
        scope = _detect_current_project(known, start=start)
        if scope is None:
            print(f"error: cwd '{start.name}' is not a known project in the portfolio brain",
                  file=sys.stderr)
            return 1
    elif args.scope:
        scope = args.scope
    else:
        print("error: `brain used` needs a scope name or --current", file=sys.stderr)
        return 1

    loaded_scopes = {ev.scope for ev in build_journey(mem).events if ev.event == "load"}
    if scope not in loaded_scopes:
        print(f"error: no load of '{scope}' recorded — nothing to mark used "
              "(a `used` marker only makes sense for context that was loaded)", file=sys.stderr)
        return 1

    record_use(mem, scope, session=args.session, note=args.note)
    if args.json:
        _emit({"used": True, "scope": scope, "session": args.session}, True)
    else:
        session_note = f" in session {args.session}" if args.session else ""
        print(f"marked '{scope}' used{session_note}")
    return 0


def cmd_brain_journey(args: argparse.Namespace) -> int:
    """Reconstruct a session's journey as a story (M4): its ordered
    load/use/export events + which loads went unused. Without ``--session``,
    the all-sessions view (every event in the log)."""
    mem = _open_brain(args)
    report = build_journey(mem, session=args.session)
    if args.json:
        _emit(report.to_dict(), True)
    else:
        print(report.story())
    return 0


def cmd_brain_unused(args: argparse.Namespace) -> int:
    """Report loads that were never marked used (M4). ``--packs`` restricts to
    packs — the spec's "report packs loaded-but-never-used" directly.
    ``--session`` scopes both the loads and the use-matching to one session."""
    mem = _open_brain(args)
    scope_kind = "pack" if args.packs else None
    unused = unused_loads(mem, session=args.session, scope_kind=scope_kind)
    if args.json:
        _emit({"session": args.session, "packs_only": bool(args.packs),
               "unused": [ev.to_dict() for ev in unused]}, True)
    else:
        if not unused:
            what = "packs" if args.packs else "loads"
            where = f" in session {args.session}" if args.session else ""
            print(f"no unused {what}{where} — everything loaded was marked used")
            return 0
        print(f"Loaded but never used ({len(unused)}):")
        for ev in unused:
            scoped = f"{ev.scope_kind} '{ev.scope}'".strip()
            via = f"  (via {ev.trigger})" if ev.trigger else ""
            print(f"  · {scoped}{via}")
    return 0


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="project-memory", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"project-memory {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser, *, db=True) -> None:
        sp.add_argument("--json", action="store_true", help="emit JSON")
        if db:
            sp.add_argument("--db", default=None, help="SQLite path (default PMEM_DB or ./project-memory.db)")
            sp.add_argument("--preset", default="generic", choices=sorted(PRESETS), help="episode taxonomy")
            sp.add_argument("--dense-url", default=None, help="OpenAI-style /v1/embeddings URL (optional booster)")

    sp = sub.add_parser("demo", help="explore the packaged demo memory")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("remember", help="append an episode")
    sp.add_argument("content")
    sp.add_argument("--kind", default="general")
    sp.add_argument("--tag", action="append", default=[])
    sp.add_argument("--batch", default=None)
    sp.add_argument("--auto-fact", action="store_true", help="also crystallize a fact")
    sp.add_argument("--reason", default=None)
    common(sp)
    sp.set_defaults(func=cmd_remember)

    sp = sub.add_parser("record", help="write a durable fact")
    sp.add_argument("claim")
    sp.add_argument("--reason", default=None)
    sp.add_argument("--tag", action="append", default=[])
    sp.add_argument("--supersedes", default=None, help="fact id this replaces")
    common(sp)
    sp.set_defaults(func=cmd_record)

    sp = sub.add_parser("recall", help="search memory")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--table", default=None, choices=["episodes", "facts"])
    common(sp)
    sp.set_defaults(func=cmd_recall)

    sp = sub.add_parser("ask", help="answer a question (routed to an ask)")
    sp.add_argument("question")
    sp.add_argument("--name", default=None, help="force a specific ask (see `asks`)")
    sp.add_argument("--limit", type=int, default=8)
    common(sp)
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("synthesize", help="MUD-check a merge of two facts")
    sp.add_argument("fact_a")
    sp.add_argument("fact_b")
    sp.add_argument("--persist", action="store_true", help="write to the synthesis_facts audit table")
    common(sp)
    sp.set_defaults(func=cmd_synthesize)

    sp = sub.add_parser("recent", help="most recent episodes")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--kind", default=None)
    common(sp)
    sp.set_defaults(func=cmd_recent)

    sp = sub.add_parser("asks", help="list the available asks")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_asks)

    sp = sub.add_parser("kinds", help="list a preset's episode kinds")
    sp.add_argument("--preset", default="generic", choices=sorted(PRESETS))
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_kinds)

    sp = sub.add_parser("dims", help="list the memory dimension palette")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_dims)

    sp = sub.add_parser("brain", help="graph-memory context injection (portfolio brain)")
    brain_sub = sp.add_subparsers(dest="brain_cmd", required=True)

    lsp = brain_sub.add_parser("load", help="print a project's context artifact")
    lsp.add_argument("name", nargs="?", default=None, help="project name (batch); omit with --current")
    lsp.add_argument("--current", action="store_true", help="detect the project from the cwd's basename")
    lsp.add_argument("--cwd", default=None,
                      help="detect --current from this path instead of the process's own cwd "
                           "(a hook's own working directory isn't guaranteed to match the session's)")
    lsp.add_argument("--db", default=None,
                      help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    lsp.add_argument("--trigger", default="cli",
                      help="who triggered this load (e.g. startup/clear/manual) — recorded as provenance")
    lsp.add_argument("--session", default=None,
                      help="session id this load belongs to (M4) — lets `brain journey`/`unused` "
                           "group a session's loads; the SessionStart hook passes Claude Code's own")
    lsp.add_argument("--hops", type=int, default=1, choices=[1, 2],
                      help="1 = direct edges (default, what the SessionStart hook uses); "
                           "2 = rescored 1-2 hop graph-walk (M1), opt-in only")
    lsp.add_argument("--json", action="store_true")
    lsp.set_defaults(func=cmd_brain_load)

    rsp = brain_sub.add_parser("reindex", help="refresh one project's atoms/milestone in-place")
    rsp.add_argument("name", help="project name (must be in PORTFOLIO_SCOPE)")
    rsp.add_argument("--root", default=str(DEFAULT_PROJECTS_ROOT), help="the ~/projects root")
    rsp.add_argument("--edges", default=_default_edges_path(), help="path to portfolio-edges.yaml")
    rsp.add_argument("--db", default=None,
                      help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    rsp.add_argument("--json", action="store_true")
    rsp.set_defaults(func=cmd_brain_reindex)

    exsp = brain_sub.add_parser(
        "export", help="write a project's artifact into CLAUDE.md/AGENTS.md/GEMINI.md (M6)")
    exsp.add_argument("name", help="project name (must be a known project, not a pack)")
    exsp.add_argument("--provider", required=True,
                       choices=["claude", "codex", "gemini", "antigravity", "all"],
                       help="claude->CLAUDE.md, codex/antigravity->AGENTS.md (shared convention), "
                            "gemini->GEMINI.md, all->all three files")
    exsp.add_argument("--root", default=str(DEFAULT_PROJECTS_ROOT),
                       help="the ~/projects root, for resolving the project's own directory "
                            "(ignored if --into is given)")
    exsp.add_argument("--into", default=None,
                       help="write here instead of the project's own resolved directory")
    exsp.add_argument("--hops", type=int, default=1, choices=[1, 2],
                       help="1 = direct edges (default); 2 = rescored 1-2 hop graph-walk (M1)")
    exsp.add_argument("--dry-run", action="store_true",
                       help="print the block(s) that would be written, without touching disk")
    exsp.add_argument("--session", default=None,
                       help="session id this export belongs to (M4) — recorded as provenance")
    exsp.add_argument("--db", default=None,
                       help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    exsp.add_argument("--json", action="store_true")
    exsp.set_defaults(func=cmd_brain_export)

    usp = brain_sub.add_parser("used", help="mark a loaded scope's context as used (M4 provenance)")
    usp.add_argument("scope", nargs="?", default=None,
                      help="project/pack name that was loaded; omit with --current")
    usp.add_argument("--current", action="store_true", help="detect the project from the cwd's basename")
    usp.add_argument("--cwd", default=None,
                      help="detect --current from this path instead of the process's own cwd")
    usp.add_argument("--session", default=None,
                      help="session id this use belongs to — match the load's --session to fold them together")
    usp.add_argument("--note", default=None, help="optional note on how the context was used")
    usp.add_argument("--db", default=None,
                      help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    usp.add_argument("--json", action="store_true")
    usp.set_defaults(func=cmd_brain_used)

    jsp = brain_sub.add_parser("journey", help="reconstruct a session's load/use/export journey as a story (M4)")
    jsp.add_argument("--session", default=None,
                      help="the session to reconstruct; omit for the all-sessions view")
    jsp.add_argument("--db", default=None,
                      help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    jsp.add_argument("--json", action="store_true")
    jsp.set_defaults(func=cmd_brain_journey)

    unsp = brain_sub.add_parser("unused", help="report loads that were never marked used (M4)")
    unsp.add_argument("--packs", action="store_true",
                       help="restrict to packs — 'report packs loaded-but-never-used'")
    unsp.add_argument("--session", default=None,
                       help="scope both the loads and the use-matching to one session")
    unsp.add_argument("--db", default=None,
                       help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    unsp.add_argument("--json", action="store_true")
    unsp.set_defaults(func=cmd_brain_unused)

    msp = brain_sub.add_parser("menu", help="interactive picker: list projects + packs, then print one")
    msp.add_argument("--select", default=None,
                      help="skip the interactive prompt — a number from the listing, or an exact name")
    msp.add_argument("--session", default=None,
                      help="session id this load belongs to (M4) — recorded as provenance")
    msp.add_argument("--db", default=None,
                      help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    msp.add_argument("--json", action="store_true",
                      help="with --select: emit the artifact as JSON; without: emit the raw item list")
    msp.set_defaults(func=cmd_brain_menu)

    remsp = brain_sub.add_parser("remember", help="append a project-scoped decision/insight episode (M2)")
    remsp.add_argument("text", help="what to remember")
    remsp.add_argument("--project", default=None, help="project name (batch); omit with --current")
    remsp.add_argument("--current", action="store_true", help="detect the project from the cwd's basename")
    remsp.add_argument("--cwd", default=None,
                        help="detect --current from this path instead of the process's own cwd")
    remsp.add_argument("--kind", default="decision",
                        help="episode kind — decision/gotcha/insight/invariant/task/general (default decision)")
    remsp.add_argument("--reason", default=None, help="why — becomes the crystallized fact's reason")
    remsp.add_argument("--no-auto-fact", action="store_true",
                        help="log the episode only — don't crystallize a standing fact "
                             "(use for events, e.g. 'the build broke again', not decisions)")
    remsp.add_argument("--supersedes", default=None, help="fact id this decision replaces")
    remsp.add_argument("--db", default=None,
                        help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    remsp.add_argument("--json", action="store_true")
    remsp.set_defaults(func=cmd_brain_remember)

    imsp = brain_sub.add_parser("ingest-memory", help="ingest Claude Code's own memory/*.md files (M2)")
    imsp.add_argument("--memory-dir", default=None,
                       help="path to a memory directory (default: inferred from --project/--current)")
    imsp.add_argument("--project", default=None,
                       help="tag ingested episodes to this project (batch); also used to infer "
                            "--memory-dir if it's omitted")
    imsp.add_argument("--current", action="store_true",
                       help="infer both --memory-dir and --project from the cwd")
    imsp.add_argument("--root", default=str(DEFAULT_PROJECTS_ROOT),
                       help="the ~/projects root, for inferring --memory-dir from --project")
    imsp.add_argument("--types", default="project",
                       help="comma-separated memory types to ingest (default: project only — "
                            "user/feedback/reference are about Eyal, not the project)")
    imsp.add_argument("--db", default=None,
                       help="portfolio db path (default PMEM_BRAIN_DB or <repo>/portfolio.db)")
    imsp.add_argument("--json", action="store_true")
    imsp.set_defaults(func=cmd_brain_ingest_memory)

    return p


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, NotImplementedError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
