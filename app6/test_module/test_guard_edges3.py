"""🔒 GUARD → Третья серия краевых тестов (docs/final).

Покрывает области, не затронутые предыдущими тестами:
  1. Quality gate: resolution_ratio и компенсация дисбаланса качества.
  2. Metric registry: 100 каналов, отсутствующие данные не фабрикуются.
  3. Pose-leakage diagnostic: недостаток данных / сильная корреляция.
  4. Baseline-return: статистика разворота векторов.
  5. Cross-bin corroboration + агрегация событий по источникам.
  6. Validation contract: fail-closed проверки финального вывода.
  7. Expression QC: детекция улыбки/рта и исключение мимических зон.
  8. FDR control: BH-процедура и not_tested вместо p=1.
  9. API pair_metrics: поиск пары, отсутствующие артефакты.
  10. API report: withheld-префиксы и секции отчёта.

Все тесты самодостаточны и не требуют весов 3DDFA или фотодатасета.
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app6.api.pair_metrics import (
    find_pair_row,
    list_stage2_artifacts,
    load_pair_metrics,
    load_stage2_artifact,
)
from app6.api.report import load_report_section, load_report_summary, report_available
from app6.stage2.baseline_return import _reversal_stats
from app6.stage2.corroboration import aggregate_events, apply_cross_bin_corroboration
from app6.stage2.expression_qc import detect_expression, exclude_mimic_zones, expression_magnitude
from app6.stage2.fdr_control import apply_fdr, benjamini_hochberg
from app6.stage2.metric_registry import (
    build_metric_catalog,
    evidence_metric_channel,
    validate_registry,
)
from app6.stage2.pose_leakage import pose_leakage_diagnostic
from app6.stage2.quality_gate import compensate_quality_disparity, resolution_ratio
from app6.stage2.validation import validate_analysis_contract


class QualityGateTests(unittest.TestCase):
    """Идея 1: quality gate."""

    def test_resolution_ratio_rejects_invalid(self):
        self.assertEqual(resolution_ratio(100, 50), 2.0)
        with self.assertRaises(ValueError):
            resolution_ratio(0, 50)
        with self.assertRaises(ValueError):
            resolution_ratio(float("nan"), 50)

    def test_quality_limited_uses_neutral_texture(self):
        out = compensate_quality_disparity(
            {"photo_a": "A", "photo_b": "B", "texture_score_0_1": 0.1},
            {"A": {"pixels": 1000, "texture_score_0_1": 0.1, "quality_limited": True},
             "B": {"pixels": 1000, "texture_score_0_1": 0.9, "quality_limited": False}},
        )
        self.assertEqual(out["texture_score_0_1"], 0.5)  # нейтральный уровень
        self.assertFalse(out["texture_conclusions_allowed"])
        self.assertEqual(out["quality_gate_reason"], "quality_limited")

    def test_missing_quality_metadata_fails_closed(self):
        pair = compensate_quality_disparity(
            {"photo_a": "A", "photo_b": "B", "texture_score_0_1": 0.1},
            {"A": {}, "B": {}},
        )
        self.assertTrue(pair["quality_limited"])
        self.assertFalse(pair["texture_conclusions_allowed"])

    def test_resolution_disparity_flagged(self):
        pair = compensate_quality_disparity(
            {"photo_a": "A", "photo_b": "B", "texture_score_0_1": 0.8},
            {"A": {"pixels": 1000, "texture_score_0_1": 0.8, "quality_limited": False},
             "B": {"pixels": 10000, "texture_score_0_1": 0.8, "quality_limited": False}},
        )
        self.assertTrue(pair["quality_disparity"])
        self.assertFalse(pair["texture_conclusions_allowed"])


class MetricRegistryTests(unittest.TestCase):
    """Идея 2: metric registry."""

    def test_registry_is_valid(self):
        self.assertEqual(validate_registry(), [])

    def test_missing_data_is_not_fabricated(self):
        catalog = build_metric_catalog([{"p95_point_z": 3.0}])
        entry = next(m for m in catalog["metrics"] if m["name"] == "mesh_rmse")
        self.assertEqual(entry["status"], "disabled_missing_data")
        self.assertNotIn("0", str(entry["reason"]))

    def test_texture_is_visualization_only(self):
        catalog = build_metric_catalog([{"texture_image_status": "ok"}])
        entry = next(m for m in catalog["metrics"] if m["name"] == "texture_image_status")
        self.assertEqual(entry["evidence_role"], "visualization_only")

    def test_evidence_channel_excludes_texture(self):
        row = {"p95_point_z": 3.0, "texture_image_status": "ok"}
        channel = evidence_metric_channel(row)
        self.assertIn("p95_point_z", channel)
        self.assertNotIn("texture_image_status", channel)


class PoseLeakageTests(unittest.TestCase):
    """Идея 3: pose leakage diagnostic."""

    def test_insufficient_data(self):
        rows = [{"pose_distance": 1.0, "ldm134_rmse": 0.5}]
        res = pose_leakage_diagnostic(rows)
        self.assertEqual(res["metrics"]["ldm134_rmse"]["status"], "insufficient_data")

    def test_strong_pose_dependence_flagged(self):
        rows = [{"pose_distance": float(i), "ldm134_rmse": float(i) * 2.0}
                for i in range(20)]
        res = pose_leakage_diagnostic(rows)
        self.assertEqual(res["status"], "pose_leakage_candidates_present")
        self.assertIn("ldm134_rmse", res["flagged_metrics"])

    def test_flat_data_no_leakage(self):
        rows = [{"pose_distance": float(i), "ldm134_rmse": 1.0} for i in range(20)]
        res = pose_leakage_diagnostic(rows)
        self.assertEqual(res["status"], "no_strong_pose_leakage_detected")


class BaselineReturnTests(unittest.TestCase):
    """Идея 4: baseline return stats."""

    def test_mismatched_shapes_return_zeros(self):
        stats = _reversal_stats(np.zeros((10, 3)), np.zeros((5, 3)))
        self.assertEqual(stats["common_vector_count"], 0)
        self.assertEqual(stats["opposite_fraction"], 0.0)

    def test_opposite_vectors_detected(self):
        v1 = np.tile(np.array([1.0, 0.0, 0.0]), (40, 1))
        v2 = np.tile(np.array([-1.0, 0.0, 0.0]), (40, 1))
        stats = _reversal_stats(v1, v2)
        self.assertGreaterEqual(stats["common_vector_count"], 30)
        self.assertGreaterEqual(stats["opposite_fraction"], 0.45)
        self.assertLessEqual(stats["median_cosine"], -0.20)


class CrossBinCorroborationTests(unittest.TestCase):
    """Идея 5: cross-bin corroboration + aggregate."""

    def _candidate(self, pid, pose, date_a, date_b, fam="fam1", src="src1"):
        return {"pair_id": pid, "pair_type": "adjacent", "pose_bin": pose,
                "date_a": date_a, "date_b": date_b, "status": "coherent_jump_candidate",
                "descriptor_top_families": fam, "source_group_b": src}

    def test_corroborated_in_multiple_pose_bins(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-01-15", "2020-02-10", src="src2"),
            self._candidate("C", "right", "2020-01-20", "2020-02-15", src="src3"),
        ]
        apply_cross_bin_corroboration(rows)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"],
                         "corroborated_multiple_pose_bins")
        self.assertGreaterEqual(rows[0]["cross_bin_support_pose_count"], 2)

    def test_reversed_support_interval_is_not_corroboration(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-03-01", "2020-02-10", src="src2"),
        ]
        apply_cross_bin_corroboration(rows)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "not_corroborated")
        self.assertEqual(rows[0]["cross_bin_support_count"], 0)

    def test_reversed_primary_interval_is_not_corroborated(self):
        rows = [
            self._candidate("A", "frontal", "2020-03-01", "2020-02-01"),
            self._candidate("B", "left", "2020-01-01", "2020-02-10", src="src2"),
        ]
        rows[0].update({
            "cross_bin_support_pose_bins": "stale",
            "cross_bin_independent_source_count": 4,
            "cross_bin_family_matched_count": 3,
        })
        apply_cross_bin_corroboration(rows)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "invalid_date_order")
        self.assertEqual(rows[0]["cross_bin_support_count"], 0)
        self.assertEqual(rows[0]["cross_bin_support_pose_bins"], "")
        self.assertEqual(rows[0]["cross_bin_independent_source_count"], 0)
        self.assertEqual(rows[0]["cross_bin_family_matched_count"], 0)

    def test_unavailable_date_clears_stale_corroboration_fields(self):
        row = self._candidate("A", "frontal", "2020-01-01", "invalid")
        row.update({
            "cross_bin_support_count": 2,
            "cross_bin_support_pose_count": 2,
            "cross_bin_support_pose_bins": "left|right",
            "cross_bin_independent_source_count": 2,
            "cross_bin_family_matched_count": 2,
        })
        apply_cross_bin_corroboration([row])
        self.assertEqual(row["cross_bin_corroboration_status"], "date_unavailable")
        self.assertEqual(row["cross_bin_support_count"], 0)
        self.assertEqual(row["cross_bin_support_pose_count"], 0)
        self.assertEqual(row["cross_bin_support_pose_bins"], "")
        self.assertEqual(row["cross_bin_independent_source_count"], 0)
        self.assertEqual(row["cross_bin_family_matched_count"], 0)

    def test_support_at_window_boundary_is_included(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-01-15", "2020-03-17", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "corroborated_one_pose_bin")

    def test_support_outside_window_is_excluded(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-01-15", "2020-03-18", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "not_corroborated")

    def test_zero_day_window_requires_same_target_date(self):
        same_day = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-02-01", "2020-02-01", src="src2"),
        ]
        apply_cross_bin_corroboration(same_day, window_days=0)
        self.assertEqual(same_day[0]["cross_bin_corroboration_status"], "corroborated_one_pose_bin")

        next_day = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-02-02", "2020-02-02", src="src2"),
        ]
        apply_cross_bin_corroboration(next_day, window_days=0)
        self.assertEqual(next_day[0]["cross_bin_corroboration_status"], "not_corroborated")

    def test_one_day_window_includes_next_target_date(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-02-01", "2020-02-02", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=1)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "corroborated_one_pose_bin")

    def test_support_interval_at_twice_window_is_included(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-03-31"),
            self._candidate("B", "left", "2020-01-01", "2020-03-31", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "corroborated_one_pose_bin")

    def test_support_interval_over_twice_window_is_excluded(self):
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-04-01"),
            self._candidate("B", "left", "2020-01-01", "2020-04-01", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "not_corroborated")

    def test_ninety_day_window_includes_distant_corroboration(self):
        """ER-163: окно 90 дней должно включать события с большим разбросом дат."""
        rows = [
            self._candidate("A", "frontal", "2020-01-01", "2020-02-01"),
            self._candidate("B", "left", "2020-01-15", "2020-04-29", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=90)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"],
                         "corroborated_one_pose_bin")

    def test_non_overlapping_intervals_not_corroborated(self):
        """ER-163 N3b: интервалы должны пересекаться; одного соседства дат B недостаточно."""
        rows = [
            # primary: 2020-01-01 – 2020-02-01
            self._candidate("A", "front", "2020-01-01", "2020-02-01"),
            # support: 2020-06-01 – 2020-06-30 — не пересекается
            self._candidate("B", "left", "2020-06-01", "2020-06-30", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"], "not_corroborated")

    def test_overlapping_intervals_are_corroborated(self):
        """ER-163 N3b: интервалы пересекаются — поддержка засчитывается."""
        rows = [
            # primary: 2020-01-01 – 2020-03-01 (~60 дней)
            self._candidate("A", "front", "2020-01-01", "2020-03-01"),
            # support: 2020-02-01 – 2020-02-10 — полностью внутри окна и пересекается
            self._candidate("B", "left", "2020-02-01", "2020-02-10", src="src2"),
        ]
        apply_cross_bin_corroboration(rows, window_days=45)
        self.assertEqual(rows[0]["cross_bin_corroboration_status"],
                         "corroborated_one_pose_bin")

    def test_aggregate_reports_independence(self):
        rows = [
            {"pair_type": "adjacent", "date_b": "2020-02-01", "pose_bin": "frontal",
             "source_group_b": "src1", "status": "coherent_jump_candidate"},
            {"pair_type": "adjacent", "date_b": "2020-02-01", "pose_bin": "left",
             "source_group_b": "src2", "status": "within_reconstruction_noise"},
        ]
        events = aggregate_events(rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["independence_status"], "multiple_known_sources")
        self.assertEqual(events[0]["candidate_count"], 1)


class ValidationContractTests(unittest.TestCase):
    """Идея 6: validation contract fail-closed."""

    def test_missing_required_file(self):
        with tempfile.TemporaryDirectory() as td:
            errors = validate_analysis_contract(
                Path(td), required_files=["pair_metrics.csv"], rows=[], changes=[],
                evidence_packets=[], public_safety={"status": "pass"})
            self.assertTrue(any(e.startswith("missing ") for e in errors))

    def test_visualization_metric_leak_detected(self):
        with tempfile.TemporaryDirectory() as td:
            errors = validate_analysis_contract(
                Path(td), required_files=[], rows=[], changes=[],
                evidence_packets=[{"pair_id": "p",
                                   "registered_metric_channel": {"texture_image_status": "ok"}}],
                public_safety={"status": "pass"})
            self.assertTrue(any(e.startswith("visualization_metric_leaked_into_evidence")
                                for e in errors))

    def test_public_safety_failed(self):
        with tempfile.TemporaryDirectory() as td:
            errors = validate_analysis_contract(
                Path(td), required_files=[], rows=[], changes=[],
                evidence_packets=[], public_safety={"status": "fail"})
            self.assertIn("public_safety_failed", errors)


class ExpressionQcTests(unittest.TestCase):
    """Идея 7: expression QC."""

    def _smile(self):
        pts = np.zeros((106, 3))
        pts[74] = [0.0, 0.0, 0.0]   # eye left
        pts[77] = [1.0, 0.0, 0.0]   # eye right → interocular = 1
        pts[84] = [0.3, 0.6, 0.0]   # mouth left (raised corners)
        pts[90] = [0.7, 0.6, 0.0]   # mouth right
        pts[87] = [0.5, 0.5, 0.0]   # mouth upper
        pts[93] = [0.5, 0.55, 0.0]  # mouth lower
        return pts

    def test_wrong_shape_rejected(self):
        with self.assertRaises(ValueError):
            expression_magnitude(np.zeros((5, 3)))

    def test_smile_detected(self):
        res = detect_expression(self._smile())
        self.assertTrue(res["smile_detected"])
        self.assertTrue(res["expression_active"])

    def test_mimic_zones_zeroed_bone_preserved(self):
        weights = {"cheek_soft_L": 1.0, "jaw_L": 1.0, "orbit_L": 1.0, "chin": 1.0}
        res = exclude_mimic_zones(self._smile(), weights)
        self.assertEqual(res["zone_weights"]["cheek_soft_L"], 0.0)
        self.assertEqual(res["zone_weights"]["jaw_L"], 0.0)
        self.assertEqual(res["zone_weights"]["orbit_L"], 1.0)
        self.assertEqual(res["zone_weights"]["chin"], 1.0)
        self.assertIn("orbit_L", res["bone_zones_preserved"])


class FdrControlTests(unittest.TestCase):
    """Идея 8: FDR control."""

    def test_bh_rejects_invalid_p(self):
        with self.assertRaises(ValueError):
            benjamini_hochberg([0.1, float("nan")])
        with self.assertRaises(ValueError):
            benjamini_hochberg([0.1, 1.5])

    def test_bh_marks_significant(self):
        q, sig = benjamini_hochberg([0.001, 0.001, 0.9])
        self.assertTrue(sig[0])
        self.assertTrue(sig[1])
        self.assertFalse(sig[2])

    def test_apply_fdr_marks_not_tested(self):
        rows = [{"mt_p_approx": 0.001}, {"mt_p_approx": None}]
        apply_fdr(rows)
        self.assertEqual(rows[0]["fdr_status"], "tested")
        self.assertEqual(rows[1]["fdr_status"], "not_tested")
        self.assertFalse(rows[1]["fdr_significant"])


class ApiPairMetricsTests(unittest.TestCase):
    """Идея 9: API pair_metrics."""

    def _write_pairs(self, root):
        with (root / "pair_metrics.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=["photo_a", "photo_b", "pose_bin"])
            w.writeheader()
            w.writerow({"photo_a": "A", "photo_b": "B", "pose_bin": "frontal"})

    def test_find_pair_reversed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_pairs(root)
            row = find_pair_row(root, "B", "A")
            self.assertIsNotNone(row)
            self.assertEqual(row["_reversed"], "True")

    def test_load_pair_metrics_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_pairs(root)
            with self.assertRaises(KeyError):
                load_pair_metrics(root, "X", "Y")

    def test_unknown_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(KeyError):
                load_stage2_artifact(Path(td), "not_a_real_artifact")

    def test_missing_artifacts_listed_as_absent(self):
        with tempfile.TemporaryDirectory() as td:
            artifacts = list_stage2_artifacts(Path(td))
            self.assertTrue(artifacts)
            self.assertTrue(all(a["present"] is False for a in artifacts))


class ApiReportTests(unittest.TestCase):
    """Идея 10: API report."""

    def test_summary_reports_withheld_prefixes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "report_data.json").write_text(
                json.dumps({"schema_version": "v1", "summary": {"x": 1}}), encoding="utf-8")
            summary = load_report_summary(root)
            self.assertIn("texture_", summary["withheld_column_prefixes"])
            self.assertIn("uv_", summary["withheld_column_prefixes"])
            self.assertIn("status_semantics", summary)

    def test_unknown_section_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "report_data.json").write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaises(KeyError):
                load_report_section(root, "not_a_section")

    def test_report_available(self):
        self.assertFalse(report_available(None))
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(report_available(Path(td)))
            (Path(td) / "report_data.json").write_text("{}", encoding="utf-8")
            self.assertTrue(report_available(Path(td)))


if __name__ == "__main__":
    unittest.main()