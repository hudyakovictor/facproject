"""Non-destructive retention helpers: preview first, then move to managed trash."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil


@dataclass(frozen=True)
class RetentionCandidate:
    path: Path
    size_bytes: int
    modified_at: datetime


def preview_candidates(root: Path, *, older_than_days: int, protected_names: set[str] | None = None) -> list[RetentionCandidate]:
    if older_than_days < 1:
        raise ValueError("older_than_days must be positive")
    protected = protected_names or {"manifest.json", "run.json", "provenance.json"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    out: list[RetentionCandidate] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in protected:
            continue
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        if modified < cutoff:
            out.append(RetentionCandidate(path, stat.st_size, modified))
    return out


def move_to_trash(candidate: RetentionCandidate, *, heavy_root: Path, batch_id: str) -> Path:
    source = candidate.path.resolve(strict=True)
    root = heavy_root.resolve(strict=True)
    try:
        relative = source.relative_to(root)
    except ValueError as exc:
        raise ValueError("candidate is outside heavy_root") from exc
    if not batch_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in batch_id):
        raise ValueError("unsafe batch_id")
    destination = root / "trash" / batch_id / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    shutil.move(str(source), str(destination))
    return destination
