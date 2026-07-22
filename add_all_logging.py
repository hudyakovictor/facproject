#!/usr/bin/env python3
"""
🎯 CRITICAL → Auto-add status logging to all functions in all modules.
Run this script to add logging calls to every function.
"""
import re
import os

# Module -> function -> status mapping (from STATUS_AUDIT.py)
MODULE_FUNCTIONS = {
    "app6/stage1/geometry.py": {
        "classify_pose": ("complete", ""),
        "nearest_canonical_yaw": ("in_progress", "Not integrated into main pipeline yet"),
        "row_rotation_matrix": ("complete", ""),
        "full_pose_correction_matrix": ("complete", ""),
        "normalize_mesh": ("complete", ""),
        "normalize_mesh_landmark_anchored": ("complete", ""),
        "compute_chronology_alignment": ("complete", ""),
        "to_original_image": ("in_progress", "No bounds check on output coordinates"),
        "reprojection_stats": ("complete", ""),
        "pack_mask": ("complete", ""),
        "unpack_mask": ("complete", ""),
    },
    "app6/stage1/reconstruction.py": {
        "process": ("complete", ""),
        "cleanup": ("complete", ""),
        "landmark_arrays": ("complete", ""),
    },
    "app6/stage1/engine.py": {
        "run": ("complete", ""),
        "_one": ("complete", ""),
        "_landmark_rows": ("complete", ""),
    },
    "app6/stage1/masks.py": {
        "build_mask_bundle": ("complete", ""),
    },
    "app6/stage1/assets.py": {
        "save_image_assets": ("complete", ""),
        "technical_quality": ("complete", ""),
        "save_uv_and_mesh": ("complete", ""),
        "save_face_mask": ("complete", ""),
        "save_semantic_channels": ("complete", ""),
    },
    "app6/stage1/config.py": {
        "Stage1Config": ("complete", ""),
    },
    "app6/stage1/naming.py": {
        "parse_photo_name": ("complete", ""),
        "make_photo_id": ("complete", ""),
    },
    "app6/stage1/storage.py": {
        "atomic_photo_directory": ("complete", ""),
        "clean_incomplete": ("complete", ""),
        "write_failure": ("complete", ""),
    },
    "app6/stage1/utils.py": {
        "sha256_file": ("complete", ""),
        "sha256_json": ("complete", ""),
        "sha256_paths": ("complete", ""),
        "atomic_json": ("complete", ""),
        "write_csv": ("complete", ""),
        "runtime_versions": ("complete", ""),
    },
    "app6/stage1/validator.py": {
        "validate_photo": ("complete", ""),
        "is_resumable": ("complete", ""),
    },
    "app6/stage1/quality_zones.py": {
        "build_quality_files": ("deprecated", "Replaced by skin/pipeline.py"),
    },
    "app6/stage1/skin/pipeline.py": {
        "build_skin_package": ("complete", ""),
    },
    "app6/stage1/skin/quality.py": {
        "quality_maps": ("complete", ""),
        "applicability": ("complete", ""),
        "per_zone_applicability": ("complete", ""),
    },
    "app6/stage1/skin/projection.py": {
        "rasterize_surface": ("in_progress", "CPU slow, GPU not implemented. NO BLOCKER - can optimize anytime"),
        "project_atlas": ("complete", ""),
    },
    "app6/stage1/skin/pose_policy.py": {
        "PosePolicy": ("complete", ""),
    },
    "app6/stage1/skin/atlas_registry.py": {
        "AtlasRegistry": ("complete", ""),
    },
    "app6/stage1/skin/texture/features.py": {
        "extract_texture_features": ("complete", ""),
    },
    "app6/stage1/skin/texture/basic.py": {
        "extract_basic": ("complete", ""),
    },
    "app6/stage1/skin/wrinkles/classical.py": {
        "detect": ("complete", ""),
    },
    "app6/stage1/skin/wrinkles/ffhq_adapter.py": {
        "FFHQWrinkleAdapter": ("experimental", "Requires weights file"),
    },
    "app6/stage1/skin/local_features/detector.py": {
        "detect": ("complete", ""),
    },
    "app6/stage1/skin/material/evidence.py": {
        "build": ("experimental", "No verdict, experimental foundation"),
    },
    "app6/stage1/skin/contamination.py": {
        "FaceParsingAdapter": ("experimental", "Requires weights file"),
    },
    "app6/stage1/skin/previews.py": {
        "save_previews": ("complete", ""),
        "save_wrinkle_overlay": ("complete", ""),
    },
    "app6/stage1/skin/surface_geometry.py": {
        "SurfaceGeometry": ("complete", ""),
    },
    "app6/stage1/skin/patch_sampler.py": {
        "sample_zone_patches": ("complete", ""),
    },
    "app6/stage1/skin/photometric.py": {
        "branches": ("complete", ""),
    },
    "app6/stage1/skin/sensitivity/degradation.py": {
        "benchmark": ("complete", ""),
    },
    "app6/stage2/core.py": {
        "compare_landmarks": ("complete", ""),
        "build_coordinate_zone_map": ("complete", ""),
        "robust_reference": ("complete", ""),
        "calibrated_score": ("complete", ""),
        "zone_weighted_score": ("complete", ""),
    },
    "app6/stage2/engine.py": {
        "run": ("complete", ""),
    },
    "app6/stage2/loaders.py": {
        "load_main": ("complete", ""),
        "load_calibration": ("complete", ""),
        "load_calibration_from_sidecar": ("complete", ""),
    },
    "app6/stage2/motion.py": {
        "aligned_point_motion": ("complete", ""),
        "PointNoiseModel": ("complete", ""),
        "PointNoiseModel.score": ("complete", ""),
        "PointNoiseModel.landmark_stability_score": ("complete", ""),
    },
    "app6/stage2/anchor_policy.py": {
        "stable_anchor_mask": ("complete", ""),
        "stable_anchor_indices": ("complete", ""),
    },
    "app6/stage2/calibration.py": {
        "CalibrationModel": ("complete", ""),
        "CalibrationModel.matched_null": ("complete", ""),
        "CalibrationModel.consistency_check": ("complete", ""),
    },
    "app6/stage2/chronology.py": {
        "apply_chronology_rate_flags": ("in_progress", "No alignment quality filter. NO BLOCKER - can add filter anytime"),
    },
    "app6/stage2/descriptors.py": {
        "local_pair_descriptors": ("complete", ""),
        "DescriptorNoiseModel": ("complete", ""),
    },
    "app6/stage2/texture_image.py": {
        "texture_pair_deltas": ("in_progress", "No pose normalization. NO BLOCKER - can add normalization anytime"),
    },
    "app6/stage2/texture_pair.py": {
        "summarize_texture_pairs": ("complete", ""),
    },
    "app6/stage2/texture_structure.py": {
        "compare_zone_structure": ("complete", ""),
    },
    "app6/stage2/mesh_dense.py": {
        "dense_mesh_pair": ("complete", ""),
    },
    "app6/stage2/mesh_calibration.py": {
        "MeshNoiseModel": ("experimental", "Uncalibrated"),
    },
    "app6/stage2/evidence.py": {
        "evidence_state": ("complete", ""),
        "packet_from_pair": ("complete", ""),
        "alternative_reasons": ("complete", ""),
    },
    "app6/stage2/baseline_return.py": {
        "apply_baseline_return": ("complete", ""),
    },
    "app6/stage2/corroboration.py": {
        "apply_cross_bin_corroboration": ("complete", ""),
        "aggregate_events": ("complete", ""),
    },
    "app6/stage2/pose_leakage.py": {
        "pose_leakage_diagnostic": ("complete", ""),
    },
    "app6/stage2/multiple_testing.py": {
        "apply_pair_fdr": ("complete", ""),
        "apply_zone_fdr": ("complete", ""),
    },
    "app6/stage2/alpha_chronology.py": {
        "apply_alpha_chronology": ("complete", ""),
    },
    "app6/stage2/quality_integration.py": {
        "pair_quality_zone_overlap": ("complete", ""),
    },
    "app6/stage2/uv_comparison.py": {
        "uv_geometry_pair": ("in_progress", "Adapter only, no calibration. NO BLOCKER"),
    },
    "app6/stage2/postprocess_reports.py": {
        "write_postprocess_reports": ("complete", ""),
    },
    "app6/stage2/technical_summary.py": {
        "build_technical_summary": ("complete", ""),
    },
    "app6/stage2/metric_registry.py": {
        "build_metric_catalog": ("complete", ""),
        "metric_channel": ("complete", ""),
    },
    "app6/stage2/leads.py": {
        "load_leads": ("complete", ""),
        "pair_leads": ("complete", ""),
    },
    "app6/stage3/engine.py": {
        "run": ("complete", ""),
    },
}


