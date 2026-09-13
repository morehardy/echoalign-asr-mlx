"""Output path planning."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence


DEFAULT_OUTPUT_DIRNAME = "outputs"


def build_output_path(
    *,
    source: Path,
    input_root: Path,
    output_root: Path,
    suffix: str,
) -> Path:
    """Build an output path under the output root while preserving layout."""

    relative_source = source.relative_to(input_root)
    return (output_root / relative_source).with_suffix(suffix)


def default_output_root(input_path: Path, explicit_output_dir: Optional[Path] = None) -> Path:
    """Return the default output root for a CLI input target."""

    if explicit_output_dir is not None:
        return explicit_output_dir.expanduser()
    if input_path.is_file():
        return input_path.parent / DEFAULT_OUTPUT_DIRNAME
    return input_path / DEFAULT_OUTPUT_DIRNAME


def validate_output_paths(
    sources: Sequence[tuple[Path, Path]],
    *,
    output_dir: Path | None,
    suffixes: Sequence[str],
) -> None:
    """Reject batch collisions before any model work or output writes."""
    owners: dict[str, Path] = {}
    collisions: list[str] = []
    for source, input_root in sources:
        source = source.expanduser().absolute()
        input_root = input_root.expanduser().absolute()
        output_root = default_output_root(input_root, explicit_output_dir=output_dir)
        for suffix in suffixes:
            target = build_output_path(
                source=source,
                input_root=input_root,
                output_root=output_root.expanduser(),
                suffix=suffix,
            ).resolve()
            # Default macOS volumes also collide when names differ only in case.
            key = str(target).casefold()
            previous = owners.get(key)
            if previous is not None and previous.resolve() != source.resolve():
                collisions.append(f"{previous} and {source} -> {target}")
            owners[key] = source
    if collisions:
        raise ValueError("Output path collision:\n" + "\n".join(collisions))
