"""Геометрия проверяется на фигурах с известной кривизной: сфера и плоскость."""
import numpy as np

from src.mesh_geometry import (boundary_vertices, gaussian_curvature, mean_curvature, normal_angle_deg,
                               vertex_areas, vertex_normals, weighted_mean, zone_features)


def icosphere(radius=1.0, subdiv=3):
    t = (1 + 5 ** 0.5) / 2
    v = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t],
                  [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    f = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4],
                  [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8],
                  [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    v = v / np.linalg.norm(v, axis=1, keepdims=True)
    for _ in range(subdiv):
        cache, faces, verts = {}, [], list(v)

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = (verts[a] + verts[b]) / 2
                verts.append(m / np.linalg.norm(m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            faces += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        v, f = np.array(verts), np.array(faces)
    return v * radius, f


def grid(n=12):
    xs, ys = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
    v = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(n * n)])
    tri = []
    for i in range(n - 1):
        for j in range(n - 1):
            a, b, c, d = i * n + j, i * n + j + 1, (i + 1) * n + j, (i + 1) * n + j + 1
            tri += [[a, b, d], [a, d, c]]
    return v, np.array(tri)


def test_sphere_area_and_normals():
    v, tri = icosphere(2.0)
    assert abs(vertex_areas(v, tri).sum() / (4 * np.pi * 4.0) - 1) < 0.02
    n = vertex_normals(v, tri)
    assert np.all(np.einsum("ij,ij->i", n, v / np.linalg.norm(v, axis=1, keepdims=True)) > 0.99)


def test_sphere_curvature_scales_with_radius():
    for r in (1.0, 2.0):
        v, tri = icosphere(r)
        assert abs(np.median(mean_curvature(v, tri)) * r - 1) < 0.05
        assert abs(np.nanmedian(gaussian_curvature(v, tri)) * r * r - 1) < 0.1


def test_plane_is_flat_and_boundary_is_nan():
    v, tri = grid()
    b = boundary_vertices(tri, len(v))
    k = gaussian_curvature(v, tri)
    assert np.all(np.isnan(k[b])) and np.all(np.abs(k[~b]) < 1e-6)
    assert np.all(np.abs(mean_curvature(v, tri)[~b]) < 1e-6)


def test_normal_angle_and_weighted_mean():
    v, tri = icosphere()
    assert np.allclose(normal_angle_deg(v, v, tri), 0, atol=1e-3)
    squashed = v * np.array([1.0, 1.0, 0.5])
    assert normal_angle_deg(v, squashed, tri).max() > 5
    assert weighted_mean(np.array([1.0, np.nan, 3.0]), np.array([0, 1, 2]), np.array([1.0, 1.0, 3.0])) == 2.5


def test_zone_features_area_fractions_sum_to_one():
    v, tri = icosphere()
    half = np.where(v[:, 2] >= 0)[0]
    rest = np.where(v[:, 2] < 0)[0]
    feats = zone_features(v, tri, {"top": half, "bottom": rest})
    assert abs(feats["top"]["area_frac"] + feats["bottom"]["area_frac"] - 1) < 1e-9
