"""Separate intrinsic3D-to-UV and observational UV-to-photo transforms."""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

EPS = 1e-12


def normalized_uv(uv_coords: np.ndarray) -> np.ndarray:
    uv = np.asarray(uv_coords, dtype=float)
    if uv.ndim != 2 or uv.shape[1] != 2 or not np.isfinite(uv).all():
        raise ValueError("finite(N,2) UV coordinates required")
    if uv.min() < -1e-6 or uv.max() > 1 + 1e-6:
        raise ValueError("diagnostics require explicitly normalized UV coordinates; units must not be guessed")
    return uv


def triangle_warp_metrics(vertices: np.ndarray, triangles: np.ndarray, uv_coords: np.ndarray,
                          projection: np.ndarray, uv_size: int) -> dict[str, np.ndarray]:
    vertices, faces = np.asarray(vertices, dtype=float), np.asarray(triangles, dtype=int)
    uv, photo = normalized_uv(uv_coords), np.asarray(projection, dtype=float)
    if vertices.shape != (len(uv), 3) or photo.shape != (len(uv), 2):
        raise ValueError("vertex, UV and original-pixel projection indexing must match")
    if faces.ndim != 2 or faces.shape[1] != 3 or faces.min() < 0 or faces.max() >= len(uv):
        raise ValueError("invalid triangle indices")
    uv_pixels = uv * (uv_size - 1)
    uv_pixels[:, 1] = (1 - uv[:, 1]) * (uv_size - 1)
    surface = vertices[faces]
    e1, e2 = surface[:, 1] - surface[:, 0], surface[:, 2] - surface[:, 0]
    length = np.linalg.norm(e1, axis=1)
    cross_length = np.linalg.norm(np.cross(e1, e2), axis=1)
    intrinsic = np.zeros((len(faces), 2, 2))
    intrinsic[:, 0, 0] = length
    intrinsic[:, 0, 1] = np.divide(np.sum(e1 * e2, axis=1), length, out=np.zeros(len(faces)), where=length > EPS)
    intrinsic[:, 1, 1] = np.divide(cross_length, length, out=np.zeros(len(faces)), where=length > EPS)
    uv_tri, uv_norm_tri, image_tri = uv_pixels[faces], uv[faces], photo[faces]
    uv_edges = np.stack((uv_tri[:, 1] - uv_tri[:, 0], uv_tri[:, 2] - uv_tri[:, 0]), axis=2)
    uv_norm_edges = np.stack((uv_norm_tri[:, 1] - uv_norm_tri[:, 0], uv_norm_tri[:, 2] - uv_norm_tri[:, 0]), axis=2)
    image_edges = np.stack((image_tri[:, 1] - image_tri[:, 0], image_tri[:, 2] - image_tri[:, 0]), axis=2)
    uv_det, image_det = np.linalg.det(uv_edges), np.linalg.det(image_edges)
    valid_surface = np.isfinite(intrinsic).all(axis=(1, 2)) & (cross_length > EPS) & (np.abs(uv_det) > EPS)
    valid_photo = valid_surface & np.isfinite(image_edges).all(axis=(1, 2)) & (np.abs(image_det) > EPS)
    intrinsic_to_uv, uv_to_photo = np.full((len(faces), 2, 2), np.nan), np.full((len(faces), 2, 2), np.nan)
    intrinsic_to_uv[valid_surface] = uv_norm_edges[valid_surface] @ np.linalg.inv(intrinsic[valid_surface])
    uv_to_photo[valid_photo] = image_edges[valid_photo] @ np.linalg.inv(uv_edges[valid_photo])
    sv_surface, sv_photo = np.full((len(faces), 2), np.nan), np.full((len(faces), 2), np.nan)
    sv_surface[valid_surface] = np.linalg.svd(intrinsic_to_uv[valid_surface], compute_uv=False)
    sv_photo[valid_photo] = np.linalg.svd(uv_to_photo[valid_photo], compute_uv=False)
    return {
        "jacobian_3d_uv": intrinsic_to_uv, "jacobian_uv_photo": uv_to_photo,
        "scales_3d_uv": sv_surface, "scales_uv_photo": sv_photo,
        "anisotropy_3d_uv": np.divide(sv_surface[:, 0], sv_surface[:, 1], out=np.full(len(faces), np.nan), where=sv_surface[:, 1] > EPS),
        "anisotropy_uv_photo": np.divide(sv_photo[:, 0], sv_photo[:, 1], out=np.full(len(faces), np.nan), where=sv_photo[:, 1] > EPS),
        "density_uv_photo": np.abs(np.linalg.det(uv_to_photo)),
        "orientation_uv_photo": np.sign(image_det * uv_det),
        "orientation_3d_uv": np.sign(np.linalg.det(uv_norm_edges)),
        "area_surface": cross_length / 2, "area_uv_normalized": np.abs(np.linalg.det(uv_norm_edges)) / 2,
        "area_uv_pixels": np.abs(uv_det) / 2, "area_photo_pixels": np.abs(image_det) / 2,
        "valid_3d_uv": valid_surface, "valid_uv_photo": valid_photo,
    }


