"""Утверждение зон по хешу и защита отчётов от смешивания разных зон."""
import json

import numpy as np
import pytest
from test_mesh_geometry import icosphere
from test_within_bin_only import run_script, write_npz

from src.zones import save_zones


def _setup(tmp_path):
    v, tri = icosphere(1.0)
    rng = np.random.default_rng(0)
    for i in range(4):
        write_npz(tmp_path / f"f{i}.npz", v + rng.normal(0, 1e-4, v.shape), "frontal")
    fm = tmp_path / "fm.npy"
    np.save(fm, {"tri": tri}, allow_pickle=True)
    zones = {"top": np.where(v[:, 2] >= 0)[0], "bottom": np.where(v[:, 2] < 0)[0]}
    zp = tmp_path / "z.json"
    save_zones(zp, zones, len(v))
    return v, fm, zp, zones


def _calibrate(tmp_path, fm, zp, out, monkeypatch, extra=()):
    run_script("geometry_calibrate", ["--meshes", str(tmp_path), "--face-model", str(fm), "--zones", str(zp),
                                      "--out", str(out), *extra], monkeypatch)
    return json.loads((out / "geometry_calibration.json").read_text())


def test_approve_records_who_when_and_hash(tmp_path, monkeypatch):
    v, fm, zp, zones = _setup(tmp_path)
    run_script("approve_zones", ["--zones", str(zp), "--by", "tester"], monkeypatch)
    d = json.loads(zp.read_text())
    assert d["validated"] is True and d["approved_by"] == "tester" and d["approved_at"].endswith("+00:00")
    assert _calibrate(tmp_path, fm, zp, tmp_path / "o1", monkeypatch)["zones_validated"] is True
    run_script("approve_zones", ["--zones", str(zp), "--revoke"], monkeypatch)
    d = json.loads(zp.read_text())
    assert d["validated"] is False and "revoked_at" in d


def test_changing_zones_invalidates_approval(tmp_path, monkeypatch):
    v, fm, zp, zones = _setup(tmp_path)
    run_script("approve_zones", ["--zones", str(zp), "--by", "tester"], monkeypatch)
    d = json.loads(zp.read_text())
    d["zones"]["top"] = d["zones"]["top"][:-5]  # правка границ после утверждения
    zp.write_text(json.dumps(d))
    rep = _calibrate(tmp_path, fm, zp, tmp_path / "o2", monkeypatch)
    assert rep["zones_validated"] is False


def test_report_with_other_zones_is_refused_unless_forced(tmp_path, monkeypatch):
    v, fm, zp, zones = _setup(tmp_path)
    out = tmp_path / "o3"
    first = _calibrate(tmp_path, fm, zp, out, monkeypatch)
    d = json.loads(zp.read_text())
    d["zones"]["top"] = d["zones"]["top"][:-5]
    zp.write_text(json.dumps(d))
    with pytest.raises(SystemExit) as exc:
        _calibrate(tmp_path, fm, zp, out, monkeypatch)
    assert "--force" in str(exc.value) and "--out" in str(exc.value)
    forced = _calibrate(tmp_path, fm, zp, out, monkeypatch, extra=("--force",))
    assert forced["zones_sha256"] != first["zones_sha256"]
