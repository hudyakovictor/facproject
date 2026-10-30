"""Deterministic CPU rasterization via upstream face3d Cython renderer + ffmpeg."""

import sys, subprocess, json
import numpy as np
from PIL import Image
from server.config import ROOT, TDDFA_ROOT, atomic_json
from server.heat import resolve as heat_resolve, segment_values

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
    path = str(TDDFA_ROOT)
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


def _source_photo_vertex_colors(photo_record, features, template_uv):
    """Sample the same baked source-photo UV atlas used by the WebGL viewer."""
    from PIL import Image, ImageOps
    from server.storage import key_for
    from server.uv_texture import UV_BAKER_VERSION, bake_photo_to_uv

    cache = ROOT / "cache" / photo_record["id"] / f"uv-atlas-{UV_BAKER_VERSION}-{key_for(photo_record)}.png"
    if not cache.exists():
        from server.models.tddfa import get_model

        meta = json.loads((ROOT / "cache" / photo_record["id"] / "meta.json").read_text())
        with Image.open(ROOT / photo_record["path"]) as image:
            rgb = np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
        model = get_model()
        source_uv = model.photo_uv(features["alpha"], rgb.shape[1], rgb.shape[0], meta["alignment"])
        atlas, _ = bake_photo_to_uv(rgb, source_uv, template_uv, np.asarray(json.loads((ROOT / "data/topology.json").read_text())["triangles"], np.int32), 1024)
        # The browser texture endpoint may be baking this same cache entry at
        # the same time as MP4 export. Never share a fixed temp filename.
        import uuid
        tmp = cache.with_name(f"{cache.stem}.{uuid.uuid4().hex}.tmp.png")
        try:
            Image.fromarray(atlas, "RGB").save(tmp, format="PNG", optimize=True)
            tmp.replace(cache)
        finally:
            tmp.unlink(missing_ok=True)
    with Image.open(cache) as image:
        atlas = np.asarray(image.convert("RGB"))
    import cv2

    uv = np.asarray(template_uv, np.float32)
    map_x = uv[:, 0] * (atlas.shape[1] - 1)
    map_y = (1.0 - uv[:, 1]) * (atlas.shape[0] - 1)
    sampled = np.empty((len(uv), 3), np.uint8)
    # OpenCV's remap limits each output dimension to signed-short range;
    # chunk the 35k template vertices instead of making one oversized column.
    for start in range(0, len(uv), 20000):
        stop = min(len(uv), start + 20000)
        chunk = cv2.remap(
            atlas,
            map_x[start:stop].reshape(-1, 1),
            map_y[start:stop].reshape(-1, 1),
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        sampled[start:stop] = chunk.reshape(-1, 3)
    return sampled.astype(np.float32) / 255.0


def export_morph(job, params):
    from server.storage import photo, load_features
    from server.models.tddfa import get_model, VERSION
    from server.registry import version

    ids = params["photo_ids"]
    ps = [photo(id) for id in ids]
    features = [load_features(p) for p in ps]
    # Cached topology is sufficient: exporting must not reload the neural net.
    topology_path = ROOT / "data/topology.json"
    topology = json.loads(topology_path.read_text()) if topology_path.exists() else get_model().topology()
    tri = np.asarray(topology["triangles"], np.int32)
    vertex_textures = None
    if params.get("texture", False):
        vertex_textures = []
        for i, (p, feature) in enumerate(zip(ps, features)):
            job.update(0.02 + 0.03 * i / len(ps), f"Подготовка текстуры {i + 1}/{len(ps)}")
            vertex_textures.append(_source_photo_vertex_colors(p, feature, topology["uv"]))
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
    if params.get("normalizeScale", False):
        landmark_ids = np.asarray(topology["landmarks"]["ldm68"], np.int32)

        def normalize_feature(feature):
            eyes = feature["vertices"][landmark_ids]
            left, right = eyes[36:42].mean(axis=0), eyes[42:48].mean(axis=0)
            center = (left + right) / 2
            iod = max(float(np.linalg.norm(left - right)), 1e-8)
            for key in ("vertices", "identity", "identity_metric"):
                if key in feature:
                    feature[key] = ((feature[key] - center) / iod).astype(np.float32)

        for feature in features:
            normalize_feature(feature)
        normalize_feature(ref)

    finished = False
    # Один и тот же helper считает значения и в preview, и здесь: калибровка
    # меняет только start/end карты, geometry остаётся = vertices.
    try:
        # Параметры не заданы — режим берётся из configs/runtime.yaml.
        mode = heat_resolve(params.get("metric"), params.get("weighting"))
    except (ValueError, FileNotFoundError) as exc:
        raise RuntimeError(str(exc)) from exc
    # Калиброванные значения живут в единицах шума, поэтому у них свой потолок.
    vmax = float(params.get("vmax") or mode["vmax"])
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
                vertex_textures[segment] * (1 - t) + vertex_textures[segment + 1] * t
                if vertex_textures is not None
                else np.tile(np.array([0.53, 0.59, 0.65], np.float32), (len(v), 1))
            )
            if params.get("heatmap", True):
                # The first route keyframe may already have a valid sequential
                # map against the preceding chronological photo. Use the
                # supplied reference there; later starts reuse the prior route
                # segment's endpoint map for exact continuity.
                previous = features[segment - 1] if segment > 0 else ref
                start_values, end_values = segment_values(
                    a, b, previous, tri, mode,
                    metric_name=params.get("metric"),
                    smoothing=int(params.get("smoothing", 0)),
                )
                heat_start = colorize(
                    start_values, params.get("vmin", 0), vmax,
                    params.get("palette", "turbo"), params.get("gamma", 1),
                    params.get("inverse", False), params,
                )
                heat_end = colorize(
                    end_values, params.get("vmin", 0), vmax,
                    params.get("palette", "turbo"), params.get("gamma", 1),
                    params.get("inverse", False), params,
                )
                heat = heat_start * (1 - t) + heat_end * t
                threshold = params.get("vmin", 0)
                opacity_value = params.get("opacity", 0.85)
                outside = params.get("outsideOpacity", 0.85)
                if params.get("onlyAbove", False):
                    alpha_start = (start_values > threshold).astype(np.float32)[:, None] * opacity_value
                    alpha_end = (end_values > threshold).astype(np.float32)[:, None] * opacity_value
                else:
                    alpha_start = np.where(start_values > threshold, opacity_value, outside).astype(np.float32)[:, None]
                    alpha_end = np.where(end_values > threshold, opacity_value, outside).astype(np.float32)[:, None]
                opacity = alpha_start * (1 - t) + alpha_end * t
                cols = cols * (1 - opacity) + heat * opacity
            rgb = rasterize(v, tri, cols, size, params.get("yaw", 0))
            proc.stdin.write(rgb.tobytes())
            if frame % max(1, fps // 4) == 0 or frame == total - 1:
                job.update(0.05 + 0.9 * (frame + 1) / total, f"Рендер {frame + 1}/{total} кадров")
        job.update(0.96, "Кодирование и проверка MP4")
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
