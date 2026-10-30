"""Зоны (фиксированные индексы) и проверка мимики на синтетике с известным эффектом."""
import json

import numpy as np
import pytest
from test_within_bin_only import make_base, run_script, write_npz

from src.zones import build_zones, check_disjoint, load_zones, save_zones


def test_zones_disjoint_and_roundtrip(tmp_path):
    base = make_base()
    zones = build_zones(base)
    assert check_disjoint(zones)
    path = tmp_path / "z.json"
    save_zones(path, zones, len(base))
    loaded, meta = load_zones(path, n_vertices=len(base))
    assert meta["validated"] is False
    assert {k: v.tolist() for k, v in zones.items()} == {k: v.tolist() for k, v in loaded.items()}
    with pytest.raises(ValueError):
        load_zones(path, n_vertices=len(base) + 1)


def test_zone_too_small_is_error():
    v = np.zeros((50, 3))
    with pytest.raises(ValueError):
        build_zones(v)


def test_zonal_calibrate_uses_fixed_zones(tmp_path, monkeypatch):
    base = make_base()
    rng = np.random.default_rng(2)
    for i in range(5):
        write_npz(tmp_path / f"f{i}.npz", base + rng.normal(0, 0.001, base.shape), "frontal")
    write_npz(tmp_path / "solo.npz", base, "left_deep")
    zp = tmp_path / "z.json"
    zones = build_zones(base)
    save_zones(zp, zones, len(base))
    out = tmp_path / "out"
    run_script("zonal_calibrate", ["--meshes", str(tmp_path), "--zones", str(zp), "--out", str(out)], monkeypatch)
    rep = json.loads((out / "zonal_calibration.json").read_text())
    assert rep["by_bin_zones"]["left_deep"]["status"] == "insufficient_frames"
    assert set(rep["by_bin_zones"]["frontal"]) == set(zones)
    assert rep["zones_validated"] is False


def test_expression_effect_found_only_in_lips(tmp_path, monkeypatch):
    base = make_base()
    zones = build_zones(base)
    rng = np.random.default_rng(3)
    for i in range(6):
        write_npz(tmp_path / f"n{i}.npz", base + rng.normal(0, 0.001, base.shape), "frontal",
                  alpha=rng.normal(0, 0.01, 8))
    smile = base + rng.normal(0, 0.001, base.shape)
    smile[zones["lips"], 2] += 0.05
    write_npz(tmp_path / "улыбка1.npz", smile, "frontal", alpha=np.full(8, 0.2))
    zp = tmp_path / "z.json"
    save_zones(zp, zones, len(base))
    out = tmp_path / "out"
    run_script("expression_check", ["--meshes", str(tmp_path), "--zones", str(zp), "--out", str(out),
                                    "--expr", "улыбка=улыбка"], monkeypatch)
    rep = json.loads((out / "expression_check_zonal.json").read_text())
    assert rep["n_neutral"] == 6
    row = rep["expressions"]["улыбка"][0]
    ratios = {z: v["ratio_to_baseline"] for z, v in row["zones"].items()}
    assert ratios["lips"] > 10
    assert all(ratios[z] < 3 for z in ratios if z != "lips")
    assert row["alpha_id_shift"]["ratio_to_baseline"] > 10
