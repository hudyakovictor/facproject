"""Самодостаточная проверка: отчёт внутригрупповой калибровки содержит MAD и p95 для frontal."""
import json

import numpy as np
from test_within_bin_only import make_base, run_script, write_npz


def test_withinbin_report_has_mad_p95(tmp_path, monkeypatch):
    base = make_base()
    rng = np.random.default_rng(5)
    for i in range(12):
        write_npz(tmp_path / f"f{i}.npz", base + rng.normal(0, 0.001, base.shape), "frontal")
    out = tmp_path / "out"
    run_script("calibrate_one_person", ["--meshes", str(tmp_path), "--out", str(out)], monkeypatch)
    f = json.loads((out / "calibration_one_person.json").read_text())["by_bin"]["frontal"]
    assert f["count"] > 10
    assert f["mad_within_bin"] is not None
    assert f["p95_within_bin"] is not None
