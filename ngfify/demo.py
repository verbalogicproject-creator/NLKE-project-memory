"""A zero-setup demo corpus so `ngfify --demo` runs with nothing else installed.

`run_demo()` ngf-ifies every file in the packaged `demo_corpus/` directory
(one sample `.py`, `.ts`, `.md`, `.css`) and writes each `.ngf.md` into
`output_dir` (default: `./ngfify-demo-output`, never inside the installed
package -- which may not be writable after a non-editable `pip install`).
"""

from __future__ import annotations

from pathlib import Path

from .config import NgfifyConfig
from .pipeline import NgfifyResult, ngfify_file

#: The bundled demo corpus filenames, in a stable, deterministic order.
DEMO_FILES: tuple[str, ...] = ("sample.py", "sample.ts", "sample.md", "sample.css")


def demo_corpus_dir() -> Path:
    """Filesystem path to the packaged demo corpus."""
    return Path(__file__).parent / "demo_corpus"


def run_demo(
    output_dir: str | Path | None = None,
    config: NgfifyConfig | None = None,
) -> list[NgfifyResult]:
    """Ngf-ify every file in the packaged demo corpus; return the results."""
    config = config or NgfifyConfig()
    corpus_dir = demo_corpus_dir()
    out_dir = Path(output_dir) if output_dir is not None else Path.cwd() / "ngfify-demo-output"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[NgfifyResult] = []
    for name in DEMO_FILES:
        source = corpus_dir / name
        output = out_dir / (name + config.output_suffix)
        results.append(
            ngfify_file(
                source,
                config=config,
                output_path=output,
                display_path=f"demo_corpus/{name}",
            )
        )
    return results
