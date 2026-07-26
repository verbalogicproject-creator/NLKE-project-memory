"""ngfify -- turn a single source file into a declared `<file>.ngf.md` ai_card.

The ONE declared boundary: **derivation-with-provenance, never fabrication.**
Every emitted `ai_card` slot is either derived from something literally
present in the source file, or emitted as the explicit sentinel
`TODO_SENTINEL` (`"<derive: not inferable from a single file>"`). ngfify
never invents a `public_interfaces` entry, a dependency, or a risk finding
that cannot be traced back to the file it just read.

Quickstart::

    from ngfify import ngfify_file

    result = ngfify_file("my_module.py")
    print(result.output_path, result.card.public_interfaces)

A whole tree at once::

    from ngfify import ngfify_tree

    result = ngfify_tree("src/", output_dir="cards/", name_prefix="myrepo")
    print(result.summary())   # "42 written, 3 skipped, 0 failed (of 45 considered)"

Tree mode derives each card from one file in isolation, exactly as
`ngfify_file` does -- it adds the walk, not cross-file resolution. Nothing is
dropped silently: every input lands in `results`, `skipped` or `failed`.

Or the packaged demo corpus::

    from ngfify import run_demo

    for result in run_demo():
        print(result.source_path.name, result.card.kind)
"""

from __future__ import annotations

from ._version import __version__
from .ai_card import AI_CARD_SLOTS, LIST_SLOTS, AiCard
from .config import NgfifyConfig, load_config
from .demo import run_demo
from .derivers import derive_ai_card
from .detection import Language, UnsupportedFileTypeError
from .emitter import render_ngf_md
from .pipeline import NgfifyResult, default_output_path, ngfify_file
from .text_utils import TODO_SENTINEL
from .tree import FailedFile, SkippedFile, TreeResult, iter_source_files, ngfify_tree

__all__ = [
    "__version__",
    "AiCard",
    "AI_CARD_SLOTS",
    "LIST_SLOTS",
    "NgfifyConfig",
    "load_config",
    "Language",
    "UnsupportedFileTypeError",
    "derive_ai_card",
    "render_ngf_md",
    "ngfify_file",
    "NgfifyResult",
    "default_output_path",
    "ngfify_tree",
    "TreeResult",
    "SkippedFile",
    "FailedFile",
    "iter_source_files",
    "run_demo",
    "TODO_SENTINEL",
]
