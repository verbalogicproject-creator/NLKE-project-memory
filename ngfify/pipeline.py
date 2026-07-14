"""The public, high-level `ngfify_file` entry point tying derive + render together."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ._version import __version__
from .ai_card import AiCard
from .config import NgfifyConfig
from .derivers import derive_ai_card
from .emitter import render_ngf_md
from .text_utils import today_iso


@dataclass
class NgfifyResult:
    """The outcome of running ngfify on a single file."""

    card: AiCard
    rendered: str
    source_path: Path
    output_path: Path | None


def default_output_path(source_path: Path, config: NgfifyConfig) -> Path:
    """`<file><output_suffix>`, sibling to `source_path` (default: `<file>.ngf.md`)."""
    return source_path.with_name(source_path.name + config.output_suffix)


def ngfify_file(
    source_path: str | Path,
    config: NgfifyConfig | None = None,
    output_path: str | Path | None = None,
    write: bool = True,
    display_path: str | None = None,
) -> NgfifyResult:
    """Derive an ai_card for `source_path` and render its `.ngf.md`.

    Args:
        source_path: the file to read (its real filesystem location).
        config: an `NgfifyConfig` override, or defaults.
        output_path: where to write the result (default: `<file>.ngf.md`
            sibling of `source_path`). Ignored when `write=False`.
        write: whether to actually write `output_path` to disk.
        display_path: the path *declared* in `main_files` and the body
            trailer -- defaults to `str(source_path)`. Set this when
            `source_path` is an installation-dependent absolute path (e.g.
            the packaged demo corpus) but a stable, portable path should be
            declared instead.
    """
    config = config or NgfifyConfig()
    source = Path(source_path)
    card, extra_keys = derive_ai_card(source, config)

    display = display_path if display_path is not None else str(source_path)
    if display_path is not None:
        card = replace(card, main_files=[display])

    rendered = render_ngf_md(
        card,
        source_display_path=display,
        generated_date=today_iso(),
        tool_version=__version__,
        extra_keys=extra_keys,
    )

    out_path = Path(output_path) if output_path is not None else default_output_path(source, config)
    if write:
        out_path.write_text(rendered, encoding="utf-8")

    return NgfifyResult(
        card=card,
        rendered=rendered,
        source_path=source,
        output_path=out_path if write else None,
    )
