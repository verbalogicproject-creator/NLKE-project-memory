"""Walk a directory and ngf-ify every supported file in it.

WHY THIS EXISTS
---------------
`ngfify_file` is strictly per-file, and `ROADMAP.md` names the gap: *"a batch/tree
mode that ngf-ifies a whole directory in one pass."* Every consumer so far has
hand-rolled the loop — `project_memory.portfolio`, the demo runner, and two
one-off export scripts. This is the extracted version, on the fleet's own
"extract on the second consumer" rule.

WHAT IT DOES NOT DO
-------------------
**No cross-file resolution.** Each card is still derived from one file in
isolation, so `depends_on` holds whatever literal import strings that file
declares — not resolved ids of sibling cards. Building the repo-wide entity
graph is a separate job (`ROADMAP.md` v0.2) and pretending otherwise here
would fabricate edges, which the package forbids.

THREE PROPERTIES WORTH KNOWING
------------------------------
1. **Nothing is dropped silently.** Every input lands in exactly one of
   `results` / `skipped` / `failed`. A tree walk that quietly ignores files it
   could not handle reports success it did not earn — and a caller reading only
   `len(results)` would never know. `TreeResult.summary()` prints all three.
2. **A bad file cannot abort the run.** Per-file errors are collected, not
   raised. One unreadable file in a 200-file tree must not cost the other 199.
3. **Declared paths stay portable.** With `output_dir` set, each card declares
   its path *relative to `root`* (optionally prefixed), not the absolute
   filesystem path it happened to be read from. Absolute paths under `/root/`,
   `/home/<user>/` and friends are exactly what `risk_areas` flags as
   hardcoded — so writing them into `main_files` would make every imported card
   self-incriminating.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import NgfifyConfig
from .detection import UnsupportedFileTypeError, detect_language
from .pipeline import NgfifyResult, ngfify_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkippedFile:
    """A file the walk deliberately did not ngf-ify, and why."""

    path: Path
    reason: str


@dataclass(frozen=True)
class FailedFile:
    """A file the walk tried to ngf-ify and could not."""

    path: Path
    error: str


@dataclass
class TreeResult:
    """The outcome of one tree walk. Every input is in exactly one list."""

    root: Path
    results: list[NgfifyResult] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    failed: list[FailedFile] = field(default_factory=list)
    #: Prior `.ngf.md` output passed over so a re-run stays idempotent. Counted
    #: rather than listed: on a re-run this equals the whole corpus, and one
    #: line per file would bury the real skips. Surfaced by `summary()`.
    prior_outputs: int = 0

    @property
    def considered(self) -> int:
        """Total files examined — written, skipped and failed together."""
        return len(self.results) + len(self.skipped) + len(self.failed)

    def summary(self) -> str:
        """A one-line summary that names the skips and failures, never hiding them."""
        line = (
            f"{len(self.results)} written, {len(self.skipped)} skipped, "
            f"{len(self.failed)} failed (of {self.considered} considered)"
        )
        if self.prior_outputs:
            line += f"; {self.prior_outputs} prior .ngf.md passed over"
        return line


def _is_excluded(path: Path, root: Path, exclude_dir_names: frozenset[str]) -> bool:
    """True when any directory component *below `root`* is on the exclude list.

    Only the part below `root` is tested. Testing the whole absolute path would
    make a root that itself sits under, say, `.../build/...` exclude everything
    inside it — the user pointed at that directory on purpose.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:  # pragma: no cover - path always comes from rglob(root)
        return False
    return any(part in exclude_dir_names for part in relative.parts[:-1])


def iter_source_files(
    root: str | Path,
    config: NgfifyConfig | None = None,
    pattern: str = "*",
) -> list[Path]:
    """Every file under `root` matching `pattern`, excluded dirs removed, sorted.

    **ngfify's own prior output is not a source file.** Files ending in
    `config.output_suffix` are left out, so running tree mode twice in sibling
    mode is idempotent instead of producing `core.py.ngf.md.ngf.md` and
    doubling the corpus on every run. Use `ngfify_file` directly (or a
    different `output_suffix`) on the rare occasion you really do want to card
    an existing card.

    Sorted so a tree walk is deterministic: the same tree yields the same order
    on every run and on every machine, which is what makes a re-run diffable.
    """
    config = config or NgfifyConfig()
    root_path = Path(root)
    if not root_path.is_dir():
        return []
    return sorted(
        p
        for p in root_path.rglob(pattern)
        if p.is_file()
        and not p.name.endswith(config.output_suffix)
        and not _is_excluded(p, root_path, config.exclude_dir_names)
    )


