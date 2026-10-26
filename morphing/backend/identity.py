"""🧭 3-way face-form classifier: процентное сходство загруженного лица с эталонами личностей.

Методика 17 робастных метрик формы — порт из
app6/private_hypothesis_seed/keypoint_analysis_90plus/analyze_keypoints_90plus.py,
но вычисляемая поверх канонических 106 точек morphing-конвейера
(app8.reconstruction.reconstruct_image + aligner.align_identity_mesh).

Эталоны (прототипы) и нормировка med/MAD строятся одним и тем же конвейером,
поэтому сравнение самосогласованно. Карантинные legacy-posteriors НЕ используются.
Вероятность — эвристика (softmax по робастному z-расстоянию), а не калиброванная
вероятность личности; так и подписывается в UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

FEATURE_ORDER: list[str] = [
    "brow_span_3d", "brow_height_asym", "eye_anchor_spacing_3d", "eye_level_asym",
    "brow_eye_left_3d", "brow_eye_right_3d", "brow_eye_asym", "nose_ridge_length_3d",
    "nose_base_width_3d", "nose_axis_bend_3d", "nose_base_asym", "nose_projection_3d",
    "midface_ratio", "mouth_width_3d", "mouth_height_3d", "mouth_nose_offset",
    "central_depth_contrast",
]

# Резкость распределения вероятностей: больше -> увереннее делим между личностями.
# На подборе held-out: beta=4 даёт ~50% у лидера, оставаясь близко к равномерному
# при реальной неоднозначности формы (near-uniform = честный сигнал «не уверен»).
SOFTMAX_BETA = 4.0
# Nearest-k по сэмплам личности: устойчивость к внутривариации (позы/выражения).
# Выключено по умолчанию: на held-out nearest-k хуже медианного прототипа (переобучается на позы).
USE_NEAREST_K = False
K_NEIGHBORS = 8

PROTOTYPES_PATH = Path(__file__).resolve().parent / "identity_prototypes.json"
# Пространство, в котором живут эталоны: канон `aligner.align_identity_mesh`
# (центрирование + краниометрический радиус = 1, без доворота позы). Смена выравнивания
# делает готовые эталоны неприменимыми, поэтому метка проверяется при загрузке.
ALIGNMENT_SPACE = "identity_object_space"


def _centroid(q: np.ndarray, idx: list[int]) -> np.ndarray:
    return q[np.array(idx)].mean(0)


def _dist(q: np.ndarray, i: int, j: int) -> float:
    return float(np.linalg.norm(q[i] - q[j]))


def _line_dev(q: np.ndarray, idx: list[int]) -> float:
    p = q[idx[0]]
    v = q[idx[-1]] - p
    v = v / (np.linalg.norm(v) + 1e-12)
    devs = [float(np.linalg.norm((q[i] - p) - np.dot(q[i] - p, v) * v)) for i in idx[1:-1]]
    return float(np.mean(devs))


def form_vector(points_106: np.ndarray) -> np.ndarray:
    """17-мерный вектор формы из канонических 106 точек (106, 3)."""
    q = np.asarray(points_106, dtype=float)
    if q.shape != (106, 3):
        raise ValueError(f"Ожидались ландамарки (106, 3), получено {q.shape}")
    lb = _centroid(q, [34, 35, 36, 37, 38, 39, 40])
    rb = _centroid(q, [42, 43, 44, 45, 47, 48, 49, 50])
    le = _centroid(q, [67, 74, 104])
    re = _centroid(q, [76, 78, 81, 83, 105])
    nb = _centroid(q, [58, 59, 60, 61, 62])
    ul = _centroid(q, [86, 87, 88])
    ll = _centroid(q, [92, 93, 94])
    mc = _centroid(q, [84, 86, 87, 88, 90, 91, 92, 93, 94, 95])
    dl = float(np.linalg.norm(lb - le))
    dr = float(np.linalg.norm(rb - re))
    eye_mid = (le + re) / 2
    vals = {
        "brow_span_3d": float(np.linalg.norm(lb - rb)),
        "brow_height_asym": abs(float(lb[1] - rb[1])),
        "eye_anchor_spacing_3d": float(np.linalg.norm(le - re)),
        "eye_level_asym": abs(float(le[1] - re[1])),
        "brow_eye_left_3d": dl,
        "brow_eye_right_3d": dr,
        "brow_eye_asym": abs(dl - dr),
        "nose_ridge_length_3d": _dist(q, 51, 54),
        "nose_base_width_3d": _dist(q, 58, 62),
        "nose_axis_bend_3d": _line_dev(q, [51, 52, 53, 54]),
        "nose_base_asym": abs(float(q[60, 0] - (q[58, 0] + q[62, 0]) / 2)),
        "nose_projection_3d": float(q[54, 2] - (q[58, 2] + q[62, 2]) / 2),
        "midface_ratio": float(np.linalg.norm(eye_mid - nb)) / (float(np.linalg.norm(le - re)) + 1e-12),
        "mouth_width_3d": _dist(q, 84, 90),
        "mouth_height_3d": abs(float(ul[1] - ll[1])),
        "mouth_nose_offset": abs(float(mc[0] - nb[0])),
        "central_depth_contrast": float(q[54, 2] - np.mean(q[[67, 74, 104, 76, 78, 81, 83, 105], 2])),
    }
    return np.array([vals[name] for name in FEATURE_ORDER], dtype=float)


@dataclass
class IdentityModel:
    identities: list[str]
    prototypes: np.ndarray  # (n_id, 17) — медиана формы по личности
    med: np.ndarray         # (17,) pooled median для робастной нормировки
    mad: np.ndarray         # (17,) pooled 1.4826*MAD
    samples: dict[str, np.ndarray]  # name -> (n_i, 17) векторы всех сэмплов (для nearest-k)
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_order": FEATURE_ORDER,
            "identities": self.identities,
            "prototypes": self.prototypes.tolist(),
            "med": self.med.tolist(),
            "mad": self.mad.tolist(),
            "samples": {name: arr.tolist() for name, arr in self.samples.items()},
            "softmax_beta": SOFTMAX_BETA,
            "k_neighbors": K_NEIGHBORS,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IdentityModel":
        if payload.get("feature_order") != FEATURE_ORDER:
            raise ValueError("Несовпадение порядка признаков в эталонах — пересоберите prototypes")
        alignment = (payload.get("meta") or {}).get("alignment")
        if alignment != ALIGNMENT_SPACE:
            # Метка вшита с канон-пересборки; её отсутствие или другое значение означает,
            # что эталоны считались в другом пространстве — молча сравнивать с ними нельзя.
            raise ValueError(
                "Эталоны собраны в другом пространстве выравнивания "
                f"(meta.alignment = {alignment!r}, нужно {ALIGNMENT_SPACE!r}) — "
                "пересоберите identity_prototypes.json"
            )
        raw_samples = payload.get("samples", {})
        return cls(
            identities=list(payload["identities"]),
            prototypes=np.array(payload["prototypes"], dtype=float),
            med=np.array(payload["med"], dtype=float),
            mad=np.array(payload["mad"], dtype=float),
            samples={name: np.array(arr, dtype=float) for name, arr in raw_samples.items()},
            meta=payload.get("meta", {}),
        )


def _robust_z(model: IdentityModel, x: np.ndarray) -> np.ndarray:
    return (x - model.med) / model.mad


def _identity_distance(model: IdentityModel, z: np.ndarray, name: str) -> float:
    """Среднее робастное z-расстояние по 17 признакам до эталона личности.

    По умолчанию — единый медианный прототип (устойчив к позам). Опционально nearest-k.
    """
    idx = model.identities.index(name)
    if USE_NEAREST_K and len(model.samples.get(name, [])) > 0:
        zs = (model.samples[name] - model.med) / model.mad
        per_sample = np.mean(np.abs(zs - z[None, :]), axis=1)
        k = min(K_NEIGHBORS, len(per_sample))
        return float(np.sort(per_sample)[:k].mean())
    return float(np.mean(np.abs(z - _robust_z(model, model.prototypes[idx]))))


def probabilities(model: IdentityModel, points_106: np.ndarray) -> dict[str, Any]:
    """Возвращает проценты сходства с каждой личностью (сумма 100) + сырые расстояния."""
    z = _robust_z(model, form_vector(points_106))
    distances = np.array([_identity_distance(model, z, name) for name in model.identities], dtype=float)
    logits = -SOFTMAX_BETA * distances
    logits -= logits.max()
    exp = np.exp(logits)
    probs = exp / exp.sum()
    by_identity = {
        name: round(float(p) * 100.0, 1)
        for name, p in zip(model.identities, probs)
    }
    best = model.identities[int(np.argmax(probs))]
    return {
        "probabilities": by_identity,
        "best_match": best,
        "distances": {name: round(float(d), 3) for name, d in zip(model.identities, distances)},
    }


def _pick_samples(files: list[Path], count: int) -> list[Path]:
    """Равномерная подвыборка по сортировке имён (даты), чтобы захватить разные позы/годы."""
    if count <= 0 or count >= len(files):
        return files
    idx = np.linspace(0, len(files) - 1, count).round().astype(int)
    return [files[i] for i in sorted(set(idx.tolist()))]


def build_prototypes(
    root: Path | str,
    identities: list[str],
    samples_per_identity: int = 40,
    model_getter: Any = None,
) -> IdentityModel:
    """Собирает прототипы формы по папкам личностей. Тяжёлый офлайн-шаг (реконструкция)."""
    root = Path(root)
    if model_getter is None:
        from app8.reconstruction import reconstruct_image
        from morphing.backend.aligner import align_identity_mesh

        def model_getter(path: Path) -> np.ndarray | None:
            recon = reconstruct_image(path, device="cpu")
            if not recon:
                return None
            _, landmarks, _ = align_identity_mesh(recon)
            return landmarks

    per_identity_vectors: dict[str, list[np.ndarray]] = {}
    used_counts: dict[str, int] = {}
    for name in identities:
        folder = root / name
        image_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        files = sorted(
            p for p in folder.glob("*")
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in image_suffixes
        )
        chosen = _pick_samples(files, samples_per_identity)
        vectors: list[np.ndarray] = []
        for photo in chosen:
            try:
                landmarks = model_getter(photo)
            except Exception:
                landmarks = None
            if landmarks is None:
                continue
            try:
                vectors.append(form_vector(landmarks))
            except Exception:
                continue
        if not vectors:
            raise RuntimeError(f"Личность '{name}': ни одно фото не реконструировалось")
        per_identity_vectors[name] = vectors
        used_counts[name] = len(vectors)
        print(f"  [{name}] использовано {len(vectors)}/{len(chosen)} фото")

    prototypes = np.array([np.median(np.vstack(per_identity_vectors[n]), axis=0) for n in identities])
    pooled = np.vstack([v for name in identities for v in per_identity_vectors[name]])
    med = np.median(pooled, axis=0)
    mad = 1.4826 * np.median(np.abs(pooled - med), axis=0)
    fallback_std = np.std(pooled, axis=0)
    mad = np.where(mad < 1e-8, fallback_std + 1e-8, mad)
    return IdentityModel(
        identities=list(identities),
        prototypes=prototypes,
        med=med,
        mad=mad,
        samples={name: np.vstack(per_identity_vectors[name]) for name in identities},
        meta={
            "root": str(root),
            "samples_per_identity_requested": samples_per_identity,
            "photos_used": used_counts,
            # Прототипы живут в каноническом объектном пространстве 3DMM (`aligner`:
            # центрирование + краниометрический радиус = 1, без доворота позы).
            # Смена выравнивания требует пересборки эталонов.
            "alignment": ALIGNMENT_SPACE,
            "note": "Эвристика формы, не калиброванная вероятность личности",
        },
    )


def save_prototypes(model: IdentityModel, path: Path | str = PROTOTYPES_PATH) -> None:
    Path(path).write_text(json.dumps(model.to_dict(), ensure_ascii=False, indent=2))


def load_prototypes(path: Path | str = PROTOTYPES_PATH) -> IdentityModel:
    return IdentityModel.from_dict(json.loads(Path(path).read_text()))


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Сборка эталонов формы личностей")
    parser.add_argument("--root", default="/Volumes/SDCARD/test_photos")
    parser.add_argument("--identities", default="put,vas,udmurt")
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--out", default=str(PROTOTYPES_PATH))
    args = parser.parse_args()

    names = [n.strip() for n in args.identities.split(",") if n.strip()]
    print(f"Сборка прототипов {names} из {args.root} (по {args.samples} фото)")
    model = build_prototypes(args.root, names, samples_per_identity=args.samples)
    save_prototypes(model, args.out)
    print(f"Сохранено: {args.out}")
    print(json.dumps(model.meta.get("photos_used", {}), ensure_ascii=False))


if __name__ == "__main__":
    _cli()
