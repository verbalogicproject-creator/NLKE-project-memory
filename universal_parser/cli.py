"""The `universal-parser` command-line interface.

    universal-parser --input file.json [--output result.json] [--pretty]
    universal-parser --batch "*.txt" --output results/
    universal-parser --detect-only file.xyz
    universal-parser --format-info json
    universal-parser --config settings.toml --input file.yaml
    universal-parser --demo

Confidence handling: by default, a result whose overall confidence falls
below the configured floor is refused (its content withheld, `refused: true`
in the JSON output) rather than emitted as if verified. Pass
`--allow-low-confidence` to see the content anyway.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from glob import glob
from pathlib import Path

from . import __version__
from .config import ParserConfig, load_config
from .core import UniversalParser
from .demo import build_demo


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI's `argparse.ArgumentParser`."""
    parser = argparse.ArgumentParser(
        prog="universal-parser",
        description="Parse 15+ file formats into one confidence-scored, schema-validated result.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", help="Input file path")
    parser.add_argument("--batch", help='Batch mode: glob pattern (e.g., "*.txt")')
    parser.add_argument("--output", help="Output file or directory")
    parser.add_argument("--detect-only", help="File path to detect format for", metavar="FILE")
    parser.add_argument("--format-info", help="Show the declared schema for a format")
    parser.add_argument("--config", help="Path to a ParserConfig TOML file", metavar="PATH")
    parser.add_argument(
        "--allow-low-confidence",
        action="store_true",
        help="Emit content even when confidence is below the configured minimum",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Parse the packaged demo corpus and print a summary (zero setup required)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _unique_output_name(source: Path, used_names: set[str]) -> str:
    """Build a collision-free ``*_parsed.json`` name for one batch result.

    Two inputs that share a stem (``report.json`` and ``report.csv``) would
    both map to ``report_parsed.json`` and silently overwrite each other,
    losing a result. The source extension is folded into the name, and a
    counter disambiguates any remaining collision (e.g. same-named files from
    different directories). The name still ends in ``_parsed.json``.
    """
    suffix = source.suffix.lstrip(".")
    stem = f"{source.stem}_{suffix}" if suffix else source.stem
    candidate = f"{stem}_parsed.json"
    counter = 1
    while candidate in used_names:
        candidate = f"{stem}_parsed_{counter}.json"
        counter += 1
    used_names.add(candidate)
    return candidate


def _run_demo() -> int:
    """Parse the packaged demo corpus and print a one-line summary per file."""
    results = build_demo()
    for result in results:
        name = Path(result.metadata["file_path"]).name
        print(
            f"  {name:24s} format={result.format:12s} "
            f"confidence={result.confidence:.2f} ({result.confidence_level.value}) "
            f"refused={result.refused}"
        )
    print(f"parsed {len(results)} demo files")
    return 0


def main() -> None:
    """CLI entry point: parse arguments and dispatch to the requested mode."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    arg_parser = _build_arg_parser()
    args = arg_parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.demo:
        sys.exit(_run_demo())

    config = load_config(args.config) if args.config else ParserConfig()
    universal_parser = UniversalParser(config)

    if args.format_info:
        schema = universal_parser.get_schema(args.format_info)
        print(json.dumps({"format": args.format_info, "schema": schema}, indent=2))
        return

    if args.detect_only:
        format_type = universal_parser.detect_format(args.detect_only)
        print(f"Detected format: {format_type}")
        return

    if args.batch:
        file_paths = glob(args.batch)
        if not file_paths:
            print(f"No files match pattern: {args.batch}", file=sys.stderr)
            sys.exit(1)

        results = universal_parser.parse_batch(file_paths, allow_low_confidence=args.allow_low_confidence)

        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            used_names: set[str] = set()
            for result in results:
                source = Path(result.metadata["file_path"])
                output_file = output_dir / _unique_output_name(source, used_names)
                with open(output_file, "w") as f:
                    json.dump(result.to_dict(), f, indent=2 if args.pretty else None)
            print(f"Parsed {len(results)} files to {args.output}")
        else:
            for result in results:
                print(json.dumps(result.to_dict(), indent=2 if args.pretty else None))
        return

    if not args.input:
        arg_parser.print_help()
        sys.exit(1)

    result = universal_parser.parse(args.input, allow_low_confidence=args.allow_low_confidence)
    output_dict = result.to_dict()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output_dict, f, indent=2 if args.pretty else None)
        print(f"Parsed to {args.output}")
    else:
        print(json.dumps(output_dict, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