def count_prior_outputs(
    root: str | Path,
    config: NgfifyConfig | None = None,
    pattern: str = "*",
) -> int:
    """How many prior `.ngf.md` files the walk passed over — reported, not hidden."""
    config = config or NgfifyConfig()
    root_path = Path(root)
    if not root_path.is_dir():
        return 0
    return sum(
        1
        for p in root_path.rglob(pattern)
        if p.is_file()
        and p.name.endswith(config.output_suffix)
        and not _is_excluded(p, root_path, config.exclude_dir_names)
    )


def _flat_output_name(source: Path, root: Path, config: NgfifyConfig, name_prefix: str | None) -> str:
    """A collision-safe flat filename for `source` when writing into one directory.

    `docs/retrieval/04-fusion.md` under root `docs/` becomes
    `retrieval--04-fusion.md.ngf.md`, and with `name_prefix="declared_core"`,
    `declared_core--retrieval--04-fusion.md.ngf.md`. Without this, two repos'
    `00-mental-model.md` would overwrite each other and the loss would be silent.
    """
    relative = source.relative_to(root)
    stem = "--".join(relative.parts)
    if name_prefix:
        stem = f"{name_prefix}--{stem}"
    return stem + config.output_suffix


def ngfify_tree(
    root: str | Path,
    config: NgfifyConfig | None = None,
    output_dir: str | Path | None = None,
    write: bool = True,
    pattern: str = "*",
    name_prefix: str | None = None,
) -> TreeResult:
    """Ngf-ify every supported file under `root`.

    Args:
        root: directory to walk (recursively).
        config: an `NgfifyConfig` override, or defaults. Its `exclude_dir_names`
            controls which directories are skipped and its `output_suffix` names
            the output files.
        output_dir: write all cards into this one directory with flattened,
            collision-safe names. When `None`, each card is written beside its
            source as `<file><output_suffix>`, matching `ngfify_file`.
        write: whether to write anything at all. `False` derives and renders
            every card in memory — useful for validating a tree before
            committing to it.
        pattern: an rglob pattern to narrow the walk (e.g. `"*.md"`).
        name_prefix: prepended to flattened names, so cards gathered from
            several repos into one directory stay distinguishable. Only
            meaningful together with `output_dir`.

    Returns:
        A `TreeResult`. Files with an extension ngfify does not support are
        recorded in `skipped`; files that raised are recorded in `failed`.
        Neither aborts the walk — check `TreeResult.summary()`.
    """
    config = config or NgfifyConfig()
    root_path = Path(root)

    if not root_path.is_dir():
        raise NotADirectoryError(f"ngfify: not a directory: {root_path}")

    result = TreeResult(root=root_path, prior_outputs=count_prior_outputs(root_path, config, pattern))

    out_dir = Path(output_dir) if output_dir is not None else None
    if out_dir is not None and write:
        out_dir.mkdir(parents=True, exist_ok=True)

    for source in iter_source_files(root_path, config, pattern):
        try:
            detect_language(source, config.extra_extension_map)
        except UnsupportedFileTypeError as exc:
            result.skipped.append(SkippedFile(path=source, reason=str(exc)))
            continue

        relative = source.relative_to(root_path)
        if out_dir is not None:
            output_path: Path | None = out_dir / _flat_output_name(source, root_path, config, name_prefix)
            # Declare the portable relative path, never the absolute one this
            # process happened to read from -- see the module docstring.
            display = f"{name_prefix}/{relative.as_posix()}" if name_prefix else relative.as_posix()
        else:
            output_path = None  # ngfify_file's own sibling default
            display = None

        try:
            result.results.append(
                ngfify_file(
                    source,
                    config=config,
                    output_path=output_path,
                    write=write,
                    display_path=display,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not abort the tree
            logger.warning("ngfify: could not ngf-ify %s: %s", source, exc)
            result.failed.append(FailedFile(path=source, error=f"{type(exc).__name__}: {exc}"))

    return result