def visible_photo_metrics(metrics: dict, triangle_visible: np.ndarray) -> dict:
    """Exclude unobserved photo transport, without changing intrinsic surface geometry."""
    visible = np.asarray(triangle_visible, dtype=bool)
    if visible.shape != np.asarray(metrics["anisotropy_uv_photo"]).shape:
        raise ValueError("visibility must match triangle metric indexing")
    result = {**metrics, "triangle_visible": visible}
    for key in ("anisotropy_uv_photo", "density_uv_photo"):
        result[key] = np.where(visible, metrics[key], np.nan)
    return result


def weighted_quantiles(values: np.ndarray, weights: np.ndarray, probabilities=(0.25, 0.5, 0.75, 0.95)) -> np.ndarray:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return np.full(len(probabilities), np.nan)
    values, weights = values[valid], weights[valid]
    order = np.argsort(values)
    centres = (np.cumsum(weights[order]) - weights[order] / 2) / weights.sum()
    return np.interp(probabilities, centres, values[order])


def largest_connected_anomaly(triangles: np.ndarray, mask: np.ndarray, areas: np.ndarray) -> float:
    faces = np.asarray(triangles, dtype=int)
    selected = np.flatnonzero(mask)
    if not len(selected):
        return 0.0
    edge_faces = {}
    rows, columns = [], []
    for index in selected:
        a, b, c = faces[index]
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(edge))
            if key in edge_faces:
                other = edge_faces[key]
                rows.extend((index, other))
                columns.extend((other, index))
            else:
                edge_faces[key] = index
    adjacency = csr_matrix((np.ones(len(rows)), (rows, columns)), shape=(len(faces), len(faces)))
    _, labels = connected_components(adjacency[selected][:, selected], directed=False)
    return float(np.bincount(labels, weights=areas[selected]).max())


def region_summary(metrics: dict, regions: np.ndarray, names: list[str], triangles: np.ndarray,
                   anomaly: np.ndarray | None = None) -> dict:
    if "triangle_visible" in metrics:
        metrics = visible_photo_metrics(metrics, metrics["triangle_visible"])
    result = {}
    area = metrics["area_surface"]
    for index, name in enumerate(names):
        mask = regions == index
        row = {"triangle_count": int(mask.sum()), "surface_area": float(area[mask].sum())}
        for key in ("anisotropy_3d_uv", "anisotropy_uv_photo", "density_uv_photo"):
            q25, median, q75, p95 = weighted_quantiles(metrics[key][mask], area[mask])
            row[key] = {"median": float(median), "iqr": float(q75 - q25), "p95": float(p95)}
        invalid = mask & ~metrics["valid_uv_photo"]
        row["invalid_count_fraction"] = float(invalid.sum() / max(mask.sum(), 1))
        row["invalid_surface_fraction"] = float(area[invalid].sum() / max(area[mask].sum(), EPS))
        row["largest_anomaly_surface_area"] = largest_connected_anomaly(triangles, mask & anomaly, area) if anomaly is not None else None
        result[name] = row
    return result
