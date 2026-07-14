"""The `ngfify` command-line interface.

    ngfify path/to/file.py                  # writes path/to/file.py.ngf.md
    ngfify path/to/file.py --out card.md    # writes card.md instead
    ngfify path/to/file.py --stdout         # prints instead of writing
    ngfify --demo                           # ngf-ifies the bundled demo corpus
    ngfify --config ngfify.toml file.ts     # load an NgfifyConfig from TOML
"""

from __future__ import annotations

import argparse
import sys

from ._version import __version__
from .config import NgfifyConfig, load_config
from .demo import run_demo
from .detection import UnsupportedFileTypeError
from .pipeline import ngfify_file


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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _run_demo(demo_out: str | None, config: NgfifyConfig) -> int:
    """Ngf-ify the packaged demo corpus and print one line per file."""
    results = run_demo(output_dir=demo_out, config=config)
    for result in results:
        print(f"  {result.source_path.name:12s} -> {result.output_path}")
    print(f"ngfify --demo: wrote {len(results)} .ngf.md files")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse arguments and dispatch. Returns the process exit code."""
    arg_parser = _build_arg_parser()
    args = arg_parser.parse_args(argv)
    config = load_config(args.config) if args.config else NgfifyConfig()

    if args.demo:
        return _run_demo(args.demo_out, config)

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
