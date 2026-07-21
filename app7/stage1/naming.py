"""Photo naming — parse YYYY_MM_DD from filename, build photo_id.

No SHA-256 in photo_id — filenames with dates are unique within the dataset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})_(?P<m>\d{1,2})_(?P<d>\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>19\d{2}|20\d{2})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"),
)
_COPY_SUFFIX = re.compile(r"(?:\s*\((?P<n1>\d+)\)|[_-](?P<n2>\d+)|[-_ ]copy)$", re.I)


@dataclass(frozen=True)
class PhotoName:
    date_iso: str
    year: int
    month: int
    day: int
    sequence: int
    canonical_stem: str


def parse_photo_name(path: Path) -> PhotoName:
    """Parse photo name: accepts YYYY_MM_DD[_N] with optional copy suffixes."""
    stem = path.stem
    parsed = None
    date_end_pos = 0
    for pattern in _DATE_PATTERNS:
        m = pattern.search(stem)
        if m:
            try:
                parsed = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
                date_end_pos = m.end()
                break
            except ValueError:
                pass
    if parsed is None:
        raise ValueError(f"invalid filename; could not parse date: {path.name}")

    suffix_match = _COPY_SUFFIX.search(stem[date_end_pos:])
    seq = int((suffix_match.group("n1") or suffix_match.group("n2")) if suffix_match else 1)
    rest = stem[date_end_pos:]
    rest = re.sub(r"[\s()]", "_", rest)
    rest = re.sub(r"_+", "_", rest).strip("_")
    canonical_stem = f"{parsed.year:04d}_{parsed.month:02d}_{parsed.day:02d}"
    if rest:
        canonical_stem += rest if rest.startswith("_") else f"_{rest}"
    return PhotoName(parsed.isoformat(), parsed.year, parsed.month, parsed.day, seq, canonical_stem)


def make_photo_id(parsed: PhotoName) -> str:
    """Simple deterministic ID: just the canonical stem from the filename.

    No SHA-256 — filename dates are unique identifiers within this dataset.
    If two photos share the exact same stem (same date, same suffix),
    a numeric disambiguator based on sequence number is appended.
    """
    if parsed.sequence > 1:
        return f"{parsed.canonical_stem}__seq{parsed.sequence}"
    return parsed.canonical_stem
