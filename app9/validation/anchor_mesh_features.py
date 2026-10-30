"""Full-mesh surface descriptors; model proxies, not measured bony anatomy."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.special import sph_harm_y

ROOT = Path(__file__).resolve().parents[2]
EPS = 1e-12
FAMILIES = ("edge_geodesic", "curvature", "spherical_moments", "anchor_distance")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_mesh(vertices: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    v, t = np.asarray(vertices, dtype=float), np.asarray(triangles)
    if v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        raise ValueError("vertices must be finite(N,3)")
    if t.ndim != 2 or t.shape[1] != 3 or not np.issubdtype(t.dtype, np.integer) or not len(t):
        raise ValueError("triangles must be integer(F,3)")
    if t.min() < 0 or t.max() >= len(v):
        raise ValueError("triangle index outside vertex array")
    return v, t.astype(np.int64, copy=False)


def surface_graph(vertices: np.ndarray, triangles: np.ndarray) -> tuple[csr_matrix, np.ndarray, np.ndarray]:
    v, t = validate_mesh(vertices, triangles)
    pairs = np.sort(np.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]])), axis=1)
    edges, counts = np.unique(pairs, axis=0, return_counts=True)
    lengths = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    keep = edges[:, 0] != edges[:, 1]
    edges, counts, lengths = edges[keep], counts[keep], lengths[keep]
    rows = np.concatenate((edges[:, 0], edges[:, 1]))
    columns = np.concatenate((edges[:, 1], edges[:, 0]))
    graph = csr_matrix((np.concatenate((lengths, lengths)), (rows, columns)), shape=(len(v), len(v)))
    boundary = np.zeros(len(v), dtype=bool)
    boundary[edges[counts == 1].ravel()] = True
    nonmanifold = np.zeros(len(v), dtype=bool)
    nonmanifold[edges[counts > 2].ravel()] = True
    return graph, boundary, nonmanifold


def discrete_curvature(vertices: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    v, t = validate_mesh(vertices, triangles)
    p = v[t]
    cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    valid = double_area > EPS
    t, p, double_area = t[valid], p[valid], double_area[valid]
    area = np.bincount(t.ravel(), weights=np.repeat(double_area / 6, 3), minlength=len(v))
    angle_sum = np.zeros(len(v))
    edge_rows, edge_columns, edge_weights = [], [], []
    for corner in range(3):
        first, second = (corner + 1) % 3, (corner + 2) % 3
        a, b = p[:, first] - p[:, corner], p[:, second] - p[:, corner]
        dot = np.sum(a * b, axis=1)
        angles = np.arctan2(np.linalg.norm(np.cross(a, b), axis=1), dot)
        angle_sum += np.bincount(t[:, corner], weights=angles, minlength=len(v))
        weight = 0.5 * dot / double_area
        edge_rows.extend((t[:, first], t[:, second]))
        edge_columns.extend((t[:, second], t[:, first]))
        edge_weights.extend((weight, weight))
    adjacency = csr_matrix((np.concatenate(edge_weights),
                            (np.concatenate(edge_rows), np.concatenate(edge_columns))), shape=(len(v), len(v)))
    laplacian_v = adjacency @ v - np.asarray(adjacency.sum(axis=1)).ravel()[:, None] * v
    h, k = np.full(len(v), np.nan), np.full(len(v), np.nan)
    usable = area > EPS
    h[usable] = 0.5 * np.linalg.norm(laplacian_v[usable] / area[usable, None], axis=1)
    k[usable] = (2 * np.pi - angle_sum[usable]) / area[usable]
    _, boundary, nonmanifold = surface_graph(v, t)
    # Both operators acquire artificial edge terms at an open surface boundary.
    excluded = boundary | nonmanifold
    h[excluded], k[excluded] = np.nan, np.nan
    return h, k, area, excluded


def weighted_quantiles(values: np.ndarray, weights: np.ndarray, quantiles: tuple[float, ...]) -> np.ndarray:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return np.full(len(quantiles), np.nan)
    values, weights = values[valid], weights[valid]
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    centres = (np.cumsum(weights) - 0.5 * weights) / weights.sum()
    return np.interp(quantiles, centres, values)


def spherical_band_powers(points: np.ndarray, weights: np.ndarray, centre: np.ndarray, ipd: float) -> dict[int, float]:
    offsets = points - centre
    radius = np.linalg.norm(offsets, axis=1)
    valid = (radius > EPS) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return {degree: float("nan") for degree in (1, 2, 3)}
    offsets, radius, weights = offsets[valid], radius[valid], weights[valid]
    azimuth = np.arctan2(offsets[:, 1], offsets[:, 0])
    polar = np.arccos(np.clip(offsets[:, 2] / radius, -1, 1))
    signal = radius / ipd
    result = {}
    for degree in (1, 2, 3):
        coefficients = [np.sum(weights * signal * sph_harm_y(degree, order, polar, azimuth)) / weights.sum()
                        for order in range(-degree, degree + 1)]
        result[degree] = float(np.sqrt(np.sum(np.abs(coefficients) ** 2)))
    return result


def compute_region_features(vertices: np.ndarray, triangles: np.ndarray, anchors: dict[str, int],
                            ipd: float, radius_fraction: float = 0.20) -> tuple[dict, dict]:
    v, t = validate_mesh(vertices, triangles)
    if not np.isfinite(ipd) or ipd <= EPS:
        raise ValueError("positive finite pupil spacing required")
    if list(anchors) != ["G", "OrbA", "OrbB", "BrowA", "BrowB"]:
        raise ValueError("fixed five-anchor order required")
    indices = np.array(list(anchors.values()), dtype=int)
    if indices.min() < 0 or indices.max() >= len(v):
        raise ValueError("anchor outside mesh")
    graph, boundary, nonmanifold = surface_graph(v, t)
    distances = dijkstra(graph, directed=False, indices=indices)
    h, k, area, excluded = discrete_curvature(v, t)
    values, descriptions, patch_quality = {}, {}, {}

    def record(name, value, family, unit, description):
        values[name] = float(value)
        descriptions[name] = {"family": family, "unit": unit, "description": description}

    labels = list(anchors)
    for a, b in itertools.combinations(range(5), 2):
        first, second = labels[a], labels[b]
        length = distances[a, indices[b]]
        chord = np.linalg.norm(v[indices[a]] - v[indices[b]])
        record(f"geo_length_{first}_{second}", length / ipd, "edge_geodesic", "dimensionless",
               "Full triangle-edge shortest-path length / model pupil spacing; upper bound to continuous geodesic.")
        record(f"geo_over_chord_{first}_{second}", length / chord if chord > EPS else np.nan,
               "edge_geodesic", "dimensionless", "Triangle-edge path length / straight3D chord.")
    for anchor_index, label in enumerate(labels):
        roi = np.isfinite(distances[anchor_index]) & (distances[anchor_index] <= radius_fraction * ipd) & (area > EPS)
        curvature_roi = roi & ~excluded
        patch_quality[label] = {"vertices": int(roi.sum()), "curvature_vertices": int(curvature_roi.sum()),
                                "area_over_ipd2": float(area[roi].sum() / ipd ** 2)}
        for prefix, field in (("H", h * ipd), ("K", k * ipd ** 2)):
            quartiles = weighted_quantiles(field[curvature_roi], area[curvature_roi], (0.25, 0.5, 0.75))
            record(f"curv_{prefix}_median_{label}", quartiles[1], "curvature", "dimensionless",
                   f"Area-weighted median {'absolute mean' if prefix == 'H' else 'signed Gaussian'} curvature in geodesic patch; boundaries excluded.")
            record(f"curv_{prefix}_iqr_{label}", quartiles[2] - quartiles[0], "curvature", "dimensionless",
                   "Area-weighted curvature interquartile spread in the fixed geodesic patch.")
        powers = spherical_band_powers(v[roi], area[roi], v[indices[anchor_index]], ipd)
        for degree, power in powers.items():
            record(f"shape_spherical_l{degree}_{label}", power, "spherical_moments", "dimensionless",
                   "Area-weighted anchor-centred radial spherical moment band norm; partial patch, not illumination alpha_sh or a closed spherical surface.")
        if label != "G":
            lengths = np.linalg.norm(v[roi] - v[anchors["G"]], axis=1) / ipd
            valid = np.isfinite(lengths) & (area[roi] > 0)
            weights = area[roi][valid]
            array = lengths[valid]
            statistics = {"min": float(array.min()) if len(array) else np.nan,
                          "mean": float(np.sum(array * weights) / weights.sum()) if len(array) else np.nan,
                          "max": float(array.max()) if len(array) else np.nan}
            for statistic, value in statistics.items():
                record(f"distance_style_{statistic}_{label}_to_G", value, "anchor_distance", "dimensionless",
                       "3D point-distance distribution from a surface patch to glabella; a PRDL-inspired analogue, NOT the original2D semantic reprojection loss.")
    metadata = {"features": descriptions, "anchors": {name: int(index) for name, index in anchors.items()},
                "radius_fraction_ipd": radius_fraction, "descriptor_count": len(values),
                "quality": {"vertex_count": len(v), "triangle_count": len(t), "boundary_vertices": int(boundary.sum()),
                            "nonmanifold_vertices": int(nonmanifold.sum()), "patches": patch_quality},
                "limitations": ["Fixed model surface proxies, not actual bony orbital/glabellar anatomy.",
                                "Edge-Dijkstra distances approximate surface geodesics; no exact continuous solver is claimed.",
                                "Spherical descriptors integrate an anchor-centred partial patch, not a full star-shaped face sphere.",
                                "Distance distributions are3D analogues, not original PRDL loss with ground-truth2D semantic masks."]}
    if len(values) != 67:
        raise RuntimeError("expected67 fixed single descriptors")
    return values, metadata


def compute_anchor_features(vertices: np.ndarray, triangles: np.ndarray, lmk106_indices: np.ndarray,
                            lmk134_indices: np.ndarray) -> tuple[dict, dict]:
    l106, l134 = np.asarray(lmk106_indices, dtype=int), np.asarray(lmk134_indices, dtype=int)
    if l106.shape != (106,) or l134.shape != (134,):
        raise ValueError("106/134 model-vertex index arrays required")
    anchors = {"G": 29891, "OrbA": int(l134[16]), "OrbB": int(l134[38]),
               "BrowA": int(l134[47]), "BrowB": int(l134[60])}
    ipd = float(np.linalg.norm(vertices[l106[104]] - vertices[l106[105]]))
    return compute_region_features(vertices, triangles, anchors, ipd)


def ensure_mesh_cache(frame, store: Path, landmark_cache: Path) -> tuple[dict, dict]:
    assets = ROOT / "3ddfa_v3/assets"
    names = ("face_model.npy", "net_recon.pth", "retinaface_resnet50_2020-07-20_old_torch.pth",
             "large_base_net.pth", "similarity_Lm3D_all.mat")
    if any(not (assets / name).is_file() for name in names):
        raise FileNotFoundError("full-mesh study requires the already installed assets; no download is attempted")
    code = [ROOT / "app8/reconstruction.py", ROOT / "app8/imaging.py", ROOT / "morphing/backend/aligner.py"]
    fingerprint_data = {str(path.relative_to(ROOT)): sha256(path) for path in [*code, *(assets / name for name in names)]}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
    store.mkdir(parents=True, exist_ok=True)
    topology_path = store / "topology.npz"
    reference = {}
    for group in frame.group.unique():
        collected = {}
        for part in sorted(landmark_cache.glob(f"lmk_{group}*.npz")):
            with np.load(part, allow_pickle=False) as archive:
                collected.update({str(name): points for name, points in zip(archive["files"], archive["pts"], strict=True)})
        reference[group] = collected
    paths, records, errors = {}, [], []
    reconstruct, align = None, None
    for position, row in enumerate(frame.to_dict("records")):
        group, filename = str(row["group"]), str(row["filename"])
        if Path(group).name != group or Path(filename).name != filename:
            raise ValueError("unsafe mesh-cache name")
        source = Path(row["source_path"])
        source_hash = sha256(source)
        if source_hash != row["sha256"]:
            raise RuntimeError(f"photo changed after landmark manifest: {group}/{filename}")
        directory = store / group
        directory.mkdir(exist_ok=True)
        path = directory / f"{Path(filename).stem}.npz"
        reused = False
        deviation = None
        if path.is_file() and topology_path.is_file():
            with np.load(path, allow_pickle=False) as cached:
                reused = str(cached["source_sha256"].item()) == source_hash and str(cached["pipeline_sha256"].item()) == fingerprint
                if reused:
                    deviation = float(cached["reference_max_abs_error"].item())
        try:
            if not reused:
                if reconstruct is None:
                    import torch
                    from app8.reconstruction import reconstruct_image
                    from morphing.backend.aligner import align_identity_mesh
                    torch.set_num_threads(2)
                    reconstruct, align = reconstruct_image, align_identity_mesh
                recon = reconstruct(source, device="cpu")
                if recon is None:
                    raise ValueError("no full reconstruction")
                vertices, _, _ = align(recon)
                triangles, l106, l134 = recon["triangles"], recon["ldm106_indices"], recon["ldm134_indices"]
                deviation = float(np.max(np.abs(vertices[l106] - reference[group][filename])))
                if deviation > 2e-5:
                    raise ValueError(f"fresh full-mesh landmark mismatch {deviation}")
                if topology_path.is_file():
                    with np.load(topology_path, allow_pickle=False) as topology:
                        if not (np.array_equal(topology["triangles"], triangles)
                                and np.array_equal(topology["ldm106_indices"], l106)
                                and np.array_equal(topology["ldm134_indices"], l134)):
                            raise ValueError("mesh topology or landmark mapping changed")
                else:
                    np.savez_compressed(topology_path, triangles=triangles, ldm106_indices=l106, ldm134_indices=l134)
                temporary = path.with_suffix(".tmp.npz")
                np.savez_compressed(temporary, vertices=vertices.astype(np.float32), source_sha256=source_hash,
                                    pipeline_sha256=fingerprint, reference_max_abs_error=deviation)
                temporary.replace(path)
            paths[(group, filename)] = path
            records.append({"group": group, "filename": filename, "path": str(path), "source_sha256": source_hash,
                            "mesh_sha256": sha256(path), "reference_max_abs_error": deviation, "reused": reused})
        except (ValueError, KeyError, RuntimeError) as exc:
            errors.append({"group": group, "filename": filename, "error": str(exc)})
        if (position + 1) % 10 == 0 or position + 1 == len(frame):
            print(f"Full meshes {position + 1}/{len(frame)}, available={len(paths)}, errors={len(errors)}", flush=True)
    manifest = {"topology_path": str(topology_path), "pipeline_sha256": fingerprint, "pipeline_files_sha256": fingerprint_data,
                "topology_sha256": sha256(topology_path) if topology_path.is_file() else None,
                "rows": records, "errors": errors, "n_meshes": len(paths), "normalization": "identity-only, centred RMS-106;CPU threads2"}
    (store / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return paths, manifest
