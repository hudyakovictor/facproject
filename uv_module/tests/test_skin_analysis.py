"""Tests for uv_module.skin_analysis — unified two-space forensic skin analysis."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uv_module.skin_analysis import SkinAnalyzer, SkinAnalysisResult


@pytest.fixture
def synthetic_face():
    """Create a synthetic face image and UV texture for testing."""
    rng = np.random.default_rng(42)

    # Original image (200x200 BGR)
    original = np.full((200, 200, 3), 180, dtype=np.uint8)
    # Add some texture variation
    noise = rng.integers(0, 30, (200, 200, 3), dtype=np.uint8)
    original = cv2.add(original, noise)
    # Add some wrinkle-like lines
    cv2.line(original, (50, 30), (150, 30), (120, 110, 100), 1)
    cv2.line(original, (60, 80), (60, 150), (110, 100, 90), 1)

    # Skin mask (elliptical)
    skin_mask_u8 = np.zeros((200, 200), dtype=np.uint8)
    cv2.ellipse(skin_mask_u8, (100, 100), (80, 90), 0, 0, 360, 255)
    skin_mask = skin_mask_u8 > 0

    # UV analytic texture (100x100)
    uv_analytic = cv2.resize(original, (100, 100))

    # UV observed mask (most of the atlas)
    uv_observed = np.zeros((100, 100), bool)
    uv_observed[10:90, 10:90] = True

    return original, skin_mask, uv_analytic, uv_observed


class TestSkinAnalyzer:
    def test_uv_geometry_analysis_returns_dict(self, synthetic_face):
        _, _, uv_analytic, uv_observed = synthetic_face
        analyzer = SkinAnalyzer()
        result = analyzer.analyze_uv_geometry(uv_analytic, uv_observed, "frontal")
        assert isinstance(result, dict)
        assert "available" in result
        assert result["available"] is True
        assert "zones" in result

    def test_uv_geometry_empty_mask(self):
        analyzer = SkinAnalyzer()
        uv = np.zeros((100, 100, 3), dtype=np.uint8)
        mask = np.zeros((100, 100), bool)
        result = analyzer.analyze_uv_geometry(uv, mask, "frontal")
        assert result["available"] is False

    def test_image_texture_analysis_returns_dict(self, synthetic_face):
        original, skin_mask, _, _ = synthetic_face
        analyzer = SkinAnalyzer()
        result = analyzer.analyze_image_texture(original, skin_mask, "frontal")
        assert isinstance(result, dict)
        assert "available" in result
        assert result["available"] is True
        assert "zones" in result

    def test_image_texture_empty_mask(self):
        analyzer = SkinAnalyzer()
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        mask = np.zeros((200, 200), bool)
        result = analyzer.analyze_image_texture(img, mask, "frontal")
        assert result["available"] is False

    def test_full_analysis_returns_result_object(self, synthetic_face):
        original, skin_mask, uv_analytic, uv_observed = synthetic_face
        analyzer = SkinAnalyzer()
        result = analyzer.analyze_full(
            uv_analytic=uv_analytic,
            uv_observed=uv_observed,
            original_bgr=original,
            skin_mask=skin_mask,
            pose_bin="frontal",
        )
        assert isinstance(result, SkinAnalysisResult)
        assert isinstance(result.uv_metrics, dict)
        assert isinstance(result.img_metrics, dict)
        assert isinstance(result.combined, dict)
        assert isinstance(result.zone_reports, dict)
        assert result.combined.get("uv_available") is True
        assert result.combined.get("img_available") is True

    def test_zone_reports_have_both_spaces(self, synthetic_face):
        original, skin_mask, uv_analytic, uv_observed = synthetic_face
        analyzer = SkinAnalyzer()
        result = analyzer.analyze_full(
            uv_analytic=uv_analytic,
            uv_observed=uv_observed,
            original_bgr=original,
            skin_mask=skin_mask,
            pose_bin="frontal",
        )
        # Frontal pose should have at least some zones with data
        for zone_name, report in result.zone_reports.items():
            assert "zone" in report
            # UV and/or img analysis should be present
            has_uv = "uv" in report
            has_img = "img" in report
            assert has_uv or has_img, f"Zone {zone_name} has neither UV nor img data"

    def test_profile_pose_only_sees_one_side(self, synthetic_face):
        original, skin_mask, uv_analytic, uv_observed = synthetic_face
        analyzer = SkinAnalyzer()

        # Left profile should not see right-side zones
        result = analyzer.analyze_uv_geometry(uv_analytic, uv_observed, "left_profile")
        right_zones = [z for z in result.get("zones", {}) if "right" in z]
        assert len(right_zones) == 0, f"Left profile should not see right zones, but found: {right_zones}"

    def test_graceful_without_skan(self):
        """Test that analyzer works even without skan (it may or may not be installed)."""
        analyzer = SkinAnalyzer()
        uv = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mask = np.zeros((100, 100), bool)
        mask[20:80, 20:80] = True
        result = analyzer.analyze_uv_geometry(uv, mask, "frontal")
        assert result["available"] is True
        # Should have some stats regardless of skan availability
        assert "skan_available" in result or "zones" in result

    def test_lbp_histogram_shape(self):
        analyzer = SkinAnalyzer()
        gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        mask = np.ones((100, 100), bool)
        hist = analyzer._lbp_histogram(gray, mask)
        assert hist.shape == (10,)
        assert abs(hist.sum() - 1.0) < 0.01  # should be normalized

    def test_glcm_stats_keys(self):
        analyzer = SkinAnalyzer()
        gray = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        mask = np.ones((100, 100), bool)
        mask[0:5, :] = False  # border
        stats = analyzer._glcm_stats(gray, mask)
        assert "glcm_contrast" in stats
        assert "glcm_homogeneity" in stats
        assert "glcm_energy" in stats
        assert "glcm_correlation" in stats
        assert all(np.isfinite(v) for v in stats.values())
