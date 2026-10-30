"""Read-only-data integration checks against a running production server.
Adds projection caches, demo MP4s and job history; never changes photos/workspace.
"""

import hashlib, json, time
from pathlib import Path
import httpx, numpy as np, imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
client = httpx.Client(base_url="http://127.0.0.1:5173", timeout=30)
report = {"checks": [], "jobs": []}


def check(label, ok, **extra):
    report["checks"].append({"label": label, "pass": bool(ok), **extra})
    print(label, ":", bool(ok), flush=True)
    assert ok, label


def submit(path, params):
    r = client.post(path, json=params)
    r.raise_for_status()
    j = r.json()
    report["jobs"].append({"id": j["id"], "kind": j["kind"]})
    return j


def finished(job, seconds=140):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        j = next(j for j in client.get("/api/jobs").json() if j["id"] == job["id"])
        if j["status"] not in ("queued", "running"):
            return j
        time.sleep(0.2)
    raise TimeoutError(job["id"])


try:
    library = client.get("/api/library").json()
    ids = [p["id"] for p in library["photos"] if p["status"] == "ready"]
    demo = [p["id"] for p in library["photos"] if p.get("demo")]
    for method, dim in [("pca", 3), ("tsne", 3), ("umap", 3)]:
        params = {
            "photo_ids": ids,
            "method": method,
            "dimensions": dim,
            "distance": "cosine",
            "seed": 183,
            "clusters": 3,
            "n_neighbors": 5,
            "min_dist": 0.17,
            "perplexity": 3,
        }
        job = finished(submit("/api/projection", params))
        check(
            f"{method.upper()} 3D completed on {len(ids)} real cached reconstructions",
            job["status"] == "completed",
            status=job["status"],
            message=job["message"],
        )
        result = job["result"]
        points = np.asarray([p["coords"] for p in result["points"]])
        matrix = np.asarray(result["matrix"])
        check(
            f"{method.upper()}: actual method / finite 3D / symmetric distances",
            result["method"] == method
            and points.shape == (len(ids), 3)
            and np.isfinite(points).all()
            and np.allclose(matrix, matrix.T),
        )
        if method == "umap":
            again = finished(submit("/api/projection", params))["result"]
            check(
                "UMAP cache/seed reproducibility",
                again["cache_hit"] and again["points"] == result["points"],
            )
    for metric in ("distance", "identity", "normal"):
        params = {
            "photo_ids": demo[:2],
            "reference_id": demo[3],
            "seconds": 0.5,
            "fps": 8,
            "resolution": 256,
            "easing": "smooth",
            "heatmap": True,
            "metric": metric,
            "palette": "custom",
            "low": "#1554aa",
            "mid": "#66ddbb",
            "high": "#ed4466",
            "midPosition": 0.42,
            "vmin": 0.0003,
            "vmax": 0.022,
            "gamma": 1.3,
            "inverse": True,
            "opacity": 0.8,
            "outsideOpacity": 0.15,
            "onlyAbove": True,
            "smoothing": 2,
            "yaw": 35,
            "texture": metric == "identity",
        }
        job = finished(submit("/api/morph", params))
        check(
            f"MP4 {metric}: external reference + custom palette/smoothing",
            job["status"] == "completed",
            status=job["status"],
            message=job["message"],
        )
        result = job["result"]
        path = ROOT / "exports" / result["filename"]
        reader = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
        meta = next(reader)
        frames = list(reader)
        manifest = client.get(result["manifest_url"]).json()
        check(
            f"MP4 {metric}: decoded H264, 256², 8fps, five distinct frames",
            meta["size"] == (256, 256)
            and meta["fps"] == 8
            and len(frames) == 5
            and len({hashlib.sha256(f).hexdigest() for f in frames}) >= 3
            and manifest["params"] == params
            and manifest["reference_photo"]["id"] == demo[3],
            filename=result["filename"],
            frames=len(frames),
            codec=meta.get("codec"),
        )
    # A deliberately long export is cancelled immediately, not left running.
    job = submit(
        "/api/morph", {"photo_ids": demo, "seconds": 10, "fps": 60, "resolution": 1024}
    )
    client.post("/api/jobs/" + job["id"] + "/cancel").raise_for_status()
    end = finished(job)
    check(
        "Cancellation stops long export and removes partial video",
        end["status"] == "cancelled"
        and not list((ROOT / "exports").glob("morph-" + job["id"] + "*")),
        status=end["status"],
    )
    check(
        "User uploads and canvas untouched",
        len(client.get("/api/library").json()["photos"]) == len(library["photos"]),
    )
except Exception as e:
    report["failure"] = repr(e)
    raise
finally:
    (ROOT / "reports/jobs-acceptance.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    client.close()
