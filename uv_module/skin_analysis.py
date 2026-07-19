"""Unified forensic skin analysis: UV-geometry + image-texture.

This module is the SINGLE entry point for all skin consistency analysis.
It replaces the previously duplicated wrinkle analysis in generator.py and
metrics.py with a coherent two-space architecture:

1. UV-SPACE ANALYSIS (geometry):  Frangi/Sato ridges + skan skeleton graph
   - Operates on the analytic UV texture (real pixels only, no enhancement)
   - Invariant to pose because UV unfolds the face into a flat atlas
   - Best for: wrinkle shape, branch density, geodesic lengths

2. IMAGE-SPACE ANALYSIS (texture): LBP/GLCM/Gabor on the original photo
   - Operates on the original photo with a skin mask
   - Preserves sensor-accurate pixel relationships (no UV resampling blur)
   - Best for: pore texture, micro-detail, LBP entropy, GLCM contrast

Both analyses produce per-zone metrics for chronological comparison.

Contract:
    result = SkinAnalyzer(cfg).analyze_full(
        uv_analytic=analysis_u8,
        uv_observed=observed_mask,
        original_bgr=bgr_image,
        skin_mask=hard_mask,
        pose_bin="frontal",
        uv_coords=uv_coords,
        triangles=triangles,
    )
    result.uv_metrics   -> dict of UV-geometry metrics per zone
    result.img_metrics  -> dict of image-texture metrics per zone
    result.combined     -> fused report with confidence weights
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .zones import ZONE_SPECS, policy_weight

# Optional heavy dependencies
try:
    from skimage import filters as _sk_filters
    from skimage.morphology import remove_small_objects, skeletonize as _sk_skeletonize
    _HAS_SKIMAGE = True
except ImportError:
    _sk_filters = None
    _HAS_SKIMAGE = False

try:
    from skan import Skeleton as _SkanSkeleton, summarize as _skan_summarize
    _HAS_SKAN = True
except ImportError:
    _SkanSkeleton = _skan_summarize = None
    _HAS_SKAN = False

try:
    from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
    _HAS_GLCM = True
except ImportError:
    graycomatrix = graycoprops = local_binary_pattern = None
    _HAS_GLCM = False


@dataclass
class SkinAnalysisResult:
    """Complete forensic skin analysis result."""
    uv_metrics: dict[str, Any] = field(default_factory=dict)
    img_metrics: dict[str, Any] = field(default_factory=dict)
    combined: dict[str, Any] = field(default_factory=dict)
    zone_reports: dict[str, dict[str, Any]] = field(default_factory=dict)


class SkinAnalyzer:
    """Unified skin analyzer operating in both UV and image space."""

    def __init__(self, cfg: Any = None):
        self.cfg = cfg
        self.lbp_P = 8
        self.lbp_R = 1
        self.glcm_levels = 16
        self.glcm_distances = [1, 2]
        self.glcm_angles = [0, np.pi / 2]
        self.ridge_sigmas = (0.5, 1.0, 1.5, 2.0)
        self.wrinkle_threshold_percentile = 82.0
        if cfg is not None:
            self.ridge_sigmas = tuple(getattr(cfg, 'wrinkle_sigmas', self.ridge_sigmas))
            self.wrinkle_threshold_percentile = getattr(cfg, 'wrinkle_threshold_percentile', self.wrinkle_threshold_percentile)

    # ------------------------------------------------------------------
    # UV-SPACE: Geometry analysis
    # ------------------------------------------------------------------

    def analyze_uv_geometry(
        self,
        uv_analytic: np.ndarray,
        uv_observed: np.ndarray,
        pose_bin: str = "frontal",
    ) -> dict[str, Any]:
        """Analyze wrinkle/micro-relief geometry in UV space.

        Returns per-zone metrics:
        - branch_count, total_length, junctions, endpoints
        - ridge_density (branches per k observed pixels)
        - mean_ridge_strength
        """
        if not uv_observed.any():
            return {"available": False, "reason": "empty observed mask"}

        gray = cv2.cvtColor(uv_analytic, cv2.COLOR_BGR2GRAY)
        gray_f = gray.astype(np.float32) / 255.0
        mask = np.asarray(uv_observed, bool)

        # Normalize: DoG high-pass with local std normalisation
        blur_coarse = cv2.GaussianBlur(gray_f, (0, 0), 8.0)
        high = gray_f - blur_coarse
        base = cv2.GaussianBlur(gray_f, (0, 0), 32.0)
        std_base = cv2.GaussianBlur(((gray_f - base) ** 2), (0, 0), 32.0) ** 0.5 + 1e-3
        normalized = (high - high.mean()) / std_base
        normalized = (normalized - normalized.min()) / (normalized.max() - normalized.min() + 1e-8)

        # Ridge detection
        if _HAS_SKIMAGE and _sk_filters is not None:
            ridges = _sk_filters.frangi(normalized, sigmas=list(self.ridge_sigmas), black_ridges=True)
        else:
            ridges = self._cv2_ridge_fallback(normalized)

        ridges = (ridges - ridges.min()) / (ridges.max() - ridges.min() + 1e-8)

        # Global threshold
        observed_ridges = ridges[mask]
        if len(observed_ridges) == 0:
            return {"available": False, "reason": "no observed ridges"}
        threshold = np.percentile(observed_ridges, self.wrinkle_threshold_percentile)
        wrinkle_bin = (ridges > threshold) & mask

        # Per-zone analysis
        h, w = gray.shape
        zone_metrics = {}
        for spec in ZONE_SPECS:
            zone_weight = policy_weight(pose_bin, spec.name)
            if zone_weight <= 0:
                continue

            # Extract zone in UV space (rasterizer convention: row 0 = v=1)
            umin, vmin, umax, vmax = spec.uv_box
            py1 = int((1.0 - vmax) * h)
            py2 = int((1.0 - vmin) * h)
            px1 = int(umin * w)
            px2 = int(umax * w)
            py1, py2 = max(0, py1), min(h, py2)
            px1, px2 = max(0, px1), min(w, px2)
            if py2 <= py1 or px2 <= px1:
                continue

            zone_mask = mask[py1:py2, px1:px2]
            zone_ridges = ridges[py1:py2, px1:px2]
            zone_wrinkles = wrinkle_bin[py1:py2, px1:px2]

            if zone_mask.sum() < 400:
                continue

            # Threshold per zone
            zr = zone_ridges[zone_mask]
            if len(zr) == 0:
                continue
            z_threshold = np.percentile(zr, self.wrinkle_threshold_percentile)
            zone_bin = (zone_ridges > z_threshold) & zone_mask

            # Skeleton + graph
            skel_result = self._skeleton_analysis(zone_bin, zone_ridges)
            area_kpx = float(zone_mask.sum()) / 1000.0
            zone_metrics[spec.name] = {
                "weight": float(zone_weight),
                "observed_px": int(zone_mask.sum()),
                "ridge_density": float(zone_bin.sum() / max(zone_mask.sum(), 1)),
                "area_kpx": area_kpx,
                **skel_result,
            }

        return {
            "available": True,
            "skimage_available": _HAS_SKIMAGE,
            "skan_available": _HAS_SKAN,
            "zones": zone_metrics,
            "global_ridge_mean": float(np.mean(ridges[mask])),
            "global_wrinkle_fraction": float(wrinkle_bin.sum() / max(mask.sum(), 1)),
        }

    # ------------------------------------------------------------------
    # IMAGE-SPACE: Texture analysis
    # ------------------------------------------------------------------

    def analyze_image_texture(
        self,
        original_bgr: np.ndarray,
        skin_mask: np.ndarray,
        pose_bin: str = "frontal",
    ) -> dict[str, Any]:
        """Analyze skin texture in the original image space.

        Returns per-zone metrics:
        - LBP histogram + entropy
        - GLCM contrast, homogeneity, energy, correlation
        - Laplacian variance (sharpness)
        - High-frequency energy ratio
        """
        mask = np.asarray(skin_mask, bool)
        if not mask.any():
            return {"available": False, "reason": "empty skin mask"}

        gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        zone_metrics = {}
        for spec in ZONE_SPECS:
            zone_weight = policy_weight(pose_bin, spec.name)
            if zone_weight <= 0:
                continue

            # Zone ROI in image space (approximate: use UV box mapped via
            # face bounding box). For now, use a simpler approach: divide
            # the masked region into a grid and use position to map zones.
            # This is an approximation that works for near-frontal poses.
            # For profile poses, the zone mapping is less critical because
            # only the visible-side zones have weight > 0.
            zone_mask = self._image_zone_mask(mask, spec, (h, w), pose_bin)
            if zone_mask.sum() < 400:
                continue

            zone_gray = gray.copy()
            zone_gray[~zone_mask] = 0

            metrics: dict[str, Any] = {}
            metrics["weight"] = float(zone_weight)
            metrics["observed_px"] = int(zone_mask.sum())

            # LBP
            lbp_hist = self._lbp_histogram(gray, zone_mask)
            metrics["lbp_entropy"] = float(-np.sum(lbp_hist * np.log2(lbp_hist + 1e-12)))

            # GLCM
            metrics.update(self._glcm_stats(gray, zone_mask))

            # Laplacian variance (sharpness proxy)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            metrics["laplacian_var"] = float(np.var(lap[zone_mask]))

            # High-frequency energy
            gf = gray.astype(np.float32)
            blur = cv2.GaussianBlur(gf, (0, 0), 2.0)
            hp = gf - blur
            metrics["highfreq_energy"] = float(np.mean(hp[zone_mask] ** 2))

            # Local contrast
            local_mean = cv2.blur(gf, (7, 7))
            local_std = (cv2.blur((gf - local_mean) ** 2, (7, 7)) ** 0.5)
            metrics["local_std_mean"] = float(np.mean(local_std[zone_mask]))

            # Dynamic range
            vals = gray[zone_mask].astype(np.float32)
            metrics["dynamic_range_p2_p98"] = float(np.percentile(vals, 98) - np.percentile(vals, 2))

            zone_metrics[spec.name] = metrics

        # Global metrics
        gray_64 = gray.astype(np.float64)
        lap_g = cv2.Laplacian(gray_64, cv2.CV_64F)

        return {
            "available": True,
            "skimage_available": _HAS_GLCM,
            "zones": zone_metrics,
            "global_laplacian_var": float(np.var(lap_g[mask])),
            "global_lbp_entropy": float(-np.sum(
                self._lbp_histogram(gray, mask) *
                np.log2(self._lbp_histogram(gray, mask) + 1e-12)
            )),
        }

    # ------------------------------------------------------------------
    # COMBINED: Full analysis
    # ------------------------------------------------------------------

    def analyze_full(
        self,
        uv_analytic: np.ndarray,
        uv_observed: np.ndarray,
        original_bgr: np.ndarray,
        skin_mask: np.ndarray,
        pose_bin: str = "frontal",
        uv_coords: np.ndarray | None = None,
        triangles: np.ndarray | None = None,
    ) -> SkinAnalysisResult:
        """Run both UV-geometry and image-texture analysis and fuse results."""
        uv_result = self.analyze_uv_geometry(uv_analytic, uv_observed, pose_bin)
        img_result = self.analyze_image_texture(original_bgr, skin_mask, pose_bin)

        # Fuse per-zone metrics
        zone_reports = {}
        all_zones = set(uv_result.get("zones", {}).keys()) | set(img_result.get("zones", {}).keys())
        for zone_name in all_zones:
            report: dict[str, Any] = {"zone": zone_name}
            if zone_name in uv_result.get("zones", {}):
                report["uv"] = uv_result["zones"][zone_name]
            if zone_name in img_result.get("zones", {}):
                report["img"] = img_result["zones"][zone_name]
            # Confidence: weight by observed pixels and zone policy
            uv_px = report.get("uv", {}).get("observed_px", 0)
            img_px = report.get("img", {}).get("observed_px", 0)
            report["confidence"] = min(1.0, (uv_px + img_px) / 2000.0)
            zone_reports[zone_name] = report

        combined = {
            "uv_available": uv_result.get("available", False),
            "img_available": img_result.get("available", False),
            "zone_count": len(zone_reports),
            "global_uv": {k: v for k, v in uv_result.items() if k != "zones"},
            "global_img": {k: v for k, v in img_result.items() if k != "zones"},
        }

        return SkinAnalysisResult(
            uv_metrics=uv_result,
            img_metrics=img_result,
            combined=combined,
            zone_reports=zone_reports,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _skeleton_analysis(self, binary_mask: np.ndarray, ridges: np.ndarray) -> dict[str, Any]:
        """Skeleton + graph analysis (skan if available, cv2 fallback)."""
        # Cleanup
        min_px = 6
        if _HAS_SKIMAGE:
            binary_mask = remove_small_objects(binary_mask, min_size=min_px)
            skeleton_img = _sk_skeletonize(binary_mask)
        else:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            opened = cv2.morphologyEx(binary_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel, iterations=2)
            binary_mask = opened.astype(bool)
            skeleton_img = self._cv2_skeleton(binary_mask)

        result: dict[str, Any] = {}
        if not skeleton_img.any():
            result["skeleton_available"] = True
            result["n_branches"] = 0
            result["skeleton_px"] = int(skeleton_img.sum())
            return result

        if _HAS_SKAN and _SkanSkeleton is not None:
            try:
                sk = _SkanSkeleton(skeleton_img)
                summary = _skan_summarize(sk, separator='_')
                # Robust column access
                dist_col = None
                for c in ('branch_distance', 'main-path-distance'):
                    if c in summary.columns:
                        dist_col = c
                        break
                if dist_col is None:
                    for c in summary.columns:
                        if 'distance' in c.lower() or 'length' in c.lower():
                            dist_col = c
                            break

                lengths = summary[dist_col].to_numpy(np.float64) if dist_col else np.array([0.0])
                area_kpx = float(binary_mask.sum()) / 1000.0
                result.update({
                    "skeleton_available": True,
                    "skan_available": True,
                    "n_branches": int(len(summary)),
                    "total_length_px": float(lengths.sum()),
                    "mean_branch_length_px": float(lengths.mean()),
                    "branch_density_per_kpx": float(len(summary) / max(area_kpx, 1e-6)),
                    "length_density_per_kpx": float(lengths.sum() / max(area_kpx, 1e-6)),
                    "junctions": int(np.sum(sk.degrees > 2)),
                    "endpoints": int(np.sum(sk.degrees == 1)),
                    "mean_ridge_strength": float(np.mean(ridges[skeleton_img])),
                })
                return result
            except Exception:
                pass  # Fall through to cv2 fallback

        # cv2 fallback
        skel_u8 = skeleton_img.astype(np.uint8)
        neighbors = cv2.filter2D(skel_u8, cv2.CV_16S, np.ones((3, 3), np.int16)) - skel_u8.astype(np.int16)
        count, _, _, _ = cv2.connectedComponentsWithStats(skel_u8, 8)
        result.update({
            "skeleton_available": True,
            "skan_available": False,
            "skeleton_px": int(skeleton_img.sum()),
            "skeleton_components": max(0, count - 1),
            "endpoints": int(np.sum(skeleton_img & (neighbors == 1))),
            "junctions": int(np.sum(skeleton_img & (neighbors >= 3))),
            "mean_ridge_strength": float(np.mean(ridges[skeleton_img])) if skeleton_img.any() else 0.0,
        })
        return result

    def _cv2_ridge_fallback(self, gray_f: np.ndarray) -> np.ndarray:
        """Pure cv2 Hessian ridge detection."""
        responses = []
        for sigma in self.ridge_sigmas:
            smooth = cv2.GaussianBlur(gray_f, (0, 0), float(sigma))
            dxx = cv2.Sobel(smooth, cv2.CV_32F, 2, 0, ksize=3)
            dyy = cv2.Sobel(smooth, cv2.CV_32F, 0, 2, ksize=3)
            dxy = cv2.Sobel(smooth, cv2.CV_32F, 1, 1, ksize=3)
            trace = dxx + dyy
            disc = np.sqrt(np.maximum((dxx - dyy) ** 2 + 4 * dxy ** 2, 0.0))
            l1 = 0.5 * (trace - disc)
            l2 = 0.5 * (trace + disc)
            ridge = np.abs(l1) * np.exp(-(l2 ** 2) / (np.maximum(np.abs(l1), 1e-6) ** 2 + 1e-6))
            responses.append(ridge)
        return np.max(np.stack(responses), axis=0)

    @staticmethod
    def _cv2_skeleton(binary: np.ndarray) -> np.ndarray:
        """Morphological thinning fallback."""
        img = binary.astype(np.uint8) * 255
        skeleton = np.zeros_like(img)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        for _ in range(256):
            opened = cv2.morphologyEx(img, cv2.MORPH_OPEN, element)
            skeleton = cv2.bitwise_or(skeleton, cv2.subtract(img, opened))
            img = cv2.erode(img, element)
            if cv2.countNonZero(img) == 0:
                break
        return skeleton > 0

    def _lbp_histogram(self, gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Compute normalized uniform LBP histogram within mask."""
        if int(mask.sum()) < 64:
            return np.zeros(10, np.float32)
        if _HAS_GLCM and local_binary_pattern is not None:
            lbp = local_binary_pattern(gray, P=self.lbp_P, R=self.lbp_R, method="uniform")
            hist, _ = np.histogram(lbp[mask], bins=10, range=(0, 10), density=False)
        else:
            # Numpy fallback
            g = gray.astype(np.int16)
            center = g[1:-1, 1:-1]
            code = np.zeros_like(center, np.uint8)
            neighbors = (
                g[:-2, :-2], g[:-2, 1:-1], g[:-2, 2:], g[1:-1, 2:],
                g[2:, 2:], g[2:, 1:-1], g[2:, :-2], g[1:-1, :-2],
            )
            for bit, nb in enumerate(neighbors):
                code |= ((nb >= center).astype(np.uint8) << bit)
            lbp = np.full(gray.shape, 9, np.uint8)
            lbp[1:-1, 1:-1] = code
            hist, _ = np.histogram(lbp[mask], bins=10, range=(0, 10), density=False)
        hist = hist.astype(np.float32)
        return hist / max(float(hist.sum()), 1e-8)

    def _glcm_stats(self, gray: np.ndarray, mask: np.ndarray) -> dict[str, float]:
        """GLCM texture statistics within mask."""
        if int(mask.sum()) < 64:
            return {k: 0.0 for k in ("glcm_contrast", "glcm_homogeneity", "glcm_energy", "glcm_correlation")}

        if _HAS_GLCM and graycomatrix is not None and graycoprops is not None:
            q = np.clip((gray.astype(np.float32) / 256.0 * self.glcm_levels).astype(np.uint8), 0, self.glcm_levels - 1)
            # Fill masked pixels with median
            q_masked = q.copy()
            median_val = int(np.median(q[mask]))
            q_masked[~mask] = median_val
            glcm = graycomatrix(
                q_masked, distances=self.glcm_distances,
                angles=self.glcm_angles, levels=self.glcm_levels,
                symmetric=True, normed=True,
            )
            return {
                "glcm_contrast": float(np.mean(graycoprops(glcm, "contrast"))),
                "glcm_homogeneity": float(np.mean(graycoprops(glcm, "homogeneity"))),
                "glcm_energy": float(np.mean(graycoprops(glcm, "energy"))),
                "glcm_correlation": float(np.mean(graycoprops(glcm, "correlation"))),
            }

        # Numpy fallback
        return self._glcm_numpy_fallback(gray, mask)

    def _glcm_numpy_fallback(self, gray: np.ndarray, mask: np.ndarray) -> dict[str, float]:
        """GLCM computation without scikit-image.

        Uses 4 directions: (0,1), (1,0), (1,1), (1,-1) to match
        texture_image.py's 4-direction GLCM analysis.
        """
        quant = np.clip((gray.astype(np.float32) / 256.0 * self.glcm_levels).astype(np.uint8), 0, self.glcm_levels - 1)
        filled = quant.copy()
        median_val = int(np.median(quant[mask]))
        filled[~mask] = median_val

        mat = np.zeros((self.glcm_levels, self.glcm_levels), np.float64)
        # 4 directions: horizontal, vertical, and two diagonals
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            # Compute valid slice ranges for offset (dy, dx)
            r_src = slice(max(0, -dy), filled.shape[0] - max(0, dy))
            c_src = slice(max(0, -dx), filled.shape[1] - max(0, dx))
            r_dst = slice(max(0, dy), filled.shape[0] - max(0, -dy))
            c_dst = slice(max(0, dx), filled.shape[1] - max(0, -dx))
            s = filled[r_src, c_src]
            d = filled[r_dst, c_dst]
            np.add.at(mat, (s.reshape(-1), d.reshape(-1)), 1)
            np.add.at(mat, (d.reshape(-1), s.reshape(-1)), 1)
        mat /= max(float(mat.sum()), 1.0)

        i, j = np.indices(mat.shape)
        contrast = float(np.sum(mat * (i - j) ** 2))
        homogeneity = float(np.sum(mat / (1.0 + np.abs(i - j))))
        energy = float(np.sqrt(np.sum(mat * mat)))
        mi = float(np.sum(i * mat))
        mj = float(np.sum(j * mat))
        si = float(np.sqrt(np.sum(((i - mi) ** 2) * mat)))
        sj = float(np.sqrt(np.sum(((j - mj) ** 2) * mat)))
        corr = float(np.sum((i - mi) * (j - mj) * mat) / max(si * sj, 1e-8))
        return {"glcm_contrast": contrast, "glcm_homogeneity": homogeneity, "glcm_energy": energy, "glcm_correlation": corr}

    def _image_zone_mask(
        self,
        skin_mask: np.ndarray,
        spec: Any,
        shape: tuple[int, int],
        pose_bin: str,
    ) -> np.ndarray:
        """Approximate an image-space zone mask from a skin mask and zone spec.

        Since image-space doesn't have a UV mapping, we approximate by:
        1. Finding the bounding box of the skin mask
        2. Dividing it into a grid
        3. Mapping the UV zone box to the grid
        This works well for near-frontal poses. For profile poses, the
        zone weights already gate out the occluded side.
        """
        h, w = shape
        ys, xs = np.where(skin_mask)
        if ys.size < 100:
            return np.zeros(shape, bool)

        # Bounding box of skin region
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        bh, bw = y1 - y0, x1 - x0

        # Map UV zone box to image bounding box
        umin, vmin, umax, vmax = spec.uv_box

        # In UV space, u is horizontal, v is vertical (v=0 at top of atlas = top of face)
        # In image space, x is horizontal, y is vertical
        # u maps to x: [umin, umax] -> [x0, x1]
        # v maps to y: [1-vmax, 1-vmin] -> [y0, y1] (UV v is inverted relative to image y)
        zx0 = x0 + int(umin * bw)
        zx1 = x0 + int(umax * bw)
        zy0 = y0 + int((1.0 - vmax) * bh)
        zy1 = y0 + int((1.0 - vmin) * bh)

        zx0, zx1 = max(0, zx0), min(w, zx1)
        zy0, zy1 = max(0, zy0), min(h, zy1)

        zone = np.zeros(shape, bool)
        zone[zy0:zy1, zx0:zx1] = skin_mask[zy0:zy1, zx0:zx1]
        return zone
