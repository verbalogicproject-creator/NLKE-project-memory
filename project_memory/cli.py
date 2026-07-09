"""project-memory — a command-line front door to a declared project memory.

    project-memory demo                      # explore the packaged demo memory
    project-memory remember "we chose X" --kind decision --auto-fact --reason "..."
    project-memory record "X is the store of record" --reason "..."
    project-memory recall "database choice"
    project-memory ask "why not Postgres?"
    project-memory synthesize "A ..." "B ..."   # MUD-checked merge
    project-memory recent --limit 5
    project-memory asks | kinds | dims

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
from typing import Any

from . import __version__
from .demo import build_demo
from .dense import http_embedder
from .dimensions import MEMORY_DIMENSIONS
from .presets import PRESETS
from .query import ProjectMemory


def _open(args: argparse.Namespace) -> ProjectMemory:
    schema = PRESETS.get(getattr(args, "preset", "generic"), PRESETS["generic"])
    embedder = None
    if getattr(args, "dense_url", None):
        embedder = http_embedder(args.dense_url)
    db = getattr(args, "db", None) or os.environ.get("PMEM_DB", "project-memory.db")
    return ProjectMemory.open(db, schema, embedder=embedder)


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

    return p


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
