"""Тесты `app6.api.bfm_topology`: реальная BFM-геометрия без torch/net_recon.

Если `3ddfa_v3/assets/face_model.tar.gz` недоступен в окружении, тесты
пропускаются (`skip`), а не падают — соответствует политике "не изобретать
недостающие данные" из `app6/AGENTS.md`.
"""
from __future__ import annotations

import numpy as np
import pytest

from app6.api.bfm_topology import is_bfm_available, load_bfm_model

pytestmark = pytest.mark.skipif(not is_bfm_available(), reason="face_model.tar.gz недоступен в этом окружении")


def test_mean_shape_has_expected_topology() -> None:
    model = load_bfm_model()
    assert model.mean_shape.shape == (35709, 3)
    assert model.triangles.shape == (70789, 3)
    assert model.triangles.max() < 35709
    assert model.triangles.min() >= 0


def test_landmark_indices_match_106_and_134_contract() -> None:
    model = load_bfm_model()
    assert model.ldm106_indices.shape == (106,)
    assert model.ldm134_indices.shape == (134,)
    assert model.ldm106_indices.max() < 35709
    assert model.ldm134_indices.max() < 35709
    # landmark vertex indices must be unique within each set
    assert len(set(model.ldm106_indices.tolist())) == 106
    assert len(set(model.ldm134_indices.tolist())) == 134


def test_primary_zones_match_pose_policy_atlas() -> None:
    """A01..A20 здесь — те же зоны, что в app6/atlas/pose_policy_v3_9bins.csv."""
    model = load_bfm_model()
    assert model.primary_zone_ids == [f"A{n:02d}" for n in range(1, 21)]
    assert len(model.primary_zone_names) == 20


def test_compute_shape_matches_recon_formula() -> None:
    """Точное соответствие model/recon.py:184 без torch: u + id@a_id + exp@a_exp."""
    model = load_bfm_model()
    alpha_id = np.zeros(80, np.float32)
    alpha_exp = np.zeros(64, np.float32)
    shape = model.compute_shape(alpha_id, alpha_exp)
    np.testing.assert_allclose(shape, model.mean_shape, atol=1e-5)


def test_compute_shape_responds_to_identity_parameters() -> None:
    model = load_bfm_model()
    rng = np.random.default_rng(7)
    alpha_id = rng.normal(0, 1, 80).astype(np.float32)
    alpha_exp = np.zeros(64, np.float32)
    shape = model.compute_shape(alpha_id, alpha_exp)
    assert not np.allclose(shape, model.mean_shape)
    # Face-like output: still centered near the model's coordinate frame.
    assert np.all(np.abs(shape) < 2.0)


def test_compute_shape_rejects_wrong_dimension() -> None:
    model = load_bfm_model()
    with pytest.raises(ValueError):
        model.compute_shape(np.zeros(10), np.zeros(64))
    with pytest.raises(ValueError):
        model.compute_shape(np.zeros(80), np.zeros(5))


def test_landmark_vertices_lie_within_mean_shape_bounds() -> None:
    model = load_bfm_model()
    landmark_points = model.mean_shape[model.ldm134_indices]
    face_min, face_max = model.mean_shape.min(axis=0), model.mean_shape.max(axis=0)
    assert np.all(landmark_points >= face_min - 1e-4)
    assert np.all(landmark_points <= face_max + 1e-4)
