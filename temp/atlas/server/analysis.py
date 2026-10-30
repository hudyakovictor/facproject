import json, time
import numpy as np
from server import registry, storage
from server.config import ROOT, CONFIG, digest, atomic_json


def metrics_table():
    import inspect
    from server.ocular import VERSION as OCULAR_VERSION, measure as measure_eyes

    cat = registry.catalog()
    ov = registry.overrides()
    rows = []
    ready = [p for p in storage.library() if p["status"] == "ready"]
    topo_path = ROOT / "data/topology.json"
    if topo_path.exists():
        landmarks = json.loads(topo_path.read_text())["landmarks"]
    elif ready:
        from server.models.tddfa import get_model

        landmarks = {k: v.tolist() for k, v in get_model().ldm.items()}
    else:
        landmarks = {}
    for p in ready:
        raw = storage.photo(p["id"])
        cachepath = ROOT / "cache" / p["id"] / "metrics.json"
        saved = json.loads(cachepath.read_text()) if cachepath.exists() else {}
        result, ctx = {}, None
        for d in registry.definitions():
            conf = ov.get((d.model, p["pose"], d.id), {})
            key = digest(
                {
                    "ocular_version": OCULAR_VERSION
                    if d.model == "mediapipe"
                    else None,
                    "ocular_detection": (
                        ROOT / "cache" / p["id"] / "ocular-detection.json"
                    ).read_text()
                    if d.model == "mediapipe"
                    and (ROOT / "cache" / p["id"] / "ocular-detection.json").exists()
                    else None,
                    "ocular_manual": (
                        ROOT / "cache" / p["id"] / "ocular-manual.json"
                    ).read_text()
                    if d.model == "mediapipe"
                    and (ROOT / "cache" / p["id"] / "ocular-manual.json").exists()
                    else None,
                    "feature": storage.key_for(raw),
                    "pose": p["pose"],
                    "config": conf,
                    "fn": inspect.getsource(d.fn),
                    "common": (ROOT / "metrics/common.py").read_text(),
                }
            )
            if d.id in saved and saved[d.id]["key"] == key:
                result[d.id] = saved[d.id]["result"]
                continue
            if (
                p["pose"] == "unclassified"
                or not conf.get("enabled", True)
                or (d.poses and p["pose"] not in d.poses)
            ):
                item = {
                    "value": None,
                    "reason": "Ракурс вне профилей или метрика выключена",
                }
            elif d.model == "mediapipe":
                try:
                    # Значения глаз публикуются для всех кадров: суженная
                    # прорезь и D/H > 1 на фото с масками — это данные, а не
                    # брак разметки, поэтому фильтра по «годности» здесь нет.
                    mp_result = measure_eyes(raw, run=False)
                    value = float(mp_result["metrics"][d.id])
                    item = {
                        "value": value if np.isfinite(value) else None,
                        "reason": None if np.isfinite(value) else "Не определено",
                    }
                except (FileNotFoundError, ValueError, KeyError) as exc:
                    item = {"value": None, "reason": str(exc)}
            elif d.model != "3ddfa_v3":
                item = {"value": None, "reason": "Модель ещё не установлена"}
            else:
                if ctx is None:
                    features = storage.load_features(raw)
                    metric_landmarks = {}
                    for k, v in landmarks.items():
                        metric_key = f"landmarks_metric_{k}"
                        render_key = f"landmarks_render_{k}"
                        if render_key in features:
                            metric_landmarks[k] = features[render_key]
                        elif metric_key in features:
                            metric_landmarks[k] = features[metric_key]
                        else:
                            metric_landmarks[k] = features["vertices"][v]
                    ctx = {
                        **features,
                        **metric_landmarks,
                    }
                try:
                    value = float(d.fn(ctx))
                    item = {
                        "value": value if np.isfinite(value) else None,
                        "reason": None if np.isfinite(value) else "Не определено",
                    }
                except Exception as exc:
                    item = {"value": None, "reason": str(exc)}
            saved[d.id] = {"key": key, "result": item}
            result[d.id] = item.copy()
        atomic_json(cachepath, saved)
        rows.append(
            {
                "id": p["id"],
                "group": p["group"],
                "date": p["date"],
                "pose": p["pose"],
                "metrics": result,
                "sharpness": p["meta"]["sharpness"],
            }
        )
    return {
        "catalog": cat,
        "rows": registry.robust_scores(rows),
        "config_version": registry.version(),
    }


