"""Самодостаточные тесты: данные строятся синтетически, абсолютных путей нет."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_script(name, argv, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(sys, "argv", [name] + argv)
    mod.main()


def make_base(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.uniform(-0.6, 0.6, n), rng.uniform(-0.8, 0.3, n), rng.uniform(-0.2, 0.2, n)])


def write_npz(path, v, pose_bin, yaw=0.0, alpha=None):
    np.savez_compressed(path, v_aligned=v.astype(np.float32), ldm106_aligned=np.zeros((106, 3), np.float32),
                        pose_bin=pose_bin, yaw=yaw,
                        alpha_id=np.zeros(8) if alpha is None else alpha)


@pytest.fixture
def mesh_dir(tmp_path):
    base = make_base()
    rng = np.random.default_rng(1)
    for i in range(6):
        write_npz(tmp_path / f"f{i}.npz", base + rng.normal(0, 0.001, base.shape), "frontal", 1.0)
    for i in range(4):
        write_npz(tmp_path / f"l{i}.npz", base + rng.normal(0, 0.002, base.shape), "left_light", -15.0)
    write_npz(tmp_path / "solo.npz", base, "right_deep", 45.0)
    return tmp_path


def test_calibrate_has_no_between_keys_and_marks_small_bins(mesh_dir, tmp_path, monkeypatch):
    out = tmp_path / "out"
    run_script("calibrate_one_person", ["--meshes", str(mesh_dir), "--out", str(out)], monkeypatch)
    rep = json.loads((out / "calibration_one_person.json").read_text())
    assert not any(k.startswith("between_") for k in rep["by_bin"])
    assert set(rep["by_bin"]) == {"frontal", "left_light", "right_deep"}
    assert rep["by_bin"]["right_deep"]["median_within_bin"] is None
    assert rep["by_bin"]["frontal"]["median_within_bin"] > 0
    assert all(p["bin"] in rep["by_bin"] for p in rep["pairs_in_bin"])
