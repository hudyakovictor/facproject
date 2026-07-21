"""Common utilities — atomic I/O, hashing, version info."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, obj: dict[str, Any]) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    tmp.replace(path)


def _json_default(o: Any) -> Any:
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    raise TypeError(f"not JSON serializable: {type(o)}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write list-of-dicts as CSV."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    writer = csv.DictWriter(path.open("w", newline="", encoding="utf-8"), fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)


def sha256_json(obj: dict[str, Any]) -> str:
    blob = json.dumps(obj, sort_keys=True, default=_json_default).encode()
    return hashlib.sha256(blob).hexdigest()


def sha256_paths(files: list[Path], root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        rel = str(f.relative_to(root)) if f.is_relative_to(root) else f.name
        h.update(rel.encode())
        if f.is_file():
            h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
    return h.hexdigest()


def runtime_versions() -> dict[str, str]:
    import torch
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
    }
