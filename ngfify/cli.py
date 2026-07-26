"""The `ngfify` command-line interface.

    ngfify path/to/file.py                  # writes path/to/file.py.ngf.md
    ngfify path/to/file.py --out card.md    # writes card.md instead
    ngfify path/to/file.py --stdout         # prints instead of writing
    ngfify --demo                           # ngf-ifies the bundled demo corpus
    ngfify --config ngfify.toml file.ts     # load an NgfifyConfig from TOML

    ngfify --tree src/                      # a card beside every file in src/
    ngfify --tree src/ --out-dir cards/     # all cards into one flat directory
    ngfify --tree docs/ --pattern '*.md'    # only markdown
    ngfify --tree docs/ --out-dir cards/ --name-prefix declared_core
    ngfify --tree src/ --dry-run            # derive everything, write nothing
"""

from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .config import NgfifyConfig, load_config
from .demo import run_demo
from .detection import UnsupportedFileTypeError
from .pipeline import ngfify_file
from .tree import ngfify_tree


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI's `argparse.ArgumentParser`."""
    parser = argparse.ArgumentParser(
        prog="ngfify",
        description="Convert a single source file into a declared <file>.ngf.md ai_card.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file", nargs="?", help="Source file to ngf-ify")
    parser.add_argument("--out", help="Output path (default: <file>.ngf.md)", metavar="PATH")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing a file")
    parser.add_argument("--config", help="Path to an ngfify.toml config file", metavar="PATH")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ngf-ify the packaged demo corpus and print a summary (zero setup required)",
    )
    parser.add_argument(
        "--demo-out",
        help="Output directory for --demo (default: ./ngfify-demo-output)",
        metavar="DIR",
    )
    tree = parser.add_argument_group("tree mode")
    tree.add_argument("--tree", help="Ngf-ify every supported file under DIR", metavar="DIR")
    tree.add_argument(
        "--out-dir",
        help="Write all cards into one directory with flattened, collision-safe names "
             "(default: a card beside each source file)",
        metavar="DIR",
    )
    tree.add_argument("--pattern", default="*", help="Narrow the walk, e.g. '*.md' (default: *)")
    tree.add_argument(
        "--name-prefix",
        help="Prefix flattened names and declared paths, so cards gathered from several "
             "repos into one directory stay distinguishable",
        metavar="NAME",
    )
    tree.add_argument(
        "--dry-run",
        action="store_true",
        help="Derive and render every card but write nothing — validates a tree before committing",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _run_demo(demo_out: str | None, config: NgfifyConfig) -> int:
    """Ngf-ify the packaged demo corpus and print one line per file."""
    results = run_demo(output_dir=demo_out, config=config)
    for result in results:
        print(f"  {result.source_path.name:12s} -> {result.output_path}")
    print(f"ngfify --demo: wrote {len(results)} .ngf.md files")
    return 0


def _run_tree(args: argparse.Namespace, config: NgfifyConfig) -> int:
    """Walk a directory, ngf-ify what it can, and report skips and failures explicitly.

    Exit code is 1 when any file *failed*, 0 otherwise. Skips are not failures:
    a mixed tree containing `.json` or `.toml` is the normal case, not an error.
    Both counts are always printed — a tree walk that reports only its successes
    claims coverage it did not earn.
    """
    try:
        result = ngfify_tree(
            args.tree,
            config=config,
            output_dir=args.out_dir,
            write=not args.dry_run,
            pattern=args.pattern,
            name_prefix=args.name_prefix,
        )
    except NotADirectoryError as exc:
        print(f"ngfify: {exc}", file=sys.stderr)
        return 1

    for item in result.results:
        target = item.output_path if item.output_path is not None else "(dry run)"
        print(f"  {item.source_path.name:32s} -> {target}")
    for skip in result.skipped:
        print(f"  SKIP {skip.path.name:27s} {skip.reason}", file=sys.stderr)
    for failure in result.failed:
        print(f"  FAIL {failure.path.name:27s} {failure.error}", file=sys.stderr)

    print(f"ngfify --tree {result.root}: {result.summary()}")
    return 1 if result.failed else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse arguments and dispatch. Returns the process exit code."""
    arg_parser = _build_arg_parser()
    args = arg_parser.parse_args(argv)
    config = load_config(args.config) if args.config else NgfifyConfig()

    if args.demo:
        return _run_demo(args.demo_out, config)

    if args.tree:
        return _run_tree(args, config)

    if not args.file:
        arg_parser.print_help()
        return 1

    try:
        result = ngfify_file(
            args.file,
            config=config,
            output_path=args.out,
            write=not args.stdout,
        )
    except FileNotFoundError as exc:
        print(f"ngfify: {exc}", file=sys.stderr)
        return 1
    except UnsupportedFileTypeError as exc:
        print(f"ngfify: {exc}", file=sys.stderr)
        return 1

    if args.stdout:
        print(result.rendered)
    else:
        print(f"ngfify: wrote {result.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
