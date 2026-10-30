"""Deterministic CPU rasterization via upstream face3d Cython renderer + ffmpeg."""

import sys, subprocess, json
import numpy as np
from PIL import Image
from server.config import ROOT, atomic_json

PALETTES = {
    "turbo": [
        (48 / 255, 18 / 255, 59 / 255),
        (58 / 255, 116 / 255, 232 / 255),
        (41 / 255, 199 / 255, 165 / 255),
        (176 / 255, 237 / 255, 61 / 255),
        (248 / 255, 170 / 255, 39 / 255),
        (204 / 255, 50 / 255, 27 / 255),
    ],
    "viridis": [
        (0.267, 0.005, 0.329),
        (0.230, 0.322, 0.546),
        (0.128, 0.567, 0.551),
        (0.369, 0.789, 0.383),
        (0.993, 0.906, 0.144),
    ],
    "coolwarm": [
        (0.23, 0.30, 0.75),
        (0.55, 0.69, 0.99),
        (0.87, 0.87, 0.87),
        (0.96, 0.60, 0.48),
        (0.70, 0.02, 0.15),
    ],
}


def colorize(
    values, lo=0.0, hi=0.05, palette="turbo", gamma=1.0, inverse=False, custom=None
):
    p = np.asarray(PALETTES.get(palette, PALETTES["turbo"]))
    x = np.clip((values - lo) / max(hi - lo, 1e-8), 0, 1)
    if inverse:
        x = 1 - x
    x = x**gamma
    if palette == "custom" and custom:
        from PIL import ImageColor

        p = (
            np.array([ImageColor.getrgb(custom[k]) for k in ["low", "mid", "high"]])
            / 255.0
        )
        mid = float(custom.get("midPosition", 0.5))
        idx = np.where(
            x < mid, x / max(mid, 0.001), 1 + (x - mid) / max(1 - mid, 0.001)
        )
    else:
        idx = x * (len(p) - 1)
    i = np.floor(idx).astype(int)
    j = np.minimum(i + 1, len(p) - 1)
    w = (idx - i)[:, None]
    return (p[i] * (1 - w) + p[j] * w).astype(np.float32)


def rasterize(
    vertices, tri, colors, size=512, yaw=0.0, pitch=0.0, zoom=1.0, wireframe=False
):
    path = str(ROOT / "vendor/3DDFA-V3")
    if path not in sys.path:
        sys.path.insert(0, path)
    from util.cython_renderer import mesh_core_cython as core

    # Fixed orthographic camera. Same camera for all exported frames.
    v = vertices.copy()
    a = np.radians(yaw)
    b = np.radians(pitch)
    ry = np.array(
        [[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]], np.float32
    )
    rx = np.array(
        [[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]], np.float32
    )
    v = v @ (ry @ rx).T
    n = np.zeros_like(v)
    tn = np.cross(v[tri[:, 1]] - v[tri[:, 0]], v[tri[:, 2]] - v[tri[:, 0]])
    for k in range(3):
        np.add.at(n, tri[:, k], tn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-10)
    lit = 0.53 + 0.47 * np.abs(n @ np.array([-0.25, 0.35, 0.90], np.float32))
    colors = np.ascontiguousarray(
        np.clip(colors * lit[:, None], 0, 1), dtype=np.float32
    )
    v[:, 0] = v[:, 0] * size / 3.6 * zoom + size * 0.5
    v[:, 1] = -v[:, 1] * size / 3.6 * zoom + size * 0.41
    v[:, 2] *= size / 3.6 * zoom
    v = np.ascontiguousarray(v, dtype=np.float32)
    tri = np.ascontiguousarray(tri, dtype=np.int32)
    img = np.empty((size, size, 3), np.float32)
    img[:] = (0.055, 0.075, 0.095)
    depth = np.full((size, size), -999999.0, np.float32)
    tb = np.full((size, size), -1, np.int32)
    bw = np.zeros((size, size, 3), np.float32)
    core.MeshRenderer_cpu_core(
        img, v, tri, colors, depth, tb, bw, len(v), len(tri), size, size, 3
    )
    rgb = np.uint8(np.clip(img, 0, 1) * 255)
    if wireframe:
        import cv2

        overlay = rgb.copy()
        for indices in tri[::7]:
            if n[indices, 2].mean() > 0.05:
                cv2.polylines(
                    overlay,
                    [v[indices, :2].astype(np.int32)],
                    True,
                    (115, 170, 182),
                    1,
                    cv2.LINE_AA,
                )
        rgb = cv2.addWeighted(rgb, 0.72, overlay, 0.28, 0)
    return rgb


