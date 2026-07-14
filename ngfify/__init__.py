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
    "run_demo",
    "TODO_SENTINEL",
]
