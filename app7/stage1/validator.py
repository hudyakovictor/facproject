"""Output validation — check that all expected files exist after extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = ("info.json", "reconstruction.npz")
REQUIRED_LDM = ("ldm106_raw.csv", "ldm106_aligned.csv", "ldm134_raw.csv", "ldm134_aligned.csv")


def validate_photo(directory: Path, *, write_result: bool = False) -> dict[str, Any]:
    """Validate that a photo directory has all expected outputs."""
    errors: list[str] = []
    for f in REQUIRED_FILES:
        if not (directory / f).is_file():
            errors.append(f"missing {f}")
    for f in REQUIRED_LDM:
        if not (directory / f).is_file():
            errors.append(f"missing {f}")
    # skin is optional at validation level (may have failed gracefully)
    skin_ok = (directory / "skin" / "manifest.json").is_file()
    if not skin_ok and (directory / "skin_failure.json").is_file():
        pass  # acceptable — skin failed but was caught
    elif not skin_ok:
        errors.append("missing skin/manifest.json and no skin_failure.json")

    result = {
        "status": "complete" if not errors else "incomplete",
        "errors": errors,
    }
    if write_result:
        from .utils import atomic_json
        atomic_json(directory / "validation.json", result)
    return result


def is_resumable(directory: Path, code_hash: str, config_hash: str) -> tuple[bool, dict | None]:
    """Check if an existing directory can be skipped (same code + config)."""
    info_path = directory / "info.json"
    if not info_path.is_file():
        return False, None
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except Exception:
        return False, None
    if info.get("code_hash") != code_hash:
        return False, None
    if info.get("config_hash") != config_hash:
        return False, None
    val = validate_photo(directory)
    if val["status"] != "complete":
        return False, None
    return True, info
