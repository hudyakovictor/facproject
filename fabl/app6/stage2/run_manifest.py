"""📤 Манифест прогона: хеши артефактов и признание зависимости наблюдений.

Критерий готовности требует совпадения четырёх хешей и детерминированного
повторного прогона. К трём существующим (code/config/model) добавляются хеши
новых нормативных артефактов, без которых результат невоспроизводим.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final

RUN_MANIFEST_SCHEMA: Final[str] = "deeputin-run-manifest-v2.0"

TRACKED_ARTIFACTS: Final[tuple[str, ...]] = (
    "app6/atlas/pose_policy_v3_9bins.csv",
    "app6/atlas/pose_gate_v2.csv",
    "app6/atlas/landmark_utility.npy",
    "app6/atlas/visibility_prior.npy",
    "app6/atlas/landmark_utility_manifest.json",
    "app6/atlas/texture_zones_bfm35709_v3.npz",
)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def artifact_hashes(root: Path) -> dict[str, str | None]:
    return {name: _sha256(root / name) for name in TRACKED_ARTIFACTS}


def build_manifest(root: Path, *, code_hash: str, config_hash: str,
                   model_hash: str, reuse_report: dict[str, Any] | None = None,
                   space_manifest: dict[str, Any] | None = None,
                   anchor_policy: dict[str, Any] | None = None,
                   modules: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    hashes = artifact_hashes(root)
    missing = [k for k, v in hashes.items() if v is None]
    return {"schema": RUN_MANIFEST_SCHEMA,
            "code_hash": code_hash,
            "config_hash": config_hash,
            "model_hash": model_hash,
            "artifact_hashes": hashes,
            "missing_artifacts": missing,
            "ready": not missing and bool(code_hash) and bool(config_hash) and bool(model_hash),
            #: Обязательная декларация: пары не независимы.
            "dependence": reuse_report or {"status": "not_reported"},
            "analysis_space": space_manifest or {"status": "not_reported"},
            "anchor_policy_by_bin": anchor_policy or {"status": "not_reported"},
            "modules": modules or {},
            "gates": ["pose_gate_v2", "visibility_gate", "quality_stratification",
                      "expression_pair_gate", "temporal_axis", "same_day_gate_v2"]}
