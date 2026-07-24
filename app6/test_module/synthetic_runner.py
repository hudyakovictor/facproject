"""Deterministic synthetic gates based on the 3DDFA-V3 face model.

These tests validate numerical contracts and chronology wiring. They are not
accuracy estimates and must never be used to calibrate forensic thresholds.
UV coordinates are checked only as a rendering/correspondence contract.
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from app6.stage1.geometry import (
    classify_pose,
    full_pose_correction_matrix,
    normalize_mesh,
    pack_mask,
    row_rotation_matrix,
    unpack_mask,
)
from app6.stage2.core import Record, compare_landmarks, robust_rigid_align
from app6.stage2.chronology import apply_chronology_rate_flags

REQUIRED = {
    "u": (107127, 1),
    "id": (107127, 80),
    "exp": (107127, 64),
    "tri": (70789, 3),
    "point_buf": (35709, 8),
    "ldm106": (106,),
    "ldm134": (134,),
    "uv_coords": (35709, 2),
}
SUITES = ("asset", "geometry", "stage2")


@dataclass
class Check:
    suite: str
    name: str
    passed: bool
    detail: str = ""


class SyntheticFailure(AssertionError):
    pass


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SyntheticFailure(message)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_face_model(path: Path) -> dict[str, np.ndarray]:
    """Load the trusted local 3DDFA asset and keep only allowed arrays."""
    if not path.is_file():
        raise FileNotFoundError(f"face model not found: {path}")
    raw = np.load(path, allow_pickle=True)
    obj = raw.item()
    if not isinstance(obj, dict):
        raise ValueError("face_model.npy must contain a dictionary")
    missing = sorted(set(REQUIRED) - set(obj))
    if missing:
        raise ValueError(f"face model missing arrays: {missing}")
    return {k: np.asarray(obj[k]) for k in obj if isinstance(obj[k], np.ndarray)}


def _mean_mesh(model: dict[str, np.ndarray]) -> np.ndarray:
    return np.asarray(model["u"], np.float32).reshape(35709, 3)


def _identity_mesh(model: dict[str, np.ndarray], coeff: np.ndarray) -> np.ndarray:
    u = np.asarray(model["u"], np.float64).reshape(-1)
    basis = np.asarray(model["id"], np.float64)
    return (u + basis @ np.asarray(coeff, np.float64)).reshape(35709, 3).astype(np.float32)


def _record(model: dict[str, np.ndarray], name: str, coeff: np.ndarray) -> Record:
    mesh = _identity_mesh(model, coeff)
    norm, _, _ = normalize_mesh(mesh)
    i106 = np.asarray(model["ldm106"], np.int64)
    i134 = np.asarray(model["ldm134"], np.int64)
    return Record(
        record_id=name,
        dataset_id="synthetic",
        date="2001-01-01",
        sequence=1,
        pose_bin="frontal",
        angles=np.zeros(3, np.float32),
        ldm106=norm[i106],
        ldm134=norm[i134],
        visible106=np.ones(106, bool),
        visible134=np.ones(134, bool),
        alpha_id=np.asarray(coeff, np.float32),
        alpha_exp=np.zeros(64, np.float32),
        identity_only106=norm[i106],
        identity_only134=norm[i134],
        quality_status="synthetic",
        quality_texture_score=1.0,
    )


def _run_check(suite: str, name: str, fn: Callable[[], str | None]) -> Check:
    try:
        detail = fn() or "ok"
        return Check(suite, name, True, detail)
    except Exception as exc:
        return Check(suite, name, False, f"{type(exc).__name__}: {exc}")


def asset_checks(model: dict[str, np.ndarray], path: Path) -> list[Check]:
    def shapes() -> str:
        for key, shape in REQUIRED.items():
            _assert(model[key].shape == shape, f"{key}: {model[key].shape} != {shape}")
        return "all required shapes match"

    def finite_and_indices() -> str:
        for key in ("u", "id", "exp", "uv_coords"):
            _assert(np.isfinite(model[key]).all(), f"{key} contains NaN/Inf")
        tri = np.asarray(model["tri"], np.int64)
        _assert(int(tri.min()) >= 0 and int(tri.max()) < 35709, "triangle index out of range")
        for key, count in (("ldm106", 106), ("ldm134", 134)):
            ids = np.asarray(model[key], np.int64)
            _assert(len(np.unique(ids)) == count, f"{key} contains duplicates")
            _assert(int(ids.min()) >= 0 and int(ids.max()) < 35709, f"{key} out of range")
        return "finite arrays and valid topology indices"

    def uv_contract_only() -> str:
        uv = np.asarray(model["uv_coords"], np.float64)
        _assert(uv.shape == (35709, 2), "UV/vertex count mismatch")
        _assert(np.isfinite(uv).all(), "UV contains NaN/Inf")
        return "UV verified for rendering/correspondence only; no evidence metric"

    return [
        _run_check("asset", "face_model_shapes", shapes),
        _run_check("asset", "face_model_indices", finite_and_indices),
        _run_check("asset", "uv_non_evidentiary_contract", uv_contract_only),
        Check("asset", "face_model_sha256", True, _sha256(path)),
    ]


def geometry_checks(model: dict[str, np.ndarray]) -> list[Check]:
    mean = _mean_mesh(model)

    def normalization_invariance() -> str:
        a, _, _ = normalize_mesh(mean)
        b, _, _ = normalize_mesh(mean * 3.7 + np.array([12.0, -9.0, 4.0], np.float32))
        err = float(np.max(np.abs(a - b)))
        _assert(err < 3e-5, f"normalization invariance error {err}")
        return f"max_error={err:.3e}"

    def rotation_recovery() -> str:
        base, _, _ = normalize_mesh(mean)
        actual = np.array([-12.0, 32.0, 7.0])
        target = np.array([0.0, 32.5, 0.0])
        posed = base @ row_rotation_matrix(*actual)
        correction = full_pose_correction_matrix(actual, target)
        recovered = posed @ correction
        expected = base @ row_rotation_matrix(*target)
        err = float(np.max(np.abs(recovered - expected)))
        _assert(err < 2e-5, f"full pose recovery error {err}")
        _assert(abs(float(np.linalg.det(correction)) - 1.0) < 1e-5, "correction is not a proper rotation")
        return f"max_error={err:.3e}"

    def nine_pose_bins() -> str:
        expected = [
            (-70, "left_profile"), (-45, "left_deep"), (-32.5, "left_mid"),
            (-17.5, "left_light"), (0, "frontal"), (17.5, "right_light"),
            (32.5, "right_mid"), (45, "right_deep"), (70, "right_profile"),
        ]
        got = [(yaw, classify_pose(yaw)[0]) for yaw, _ in expected]
        _assert([x[1] for x in got] == [x[1] for x in expected], f"pose mismatch: {got}")
        return "all nine canonical poses classified"

    def mask_roundtrip() -> str:
        rng = np.random.default_rng(20260724)
        mask = rng.integers(0, 2, size=35709, dtype=np.uint8)
        out = unpack_mask(pack_mask(mask), len(mask))
        _assert(np.array_equal(mask, out), "mask pack/unpack mismatch")
        return "35709-bit visibility mask roundtrip"

    return [
        _run_check("geometry", "normalization_invariance", normalization_invariance),
        _run_check("geometry", "full_pose_rotation_recovery", rotation_recovery),
        _run_check("geometry", "nine_pose_bins", nine_pose_bins),
        _run_check("geometry", "visibility_mask_roundtrip", mask_roundtrip),
    ]


def stage2_checks(model: dict[str, np.ndarray]) -> list[Check]:
    rng = np.random.default_rng(20260724)
    coeff_a = np.zeros(80, np.float32)
    coeff_b = np.clip(rng.normal(0.0, 0.65, 80), -1.5, 1.5).astype(np.float32)
    a = _record(model, "A", coeff_a)
    a2 = _record(model, "A2", coeff_a)
    b = _record(model, "B", coeff_b)
    z106 = np.asarray([f"z{i % 9}" for i in range(106)])
    z134 = np.asarray([f"z{i % 9}" for i in range(134)])

    def rigid_recovery() -> str:
        src = a.ldm134
        rot = row_rotation_matrix(4.0, -18.0, 3.0)
        moved = src @ rot + np.array([0.2, -0.3, 0.1], np.float32)
        aligned, recovered_rot, _, meta = robust_rigid_align(moved, src, min_points=30)
        err = float(np.sqrt(np.mean(np.sum((aligned - src) ** 2, axis=1))))
        _assert(err < 2e-5, f"Kabsch recovery RMSE {err}")
        _assert(float(np.linalg.det(recovered_rot)) > 0.999, "reflection was introduced")
        return f"rmse={err:.3e}; {meta.get('alignment_policy')}"

    def same_identity_near_zero() -> str:
        c = compare_landmarks(a, a2, z106, z134)
        _assert(c.status == "measured", f"status={c.status}")
        rmse = float(c.metrics["ldm134_rmse"])
        _assert(rmse < 1e-7, f"same identity RMSE {rmse}")
        return f"ldm134_rmse={rmse:.3e}"

    def different_identity_separates() -> str:
        same = compare_landmarks(a, a2, z106, z134)
        diff = compare_landmarks(a, b, z106, z134)
        _assert(diff.status == "measured", f"status={diff.status}")
        sr = float(same.metrics["ldm134_rmse"])
        dr = float(diff.metrics["ldm134_rmse"])
        _assert(dr > sr + 1e-5, f"different identity did not separate: same={sr} diff={dr}")
        return f"same={sr:.3e}; different={dr:.3e}"

    def chronology_same_day_and_missing_date() -> str:
        rows = [
            {"pair_type": "adjacent", "pose_bin": "frontal", "pair_index": 1,
             "date_a": "2003-06-15", "date_b": "2003-06-15", "p95_point_z": 5.0,
             "coherent_motion_fraction": 0.5, "significant_point_fraction": 0.2,
             "status": "coherent_jump_candidate"},
            {"pair_type": "adjacent", "pose_bin": "right_light", "pair_index": 2,
             "date_a": None, "date_b": "2004-01-01", "p95_point_z": 9.0,
             "coherent_motion_fraction": 0.8, "significant_point_fraction": 0.4,
             "status": "coherent_jump_candidate"},
        ]
        apply_chronology_rate_flags(rows)
        _assert(rows[0]["chronology_rate_status"] == "same_day_structural_conflict", str(rows[0]))
        _assert(rows[1]["chronology_rate_status"] == "date_missing", str(rows[1]))
        return "same-day conflict and missing-date fail-closed behavior"

    return [
        _run_check("stage2", "robust_rigid_alignment", rigid_recovery),
        _run_check("stage2", "same_identity_near_zero", same_identity_near_zero),
        _run_check("stage2", "different_identity_separates", different_identity_separates),
        _run_check("stage2", "chronology_edge_contracts", chronology_same_day_and_missing_date),
    ]


def run(face_model_path: Path, suites: list[str] | None = None) -> dict:
    selected = suites or list(SUITES)
    unknown = sorted(set(selected) - set(SUITES))
    if unknown:
        raise ValueError(f"unknown synthetic suites: {unknown}")
    model = load_face_model(face_model_path)
    checks: list[Check] = []
    if "asset" in selected:
        checks.extend(asset_checks(model, face_model_path))
    if "geometry" in selected:
        checks.extend(geometry_checks(model))
    if "stage2" in selected:
        checks.extend(stage2_checks(model))
    payload = {
        "schema": "app6-synthetic-gate-v1",
        "face_model": str(face_model_path),
        "suites": selected,
        "passed": all(c.passed for c in checks),
        "check_count": len(checks),
        "failed_count": sum(not c.passed for c in checks),
        "checks": [c.__dict__ for c in checks],
        "interpretation": "Numerical regression gate only; not a real-photo accuracy or forensic validation.",
        "uv_policy": "UV is visualization/correspondence only and is excluded from evidence.",
    }
    return payload


def print_result(payload: dict) -> None:
    for c in payload["checks"]:
        print(("✅" if c["passed"] else "❌"), f"[{c['suite']}] {c['name']}: {c['detail']}")
    print(f"SYNTHETIC {'PASS' if payload['passed'] else 'FAIL'}: "
          f"{payload['check_count'] - payload['failed_count']}/{payload['check_count']}")
