"""Deterministic extraction sampling policies used by API and Stage1Engine."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from .naming import parse_photo_name

def select_per_year(paths: Iterable[Path], per_year: int = 5) -> list[Path]:
    if per_year < 1:
        raise ValueError("per_year must be >= 1")
    groups: dict[int, list[Path]] = defaultdict(list)
    for path in sorted((Path(p) for p in paths), key=lambda p: p.as_posix()):
        groups[parse_photo_name(path).year].append(path)
    return [path for year in sorted(groups) for path in groups[year][:per_year]]
