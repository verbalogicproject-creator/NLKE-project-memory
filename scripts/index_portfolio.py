#!/usr/bin/env python3
"""Build the Portfolio Brain — index every ``~/projects`` repo in
``project_memory.portfolio.PORTFOLIO_SCOPE`` into one `project_memory` store.

    python scripts/index_portfolio.py
    python scripts/index_portfolio.py --root /root/projects --db portfolio.db
    python scripts/index_portfolio.py --json

Needs the ``portfolio`` extra (``pip install -e '.[portfolio]'``) for
``portfolio-edges.yaml`` (PyYAML) and the ``ngfify`` auto-declare fallback.
By default the target ``--db`` file is deleted and rebuilt fresh each run —
episodes are append-only, so re-indexing into an existing store would
duplicate every atom; pass ``--no-fresh`` to append/skip-on-conflict instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running straight from a checkout without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project_memory import ProjectMemory  # noqa: E402
from project_memory.portfolio import (  # noqa: E402
    DEFAULT_PROJECTS_ROOT,
    PORTFOLIO_SCHEMA,
    PORTFOLIO_SCOPE,
    index_portfolio,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EDGES_PATH = REPO_ROOT / "portfolio-edges.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_PROJECTS_ROOT),
                         help=f"the ~/projects root to index (default {DEFAULT_PROJECTS_ROOT})")
    parser.add_argument("--db", default="portfolio.db", help="SQLite path to build (default portfolio.db)")
    parser.add_argument("--edges", default=str(DEFAULT_EDGES_PATH), help="path to portfolio-edges.yaml")
    parser.add_argument("--no-fresh", action="store_true",
                         help="append to an existing --db instead of deleting it first")
    parser.add_argument("--json", action="store_true", help="emit the IndexReport as JSON")
    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)

    root = Path(args.root).expanduser()
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return 1

    db_path = Path(args.db)
    if db_path.name != ":memory:" and not args.no_fresh and db_path.exists():
        db_path.unlink()

    mem = ProjectMemory.open(str(db_path), PORTFOLIO_SCHEMA)
    edges_path = Path(args.edges) if args.edges else None
    report = index_portfolio(mem, root=root, edges_path=edges_path, scope=PORTFOLIO_SCOPE)
    mem.close()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
