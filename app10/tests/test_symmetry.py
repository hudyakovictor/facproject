"""Плоскость симметрии по парам, поворот в систему плоскости, многоугольник и зоны на наклонённой сетке."""
import json
import os
from pathlib import Path

import numpy as np
import pytest
from test_within_bin_only import run_script
from test_zones_annotation import GROUPS, _as_sets, grid_triangles, synthetic_face

from src.symmetry import fit_symmetry_plane, points_in_polygon, rotation_to_x, to_symmetry_frame
from src.zones_annotation import zones_from_annotation


def rot(axis, deg):
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def test_fit_plane_recovers_tilted_plane_and_ignores_pair_order():
    rng = np.random.default_rng(0)
    n_true = rot("y", 3.0) @ rot("z", 1.0) @ np.array([1.0, 0, 0])
    c_true = 0.05
    right = rng.normal(0, 1, (30, 3)) * np.array([1.0, 1.0, 0.3]) + np.array([-1.0, 0, 0])
    left = right - 2.0 * ((right @ n_true) - c_true)[:, None] * n_true[None, :]  # зеркальные образы
    left += rng.normal(0, 1e-3, left.shape)
    lm = np.vstack([right, left])
    pairs = [[i, 30 + i] if i % 2 == 0 else [30 + i, i] for i in range(30)]  # половина пар «наоборот»
    plane = fit_symmetry_plane(lm, pairs)
    assert abs(plane["tilt_deg"] - np.degrees(np.arccos(n_true[0]))) < 0.3
    assert abs(plane["offset"] - c_true) < 0.01
    assert plane["rms_reflection"] < 0.01


def test_fit_plane_needs_pairs():
    with pytest.raises(ValueError):
        fit_symmetry_plane(np.zeros((4, 3)), [[0, 1], [2, 3]])


def test_rotation_maps_normal_to_x():
    for n in ([1, 0, 0], [0.99, 0.05, -0.1], [-1, 0, 0], [0.9, -0.3, 0.2]):
        n = np.array(n, float) / np.linalg.norm(n)
        r = rotation_to_x(n)
        assert np.allclose(r @ n, [1, 0, 0], atol=1e-9)
        assert np.allclose(r @ r.T, np.eye(3), atol=1e-9) and abs(np.linalg.det(r) - 1) < 1e-9


def test_points_in_polygon_square_concave_and_tolerance():
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
    pts = np.array([[0.5, 0.5], [1.5, 0.5], [-0.1, 0.5], [0.5, 1.2]])
    assert points_in_polygon(pts, square).tolist() == [True, False, False, False]
    l_shape = np.array([[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]], float)
    probe = np.array([[0.5, 1.5], [1.5, 1.5], [1.5, 0.5]])
    assert points_in_polygon(probe, l_shape).tolist() == [True, False, True]
    edge = np.array([[1.0, 0.5], [0.0, 0.5], [1.0 + 5e-10, 0.5]])  # точки на краю и чуть снаружи
    assert points_in_polygon(edge, square, tol=1e-9).all()
    assert not points_in_polygon(np.array([[1.1, 0.5]]), square, tol=1e-9).any()


def test_zones_do_not_depend_on_head_rotation():
    """Остаточный поворот головы превращается в наклон плоскости: состав зон остаётся тем же."""
    ann, v, ldm106 = synthetic_face()
    base = _as_sets(zones_from_annotation(ann, v, ldm106, groups=GROUPS))
    for axes in ((("y", 3.0),), (("z", 2.0),), (("y", 3.0), ("z", 1.0))):
        r = np.eye(3)
        for axis, deg in axes:
            r = rot(axis, deg) @ r
        moved = _as_sets(zones_from_annotation(ann, v @ r.T, ldm106, groups=GROUPS))
        differ = sum(len(base[k] ^ moved[k]) for k in base)
        assert differ <= 0.01 * len(v), (axes, differ)


def test_info_reports_plane_and_midline_offset():
    ann, v, ldm106 = synthetic_face()
    r = rot("y", 3.0)
    _, info = zones_from_annotation(ann, v @ r.T, ldm106, groups=GROUPS, return_info=True)
    assert abs(info["plane"]["tilt_deg"] - 3.0) < 0.2
    assert abs(info["midline_offset"]) < 0.02


