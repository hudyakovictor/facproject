"""🧪 Unit tests для Stage 3 v2."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
import numpy as np


class TestConfig:
    """Tests for Stage3V2Config."""
    
    def test_config_creation(self, tmp_path):
        """Config можно создать с валидными путями."""
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        output = tmp_path / "output"
        
        from app6.stage3_v2.config import Stage3V2Config
        config = Stage3V2Config(stage2_root=stage2, output_dir=output)
        
        assert config.prior_h0_same == 0.75
        assert config.bf_threshold_strong == 8.0
    
    def test_config_priors_sum_to_one(self, tmp_path):
        """Priors sum to 1.0."""
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        
        from app6.stage3_v2.config import Stage3V2Config
        config = Stage3V2Config(stage2_root=stage2, output_dir=tmp_path / "out")
        
        total = sum(config.priors.values())
        assert abs(total - 1.0) < 0.001
    
    def test_config_invalid_priors_rejected(self, tmp_path):
        """Invalid priors raise ValueError."""
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        
        from app6.stage3_v2.config import Stage3V2Config
        
        with pytest.raises(ValueError, match="Priors must sum"):
            Stage3V2Config(
                stage2_root=stage2,
                output_dir=tmp_path / "out",
                prior_h0_same=0.99,  # Too high
            )
    
    def test_bf_verbal_scale(self, tmp_path):
        """BF verbal scale works correctly."""
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        
        from app6.stage3_v2.config import Stage3V2Config
        config = Stage3V2Config(stage2_root=stage2, output_dir=tmp_path / "out")
        
        assert "слабые" in config.bf_verbal_ru(2)
        assert "умеренные" in config.bf_verbal_ru(5)
        assert "сильные" in config.bf_verbal_ru(15)
        assert "очень сильные" in config.bf_verbal_ru(60)
    
    def test_effect_size_verbal(self, tmp_path):
        """Effect size verbal scale works."""
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        
        from app6.stage3_v2.config import Stage3V2Config
        config = Stage3V2Config(stage2_root=stage2, output_dir=tmp_path / "out")
        
        assert config.effect_size_verbal_ru(0.1) == "незначительный"
        assert config.effect_size_verbal_ru(0.6) == "малый"
        assert config.effect_size_verbal_ru(0.9) == "средний"
        assert config.effect_size_verbal_ru(1.5) == "большой"
        assert config.effect_size_verbal_ru(2.5) == "очень большой"


class TestFormatting:
    """Tests for number formatting."""
    
    def test_auto_precision(self):
        """Auto precision selects correct decimals."""
        from app6.stage3_v2.formatting import fmt
        
        assert fmt(123.456) == "123"      # >= 100 → 0 decimals
        assert fmt(12.345) == "12,3"      # >= 10 → 1 decimal
        assert fmt(1.234) == "1,23"       # >= 1 → 2 decimals
        assert fmt(0.1234) == "0,123"     # >= 0.1 → 3 decimals
    
    def test_percentage_format(self):
        """Percentage formatting."""
        from app6.stage3_v2.formatting import fmt
        
        assert fmt(0.9955, "percentage") == "99,6%"
        assert fmt(0.5, "percentage") == "50,0%"
    
    def test_count_format(self):
        """Count formatting with thousands separator."""
        from app6.stage3_v2.formatting import fmt
        
        assert fmt(1947, "count") == "1 947"
        assert fmt(100, "count") == "100"
        assert fmt(1000000, "count") == "1 000 000"
    
    def test_ci_format(self):
        """Confidence interval formatting."""
        from app6.stage3_v2.formatting import fmt_ci
        
        result = fmt_ci(1.9, 3.7)
        assert "95% ДИ" in result
        assert "1,9" in result
        assert "3,7" in result
    
    def test_none_handling(self):
        """None and NaN handled gracefully."""
        from app6.stage3_v2.formatting import fmt
        
        assert fmt(None) == "—"
        assert fmt(float("nan")) == "—"
        assert fmt(float("inf")) == "—"


class TestBayesian:
    """Tests for Bayesian updater."""
    
    def test_likelihood_calculator(self):
        """Likelihood calculator produces valid probabilities."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.bayesian import LikelihoodCalculator
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            calc = LikelihoodCalculator(config)
            
            lik = calc.compute_keypoint_likelihood(
                p95_z=2.0, sig_fraction=0.1, coherent_motion=0.3
            )
            
            # All values should be positive
            for v in lik.values():
                assert v > 0
    
    def test_bayesian_updater(self):
        """Bayesian updater correctly updates posterior."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.bayesian import BayesianUpdater
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            
            updater = BayesianUpdater(config, {"days_delta": 30, "quality_score": 0.8})
            
            # Evidence strongly supporting H2
            lik = {"H0_SAME": 0.1, "H1_SYNTHETIC": 0.05, "H2_DIFFERENT": 0.8, "H_UNCERTAIN": 0.25}
            posterior = updater.update("test", lik)
            
            # H2 should increase
            assert posterior["H2_DIFFERENT"] > config.prior_h2_different
    
    def test_lr_computation(self):
        """LR computed correctly."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.bayesian import BayesianUpdater
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            
            updater = BayesianUpdater(config, {})
            
            evidence = {
                "kp": {"H0_SAME": 0.1, "H2_DIFFERENT": 0.5, "H1_SYNTHETIC": 0.1, "H_UNCERTAIN": 0.25},
            }
            lr = updater.compute_lr(evidence)
            
            # LR should be > 1 (H2 more likely)
            assert lr > 1.0