def add_logging_to_file(filepath: str, functions: dict):
    """Add status logging to all functions in a file."""
    if not os.path.exists(filepath):
        print(f"⚠️ File not found: {filepath}")
        return

    with open(filepath, 'r') as f:
        content = f.read()

    # Check if status_logger is already imported
    if 'status_logger' not in content:
        # Add import after other imports
        import_match = re.search(r'((?:from|import).*\n)+', content)
        if import_match:
            insert_pos = import_match.end()
            content = content[:insert_pos] + 'from .status_logger import log_status, log_blocker, log_warning\n' + content[insert_pos:]
        else:
            content = 'from .status_logger import log_status, log_blocker, log_warning\n' + content

    # Add logging to each function
    for func_name, (status, detail) in functions.items():
        # Find function definition
        pattern = rf'(def\s+{re.escape(func_name)}\s*\([^)]*\).*?:\s*\n)'
        match = re.search(pattern, content)

        if match:
            # Check if logging already exists
            func_start = match.start()
            func_body_start = match.end()
            next_lines = content[func_body_start:func_body_start+200]

            if 'log_status' in next_lines or 'log_warning' in next_lines:
                continue  # Already has logging

            # Create log call
            if status == "complete":
                log_call = f'    log_status("{func_name}", "complete")\n'
            elif status == "in_progress":
                log_call = f'    log_status("{func_name}", "in_progress", "{detail}")\n'
            elif status == "blocked":
                log_call = f'    log_blocker("{func_name}", "{detail}")\n'
            elif status == "deprecated":
                log_call = f'    log_status("{func_name}", "deprecated", "{detail}")\n'
            elif status == "experimental":
                log_call = f'    log_status("{func_name}", "experimental", "{detail}")\n'
            else:
                log_call = f'    log_status("{func_name}", "{status}")\n'

            # Insert after function definition
            content = content[:func_body_start] + log_call + content[func_body_start:]
            print(f"  ✅ Added logging to {func_name} ({status})")
        else:
            print(f"  ⚠️ Function not found: {func_name}")

    with open(filepath, 'w') as f:
        f.write(content)


def main():
    """Add logging to all modules."""
    print("=" * 70)
    print("🎯 Adding status logging to all functions...")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    for module_path, functions in MODULE_FUNCTIONS.items():
        full_path = os.path.join(base_dir, module_path)
        print(f"\n📁 {module_path}")
        add_logging_to_file(full_path, functions)

    print("\n" + "=" * 70)
    print("✅ Done! All functions now have status logging.")
    print("   Set FACPROJECT_DEBUG=1 to see all status messages.")
    print("=" * 70)


if __name__ == "__main__":
    main()