def test_jaw_and_cheek_stay_symmetric_under_small_plane_shift():
    """Санити-проверка: малый сдвиг плоскости не разваливает симметрию. Допуск 12% включает квантование
    сетки (столбец x=0 переходит через границу). Скачок у подбородка, который агент видел на средней
    форме BFM (jaw 14–22% при сдвиге 0.005), на этой синтетической сетке НЕ воспроизводится; его
    проверяет приёмка build_zones_meanshape.py на реальной форме (test_acceptance_on_real_bfm_mean_shape)."""
    ann, v, ldm106 = synthetic_face()
    for dx in (-0.01, -0.005, 0.005, 0.01):
        zones = zones_from_annotation(ann, v, ldm106, groups=GROUPS, plane_shift=dx)
        for a, b in (("cheek_r", "cheek_l"), ("jaw_r", "jaw_l")):
            na, nb = len(zones[a]), len(zones[b])
            assert abs(na - nb) <= 0.12 * max(na, nb), (dx, a, na, nb)  # 1 столбец сетки ~ 0.06 >> сдвига


def _mean_shape_model(tmp_path):
    ann, v, ldm106 = synthetic_face()
    rng = np.random.default_rng(1)
    u = (v * 40.0 + np.array([3.0, -2.0, 1.0])).ravel()  # другая единица и перенос: нормировка должна их убрать
    fm = tmp_path / "fm.npy"
    np.save(fm, {"tri": grid_triangles(), "annotation": ann, "ldm106": ldm106, "u": u + rng.normal(0, 0, u.shape)},
            allow_pickle=True)
    return fm


def test_meanshape_script_end_to_end_on_synthetic_model(tmp_path, monkeypatch):
    fm = _mean_shape_model(tmp_path)
    out_json, report = tmp_path / "z.json", tmp_path / "rep.json"
    with pytest.raises(SystemExit) as exc:
        run_script("build_zones_meanshape", ["--face-model", str(fm), "--out-json", str(out_json),
                                             "--report", str(report), "--max-asym", "8"], monkeypatch)
    assert exc.value.code == 0
    rep = json.loads(report.read_text())
    assert rep["passed"] is True and rep["checks"]["covered"] == rep["checks"]["n_vertices"]
    assert set(rep["sensitivity_to_plane_shift"]) == {"-0.010", "-0.005", "+0.000", "+0.005", "+0.010"}
    zones = json.loads(out_json.read_text())
    assert zones["validated"] is False and zones["source"]["base"] == "bfm_mean_shape"


def test_meanshape_script_fails_when_threshold_is_too_strict(tmp_path, monkeypatch):
    fm = _mean_shape_model(tmp_path)
    with pytest.raises(SystemExit) as exc:
        run_script("build_zones_meanshape", ["--face-model", str(fm), "--out-json", str(tmp_path / "z.json"),
                                             "--report", str(tmp_path / "rep.json"), "--max-asym", "-1"], monkeypatch)
    assert exc.value.code == 1  # приёмка не вхолостую: невозможный порог даёт провал


@pytest.mark.skipif(not os.environ.get("APP10_FACE_MODEL") or not Path(os.environ.get("APP10_FACE_MODEL", "")).exists(),
                    reason="нет APP10_FACE_MODEL (путь к 3ddfa_v3/assets/face_model.npy); приёмка на средней форме BFM пропущена")
def test_acceptance_on_real_bfm_mean_shape(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_script("build_zones_meanshape", ["--face-model", os.environ["APP10_FACE_MODEL"],
                                             "--out-json", str(tmp_path / "z.json"),
                                             "--report", str(tmp_path / "rep.json")], monkeypatch)
    rep = json.loads((tmp_path / "rep.json").read_text())
    assert exc.value.code == 0, rep["asymmetry_pct"]
    assert rep["worst_asym_pct_with_shifts"] <= 10.0, rep["sensitivity_to_plane_shift"]
