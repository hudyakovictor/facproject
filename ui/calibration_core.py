"""
calibration_core.py v3.3 — Rewritten over uv_module + app6/stage1.

Previous version depended on non-existent src/ modules (face_model_loader,
texture_extractor, forensic_analyzer). This version uses the actual project
architecture: uv_module.SkinAnalyzer + app6/stage1 pipeline.

Calibration flow:
1. Discover images in 9 pose subfolders
2. Run stage1 extraction via run_calibration.py (or inline ReconstructionEngine)
3. For each extracted photo, run SkinAnalyzer.analyze_full()
4. Aggregate same-person same-day variability
5. Compute calibration thresholds
"""
from __future__ import annotations

import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field
import itertools

# Ensure project root in path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uv_module.skin_analysis import SkinAnalyzer
from uv_module.zones import ZONE_SPECS, POSE_POLICY


POSE_FOLDERS = [
    "frontal", "left_15", "right_15", "left_30", "right_30",
    "left_45", "right_45", "left_60_90", "right_60_90",
]


class CalibrationSession:
    """One calibration session: all photos of one person on one day."""
    def __init__(self, calibration_root: str, uv_size: int = 1000):
        self.root = Path(calibration_root)
        self.uv_size = uv_size
        self.results: Dict[str, List[Dict]] = {}  # pose -> list of forensic results

    def discover_images(self) -> Dict[str, List[Path]]:
        """Find all images by pose subfolder."""
        images_by_pose: Dict[str, List[Path]] = {}
        exts = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.PNG', '*.JPEG']
        for pose in POSE_FOLDERS:
            folder = self.root / pose
            if not folder.exists():
                continue
            files: List[Path] = []
            for ext in exts:
                files.extend(folder.glob(ext))
            if files:
                images_by_pose[pose] = sorted(files)
        return images_by_pose