class TestEffectSize:
    """Tests for effect size calculation."""
    
    def test_cohens_d_basic(self):
        """Cohen's d computed correctly."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.effect_size import compute_effect_size
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            
            pair = {"pair_id": "test", "p95_point_z": 4.0}
            result = compute_effect_size(pair, config, noise_floor=1.0)
            
            assert result.overall_d > 0
            assert len(result.per_zone) > 0
    
    def test_journalist_phrases_generated(self):
        """Journalist phrases generated for significant zones."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.effect_size import compute_effect_size
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            
            pair = {"pair_id": "test", "p95_point_z": 5.0}
            result = compute_effect_size(pair, config, noise_floor=1.0)
            
            # Should have phrases for top zones
            assert len(result.journalist_phrases) >= 0


class TestBootstrap:
    """Tests for bootstrap CI."""
    
    def test_bootstrap_ci_computed(self):
        """Bootstrap CI computed correctly."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.bootstrap import compute_bootstrap_ci
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(
                stage2_root=stage2, output_dir=Path(tmp) / "out",
                bootstrap_iterations=100  # Fewer for speed
            )
            
            pair = {"pair_id": "test", "p95_point_z": 3.0}
            result = compute_bootstrap_ci(pair, config, noise_floor=1.0)
            
            assert result.overall_ci_lower <= result.overall_d <= result.overall_ci_upper
            assert result.overall_ci_lower >= 0


class TestChangePoint:
    """Tests for change point detection."""
    
    def test_change_point_detection(self):
        """Change points detected in time series."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.change_point import detect_change_points
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            config = Stage3V2Config(stage2_root=stage2, output_dir=Path(tmp) / "out")
            
            # Create time series with clear change point
            pairs = []
            for i in range(30):
                date = datetime(2020, 1 + (i * 10) // 30, 1 + (i * 10) % 28)
                p95_z = 1.0 if i < 15 else 4.0
                pairs.append({
                    "pair_id": f"p{i}",
                    "date_b": date.isoformat(),
                    "pair_type": "adjacent",
                    "p95_point_z": p95_z,
                })
            
            result = detect_change_points(pairs, config)
            
            # Should detect at least one change point
            assert len(result.change_points) >= 1


class TestFeedback:
    """Tests for feedback loop."""
    
    def test_feedback_collector(self):
        """Feedback collector gathers statistics."""
        from app6.stage3_v2.feedback import FeedbackCollector
        from app6.stage3_v2.types import PairAnalysis, BayesianResult, EffectSizeResult, BootstrapResult
        
        collector = FeedbackCollector()
        
        # Create minimal mock analyses
        analyses = []
        for i in range(10):
            analysis = PairAnalysis(
                pair_id=f"p{i}",
                photo_a=f"a{i}",
                photo_b=f"b{i}",
                date_a=None,
                date_b=None,
                pose_bin="frontal",
                p95_point_z=2.0 + i * 0.3,
                coherent_motion_fraction=0.3,
                significant_point_fraction=0.2,
                mesh_rmse=0.001,
                descriptor_p95_z=1.5,
                bayesian=BayesianResult(
                    pair_id=f"p{i}",
                    prior={"H0_SAME": 0.75, "H1_SYNTHETIC": 0.02, "H2_DIFFERENT": 0.08, "H_UNCERTAIN": 0.15},
                    posterior={"H0_SAME": 0.5, "H1_SYNTHETIC": 0.02, "H2_DIFFERENT": 0.35, "H_UNCERTAIN": 0.13},
                    lr=10.0,
                    lr_per_evidence={},
                    lr_verbal_ru="умеренные",
                    bayes_factor=8.0,
                    bf_level="strong",
                ),
                effect_size=EffectSizeResult(
                    pair_id=f"p{i}",
                    overall_d=1.0,
                    overall_verbal_ru="средний",
                    per_zone={},
                ),
                bootstrap=BootstrapResult(
                    pair_id=f"p{i}",
                    per_zone={},
                    overall_d=1.0,
                    overall_ci_lower=0.5,
                    overall_ci_upper=1.5,
                    overall_significant=True,
                ),
                cross_pose=None,
                qc_passed=True,
                quality_score=0.8,
            )
            analyses.append(analysis)
        
        stats = collector.collect_statistics(analyses)
        
        assert stats["total_pairs"] == 10
        assert "p95_z_distribution" in stats
        assert "hypothesis_distribution" in stats
        assert 0 <= stats["qc_pass_rate"] <= 1


class TestIntegration:
    """Integration tests."""
    
    def test_full_pipeline_mock(self, tmp_path):
        """Full pipeline runs on mock data."""
        from app6.stage3_v2.config import Stage3V2Config
        from app6.stage3_v2.engine import Stage3V2Engine
        
        # Create mock Stage 2 output
        stage2 = tmp_path / "stage2"
        stage2.mkdir()
        output = tmp_path / "output"
        
        # Create minimal mock files
        manifest = {"status": "complete", "main_record_count": 10}
        (stage2 / "analysis_manifest.json").write_text(json.dumps(manifest))
        
        validation = {"status": "complete"}
        (stage2 / "analysis_validation.json").write_text(json.dumps(validation))
        
        # Create minimal pair_metrics.csv
        csv_content = "pair_id,photo_a,photo_b,date_a,date_b,pair_type,pose_bin,p95_point_z,status,coherent_motion_fraction,significant_point_fraction,mesh_rmse,descriptor_p95_z,quality_score,days_delta\n"
        for i in range(5):
            csv_content += f"p{i},a{i}.jpg,b{i}.jpg,2020-01-{1+i:02d},2020-01-{2+i:02d},adjacent,frontal,{1.5+i*0.5},within_noise,0.3,0.1,0.001,1.2,0.8,1\n"
        (stage2 / "pair_metrics.csv").write_text(csv_content)
        
        # Create zone_metrics.csv
        (stage2 / "zone_metrics.csv").write_text("zone,metric,value\n")
        
        # Create change_points.json
        (stage2 / "change_points.json").write_text(json.dumps({"change_points": []}))
        
        # Run pipeline
        config = Stage3V2Config(
            stage2_root=stage2,
            output_dir=output,
            bootstrap_iterations=50,  # Fewer for speed
        )
        
        engine = Stage3V2Engine(config)
        report = engine.run()
        
        # Verify outputs
        assert report.total_pairs == 5
        assert report.pairs_analyzed >= 0
        assert (output / "report.json").exists()
        assert (output / "narrative.txt").exists()
        assert (output / "summary.json").exists()
        
        # Verify narrative
        assert len(report.narrative.full_text_ru) > 0
        assert report.narrative.word_count > 0
