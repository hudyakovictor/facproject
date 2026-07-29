"""ТЗ п.9–14 и инфраструктурные гейты: FDR, целостность, CSV, guard, архив."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app6.stage2.export import CsvHeaderError, stable_fieldnames, validate_csv_headers
from app6.stage2.fdr_control import DEFAULT_FDR_LEVEL, apply_fdr, benjamini_hochberg
from app6.stage2.integrity import IntegrityError, verify_integrity_hashes
from app6.stage2.legacy_bridge import bridge_coverage, normalize_photo_id, normalize_pose_bin
from app6.stage2.quality_gate import compensate_quality_disparity
from app6.stage2.same_day_gate import check_same_day_conflict
from app6.test_module.pipeline_guard import (
    PipelineOrderError,
    assert_predecessor_output,
    enforce_stage,
    required_predecessor,
)


class TestFDR:
    def test_level_matches_specification(self) -> None:
        """ТЗ п.9 требует FDR ≤ 0.05; движок использовал 0.10 (D7)."""
        assert DEFAULT_FDR_LEVEL == 0.05

    def test_uniform_p_values_yield_few_significant(self) -> None:
        p = np.random.default_rng(1).uniform(size=100)
        _, significant = benjamini_hochberg(p)
        assert int(significant.sum()) <= 5

    def test_all_small_p_values_significant(self) -> None:
        _, significant = benjamini_hochberg([0.001] * 20)
        assert int(significant.sum()) == 20

    def test_empty_input(self) -> None:
        adjusted, significant = benjamini_hochberg([])
        assert adjusted.size == 0 and significant.size == 0

    def test_monotonic_in_p(self) -> None:
        p = sorted(np.random.default_rng(2).uniform(size=40))
        adjusted, _ = benjamini_hochberg(p)
        assert all(adjusted[i] <= adjusted[i + 1] + 1e-12 for i in range(39))

    def test_nonfinite_rejected(self) -> None:
        with pytest.raises(ValueError):
            benjamini_hochberg([0.5, float("nan")])

    def test_rows_without_p_are_not_tested(self) -> None:
        rows = [{"mt_p_approx": 0.001}, {"other": 1}]
        report = apply_fdr(rows)
        assert report["test_count"] == 1
        assert rows[1]["fdr_status"] == "not_tested"


class TestIntegrity:
    HASHES = {"dataset_hash": "a", "code_hash": "b", "model_hash": "c", "config_hash": "d"}

    def test_matching_hashes_pass(self) -> None:
        assert verify_integrity_hashes(self.HASHES, dict(self.HASHES))["status"] == "ok"

    def test_dataset_mismatch_blocks(self) -> None:
        tampered = {**self.HASHES, "dataset_hash": "X"}
        with pytest.raises(IntegrityError):
            verify_integrity_hashes(self.HASHES, tampered)

    def test_missing_key_blocks(self) -> None:
        partial = {k: v for k, v in self.HASHES.items() if k != "model_hash"}
        with pytest.raises(IntegrityError):
            verify_integrity_hashes(self.HASHES, partial)

    def test_non_strict_reports_without_raising(self) -> None:
        tampered = {**self.HASHES, "code_hash": "Y"}
        report = verify_integrity_hashes(self.HASHES, tampered, strict=False)
        assert report["status"] == "blocked"
        assert report["mismatched"] == ["code_hash"]


class TestCsvContract:
    def test_all_fields_present(self) -> None:
        assert validate_csv_headers([{"a": 1, "b": 2}], ["a", "b"]) is True

    def test_missing_field_strict_raises(self) -> None:
        with pytest.raises(CsvHeaderError):
            validate_csv_headers([{"a": 1}], ["a", "b"])

    def test_missing_field_non_strict_returns_false(self) -> None:
        assert validate_csv_headers([{"a": 1}], ["a", "b"], strict=False) is False

    def test_column_order_is_stable(self) -> None:
        """D9: порядок зависел от порядка ключей первой строки."""
        first = stable_fieldnames([{"b": 2, "a": 1}], preferred=["a"])
        second = stable_fieldnames([{"a": 1, "b": 2}], preferred=["a"])
        assert first == second == ["a", "b"]

    def test_empty_expected_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_csv_headers([{"a": 1}], [])


class TestQualityGate:
    QUALITIES = {
        "vhs": {"pixels": 320 * 240, "quality_limited": True},
        "hd": {"pixels": 4000 * 3000, "quality_limited": False},
        "a": {"pixels": 1920 * 1080}, "b": {"pixels": 1920 * 1080},
    }

    def test_disparity_detected(self) -> None:
        out = compensate_quality_disparity(
            {"photo_a": "vhs", "photo_b": "hd", "texture_score_0_1": 0.1}, self.QUALITIES)
        assert out["quality_disparity"] is True
        assert out["texture_conclusions_allowed"] is False

    def test_equal_quality_not_flagged(self) -> None:
        out = compensate_quality_disparity(
            {"photo_a": "a", "photo_b": "b", "texture_score_0_1": 0.31}, self.QUALITIES)
        assert out["quality_disparity"] is False
        assert out["texture_score_0_1"] == 0.31

    def test_texture_score_floored_at_neutral(self) -> None:
        """Размытый архив не должен читаться как признак материала."""
        out = compensate_quality_disparity(
            {"photo_a": "vhs", "photo_b": "hd", "texture_score_0_1": 0.02}, self.QUALITIES)
        assert out["texture_score_0_1"] == 0.5

    def test_missing_photo_ids_fail_closed(self) -> None:
        with pytest.raises(KeyError):
            compensate_quality_disparity({"photo_a": "vhs"}, self.QUALITIES)


class TestSameDayGate:
    @staticmethod
    def _rows(values):
        return [{"date_a": "2019-03-18", "date_b": "2019-03-18", "ldm134_rmse": v,
                 "photo_a": f"p{i}", "photo_b": f"q{i}", "pair_id": f"pair{i}"}
                for i, v in enumerate(values)]

    def test_outlier_flagged(self) -> None:
        conflicts = check_same_day_conflict(
            self._rows([0.004, 0.0042, 0.0038, 0.0041, 0.0039, 0.0040, 0.045]))
        assert len(conflicts) == 1
        assert conflicts[0]["status"] == "SAME_DAY_IDENTITY_CONFLICT"
        assert conflicts[0]["not_a_verdict"] is True

    def test_consistent_day_has_no_conflict(self) -> None:
        assert check_same_day_conflict(
            self._rows([0.004, 0.0041, 0.0039, 0.0040, 0.0042, 0.0038])) == []

    def test_insufficient_pairs_returns_empty(self) -> None:
        assert check_same_day_conflict(self._rows([0.004, 0.9])) == []

    def test_different_dates_ignored(self) -> None:
        rows = self._rows([0.004] * 6)
        rows[0]["date_b"] = "2020-01-01"
        assert all(c["photo_a"] != "p0" for c in check_same_day_conflict(rows))


class TestLegacyBridge:
    def test_all_nine_bins_map(self) -> None:
        """D12: 6 из 9 ракурсов не сопоставлялись."""
        legacy = ["frontal", "left_profile", "right_profile",
                  "left_threequarter_light", "right_threequarter_light",
                  "left_threequarter_mid", "right_threequarter_mid",
                  "left_threequarter_deep", "right_threequarter_deep"]
        coverage = bridge_coverage(legacy)
        assert coverage["coverage_fraction"] == 1.0
        assert coverage["unmapped_count"] == 0

    def test_bin_translation(self) -> None:
        assert normalize_pose_bin("left_threequarter_deep") == "left_deep"
        assert normalize_pose_bin("frontal") == "frontal"

    def test_unknown_bin_returns_none(self) -> None:
        assert normalize_pose_bin("frontal_yaw15") is None

    def test_legacy_photo_ids_normalized(self) -> None:
        assert normalize_photo_id("1999_08_12 (2)") == "1999_08_12_2"
        assert normalize_photo_id("1999_08_16(2)") == "1999_08_16_2"
        assert normalize_photo_id("2019_03_18") == "2019_03_18"


class TestPipelineGuard:
    def test_all_stages_allowed_in_order(self) -> None:
        for stage in ("stage1", "stage2", "stage2b", "stage3"):
            assert enforce_stage(stage)["status"] == "allowed"

    def test_unknown_stage_rejected(self) -> None:
        with pytest.raises(ValueError):
            enforce_stage("stage9")

    def test_predecessor_chain(self) -> None:
        assert required_predecessor("stage1") is None
        assert required_predecessor("stage2") == "stage1"
        assert required_predecessor("stage3") == "stage2b"

    def test_missing_predecessor_output_blocks(self, tmp_path: Path) -> None:
        with pytest.raises(PipelineOrderError):
            assert_predecessor_output("stage2", tmp_path)

    def test_incomplete_manifest_blocks(self, tmp_path: Path) -> None:
        (tmp_path / "analysis_manifest.json").write_text('{"status": "partial"}', encoding="utf-8")
        with pytest.raises(PipelineOrderError):
            assert_predecessor_output("stage3", tmp_path)

    def test_complete_manifest_passes(self, tmp_path: Path) -> None:
        (tmp_path / "analysis_manifest.json").write_text('{"status": "complete"}', encoding="utf-8")
        assert assert_predecessor_output("stage3", tmp_path)["status"] == "ok"
