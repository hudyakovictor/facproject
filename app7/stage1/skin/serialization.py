"""Atomic file I/O for skin sub-package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def atomic_json(path: Path, obj: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=_default), encoding="utf-8")
    tmp.replace(path)


def _default(o: Any) -> Any:
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    """Save compressed NPZ atomically."""
    tmp = path.with_suffix(".tmp")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path.with_suffix(".npz"))


def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for chunk in iter(lambda: path.open("rb").read(1 << 20), b""):
        h.update(chunk)
    return h.hexdigest()