def export_morph(job, params):
    from server.storage import photo, load_features
    from server.models.tddfa import get_model, VERSION
    from server.registry import version

    ids = params["photo_ids"]
    ps = [photo(id) for id in ids]
    features = [load_features(p) for p in ps]
    # Cached topology is sufficient: exporting must not reload the neural net.
    topology_path = ROOT / "data/topology.json"
    tri = (
        np.asarray(json.loads(topology_path.read_text())["triangles"], np.int32)
        if topology_path.exists()
        else get_model().tri
    )
    seconds = float(params.get("seconds", 2))
    fps = int(params.get("fps", 24))
    size = int(params.get("resolution", 512))
    frames_per = max(1, round(seconds * fps))
    total = (len(ids) - 1) * frames_per + 1
    out = ROOT / "exports" / f"morph-{job.id}.mp4"
    tmp = out.with_suffix(".tmp.mp4")
    out.parent.mkdir(exist_ok=True)
    import imageio_ffmpeg

    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{size}x{size}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    reference_photo = (
        photo(params["reference_id"]) if params.get("reference_id") else ps[0]
    )
    ref = load_features(reference_photo)
    reference = (
        ref["identity"] if params.get("metric") == "identity" else ref["vertices"]
    )
    finished = False
    neighbors = None
    if params.get("smoothing", 0):
        neighbors = [set() for _ in range(len(reference))]
        for a, b, c in tri:
            neighbors[a].update((b, c))
            neighbors[b].update((a, c))
            neighbors[c].update((a, b))
        neighbors = [list(s) for s in neighbors]
    normals = None
    if params.get("metric") == "normal":
        normals = np.zeros_like(reference)
        tn = np.cross(
            reference[tri[:, 1]] - reference[tri[:, 0]],
            reference[tri[:, 2]] - reference[tri[:, 0]],
        )
        for k in range(3):
            np.add.at(normals, tri[:, k], tn)
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
    try:
        for frame in range(total):
            job.check()
            segment = min(frame // frames_per, len(features) - 2)
            t = min((frame - segment * frames_per) / frames_per, 1.0)
            if params.get("easing", "smooth") == "smooth":
                t = t * t * (3 - 2 * t)
            a, b = features[segment], features[segment + 1]
            v = a["vertices"] * (1 - t) + b["vertices"] * t
            cols = (
                a["albedo"] * (1 - t) + b["albedo"] * t
                if params.get("texture", False)
                else np.tile(np.array([0.53, 0.59, 0.65], np.float32), (len(v), 1))
            )
            if params.get("heatmap", True):
                comparison = (
                    a["identity"] * (1 - t) + b["identity"] * t
                    if params.get("metric") == "identity"
                    else v
                )
                delta = (
                    np.abs(np.sum((comparison - reference) * normals, axis=1))
                    if normals is not None
                    else np.linalg.norm(comparison - reference, axis=1)
                )
                if neighbors is not None:
                    for _ in range(int(params.get("smoothing", 0))):
                        delta = np.array(
                            [
                                (delta[i] + delta[ix].sum()) / (len(ix) + 1)
                                for i, ix in enumerate(neighbors)
                            ],
                            np.float32,
                        )
                heat = colorize(
                    delta,
                    params.get("vmin", 0),
                    params.get("vmax", 0.06),
                    params.get("palette", "turbo"),
                    params.get("gamma", 1),
                    params.get("inverse", False),
                    params,
                )
                opacity = np.full((len(v), 1), params.get("opacity", 0.85), np.float32)
                opacity[
                    (delta < params.get("vmin", 0)) | (delta > params.get("vmax", 0.06))
                ] = params.get("outsideOpacity", 0.85)
                if params.get("onlyAbove", False):
                    opacity[delta < params.get("vmin", 0)] = 0
                cols = cols * (1 - opacity) + heat * opacity
            rgb = rasterize(v, tri, cols, size, params.get("yaw", 0))
            proc.stdin.write(rgb.tobytes())
            if frame % max(1, fps // 4) == 0:
                job.update(frame / total, f"Рендер {frame + 1}/{total} кадров")
        proc.stdin.close()
        err = proc.stderr.read().decode()
        code = proc.wait(timeout=60)
        if code:
            raise RuntimeError("ffmpeg: " + err[-1000:])
        job.check()
        tmp.replace(out)
        finished = True
        manifest = {
            "model": VERSION,
            "seed": 42,
            "config_version": version(),
            "params": params,
            "source_photos": [
                {
                    "id": p["id"],
                    "hash": p["hash"],
                    "date": p["date"],
                    "group": p["group"],
                    "feature_metadata": json.loads(
                        (ROOT / "cache" / p["id"] / "meta.json").read_text()
                    ),
                }
                for p in ps
            ],
            "reference_photo": {
                "id": reference_photo["id"],
                "hash": reference_photo["hash"],
                "feature_metadata": json.loads(
                    (ROOT / "cache" / reference_photo["id"] / "meta.json").read_text()
                ),
            },
            "frames": total,
            "duration_seconds": total / fps,
            "camera": "fixed orthographic",
            "geometry": "linear interpolation of 3DMM identity/expression and PCA albedo; smooth easing if selected",
            "units": "template IOD",
            "note": "Reconstruction and synthetic interpolation, not medical or biometric conclusions.",
        }
        atomic_json(out.with_suffix(".json"), manifest)
        return {
            "url": f"/api/exports/{out.name}",
            "manifest_url": f"/api/exports/{out.stem}.json",
            "frames": total,
            "filename": out.name,
        }
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        if not finished:
            tmp.unlink(missing_ok=True)
