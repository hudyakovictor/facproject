from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from morphing.backend.aligner import (
    align_identity_mesh,
    group_pose_reference,
    pose_alignment_report,
)
from morphing.backend.identity import ALIGNMENT_SPACE, IdentityModel
from morphing.backend.pose_noise_model import (
    RESHOOT_PATH,
    noise_reference,
    pair_noise_reference,
    reshoot_reference,
)

# Заведомо несуществующий файл полос пересъёмок: тесты видео-слоя должны проверять
# именно видео-полосу, а не переопределяться боевым reshoot_bands.json из репозитория.
NO_RESHOOT = Path(__file__).resolve().parent / "no_such_reshoot_bands.json"


def fake_recon(yaw: float, pitch: float = 0.0, roll: float = 0.0, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    vertices = rng.normal(size=(400, 3)).astype(np.float32)
    return {
        "vertices_identity_only": vertices,
        "angles_deg": np.array([pitch, yaw, roll], dtype=np.float32),
        "ldm106_indices": np.arange(106, dtype=np.int64),
        "pose_bin": None,
    }


def canonicalize(vertices: np.ndarray, idx: np.ndarray | None = None) -> np.ndarray:
    """Ровно то, что делает aligner: центр и RMS-масштаб по 106 ландмаркам.

    idx — индексы ландмарков в сетке (у fake_recon это первые 106 вершин); нормировку
    считаем по ним, а применяем ко всей сетке.
    """
    pts = np.asarray(vertices, np.float64)
    subset = pts if idx is None else pts[np.asarray(idx, np.int64)]
    center = subset.mean(axis=0)
    d = subset - center
    scale = float(np.sqrt(np.mean(np.sum(d * d, axis=1))))
    return (pts - center) / scale


class AlignerPoseTests(unittest.TestCase):
    def test_mesh_is_normalized_by_landmark_rms(self) -> None:
        vertices, landmarks, scale = align_identity_mesh(fake_recon(12.0))
        # Нормировка RMS по 106 точкам, поэтому максимальный радиус больше 1 — это норма.
        self.assertAlmostEqual(float(np.sqrt(np.mean(np.sum(landmarks * landmarks, axis=1)))), 1.0, places=5)
        self.assertGreater(float(np.max(np.linalg.norm(vertices, axis=1))), 1.0)
        self.assertTrue(scale > 0)
        self.assertEqual(landmarks.shape, (106, 3))

    def test_alignment_ignores_the_reported_pose(self) -> None:
        """`vertices_identity_only` уже без позы: юстировка не должна зависеть от углов.

        Доворот каждого фото в «канон бина» не убирает ракурс, а добавляет его —
        на calibration_rakurs такая коррекция увеличивала разницу в 10 раз.
        """
        base = np.random.default_rng(7).normal(size=(400, 3)).astype(np.float32)
        left = {"vertices_identity_only": base, "angles_deg": np.array([0.0, -20.0, 0.0], np.float32),
                "ldm106_indices": np.arange(106, dtype=np.int64)}
        right = {"vertices_identity_only": base.copy(), "angles_deg": np.array([0.0, 20.0, 0.0], np.float32),
                 "ldm106_indices": np.arange(106, dtype=np.int64)}
        va, _, _ = align_identity_mesh(left)
        vb, _, _ = align_identity_mesh(right)
        np.testing.assert_allclose(va, canonicalize(base, left["ldm106_indices"]), rtol=0, atol=1e-5)
        self.assertLess(float(np.mean(np.linalg.norm(va - vb, axis=1))), 1e-6)

    def test_differential_rotation_would_inflate_the_delta(self) -> None:
        """Страхует от возврата к коррекции: тот же кейс с доворотом даёт большую «разницу»."""
        from app8.geometry import apply_pose_correction, full_pose_correction_matrix

        meshes = []
        for yaw in (-20.0, 20.0):
            recon = fake_recon(yaw, seed=3)
            r_corr = full_pose_correction_matrix(np.array([0.0, yaw, 0.0], np.float32),
                                                 np.array([0.0, 0.0, 0.0], np.float32))
            meshes.append(canonicalize(apply_pose_correction(recon["vertices_identity_only"], r_corr),
                                       recon["ldm106_indices"]))
        delta_rotated = float(np.mean(np.linalg.norm(meshes[0] - meshes[1], axis=1)))
        delta_aligned = float(np.mean(
            np.linalg.norm(align_identity_mesh(fake_recon(-20.0))[0] - align_identity_mesh(fake_recon(20.0))[0], axis=1)
        ))
        self.assertGreater(delta_rotated, 0.05)
        self.assertLess(delta_aligned, delta_rotated / 10.0)

    def test_group_reference_uses_bin_of_median_yaw(self) -> None:
        reference = group_pose_reference([fake_recon(-9.5), fake_recon(-8.0), fake_recon(-7.0)])
        self.assertEqual(reference["pose_bin"], "frontal")
        self.assertEqual(reference["canonical_yaw"], 0.0)
        self.assertEqual(reference["median_yaw"], -8.0)

    def test_report_flags_mismatched_pose_bins(self) -> None:
        faces = [fake_recon(-5.0), fake_recon(35.0)]
        report = pose_alignment_report(faces, group_pose_reference(faces))
        self.assertEqual(report["aligned_to"], "identity_object_space")
        self.assertFalse(report["same_pose_bin"])
        self.assertEqual(sorted(report["distinct_bins"]), ["frontal", "right_mid"])
        self.assertIn("Ракурсы не совпадают", report["warning"])

    def test_report_warns_on_wide_yaw_spread_inside_one_bin(self) -> None:
        faces = [fake_recon(11.0), fake_recon(24.0)]
        report = pose_alignment_report(faces, group_pose_reference(faces))
        self.assertTrue(report["same_pose_bin"])
        self.assertIn("разброс по yaw", report["warning"])


class NoiseModelTests(unittest.TestCase):
    def test_missing_calibration_is_reported_not_fabricated(self) -> None:
        result = noise_reference("frontal", 0.02, path=Path(tempfile.mkdtemp()) / "absent.json")
        self.assertFalse(result["available"])
        self.assertEqual(result["verdict"], "unknown")

    def test_verdicts_against_calibration_band(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps({
                "schema_version": "test",
                "units": "доли радиуса",
                "bins": {
                    "frontal": {
                        "people": 6,
                        "photos": 60,
                        "auc": 0.98,
                        "within": {"n": 100, "p50": 0.008, "p95": 0.015},
                        "within_close_pose": {"pairs": 40, "p50": 0.0024, "p95": 0.004},
                        "within_vertex_p95": {"n": 100, "p50": 0.021, "p95": 0.04},
                        "between_vertex_p95": {"n": 15, "p50": 0.09},
                        "between": {"n": 15, "p50": 0.06},
                        "drift": {"median_abs_dyaw_deg": 4.1},
                        "zones": {"nose": {"n": 100, "p50": 0.006, "p95": 0.011}},
                    }
                },
            }))
            self.assertEqual(noise_reference("frontal", 0.005, path=path, reshoot_path=NO_RESHOOT)["verdict"], "within_noise")
            self.assertEqual(noise_reference("frontal", 0.012, path=path, reshoot_path=NO_RESHOOT)["verdict"], "near_noise")
            loud = noise_reference("frontal", 0.04, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(loud["verdict"], "above_noise")
            self.assertEqual(loud["excess_over_noise_p50"], 0.032)
            # Отношение к границе полосы не клипуется: >1 честно говорит «реже 5%»,
            # а не превращается в «всё объяснено шумом».
            self.assertEqual(loud["band_ratio_p95"], round(0.04 / 0.015, 4))
            self.assertIn("видеокадрах", loud["band_status"])
            # Поля, по которым строятся вывод и шкала heatmap, читаются из калибровки.
            self.assertEqual(loud["floor_p50"], 0.0024)
            self.assertEqual(loud["noise_vertex_p95"], 0.021)
            self.assertEqual(loud["signal_vertex_p95"], 0.09)
            self.assertEqual(loud["median_abs_dyaw_deg"], 4.1)
            # Неоткалиброванный бин не должен выглядеть как «шума нет».
            self.assertFalse(noise_reference("left_profile", 0.04, path=path, reshoot_path=NO_RESHOOT)["available"])

    def test_drift_bucket_band_is_used_for_yaw_spread(self) -> None:
        """Пара с разбросом поз сравнивается с шумом этого разброса, а не «нулевого»."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps({
                "schema_version": "test",
                "bins": {
                    "frontal": {
                        "within": {"n": 270, "p50": 0.013, "p95": 0.06},
                        "drift": {"buckets": [
                            {"lo_deg": 0.0, "hi_deg": 1.0, "pairs": 6, "n": 6, "p50": 0.0034, "p95": 0.007},
                            {"lo_deg": 2.0, "hi_deg": 3.0, "pairs": 30, "n": 30, "p50": 0.009, "p95": 0.014},
                        ]},
                    }
                },
            }))
            # 0.012 при Δyaw 2.9° — выше шумового пола (0.0034), но в пределах кармана.
            drift = noise_reference("frontal", 0.012, yaw_spread_deg=2.9, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(drift["band_source"], "drift_bucket")
            self.assertEqual(drift["expected_p95"], 0.014)
            self.assertEqual(drift["verdict"], "near_noise")
            # Тот же Δ без информации о разбросе — плоская полоса бина.
            flat = noise_reference("frontal", 0.012, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(flat["band_source"], "bin_flat")
            self.assertEqual(flat["expected_p50"], 0.013)
            self.assertEqual(flat["verdict"], "within_noise")
            # Маленький карман (pairs < MIN_BUCKET_PAIRS) как границу не используем.
            thin = noise_reference("frontal", 0.012, yaw_spread_deg=0.5, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(thin["band_source"], "bin_flat")

    def test_above_noise_label_distinguishes_noise_from_person_difference(self) -> None:
        """>p95 — ещё не «разные люди»: подписываем по типичному межличностному расстоянию."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps({
                "schema_version": "test",
                "bins": {"frontal": {
                    "within": {"n": 100, "p50": 0.008, "p95": 0.015},
                    "between": {"n": 15, "p50": 0.06},
                }},
            }))
            slight = noise_reference("frontal", 0.02, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(slight["verdict"], "above_noise")
            self.assertEqual(slight["verdict_label"], "выше полосы, но меньше типичного различия людей")
            self.assertEqual(slight["delta_vs_between_p50"], 0.3333)
            strong = noise_reference("frontal", 0.08, path=path, reshoot_path=NO_RESHOOT)
            self.assertEqual(strong["verdict_label"], "выше типичного различия между людьми")

    def test_reshoot_band_overrides_video_band_when_measured(self) -> None:
        """Разброс независимых съёмок одного человека — оперативная полоса для фото.

        Видео-полоса серии (p95 0.015) на пересъёмках занижена: 0.012 — это типичная
        разница двух снимков одного лица, а не «шум выше границы».
        """
        with tempfile.TemporaryDirectory() as tmp:
            calib = Path(tmp) / "calibration.json"
            calib.write_text(json.dumps({
                "schema_version": "test",
                "bins": {"frontal": {"within": {"n": 100, "p50": 0.008, "p95": 0.015},
                                     "between": {"n": 15, "p50": 0.06}}},
            }))
            bands = Path(tmp) / "reshoot.json"
            bands.write_text(json.dumps({
                "schema_version": "morphing-reshoot-bands-v2",
                "population": "фотоархивы трёх людей, не входивших в калибровку",
                "near_days": 7,
                "min_pairs_to_use": 20,
                "bins": {"frontal": {
                    "near": {"pairs": 38, "p50": 0.02, "p95": 0.03, "max": 0.04, "median_dyaw": 4.1},
                    "spread": {"pairs": 300, "p50": 0.017, "p95": 0.031, "max": 0.045, "median_dyaw": 5.0},
                    "operative": True, "between_photos": {"n": 1400, "p50": 0.05},
                    "auc_near": 0.85, "auc_spread": 0.76,
                }},
            }))
            ref = noise_reference("frontal", 0.012, path=calib, reshoot_path=bands)
            self.assertEqual(ref["band_source"], "reshoot_photos")
            self.assertEqual(ref["verdict"], "within_noise")
            self.assertIn("разброса двух съёмок", ref["verdict_label"])
            # Видео-цифры не прячутся: видно, во сколько раз оперативная полоса шире.
            self.assertEqual(ref["video_p95"], 0.015)
            self.assertEqual(ref["band_ratio_p95"], 0.4)
            self.assertEqual(ref["video_band_ratio_p95"], 0.8)
            # Опора «до различия людей» берётся из межличностных пар фото, не центроидов.
            self.assertEqual(ref["between_p50"], 0.05)
            self.assertEqual(ref["between_centroid_p50"], 0.06)
            self.assertIn("пары фото разных людей", ref["between_basis"])
            self.assertIn("n=38", ref["band_status"])

    def test_reshoot_with_few_near_pairs_is_reference_not_boundary(self) -> None:
        """Мало ближних пар — полоса остаётся ориентиром: на 1–3 парах p95 это максимум."""
        with tempfile.TemporaryDirectory() as tmp:
            calib = Path(tmp) / "calibration.json"
            calib.write_text(json.dumps({
                "schema_version": "test",
                "bins": {"right_profile": {"within": {"n": 100, "p50": 0.008, "p95": 0.015},
                                           "between": {"n": 15, "p50": 0.06}}},
            }))
            bands = Path(tmp) / "reshoot.json"
            bands.write_text(json.dumps({
                "near_days": 7,
                "min_pairs_to_use": 20,
                "bins": {"right_profile": {
                    "near": {"pairs": 1},
                    "spread": {"pairs": 35, "p50": 0.0169, "p95": 0.0404, "median_dyaw": 3.2},
                    "operative": False, "between_photos": {"p50": 0.05},
                }},
            }))
            ref = noise_reference("right_profile", 0.02, path=calib, reshoot_path=bands)
            self.assertEqual(ref["band_source"], "bin_flat")
            self.assertEqual(ref["verdict"], "above_noise")
            self.assertTrue(ref["reshoot"]["available"])
            self.assertFalse(ref["reshoot"]["operative"])
            # Оговорка о переносимости и ориентир по дальним датам обязаны доехать до UI.
            self.assertIn("переносимость проверена", ref["band_status"])
            self.assertIn("границей вердикта он не является", ref["band_status"])

    def test_shipped_reshoot_band_is_applied_to_frontal(self) -> None:
        """Боевой артефакт: типичная пара фото одного лица не должна звать «шум выше границы»."""
        self.assertTrue(RESHOOT_PATH.exists(), "потеряны меры полос пересъёмок")
        frontal = reshoot_reference("frontal")
        self.assertTrue(frontal["available"])
        if not frontal["operative"]:
            self.skipTest("near-пар фронта меньше min_pairs_to_use — полоса не оперативна")
        self.assertGreaterEqual(frontal["near"]["pairs"], frontal["min_pairs"])
        ref = noise_reference("frontal", 0.0123, yaw_spread_deg=2.9)
        self.assertTrue(ref["available"])
        self.assertEqual(ref["band_source"], "reshoot_photos")
        self.assertLessEqual(ref["mean_delta"], ref["expected_p50"] * 1.0001)

    def test_person_baseline_is_not_claimed_where_people_are_not_separable(self) -> None:
        """В правом профиле 40% пар одного человека выше медианы разных людей:
        ярлык «выше различия между людьми» там ничего не утверждает."""
        with tempfile.TemporaryDirectory() as tmp:
            calib = Path(tmp) / "calibration.json"
            calib.write_text(json.dumps({
                "schema_version": "test",
                "bins": {"right_profile": {"within": {"n": 100, "p50": 0.008, "p95": 0.015},
                                           "between": {"n": 15, "p50": 0.06}}},
            }))
            bands = Path(tmp) / "reshoot.json"
            bands.write_text(json.dumps({
                "schema_version": "morphing-reshoot-bands-v2",
                "near_days": 7,
                "min_pairs_to_use": 20,
                "bins": {"right_profile": {
                    "near": {"pairs": 2},
                    "spread": {"pairs": 228, "p50": 0.0177, "p95": 0.0301, "median_dyaw": 5.0},
                    "operative": False, "between_photos": {"n": 475, "p50": 0.0191},
                    "auc_spread": 0.5611, "share_spread_above_between_p50": 0.4035,
                }},
            }))
            ref = noise_reference("right_profile", 0.0212, path=calib, reshoot_path=bands)
            self.assertEqual(ref["verdict"], "above_noise")
            self.assertGreater(ref["mean_delta"], ref["between_p50"])
            # Формально больше опоры — но опора в этом бине не работает, поэтому
            # «разные люди» не пишутся.
            self.assertIn("метрика их не разделяет", ref["verdict_label"])
            self.assertFalse(ref["person_baseline_separable"])
            self.assertEqual(ref["same_person_above_between_share"], 0.4035)

    def test_transfer_and_attribution_notes_travel_with_the_band(self) -> None:
        """Оговорки — часть ответа API, а не только README: без них «выше полосы» читают
        как «лица разные», а разброс пересъёмки приписывают освещению."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text(json.dumps({
                "schema_version": "test",
                "bins": {"frontal": {
                    "within": {"n": 100, "p50": 0.008, "p95": 0.015},
                    "between": {"n": 15, "p50": 0.06},
                }},
            }))
            ref = noise_reference("frontal", 0.02, path=path, reshoot_path=NO_RESHOOT)
        self.assertIn("переносимость", ref["transfer_note"])
        self.assertIn("видео-p95", ref["transfer_note"])
        self.assertIn("детектора/лендмарков", ref["attribution_note"])

    def test_mismatched_poses_cannot_use_noise_band(self) -> None:
        pose = {"same_pose_bin": False, "distinct_bins": ["frontal", "left_mid"]}
        metrics = {"euclidean_mean": 0.03, "zones": {}}
        result = pair_noise_reference(pose, metrics)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "pose_mismatch")


class IdentityPrototypeProvenanceTests(unittest.TestCase):
    def test_shipped_prototypes_declare_the_current_alignment_space(self) -> None:
        path = Path(__file__).resolve().parents[1] / "identity_prototypes.json"
        payload = json.loads(path.read_text())
        self.assertEqual((payload.get("meta") or {}).get("alignment"), ALIGNMENT_SPACE)
        IdentityModel.from_dict(payload)

    def test_prototypes_from_another_alignment_space_are_rejected(self) -> None:
        """Legacy-эталоны (без метки или из другого канона) не должны грузиться молча."""
        path = Path(__file__).resolve().parents[1] / "identity_prototypes.json"
        payload = json.loads(path.read_text())
        payload["meta"] = {"note": "без метки выравнивания"}
        with self.assertRaises(ValueError):
            IdentityModel.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
