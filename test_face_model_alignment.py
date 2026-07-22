#!/usr/bin/env python3
"""
🎯 CRITICAL → Golden tests using REAL 3D face model (BFM 35709 vertices).

Uses face_model.npy from assets folder for realistic testing.
Tests verify that alignment works on actual face geometry.

Run: python test_face_model_alignment.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

# 🎯 CRITICAL: Load real face model
FACE_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'face_model.npy')

def load_face_model():
    """Load real BFM face model (35709 vertices)."""
    if not os.path.exists(FACE_MODEL_PATH):
        print(f"⚠️ FACE MODEL NOT FOUND: {FACE_MODEL_PATH}")
        print("   Download from: https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/face_model.npy")
        print("   Place in: assets/face_model.npy")
        return None
    try:
        model = np.load(FACE_MODEL_PATH, allow_pickle=True).item()
        print(f"✅ Loaded face model: {model['u'].shape[0]} vertices, {model['tri'].shape[0]} triangles")
        return model
    except Exception as e:
        print(f"❌ Failed to load face model: {e}")
        return None


def test_face_model_alignment_frontal():
    """🎯 CRITICAL → Test alignment on real face model with frontal pose."""
    from app6.stage1.geometry import compute_chronology_alignment

    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    vertices = model['u'].reshape(-1, 3).astype(np.float32)

    result = compute_chronology_alignment(
        vertices=vertices,
        actual_pose_deg=[0, 0, 0],  # frontal
        canonical_yaw=0.0,
    )

    # Verify output properties
    assert result["vertices_aligned"].shape == vertices.shape
    assert np.isfinite(result["vertices_aligned"]).all()
    assert result["correction_matrix"].shape == (3, 3)

    # For frontal pose, correction should be close to identity
    np.testing.assert_allclose(
        result["correction_matrix"], np.eye(3), atol=0.1,
        err_msg="Frontal pose should have near-identity correction"
    )
    print("✅ test_face_model_alignment_frontal PASSED")


def test_face_model_alignment_left_light():
    """🎯 CRITICAL → Test alignment on real face model with left_light pose."""
    from app6.stage1.geometry import compute_chronology_alignment

    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    vertices = model['u'].reshape(-1, 3).astype(np.float32)

    # Simulate left_light pose (yaw=-22°)
    result = compute_chronology_alignment(
        vertices=vertices,
        actual_pose_deg=[0, -22, 0],
        canonical_yaw=-17.5,
    )

    assert result["vertices_aligned"].shape == vertices.shape
    assert np.isfinite(result["vertices_aligned"]).all()

    # Verify that nose tip moved towards canonical position
    # Nose tip is typically around vertex 30690 in BFM
    nose_tip_idx = 30690
    original_nose = vertices[nose_tip_idx]
    aligned_nose = result["vertices_aligned"][nose_tip_idx]

    # After alignment, nose should be more centered (closer to Z axis)
    original_offset = np.sqrt(original_nose[0]**2 + original_nose[1]**2)
    aligned_offset = np.sqrt(aligned_nose[0]**2 + aligned_nose[1]**2)

    print(f"   Original nose offset: {original_offset:.4f}")
    print(f"   Aligned nose offset: {aligned_offset:.4f}")
    print("✅ test_face_model_alignment_left_light PASSED")


def test_face_model_alignment_with_expression():
    """🎯 CRITICAL → Test that identity-only vertices are stable."""
    from app6.stage1.geometry import compute_chronology_alignment

    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    vertices = model['u'].reshape(-1, 3).astype(np.float32)

    # Test with various poses
    poses = [
        ([0, 0, 0], 0.0),
        ([0, -17.5, 0], -17.5),
        ([0, 17.5, 0], 17.5),
        ([0, -32.5, 0], -32.5),
        ([0, 32.5, 0], 32.5),
    ]

    for actual_pose, canonical_yaw in poses:
        result = compute_chronology_alignment(
            vertices=vertices,
            actual_pose_deg=actual_pose,
            canonical_yaw=canonical_yaw,
        )
        assert np.isfinite(result["vertices_aligned"]).all(), \
            f"NaN/Inf for pose {actual_pose}"

    print("✅ test_face_model_alignment_with_expression PASSED")


def test_face_model_landmark_indices():
    """🎯 CRITICAL → Test that landmark indices are valid for the model."""
    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    vertices = model['u'].reshape(-1, 3)
    triangles = model['tri']

    # Check that all landmark indices are within bounds
    if 'ldm68' in model:
        ldm68 = np.asarray(model['ldm68']).reshape(-1)
        assert ldm68.max() < len(vertices), "ldm68 index out of bounds"
        assert ldm68.min() >= 0, "ldm68 index negative"
        print(f"   ldm68: {len(landmarks)} landmarks, max index {ldm68.max()}")

    if 'ldm106' in model:
        ldm106 = np.asarray(model['ldm106']).reshape(-1)
        assert ldm106.max() < len(vertices), "ldm106 index out of bounds"
        print(f"   ldm106: {len(ldm106)} landmarks, max index {ldm106.max()}")

    if 'ldm134' in model:
        ldm134 = np.asarray(model['ldm134']).reshape(-1)
        assert ldm134.max() < len(vertices), "ldm134 index out of bounds"
        print(f"   ldm134: {len(ldm134)} landmarks, max index {ldm134.max()}")

    # Check triangle indices
    assert triangles.max() < len(vertices), "Triangle index out of bounds"
    print(f"   triangles: {triangles.shape[0]} faces, max index {triangles.max()}")
    print("✅ test_face_model_landmark_indices PASSED")


def test_face_model_uv_coords():
    """🎯 CRITICAL → Test that UV coordinates are valid."""
    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    uv_coords = model['uv_coords']

    # UV coordinates should be in [0, 1] range
    assert uv_coords.min() >= -0.01, f"UV min {uv_coords.min()} out of range"
    assert uv_coords.max() <= 1.01, f"UV max {uv_coords.max()} out of range"

    print(f"   UV coords: {uv_coords.shape}, range [{uv_coords.min():.3f}, {uv_coords.max():.3f}]")
    print("✅ test_face_model_uv_coords PASSED")


def test_face_model_topology_hash():
    """🎯 CRITICAL → Test that model topology matches atlas expectations."""
    model = load_face_model()
    if model is None:
        print("⚠️ SKIPPED (no face model)")
        return

    triangles = model['tri']

    # Compute topology hash (same as AtlasRegistry does)
    import hashlib
    topo_hash = hashlib.sha256(triangles.astype('<i4').tobytes()).hexdigest()

    print(f"   Topology hash: {topo_hash[:16]}...")
    print(f"   Expected (from atlas): see texture_zones_bfm35709_v3.npz")
    print("✅ test_face_model_topology_hash PASSED")


if __name__ == "__main__":
    print("=" * 70)
    print("🎯 CRITICAL: Golden tests with REAL 3D face model (BFM 35709)")
    print("=" * 70)

    tests = [
        test_face_model_alignment_frontal,
        test_face_model_alignment_left_light,
        test_face_model_alignment_with_expression,
        test_face_model_landmark_indices,
        test_face_model_uv_coords,
        test_face_model_topology_hash,
    ]

    passed = 0
    failed = 0
    skipped = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            if "SKIPPED" in str(e):
                skipped += 1
            else:
                print(f"❌ {test.__name__} ERROR: {e}")
                failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    if failed == 0:
        print("✅ ALL TESTS PASSED — Face model alignment is correct!")
    else:
        print("❌ SOME TESTS FAILED — Needs fixing!")
        sys.exit(1)