class CalibrationEngine:
    """Calibration engine using uv_module.SkinAnalyzer.

    Works in two modes:
    1. stage1 mode: reads pre-extracted stage1 output directories
    2. direct mode: processes images inline (requires 3DDFA weights)

    For MacBook M1 deployment, stage1 mode is preferred (pre-extract once,
    then calibrate interactively).
    """
    def __init__(self, uv_size: int = 1000):
        self.uv_size = uv_size
        self.analyzer = SkinAnalyzer()

    def calibrate_from_stage1(self, stage1_dir: str | Path) -> Dict[str, Any]:
        """Calibrate from pre-extracted stage1 output.

        Each photo directory under stage1_dir should contain:
        - info.json (with pose_bin, date, etc.)
        - uv.npz (with analysis_bgr, observed_mask, etc.)
        - face_mask.npz (with skin mask)
        """
        stage1_dir = Path(stage1_dir)
        if not stage1_dir.is_dir():
            return {'error': f'{stage1_dir} is not a directory'}

        # Discover photo directories
        photo_dirs = sorted(d for d in stage1_dir.iterdir() if d.is_dir() and (d / 'info.json').exists())
        if not photo_dirs:
            return {'error': f'No photo directories with info.json found in {stage1_dir}'}

        # Group by pose_bin
        by_pose: Dict[str, List[Path]] = {}
        for d in photo_dirs:
            try:
                info = json.loads((d / 'info.json').read_text(encoding='utf-8'))
                pose = info.get('pose', {}).get('pose_bin', 'unknown')
                by_pose.setdefault(pose, []).append(d)
            except Exception:
                continue

        if not by_pose:
            return {'error': 'No valid photo records found'}

        # Analyze each photo
        all_results: Dict[str, List[Dict]] = {}
        all_uv_metrics: Dict[str, List[Dict]] = {}
        all_img_metrics: Dict[str, List[Dict]] = {}

        for pose, dirs in by_pose.items():
            pose_results = []
            for d in dirs:
                try:
                    result = self._analyze_stage1_photo(d)
                    if result:
                        pose_results.append(result)
                except Exception as e:
                    print(f"  Failed {d.name}: {e}")
                    continue
            all_results[pose] = pose_results

        if not all_results:
            return {'error': 'No successful analyses'}

        # Aggregate
        aggregated = self._aggregate_by_pose(all_results)

        # Compute thresholds
        thresholds = self._compute_thresholds(all_results, aggregated)

        # Cross-pose validation
        cross_matrix = self._cross_pose_validation(all_results)

        # Verdict
        poses_found = list(all_results.keys())
        total_images = sum(len(v) for v in all_results.values())

        # Check: for same person same day, metrics should have LOW variability
        all_lap_vars = []
        all_lbp_entropies = []
        for pose_results in all_results.values():
            for r in pose_results:
                if 'img' in r and r['img'].get('available'):
                    for zone_data in r['img'].get('zones', {}).values():
                        all_lap_vars.append(zone_data.get('laplacian_var', 0))
                        all_lbp_entropies.append(zone_data.get('lbp_entropy', 0))

        lap_var_std = float(np.std(all_lap_vars)) if len(all_lap_vars) >= 2 else 0
        lbp_std = float(np.std(all_lbp_entropies)) if len(all_lbp_entropies) >= 2 else 0

        # Same-person consistency: low std means same skin
        same_person = lap_var_std < thresholds.get('lap_var_max_std', 50) and lbp_std < thresholds.get('lbp_max_std', 0.5)

        profile = {
            'calibration_root': str(stage1_dir),
            'poses_found': poses_found,
            'total_images': total_images,
            'aggregated_by_pose': aggregated,
            'cross_pose_validation': cross_matrix,
            'thresholds': thresholds,
            'variability': {
                'laplacian_var_std': lap_var_std,
                'lbp_entropy_std': lbp_std,
            },
            'verdict': {
                'same_person': same_person,
                'confidence': 'HIGH' if same_person and len(poses_found) >= 3 else 'MEDIUM' if same_person else 'LOW',
                'message': f"Same-person calibration: {len(poses_found)} poses, {total_images} images, lap_var_std={lap_var_std:.2f}, lbp_std={lbp_std:.4f}",
            },
        }

        return profile

    def _analyze_stage1_photo(self, photo_dir: Path) -> Dict | None:
        """Analyze a single stage1 photo directory."""
        info_path = photo_dir / 'info.json'
        uv_path = photo_dir / 'uv.npz'
        mask_path = photo_dir / 'face_mask.npz'

        if not info_path.exists() or not uv_path.exists():
            return None

        try:
            info = json.loads(info_path.read_text(encoding='utf-8'))
        except Exception:
            return None

        pose_bin = info.get('pose', {}).get('pose_bin', 'unknown')

        # Load UV data
        try:
            with np.load(uv_path, allow_pickle=False) as z:
                analysis_bgr = z['analysis_bgr']
                observed_mask = z['observed_mask']
        except Exception:
            return None

        # UV geometry analysis
        uv_result = self.analyzer.analyze_uv_geometry(analysis_bgr, observed_mask, pose_bin)

        # Image texture analysis (if face_mask.npz exists)
        img_result = {'available': False}
        if mask_path.exists():
            try:
                with np.load(mask_path, allow_pickle=False) as z:
                    skin_mask = z['mask_original']
                # Try to load original image
                img_path = None
                for candidate in ('original.jpg', 'original.png', 'face_crop.jpg'):
                    if (photo_dir / candidate).exists():
                        img_path = photo_dir / candidate
                        break
                if img_path is not None:
                    original_bgr = cv2.imread(str(img_path))
                    if original_bgr is not None:
                        # Resize mask if needed
                        if skin_mask.shape[:2] != original_bgr.shape[:2]:
                            skin_mask = cv2.resize(
                                skin_mask.astype(np.uint8),
                                (original_bgr.shape[1], original_bgr.shape[0]),
                                interpolation=cv2.INTER_NEAREST,
                            ).astype(bool)
                        img_result = self.analyzer.analyze_image_texture(original_bgr, skin_mask, pose_bin)
            except Exception as e:
                img_result = {'available': False, 'error': str(e)}

        return {
            'photo_dir': str(photo_dir),
            'pose_bin': pose_bin,
            'uv': uv_result,
            'img': img_result,
        }

    def _aggregate_by_pose(self, all_results: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Aggregate metrics per pose."""
        aggregated = {}
        for pose, results in all_results.items():
            if not results:
                continue

            # Collect global metrics
            uv_ridge_densities = []
            uv_branch_counts = []
            img_lap_vars = []
            img_lbp_entropies = []

            for r in results:
                uv = r.get('uv', {})
                if uv.get('available'):
                    uv_ridge_densities.append(uv.get('global_wrinkle_fraction', 0))
                    for zone_data in uv.get('zones', {}).values():
                        uv_branch_counts.append(zone_data.get('n_branches', zone_data.get('skeleton_components', 0)))

                img = r.get('img', {})
                if img.get('available'):
                    img_lap_vars.append(img.get('global_laplacian_var', 0))
                    img_lbp_entropies.append(img.get('global_lbp_entropy', 0))

            aggregated[pose] = {
                'count': len(results),
                'uv_ridge_density_mean': float(np.mean(uv_ridge_densities)) if uv_ridge_densities else 0,
                'uv_ridge_density_std': float(np.std(uv_ridge_densities)) if uv_ridge_densities else 0,
                'uv_branch_count_mean': float(np.mean(uv_branch_counts)) if uv_branch_counts else 0,
                'img_lap_var_mean': float(np.mean(img_lap_vars)) if img_lap_vars else 0,
                'img_lap_var_std': float(np.std(img_lap_vars)) if img_lap_vars else 0,
                'img_lbp_entropy_mean': float(np.mean(img_lbp_entropies)) if img_lbp_entropies else 0,
                'img_lbp_entropy_std': float(np.std(img_lbp_entropies)) if img_lbp_entropies else 0,
            }
        return aggregated

    def _compute_thresholds(self, all_results: Dict, aggregated: Dict) -> Dict[str, float]:
        """Compute calibration thresholds from same-person variability."""
        # Collect all metrics across poses
        all_lap_vars = []
        all_lbp = []
        all_ridge = []

        for pose, results in all_results.items():
            for r in results:
                uv = r.get('uv', {})
                img = r.get('img', {})
                if uv.get('available'):
                    all_ridge.append(uv.get('global_wrinkle_fraction', 0))
                if img.get('available'):
                    all_lap_vars.append(img.get('global_laplacian_var', 0))
                    all_lbp.append(img.get('global_lbp_entropy', 0))

        thresholds = {}
        if all_lap_vars:
            m, s = float(np.mean(all_lap_vars)), float(np.std(all_lap_vars))
            thresholds['lap_var_mean'] = m
            thresholds['lap_var_max_std'] = max(s * 3, 10)  # 3-sigma tolerance
            thresholds['lap_var_anomaly_threshold'] = m + 3 * s
        if all_lbp:
            m, s = float(np.mean(all_lbp)), float(np.std(all_lbp))
            thresholds['lbp_mean'] = m
            thresholds['lbp_max_std'] = max(s * 3, 0.1)
            thresholds['lbp_anomaly_threshold'] = m + 3 * s
        if all_ridge:
            m, s = float(np.mean(all_ridge)), float(np.std(all_ridge))
            thresholds['ridge_density_mean'] = m
            thresholds['ridge_density_max_std'] = max(s * 3, 0.01)
            thresholds['ridge_anomaly_threshold'] = m + 3 * s

        return thresholds

    def _cross_pose_validation(self, all_results: Dict) -> Dict[str, Any]:
        """Cross-pose consistency check."""
        poses = [p for p, r in all_results.items() if r]
        matrix = {}
        for pa, pb in itertools.combinations(poses, 2):
            # Compare first result from each pose
            ra = all_results[pa][0] if all_results[pa] else None
            rb = all_results[pb][0] if all_results[pb] else None
            if ra is None or rb is None:
                continue

            # Simple metric: compare available zone counts
            uv_a_zones = len(ra.get('uv', {}).get('zones', {}))
            uv_b_zones = len(rb.get('uv', {}).get('zones', {}))
            common_zones = len(set(ra.get('uv', {}).get('zones', {}).keys()) &
                             set(rb.get('uv', {}).get('zones', {}).keys()))
            max_zones = max(uv_a_zones, uv_b_zones, 1)

            matrix[f"{pa}_vs_{pb}"] = {
                'common_zones': common_zones,
                'max_zones': max_zones,
                'overlap_ratio': common_zones / max_zones,
            }
        return matrix

    def save_profile(self, profile: Dict, out_path: str):
        """Save calibration profile to JSON."""
        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [sanitize(x) for x in obj]
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return sanitize(obj.tolist())
            return obj
        with open(out_path, 'w') as f:
            json.dump(sanitize(profile), f, indent=2, ensure_ascii=False)
        print(f"[Calibration] Profile saved to {out_path}")
