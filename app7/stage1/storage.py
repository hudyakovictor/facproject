"""Atomic storage — create photo directories, handle incomplete runs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def atomic_photo_directory(root: Path, photo_id: str, *, overwrite: bool = False) -> Path:
    """Create a photo output directory atomically.

    If overwrite is True, remove existing directory first.
    Otherwise, raise FileExistsError if directory exists.
    """
    target = root / photo_id
    if target.exists() and overwrite:
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def clean_incomplete(output_dir: Path) -> None:
    """Remove photo directories that have no info.json (incomplete runs)."""
    if not output_dir.is_dir():
        return
    for d in output_dir.iterdir():
        if d.is_dir() and not (d / "info.json").is_file():
            shutil.rmtree(d, ignore_errors=True)


def write_failure(output_dir: Path, photo_id: str, payload: dict[str, Any]) -> None:
    """Write failure record for a photo that could not be processed."""
    d = output_dir / photo_id
    d.mkdir(parents=True, exist_ok=True)
    from .utils import atomic_json
    atomic_json(d / "failure.json", payload)