def project(job, params):
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
    from sklearn.metrics import pairwise_distances, silhouette_score
    from sklearn.preprocessing import normalize

    ps = [
        storage.photo(id)
        for id in params["photo_ids"]
        if storage.feature_path(storage.photo(id)).exists()
    ]
    if len(ps) < 2:
        raise ValueError("Для проекции нужны хотя бы 2 обработанных фото")
    n, seed = len(ps), int(params.get("seed", 42))
    dim, method = int(params.get("dimensions", 2)), params.get("method", "pca")
    distance = params.get("distance", "cosine")
    cachekey = digest({"params": params, "features": [storage.key_for(p) for p in ps]})
    path = ROOT / "cache/projections" / f"{cachekey}.json"
    if path.exists():
        return json.loads(path.read_text()) | {"cache_hit": True}
    job.update(0.05, "Загрузка α_id")
    x = np.array([storage.load_features(p, ["alpha"])["alpha"][:80] for p in ps])
    embedding_dim = max(1, min(dim, n, x.shape[1]))
    used, note = method, None
    if method == "umap" and n < 6:
        used, note = "pca", "Для UMAP нужно не менее 6 фото. Показан PCA."
    if used == "pca":
        k = min(dim, n, x.shape[1])
        pca = PCA(n_components=k, random_state=seed)
        coords, explained = (
            pca.fit_transform(x),
            float(pca.explained_variance_ratio_.sum()),
        )
    elif used == "tsne":
        perplexity = min(float(params.get("perplexity", 15)), n - 1)
        coords = TSNE(
            n_components=embedding_dim,
            perplexity=perplexity,
            metric=distance,
            random_state=seed,
            init="pca" if dim < min(n, x.shape[1]) else "random",
            learning_rate="auto",
            max_iter=750,
        ).fit_transform(x)
        explained = None
    elif used == "umap":
        job.update(0.15, "UMAP · первый запуск может компилировать numba")
        import umap

        coords = umap.UMAP(
            n_components=embedding_dim,
            n_neighbors=min(int(params.get("n_neighbors", 15)), n - 1),
            min_dist=float(params.get("min_dist", 0.1)),
            metric=distance,
            random_state=seed,
            n_jobs=1,
        ).fit_transform(x)
        explained = None
    else:
        raise ValueError("Неизвестный метод проекции")
    if coords.shape[1] < dim:
        coords = np.pad(coords, ((0, 0), (0, dim - coords.shape[1])))
    job.update(0.75, "Расстояния и статистика")
    matrix = pairwise_distances(x, metric=distance)
    groups = [p["group"] for p in ps]
    unique = sorted(set(groups))
    centroids = np.array([x[np.array(groups) == group].mean(0) for group in unique])
    dispersion = {
        group: float(
            np.mean(np.sum((x[np.array(groups) == group] - centroids[i]) ** 2, axis=1))
        )
        for i, group in enumerate(unique)
    }
    # Synthetic demo samples are not independent labeled subjects: never report
    # their group separation as a meaningful silhouette statistic.
    is_demo_only = all(p.get("demo", False) for p in ps)
    sil = (
        float(silhouette_score(x, groups, metric=distance))
        if 1 < len(unique) < n and not is_demo_only
        else None
    )
    count = min(max(1, int(params.get("clusters", 3))), n)
    labels = KMeans(n_clusters=count, random_state=seed, n_init=10).fit_predict(
        normalize(x) if distance == "cosine" else x
    )
    result = {
        "points": [
            {
                "id": p["id"],
                "group": p["group"],
                "coords": coords[i].tolist(),
                "norm": float(np.linalg.norm(x[i])),
                "cluster": int(labels[i]),
            }
            for i, p in enumerate(ps)
        ],
        "matrix": matrix.round(5).tolist(),
        "groups": unique,
        "centroid_distances": pairwise_distances(centroids, metric=distance)
        .round(5)
        .tolist(),
        "dispersion": dispersion,
        "silhouette": sil,
        "explained_variance": explained,
        "method": used,
        "requested_method": method,
        "note": note,
        "seed": seed,
        "params": params,
        "cache_key": cachekey,
        "cache_hit": False,
        "note_embedding": "α_id — параметры 3DMM, не AdaFace и не достоверность личности.",
    }
    atomic_json(path, result)
    return result
