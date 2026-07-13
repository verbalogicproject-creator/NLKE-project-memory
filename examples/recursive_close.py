#!/usr/bin/env python3
"""recursive_close — the Portfolio Brain answering questions about itself.

The "recursive close": `project_memory`'s own substrate indexes the whole
`~/projects` ecosystem (`scripts/index_portfolio.py`) — including itself — and
then this script asks the REAL `project-memory` CLI questions about what it
just indexed, printing the actual output. Nothing here is staged; every line
of output below is what the CLI prints against the store this script just
built.

    python examples/recursive_close.py [--root ~/projects] [--db portfolio-demo.db]

Needs the ``portfolio`` extra installed (``pip install -e '.[portfolio]'``)
plus ``ngfify``/``universal_parser`` on PATH for the auto-declare fallback —
see PORTFOLIO-BRAIN-SPEC.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: (title, CLI subcommand args) — every one of these is a real `project-memory`
#: invocation; ``--table facts`` is used where the interesting answer is a
#: *declared edge* (a fact), not prose, so the result isn't diluted by the 258
#: interface atoms every repo also contributes.
QUERIES: tuple[tuple[str, list[str]], ...] = (
    ('what composes Map? (ctx-architecture\'s product name)',
     ["ask", "what composes Map?"]),
    ('show the Verbalogix line',
     ["recall", "Verbalogix", "--limit", "8"]),
    ("what is project_memory's public twin?",
     ["recall", "public twin", "--table", "facts", "--limit", "8"]),
    ("what did declared_repo_factory build?",
     ["recall", "declared_repo_factory built", "--table", "facts", "--limit", "8"]),
    ("retrieval cluster around declared_core",
     ["recall", "declared_core", "--limit", "10"]),
)


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return (result.stdout + result.stderr).rstrip()


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=None, help="~/projects root (default: project_memory.portfolio's)")
    parser.add_argument("--db", default="portfolio-demo.db")
    parser.add_argument("--rebuild", action="store_true", help="rebuild --db even if it already exists")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if args.rebuild or not db_path.exists():
        print(f"# building the portfolio store at {db_path} ...")
        build_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "index_portfolio.py"), "--db", str(db_path)]
        if args.root:
            build_cmd += ["--root", args.root]
        build = subprocess.run(build_cmd, cwd=REPO_ROOT)
        if build.returncode != 0:
            print("index_portfolio.py failed", file=sys.stderr)
            return build.returncode
        print()

    for title, sub_args in QUERIES:
        cmd = ["project-memory", *sub_args, "--db", str(db_path)]
        print(f"$ project-memory {' '.join(sub_args)} --db {db_path.name}   # {title}")
        print(_run(cmd))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
