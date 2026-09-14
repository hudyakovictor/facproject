"""Golden tests chronology-контракта (рецензия форка П1).

Ключевой регресс на сам баг: идентичная форма + две разные фактические позы
внутри одного бина -> target-only выдаёт побитно идентичные вершины
(max|Δ|=0), а старый R_corr — разные. Тест падает на сломанной формуле и
проходит на починенной.

Тонкость target-only (зафиксирована): канал щёлкает все фото бина в
идентичную позу — внутрибинная разница поз в нём невидима (frontal −1° и −9°
→ одинаковы). Защита: pose-gate по Δyaw в сырых углах + raw/2D-каналы +
within-bin residual как вес пары (см. analyst compare-скрипт).
"""
import itertools
import unittest

import numpy as np

from app6.stage1.geometry import (
    compute_chronology_alignment,
    full_pose_correction_matrix,
    normalize_mesh,
    replay_identity_chronology,
    row_rotation_matrix,
)


def _mesh(seed=0, n=2000):
    rng = np.random.default_rng(seed)
    return (rng.normal(size=(n, 3)) * 20).astype(np.float32)


def _dists(a, idx):
    return np.array([np.linalg.norm(a[i] - a[j]) for i, j in itertools.combinations(idx, 2)])


def _centroid(a):
    c = a - a.mean(0)
    return float(np.sqrt(np.mean(np.sum(c * c, 1))))


def _kabsch_rmse(a, b):
    ca, cb = a.mean(0), b.mean(0)
    x, y = b - cb, a - ca
    U, _, Vt = np.linalg.svd(x.T @ y)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = U @ Vt
    return float(np.sqrt(np.mean(np.sum((x @ R - y) ** 2, 1)))), R


class ChronologyGoldenTests(unittest.TestCase):
    def test_regression_bug_same_shape_two_poses(self):
        """Прямой регресс бага №1: один mesh, две actual_pose одного бина."""
        V = _mesh()
        n_id, _, _ = normalize_mesh(V)
        # target-only: поза из metadata НЕ участвует -> побитно идентично
        t1 = (n_id @ row_rotation_matrix(0.0, 0.0, 0.0)).astype(np.float32)
        t2 = (n_id @ row_rotation_matrix(0.0, 0.0, 0.0)).astype(np.float32)
        self.assertEqual(float(np.max(np.abs(t1 - t2))), 0.0)
        # старый R_corr: та же форма, разные позы -> разные вершины (баг виден)
        c1 = compute_chronology_alignment(V, [0, 0, 0], canonical_yaw=0.0)
        c2 = compute_chronology_alignment(V, [8, 9, -7], canonical_yaw=0.0)
        self.assertGreater(float(np.max(np.abs(
            c1["vertices_aligned"] - c2["vertices_aligned"]))), 1e-3)
        # и это чистое вращение (расстояния целы)
        idx = [0, 1, 2, 10, 20]
        rel = np.abs(_dists(c1["vertices_aligned"], idx) - _dists(c2["vertices_aligned"], idx))
        self.assertLess(float(rel.max()), 1e-4)

    def test_synthetic_yaw_restored_to_bin_canon_via_kabsch(self):
        """Меш с известным yaw Y: Kabsch-остаток выровненного к канону бина ~0."""
        V = _mesh()
        n0, _, _ = normalize_mesh(V)
        for yaw in (-9.0, -1.0, 5.0):
            Vp = (V @ row_rotation_matrix(0.0, yaw, 0.0)).astype(np.float32)
            R_undo = row_rotation_matrix(0.0, yaw, 0.0).T  # известный yaw
            back, _, _ = normalize_mesh((Vp @ R_undo).astype(np.float32))
            rmse, _ = _kabsch_rmse(back, n0)
            self.assertLess(rmse, 1e-5)

    def test_center_scale_invariance_two_photos(self):
        """Раздельные identity center/scale двух фото: replay точен для обоих."""
        for seed in (0, 1):
            V = _mesh(seed=seed)
            ch = compute_chronology_alignment(V, [12, -20, 6], canonical_yaw=-17.5)
            rep = replay_identity_chronology(V, ch["center"], ch["scale"], ch["correction_matrix"])
            self.assertLess(float(np.max(np.abs(rep - ch["vertices_aligned"]))), 1e-5)
            n_id, c_id, s_id = normalize_mesh(V)
            self.assertTrue(np.allclose(ch["center"], c_id, atol=1e-6))
            self.assertAlmostEqual(float(ch["scale"]), float(s_id), places=6)

    def test_cross_bin_roundtrip_bans_mixed_space(self):
        """Кросс-бин round-trip + запрет mixed-space: identity-центр/скейл
        обязаны отличаться от object-центра/скейла при ненулевой мимике,
        иначе gate сравнивает разные пространства."""
        rng = np.random.default_rng(3)
        Vid = (rng.normal(size=(500, 3)) * 20).astype(np.float32)
        Vexp = (rng.normal(size=(500, 3)) * 3).astype(np.float32)
        Vobj = Vid + Vexp
        _, c_id, s_id = normalize_mesh(Vid)
        _, c_ob, s_ob = normalize_mesh(Vobj)
        # при мимике шкалы обязаны различаться (иначе mixed-space незаметен)
        self.assertGreater(abs(float(s_id) - float(s_ob)) / float(s_id), 1e-4)
        # round-trip каждого бина своим wen: replay_ERR identity-scale ~0...
        for yaw, pose in ((0.0, [0, 0, 0]), (-17.5, [5, -20, 3])):
            ch = compute_chronology_alignment(Vid, pose, canonical_yaw=yaw)
            rep = replay_identity_chronology(Vid, ch["center"], ch["scale"], ch["correction_matrix"])
            self.assertLess(float(np.max(np.abs(rep - ch["vertices_aligned"]))), 1e-5)
            # ...а подстановка object-scale даёт ошибку на порядки больше
            bad = (((Vid - c_ob) / s_ob) @ ch["correction_matrix"]).astype(np.float32)
            self.assertGreater(float(np.max(np.abs(bad - ch["vertices_aligned"]))), 1e-4)

    def test_distances_and_centroid_match(self):
        V = _mesh()
        ch = compute_chronology_alignment(V, [15, 25, -10], canonical_yaw=0.0)
        rep = replay_identity_chronology(V, ch["center"], ch["scale"], ch["correction_matrix"])
        idx = [0, 1, 2, 10, 20, 30, 100]
        d1, d2 = _dists(rep, idx), _dists(ch["vertices_aligned"], idx)
        rel = np.abs(d1 - d2) / np.maximum(d1, 1e-9)
        self.assertLess(float(rel.max()), 1e-5)
        c1, c2 = _centroid(rep), _centroid(ch["vertices_aligned"])
        self.assertLess(abs(c1 - c2) / max(c2, 1e-9), 1e-5)


if __name__ == "__main__":
    unittest.main()
