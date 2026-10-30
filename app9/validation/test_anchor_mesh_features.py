import numpy as np
import pytest
from scipy.sparse.csgraph import dijkstra

from app9.validation import anchor_mesh_features as geometry


def grid_mesh(size=7):
    vertices = np.array([[x, y, 0] for y in range(size) for x in range(size)], dtype=float)
    triangles = []
    for y in range(size - 1):
        for x in range(size - 1):
            a = y * size + x
            triangles.extend(((a, a + 1, a + size + 1), (a, a + size + 1, a + size)))
    return vertices, np.array(triangles, dtype=int)


def test_edge_geodesics_are_not_shorter_than_chords():
    vertices, triangles = grid_mesh()
    graph, _, _ = geometry.surface_graph(vertices, triangles)
    distances = dijkstra(graph, indices=0, directed=False)
    assert np.all(distances + 1e-12 >= np.linalg.norm(vertices - vertices[0], axis=1))
    assert distances[6] == pytest.approx(6)


def test_planar_interior_curvature_zero_and_boundary_excluded():
    vertices, triangles = grid_mesh()
    h, k, area, excluded = geometry.discrete_curvature(vertices, triangles)
    assert np.all(area > 0)
    assert np.allclose(h[~excluded], 0, atol=1e-10)
    assert np.allclose(k[~excluded], 0, atol=1e-10)
    assert np.isnan(h[excluded]).all()
    assert np.isnan(k[excluded]).all()


def test_curvature_scaling_law_on_closed_octahedron():
    vertices = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
    triangles = np.array([[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4],
                          [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
    h, k, _, excluded = geometry.discrete_curvature(vertices, triangles)
    h2, k2, _, _ = geometry.discrete_curvature(vertices * 3 + [4, 5, 6], triangles)
    assert not excluded.any()
    assert np.all(h > 0) and np.all(k > 0)
    assert np.allclose(h2 * 3, h)
    assert np.allclose(k2 * 9, k)


def test_spherical_band_powers_are_rigid_rotation_and_scale_invariant():
    rng = np.random.default_rng(8)
    points = rng.normal(size=(80, 3))
    weights = rng.uniform(0.1, 1, size=80)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    first = geometry.spherical_band_powers(points, weights, np.zeros(3), 2)
    second = geometry.spherical_band_powers(points @ rotation * 4 + [5, 6, 7], weights * 16, np.array([5, 6, 7]), 8)
    for degree in first:
        assert second[degree] == pytest.approx(first[degree], abs=1e-12)


def test_weighted_quantiles_ignore_invalid_values_and_follow_mass():
    measured = geometry.weighted_quantiles(np.array([0, 1, np.nan, 10]), np.array([1, 8, 1, 1]), (0.5,))
    assert measured[0] == pytest.approx(1)


def test_invalid_topology_rejected():
    vertices, triangles = grid_mesh()
    bad = triangles.copy()
    bad[0, 0] = len(vertices)
    with pytest.raises(ValueError):
        geometry.surface_graph(vertices, bad)


def test_fixed_region_descriptor_count_and_normalized_scale_invariance():
    vertices, triangles = grid_mesh(11)
    vertices[:, 2] = 0.002 * (vertices[:, 0] ** 2 + vertices[:, 1] ** 2)
    anchors = {"G": 60, "OrbA": 58, "OrbB": 62, "BrowA": 38, "BrowB": 42}
    first, meta = geometry.compute_region_features(vertices, triangles, anchors, 10, 0.25)
    second, _ = geometry.compute_region_features(vertices * 3 + [2, 4, 6], triangles, anchors, 30, 0.25)
    assert len(first) == len(meta["features"]) == 67
    for name, value in first.items():
        assert second[name] == pytest.approx(value, abs=1e-9)
