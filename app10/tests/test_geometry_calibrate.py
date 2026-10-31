import json

import numpy as np
from test_mesh_geometry import icosphere
from test_within_bin_only import run_script, write_npz

from src.zones import save_zones


def test_geometry_calibrate_on_old_style_npz(tmp_path, monkeypatch):
    v, tri = icosphere(1.0)
    rng = np.random.default_rng(0)
    for i in range(5):
        write_npz(tmp_path / f"f{i}.npz", v + rng.normal(0, 1e-4, v.shape), "frontal")
    for i in range(2):
        write_npz(tmp_path / f"g{i}.npz", v, "left_light")
    fm = tmp_path / "fm.npy"
    np.save(fm, {"tri": tri}, allow_pickle=True)
    zones = {"top": np.where(v[:, 2] >= 0)[0], "bottom": np.where(v[:, 2] < 0)[0]}
    zp = tmp_path / "z.json"
    save_zones(zp, zones, len(v))
    out = tmp_path / "out"
    run_script("geometry_calibrate", ["--meshes", str(tmp_path), "--face-model", str(fm),
                                      "--zones", str(zp), "--out", str(out)], monkeypatch)
    rep = json.loads((out / "geometry_calibration.json").read_text())
    assert rep["by_bin"]["left_light"]["status"] == "insufficient_frames"
    top = rep["by_bin"]["frontal"]["top"]
    assert set(top["features"]) == {"area", "area_frac", "mean_curvature", "gauss_curvature"}
    assert abs(top["features"]["mean_curvature"]["per_frame"]["median"] - 1) < 0.2
    assert top["normal_angle_deg_pairs"]["k_differ_p97_5"] < 5
    assert rep["zones_validated"] is False


def test_geometry_calibrate_detects_local_change(tmp_path, monkeypatch):
    v, tri = icosphere(1.0)
    zones = {"top": np.where(v[:, 2] >= 0.5)[0], "bottom": np.where(v[:, 2] < -0.5)[0]}
    rng = np.random.default_rng(1)
    for i in range(4):
        w = v + rng.normal(0, 1e-4, v.shape)
        write_npz(tmp_path / f"a{i}.npz", w, "frontal")
    fm = tmp_path / "fm.npy"
    np.save(fm, {"tri": tri}, allow_pickle=True)
    zp = tmp_path / "z.json"
    save_zones(zp, zones, len(v))
    changed = tmp_path / "chg"
    changed.mkdir()
    for i in range(4):
        w = v + rng.normal(0, 1e-4, v.shape)
        w[zones["top"]] *= 1.1
        write_npz(changed / f"b{i}.npz", w, "frontal")
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    run_script("geometry_calibrate", ["--meshes", str(tmp_path), "--face-model", str(fm), "--zones", str(zp),
                                      "--out", str(out1)], monkeypatch)
    base = json.loads((out1 / "geometry_calibration.json").read_text())["by_bin"]["frontal"]
    run_script("geometry_calibrate", ["--meshes", str(changed), "--face-model", str(fm), "--zones", str(zp),
                                      "--out", str(out2)], monkeypatch)
    chg = json.loads((out2 / "geometry_calibration.json").read_text())["by_bin"]["frontal"]
    d_top = abs(chg["top"]["features"]["area"]["per_frame"]["median"] - base["top"]["features"]["area"]["per_frame"]["median"])
    d_bot = abs(chg["bottom"]["features"]["area"]["per_frame"]["median"] - base["bottom"]["features"]["area"]["per_frame"]["median"])
    assert d_top > 100 * max(d_bot, 1e-9)
