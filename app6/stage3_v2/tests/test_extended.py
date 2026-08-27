"""🧪 Дополнительные тесты для stage3_v2 (cross-pose, legacy, narrative, edge cases)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest
import numpy as np


# ═══════════════════════════════════════════
# Test 20: Cross-Pose Analyzer
# ═══════════════════════════════════════════

class TestCrossPose:
    def test_cross_pose_no_confirmation(self):
        """Нет подтверждения если только один ракурс."""
        from app6.stage3_v2.cross_pose import CrossPoseAnalyzer
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.types import PairAnalysis, BayesianResult, EffectSizeResult, BootstrapResult

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")
            analyzer = CrossPoseAnalyzer(config)

            def _make_analysis(pid, pose, d, hyp="H2_DIFFERENT"):
                post = {"H0_SAME": 0.5, "H1_SYNTHETIC": 0.02, "H2_DIFFERENT": 0.35, "H_UNCERTAIN": 0.13}
                if hyp == "H0_SAME":
                    post = {"H0_SAME": 0.85, "H1_SYNTHETIC": 0.02, "H2_DIFFERENT": 0.05, "H_UNCERTAIN": 0.08}
                return PairAnalysis(
                    pair_id=pid, photo_a=f"a{pid}", photo_b=f"b{pid}",
                    date_a=datetime(2020, 6, 1), date_b=datetime(2020, 6, 5),
                    pose_bin=pose,
                    p95_point_z=4.0, coherent_motion_fraction=0.5,
                    significant_point_fraction=0.3, mesh_rmse=0.003,
                    descriptor_p95_z=3.0,
                    bayesian=BayesianResult(
                        pair_id=pid,
                        prior=config.priors, posterior=post,
                        lr=10.0, lr_per_evidence={}, lr_verbal_ru="умеренные",
                        bayes_factor=8.0, bf_level="strong",
                    ),
                    effect_size=EffectSizeResult(
                        pair_id=pid, overall_d=d, overall_verbal_ru="большой", per_zone={},
                    ),
                    bootstrap=BootstrapResult(
                        pair_id=pid, per_zone={}, overall_d=d,
                        overall_ci_lower=0.5, overall_ci_upper=1.5, overall_significant=True,
                    ),
                    cross_pose=None, qc_passed=True, quality_score=0.9,
                )

            primary = _make_analysis("p1", "frontal", 1.5)
            # Only same pose — no confirmation
            others = [_make_analysis("p2", "frontal", 1.3)]
            result = analyzer.find_confirmations(primary, [primary] + others)
            assert result is None  # No cross-pose confirmation

    def test_cross_pose_with_confirmation(self):
        """Подтверждение когда есть разные ракурсы."""
        from app6.stage3_v2.cross_pose import CrossPoseAnalyzer
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.types import PairAnalysis, BayesianResult, EffectSizeResult, BootstrapResult

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(
                stage2_root=s2, output_dir=Path(tmp) / "out",
                min_poses_for_confirmation=2,
            )
            analyzer = CrossPoseAnalyzer(config)

            def _make(pid, pose, d):
                post = {"H0_SAME": 0.3, "H1_SYNTHETIC": 0.02, "H2_DIFFERENT": 0.55, "H_UNCERTAIN": 0.13}
                return PairAnalysis(
                    pair_id=pid, photo_a=f"a{pid}", photo_b=f"b{pid}",
                    date_a=datetime(2020, 6, 1), date_b=datetime(2020, 6, 5),
                    pose_bin=pose, p95_point_z=4.0, coherent_motion_fraction=0.5,
                    significant_point_fraction=0.3, mesh_rmse=0.003, descriptor_p95_z=3.0,
                    bayesian=BayesianResult(
                        pair_id=pid, prior=config.priors, posterior=post,
                        lr=10.0, lr_per_evidence={}, lr_verbal_ru="умеренные",
                        bayes_factor=8.0, bf_level="strong",
                    ),
                    effect_size=EffectSizeResult(
                        pair_id=pid, overall_d=d, overall_verbal_ru="большой", per_zone={},
                    ),
                    bootstrap=BootstrapResult(
                        pair_id=pid, per_zone={}, overall_d=d,
                        overall_ci_lower=0.5, overall_ci_upper=1.5, overall_significant=True,
                    ),
                    cross_pose=None, qc_passed=True, quality_score=0.9,
                )

            primary = _make("p1", "frontal", 1.5)
            others = [_make("p2", "left_30", 1.3), _make("p3", "right_30", 1.4)]
            result = analyzer.find_confirmations(primary, [primary] + others)

            assert result is not None
            assert result.n_confirming == 2
            assert result.consistency > 0
            assert result.combined_lr > 0
            assert len(result.journalist_note_ru) > 0


# ═══════════════════════════════════════════
# Test 21-22: Legacy Integration
# ═══════════════════════════════════════════

class TestLegacy:
    def test_legacy_integrator_empty(self):
        """Legacy integrator works with no data."""
        from app6.stage3_v2.legacy import LegacyIntegrator
        from app6.stage3_v2.config import Stage3V2Config

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")
            integrator = LegacyIntegrator(config)

            assert integrator.get_legacy_record("any_photo") is None

    def test_legacy_correction_factors(self):
        """Legacy correction factors computed correctly."""
        from app6.stage3_v2.legacy import LegacyIntegrator
        from app6.stage3_v2.config import Stage3V2Config

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")
            integrator = LegacyIntegrator(config)

            record = {
                "photo_id": "test_photo",
                "posterior": {"H0_SAME": 0.2, "H1_SYNTHETIC": 0.05, "H2_DIFFERENT": 0.6, "H_UNCERTAIN": 0.15},
                "calibration_pair": {
                    "pose_distance_deg": 12.0,
                    "match_score": 0.65,
                },
            }

            correction = integrator.compute_correction_factor(record, "left_30")

            # H2 should be reduced (pose > 10 + match < 0.7)
            assert correction["H2_DIFFERENT"] < 1.0
            assert correction["H_UNCERTAIN"] >= 1.0
            assert 0 < correction["reliability"] <= 1.0


# ═══════════════════════════════════════════
# Test 23: Narrative Engine
# ═══════════════════════════════════════════

class TestNarrative:
    def test_narrative_generation(self):
        """Narrative engine generates Russian text."""
        from app6.stage3_v2.narrative import NarrativeEngine
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.types import (
            PairAnalysis, BayesianResult, EffectSizeResult, BootstrapResult,
            ZoneAnalysisResult, ZoneSummary, ChangePointResult,
        )

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")
            engine = NarrativeEngine(config)

            # Minimal analysis
            post = {"H0_SAME": 0.1, "H1_SYNTHETIC": 0.01, "H2_DIFFERENT": 0.78, "H_UNCERTAIN": 0.11}
            analysis = PairAnalysis(
                pair_id="p1", photo_a="a.jpg", photo_b="b.jpg",
                date_a=datetime(2020, 1, 1), date_b=datetime(2020, 6, 1),
                pose_bin="frontal", p95_point_z=4.5,
                coherent_motion_fraction=0.6, significant_point_fraction=0.35,
                mesh_rmse=0.003, descriptor_p95_z=3.5,
                bayesian=BayesianResult(
                    pair_id="p1", prior=config.priors, posterior=post,
                    lr=67.0, lr_per_evidence={"keypoint": 12}, lr_verbal_ru="сильные доказательства",
                    bayes_factor=42.0, bf_level="very_strong",
                ),
                effect_size=EffectSizeResult(
                    pair_id="p1", overall_d=1.8, overall_verbal_ru="очень большой",
                    per_zone={},
                    journalist_phrases=["Скулы: 2.8 мм — в 2.8 раз больше шума (d = 2.8, очень большой)"],
                ),
                bootstrap=BootstrapResult(
                    pair_id="p1", per_zone={}, overall_d=1.8,
                    overall_ci_lower=1.2, overall_ci_upper=2.4, overall_significant=True,
                ),
                cross_pose=None, qc_passed=True, quality_score=0.92,
            )

            zone_analysis = ZoneAnalysisResult(
                per_zone={
                    "bone_structure": ZoneSummary(
                        zone="bone_structure", zone_label_ru="Костные структуры",
                        n_pairs=10, h2_count=5, h2_rate=0.5, mean_d=1.5,
                        mean_lr=30.0, top_points=[], reliability_note_ru="Высокая",
                    ),
                },
                most_affected_zone="bone_structure",
                overall_h2_rate=0.5, overall_mean_d=1.5,
            )

            change_points = ChangePointResult(change_points=[], phases=[], overall_trend="stable")

            manifest = {"main_record_count": 100}

            narrative = engine.generate([analysis], zone_analysis, change_points, manifest)

            assert len(narrative.headline_ru) > 10
            assert len(narrative.full_text_ru) > 100
            assert narrative.word_count > 20
            assert len(narrative.disclaimers_ru) > 0
            # Check Russian text
            assert any(c >= 'а' and c <= 'я' for c in narrative.headline_ru)


# ═══════════════════════════════════════════
# Test 24: Edge Case — extreme LR values
# ═══════════════════════════════════════════

class TestEdgeCases:
    def test_extreme_p95_z(self):
        """Extreme p95_z doesn't crash."""
        from app6.stage3_v2.bayesian import LikelihoodCalculator
        from app6.stage3_v2.config import Stage3V2Config

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")
            calc = LikelihoodCalculator(config)

            # Very high z-score
            lik = calc.compute_keypoint_likelihood(p95_z=50.0, sig_fraction=0.99, coherent_motion=0.95)
            assert lik["H2_DIFFERENT"] > 0
            assert lik["H0_SAME"] > 0  # Should not be zero

            # Zero z-score
            lik = calc.compute_keypoint_likelihood(p95_z=0.0, sig_fraction=0.0, coherent_motion=0.0)
            assert lik["H0_SAME"] > 0
            assert lik["H2_DIFFERENT"] > 0

    def test_config_to_dict_serialization(self):
        """Config serializes to dict correctly."""
        from app6.stage3_v2.config import Stage3V2Config

        with tempfile.TemporaryDirectory() as tmp:
            s2 = Path(tmp) / "stage2"
            s2.mkdir()
            config = Stage3V2Config(stage2_root=s2, output_dir=Path(tmp) / "out")

            d = config.to_dict()
            assert isinstance(d, dict)
            assert "prior_h0_same" in d
            assert "bf_threshold_strong" in d
            assert "zone_weights" in d
            # Paths should be strings
            assert isinstance(d["stage2_root"], str)

    def test_report_serialization(self):
        """FullReport serializes to dict without errors."""
        from app6.stage3_v2.types import FullReport, NarrativeResult, ZoneAnalysisResult, ChangePointResult

        report = FullReport(
            schema_version="test",
            created_at=datetime.now(),
            stage2_root="/tmp/test",
            total_pairs=10,
            pairs_analyzed=8,
            pairs_with_changes=3,
            pair_analyses=[],
            zone_analysis=ZoneAnalysisResult(
                per_zone={}, most_affected_zone="bone_structure",
                overall_h2_rate=0.3, overall_mean_d=1.0,
            ),
            change_points=ChangePointResult(change_points=[], phases=[], overall_trend="stable"),
            narrative=NarrativeResult(
                headline_ru="Тест", lead_ru="Тест лид", exposition_ru="Экспозиция",
                rising_action_ru="Нарастание", climax_ru="Кульминация",
                falling_action_ru="Развитие", resolution_ru="Выводы",
                full_text_ru="Полный текст", word_count=2,
                key_findings=["finding 1"], disclaimers_ru=["disclaimer 1"],
            ),
            suggestions=[],
            processing_time_seconds=1.5,
            memory_peak_mb=100.0,
        )

        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["total_pairs"] == 10
        assert d["narrative"]["headline_ru"] == "Тест"
        # Should be JSON serializable
        json_str = json.dumps(d, ensure_ascii=False, default=str)
        assert len(json_str) > 0
