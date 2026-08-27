"""🎯 Stage 3 v2 Engine — главный оркестратор аналитического движка.

Pipeline:
  1. Load Stage 2 output
  2. Fast Pass (опционально) → statistics + suggestions
  3. Full Pass → evidence modules
  4. Bayesian → LR + Effect Size + Change Point + Bootstrap CI
  5. Zone aggregation + Cross-pose confirmation
  6. Narrative Engine → journalist text
  7. Export (JSON, Markdown, PDF)

Архитектура: Bayesian ВНУТРИ, LR СНАРУЖИ.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from datetime import datetime

from .config import Stage3V2Config
from .types import (
    PairAnalysis, BayesianResult, EffectSizeResult, BootstrapResult,
    ChangePointResult, ZoneAnalysisResult, ZoneSummary,
    NarrativeResult, FullReport, CalibrationSuggestion
)
from .loader import Stage2Loader, load_stage2_data
from .bayesian import analyze_pair_bayesian, BayesianUpdater, LikelihoodCalculator
from .effect_size import compute_effect_size, ZONE_LABELS_RU
from .bootstrap import compute_bootstrap_ci
from .change_point import detect_change_points
from .narrative import NarrativeEngine
from .formatting import fmt


class Stage3V2Engine:
    """Главный движок Stage 3 v2."""
    
    def __init__(self, config: Stage3V2Config):
        self.config = config
        self.loader = Stage2Loader(config.stage2_root)
        self.narrative = NarrativeEngine(config)
    
    def run(self) -> FullReport:
        """
        Запустить полный pipeline Stage 3 v2.
        
        Returns:
            FullReport с полными результатами
        """
        start_time = time.time()
        
        # ═══════════════════════════════════════════
        # STEP 1: Load Stage 2 output
        # ═══════════════════════════════════════════
        print("📥 Loading Stage 2 output...")
        pairs, manifest, change_points_raw = load_stage2_data(self.config.stage2_root)
        print(f"   Loaded {len(pairs)} pairs")
        
        # ═══════════════════════════════════════════
        # STEP 2: Fast Pass (optional)
        # ═══════════════════════════════════════════
        suggestions = []
        if self.config.fast_pass_enabled:
            print("⚡ Running Fast Pass...")
            fast_stats = self._fast_pass(pairs)
            suggestions = self._generate_suggestions(fast_stats)
            print(f"   Generated {len(suggestions)} suggestions")
        
        # ═══════════════════════════════════════════
        # STEP 3: Analyze pairs (Full Pass)
        # ═══════════════════════════════════════════
        print("🔬 Analyzing pairs...")
        pair_analyses = []
        
        # Filter to adjacent pairs for temporal analysis
        adjacent_pairs = [p for p in pairs if p.get("pair_type") == "adjacent"]
        
        for i, pair in enumerate(adjacent_pairs):
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(adjacent_pairs)}")
            
            analysis = self._analyze_pair(pair)
            if analysis:
                pair_analyses.append(analysis)
        
        print(f"   Analyzed {len(pair_analyses)} pairs")
        
        # ═══════════════════════════════════════════
        # STEP 4: Zone aggregation
        # ═══════════════════════════════════════════
        print("📊 Aggregating by zones...")
        zone_analysis = self._aggregate_zones(pair_analyses)
        
        # ═══════════════════════════════════════════
        # STEP 5: Change Point Detection
        # ═══════════════════════════════════════════
        print("📅 Detecting change points...")
        change_points = detect_change_points(adjacent_pairs, self.config)
        print(f"   Found {len(change_points.change_points)} change points")
        
        # ═══════════════════════════════════════════
        # STEP 6: Narrative generation
        # ═══════════════════════════════════════════
        print("📝 Generating narrative...")
        narrative = self.narrative.generate(
            pair_analyses=pair_analyses,
            zone_analysis=zone_analysis,
            change_points=change_points,
            manifest=manifest,
        )
        print(f"   Generated {narrative.word_count} words")
        
        # ═══════════════════════════════════════════
        # STEP 7: Build report
        # ═══════════════════════════════════════════
        elapsed = time.time() - start_time
        
        report = FullReport(
            schema_version="deeputin-stage3v2-v3.2",
            created_at=datetime.now(),
            stage2_root=str(self.config.stage2_root),
            total_pairs=len(pairs),
            pairs_analyzed=len(pair_analyses),
            pairs_with_changes=len([a for a in pair_analyses 
                                    if a.bayesian.primary_hypothesis() == "H2_DIFFERENT"]),
            pair_analyses=pair_analyses,
            zone_analysis=zone_analysis,
            change_points=change_points,
            narrative=narrative,
            suggestions=suggestions,
            processing_time_seconds=elapsed,
            memory_peak_mb=0.0,  # TODO: measure
        )
        
        # ═══════════════════════════════════════════
        # STEP 8: Export
        # ═══════════════════════════════════════════
        print("📤 Exporting results...")
        self._export(report)
        
        print(f"✅ Complete in {elapsed:.1f}s")
        return report
    
    def _fast_pass(self, pairs: list[dict]) -> dict[str, Any]:
        """Quick statistics from Fast Pass."""
        p95_z_values = []
        qc_passed = 0
        
        for pair in pairs:
            p95_z = float(pair.get("p95_point_z", 0))
            p95_z_values.append(p95_z)
            
            if float(pair.get("quality_score", 0.8)) >= 0.6:
                qc_passed += 1
        
        return {
            "total_pairs": len(pairs),
            "p95_z_mean": sum(p95_z_values) / len(p95_z_values) if p95_z_values else 0,
            "p95_z_p95": sorted(p95_z_values)[int(len(p95_z_values) * 0.95)] if p95_z_values else 0,
            "qc_pass_rate": qc_passed / len(pairs) if pairs else 0,
        }
    
    def _generate_suggestions(self, stats: dict) -> list[CalibrationSuggestion]:
        """Generate calibration suggestions from Fast Pass stats."""
        suggestions = []
        
        # Check noise floor
        p95_median = stats.get("p95_z_mean", 1.0)
        if p95_median < 0.5:
            suggestions.append(CalibrationSuggestion(
                parameter="noise_floor_keypoint",
                current_value=self.config.full_pass_p95_z_threshold,
                suggested_value=self.config.full_pass_p95_z_threshold * 0.8,
                reason_ru=f"Median p95_z = {p95_median:.2f} (слишком низко). Noise floor завышен.",
                confidence=0.90,
                impact_ru="Увеличит чувствительность к реальным изменениям",
                auto_apply=True,
            ))
        
        # Check QC rate
        qc_rate = stats.get("qc_pass_rate", 0.9)
        if qc_rate < 0.8:
            suggestions.append(CalibrationSuggestion(
                parameter="qc_min_confidence",
                current_value=0.6,
                suggested_value=0.5,
                reason_ru=f"QC pass rate = {qc_rate:.0%} (<80%). Слишком много пар отклоняется.",
                confidence=0.75,
                impact_ru="Увеличит количество обработанных пар",
                auto_apply=False,
            ))
        
        return suggestions
    
    def _analyze_pair(self, pair: dict) -> PairAnalysis | None:
        """Analyze a single pair."""
        try:
            # Extract features
            features = self.loader.extract_pair_features(pair)
            
            # Load motion data (if available)
            motion_file = pair.get("motion_file")
            motion_data = None
            if motion_file:
                motion_data = self.loader.load_motion_file(motion_file)
            
            # Bayesian analysis
            bayesian = analyze_pair_bayesian(pair, self.config, features)
            
            # Effect size
            effect_size = compute_effect_size(
                pair, self.config, motion_data,
                noise_floor=1.0  # TODO: from calibration
            )
            
            # Bootstrap CI
            bootstrap = compute_bootstrap_ci(
                pair, self.config, motion_data,
                noise_floor=1.0
            )
            
            # Parse dates
            date_a = None
            date_b = None
            try:
                if pair.get("date_a"):
                    date_a = datetime.fromisoformat(pair["date_a"])
                if pair.get("date_b"):
                    date_b = datetime.fromisoformat(pair["date_b"])
            except (ValueError, TypeError):
                pass
            
            return PairAnalysis(
                pair_id=pair.get("pair_id", "unknown"),
                photo_a=pair.get("photo_a", ""),
                photo_b=pair.get("photo_b", ""),
                date_a=date_a,
                date_b=date_b,
                pose_bin=pair.get("pose_bin", "unknown"),
                p95_point_z=features["p95_point_z"],
                coherent_motion_fraction=features["coherent_motion_fraction"],
                significant_point_fraction=features["significant_point_fraction"],
                mesh_rmse=features["mesh_rmse"],
                descriptor_p95_z=features["descriptor_p95_z"],
                bayesian=bayesian,
                effect_size=effect_size,
                bootstrap=bootstrap,
                cross_pose=None,  # TODO: cross-pose analysis
                qc_passed=features["quality_score"] >= 0.6,
                quality_score=features["quality_score"],
            )
        
        except Exception as e:
            print(f"   ⚠ Error analyzing pair {pair.get('pair_id')}: {e}")
            return None
    
    def _aggregate_zones(self, analyses: list[PairAnalysis]) -> ZoneAnalysisResult:
        """Aggregate results by zone."""
        per_zone: dict[str, ZoneSummary] = {}
        
        for zone, label_ru in ZONE_LABELS_RU.items():
            # Collect d values for this zone
            d_values = []
            h2_count = 0
            
            for analysis in analyses:
                if zone in analysis.effect_size.per_zone:
                    ze = analysis.effect_size.per_zone[zone]
                    d_values.append(ze.d)
                    
                    if analysis.bayesian.primary_hypothesis() == "H2_DIFFERENT" and ze.d > 0.5:
                        h2_count += 1
            
            if d_values:
                mean_d = sum(d_values) / len(d_values)
                h2_rate = h2_count / len(analyses)
                
                per_zone[zone] = ZoneSummary(
                    zone=zone,
                    zone_label_ru=label_ru,
                    n_pairs=len(d_values),
                    h2_count=h2_count,
                    h2_rate=h2_rate,
                    mean_d=mean_d,
                    mean_lr=0.0,  # TODO
                    top_points=[],  # TODO
                    reliability_note_ru="Высокая надёжность" if zone == "bone_structure" else "Средняя надёжность",
                )
        
        # Find most affected zone
        if per_zone:
            most_affected = max(per_zone.items(), key=lambda x: x[1].mean_d)[0]
            overall_h2_rate = sum(z.h2_rate for z in per_zone.values()) / len(per_zone)
            overall_mean_d = sum(z.mean_d for z in per_zone.values()) / len(per_zone)
        else:
            most_affected = "unknown"
            overall_h2_rate = 0.0
            overall_mean_d = 0.0
        
        return ZoneAnalysisResult(
            per_zone=per_zone,
            most_affected_zone=most_affected,
            overall_h2_rate=overall_h2_rate,
            overall_mean_d=overall_mean_d,
        )
    
    def _export(self, report: FullReport):
        """Export results to output directory."""
        output_dir = Path(self.config.output_dir)
        
        if output_dir.exists() and self.config.overwrite:
            import shutil
            shutil.rmtree(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export JSON
        report_dict = report.to_dict()
        json_path = output_dir / "report.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        
        # Export narrative text
        text_path = output_dir / "narrative.txt"
        with text_path.open("w", encoding="utf-8") as f:
            f.write(report.narrative.full_text_ru)
        
        # Export summary
        summary_path = output_dir / "summary.json"
        summary = {
            "schema_version": report.schema_version,
            "created_at": report.created_at.isoformat(),
            "total_pairs": report.total_pairs,
            "pairs_analyzed": report.pairs_analyzed,
            "pairs_with_changes": report.pairs_with_changes,
            "processing_time_seconds": report.processing_time_seconds,
            "headline": report.narrative.headline_ru,
            "key_findings": report.narrative.key_findings,
        }
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"   Exported to {output_dir}")
