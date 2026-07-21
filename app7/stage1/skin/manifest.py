"""Skin package manifest — creation and finalization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .serialization import sha256_file


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_manifest(
    photo_id: str, input_path: Path, bgr: np.ndarray, *,
    coordinate_chain: dict, models: dict, atlas: dict,
    config: dict, backend: dict, warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "photo_id": photo_id,
        "source_file": input_path.name,
        "image_shape": list(bgr.shape),
        "created_at_utc": _utc(),
        "coordinate_chain": coordinate_chain,
        "models": models,
        "atlas": atlas,
        "config": config,
        "backend": backend,
        "warnings": warnings or [],
        "state": "in_progress",
    }


def finalize_manifest(skin_dir: Path, manifest: dict, state: str) -> dict:
    manifest["state"] = state
    manifest["completed_at_utc"] = _utc()
    # Write SUCCESS marker
    (skin_dir / "SUCCESS").write_text(state, encoding="utf-8")
    from .serialization import atomic_json
    atomic_json(skin_dir / "manifest.json", manifest)
    return manifest
