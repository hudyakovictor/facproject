"""🎯 CRITICAL → Построение payload таймлайна для `/api/v1/timeline`.

🔗 DEPENDS ON: app6.stage2.core (реальная геометрия), app6.stage2.expression_qc,
app6.api.demo_data (fallback-источник, когда исследовательские данные
недоступны).

Контракт полей соответствует `ui/API_CONTRACT.md` и `ui/src/data.ts#Photo`.
Модуль не изобретает вердикт: `dominant`/`p0..p2`/`fuzzy` — это калиброванная
проекция геометрического расхождения на три гипотезы Байесовского зала
судебных заседаний (см. `docs/техническое задание проекта/aboutplatform.txt`),
явно помеченная как ограниченная эвристика, а не итог полноценного
байесовского вывода Stage 2 (которому нужны веса 3DDFA_V3 и текстурные
каналы, недоступные без них).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app6.stage2.core import Comparison, calibrated_score, robust_reference

from .demo_data import DemoPhoto, POSE_BINS, build_demo_records, build_demo_zone_maps, compare_demo_pair

TIMELINE_SCHEMA = "deeputin-api-timeline-v1.0"

#: Три гипотезы Байесовского зала судебных заседаний (aboutplatform.txt):
#: H0 — тот же человек, H1 — подмена/маска, H2 — разные люди.
HYPOTHESES = ("H0", "H1", "H2")


def _era_meta_from_segments() -> dict[str, dict[str, str]]:
    from .demo_data import _ERA_PLAN  # noqa: SLF001 - internal reuse within api package
    labels = {
        "DEMO_SEGMENT_1": "Демо-сегмент 1 (illustrative carrier A)",
        "DEMO_SEGMENT_2": "Демо-сегмент 2 (illustrative carrier A)",
        "DEMO_SEGMENT_3": "Демо-сегмент 3 (illustrative carrier B)",
        "DEMO_SEGMENT_4": "Демо-сегмент 4 (illustrative carrier B)",
        "DEMO_SEGMENT_5": "Демо-сегмент 5 (illustrative carrier C)",
    }
    return {seg["id"]: {"label": labels.get(seg["id"], seg["id"]), "start": seg["start"], "end": seg["end"]}
            for seg in _ERA_PLAN}


def _zone_rmse_lookup(comparison: Comparison) -> dict[str, float]:
    return {str(z["zone"]): float(z["rmse"]) for z in comparison.zones if z.get("status") == "measured"}


def _bayesian_projection(rmse_ratio: float, alpha_id_z: float | None) -> tuple[dict[str, float], str]:
    """🔬 EXPERIMENTAL → Грубая проекция геометрического расхождения на H0/H1/H2.

    🚨 WARNING: это НЕ полный Байесовский синтез из `aboutplatform.txt`
    (который требует SNR геометрии + вероятность силикона по текстуре +
    хронологические флаги). Здесь используется только geometry SNR
    (`rmse_ratio` = расхождение относительно калибровочного/референсного
    шума). Значение экспонируется как иллюстративная оценка, а не как
    Stage 2 evidence packet.
    """
    ratio = float(np.clip(rmse_ratio, 0.0, 20.0))
    # Более резкое расхождение относительно калибровочного шума снижает P(H0).
    p0 = float(np.exp(-0.6 * ratio))
    remainder = 1.0 - p0
    id_push = float(np.clip((alpha_id_z or 0.0) / 6.0, 0.0, 1.0))
    p1 = remainder * (0.25 + 0.5 * id_push)
    p2 = remainder - p1
    total = p0 + p1 + p2
    if total <= 0:
        p0, p1, p2 = 1.0, 0.0, 0.0
    else:
        p0, p1, p2 = p0 / total, p1 / total, p2 / total
    dominant = HYPOTHESES[int(np.argmax([p0, p1, p2]))]
    return {"H0": p0, "H1": p1, "H2": p2}, dominant


def _fuzzy_label(ratio: float, expression_active: bool, visibility_ratio: float) -> str:
    if visibility_ratio < 0.35:
        return "INSUFFICIENT_DATA"
    if expression_active and ratio < 2.5:
        return "WEAK_EVIDENCE"
    if ratio < 0.8:
        return "STRONGLY_MATCHING"
    if ratio < 1.5:
        return "CONSISTENT"
    if ratio < 2.5:
        return "WEAK_EVIDENCE"
    if ratio < 4.0:
        return "SUSPICIOUS_TEXTURE"
    if ratio < 7.0:
        return "GEOMETRIC_MISMATCH"
    return "IDENTITY_ANOMALY"


@dataclass
class TimelineRow:
    payload: dict[str, Any]


def build_demo_timeline() -> dict[str, Any]:
    """🚪 ENTRY POINT (программный) → Построить полный demo-timeline payload.

    Каждая метрика рассчитана реальным кодом `app6.stage2.core` над
    синтетической, но геометрически честной хронологией (`demo_data.py`).
    Текстурные каналы (silicone/specular/LBP/frangi/wrinkle/subsurface)
    Stage 1 не запускался — они физически недоступны без 3DDFA_V3 и
    настоящих фотографий, поэтому генерируются отдельным помеченным
    иллюстративным генератором (см. `_illustrative_texture_channel`) и
    никогда не участвуют в геометрической части байесовской проекции.
    """
    photos = build_demo_records()
    zone106, zone134 = build_demo_zone_maps(photos)
    era_meta = _era_meta_from_segments()

    # Референс "нормального" расхождения строится из соседних кадров внутри
    # одного pose bin и одного сегмента (аналог calibration same-person noise).
    by_bin: dict[str, list[DemoPhoto]] = {bin_name: [] for bin_name in POSE_BINS}
    for photo in photos:
        by_bin[photo.pose_bin].append(photo)

    reference_by_bin: dict[str, dict[str, float]] = {}
    for bin_name, group in by_bin.items():
        same_segment_rmse = []
        for i in range(len(group) - 1):
            if group[i].era != group[i + 1].era:
                continue
            comparison = compare_demo_pair(group[i], group[i + 1], zone106, zone134)
            if comparison.status == "measured":
                same_segment_rmse.append(comparison.metrics["ldm134_rmse"])
        reference_by_bin[bin_name] = robust_reference(same_segment_rmse)

    rows: list[dict[str, Any]] = []
    for bin_name, group in by_bin.items():
        reference = reference_by_bin[bin_name]
        for i, photo in enumerate(group):
            prev_photo = group[i - 1] if i > 0 else None
            if prev_photo is None:
                comparison = None
            else:
                comparison = compare_demo_pair(prev_photo, photo, zone106, zone134)

            visibility_ratio = float(np.asarray(photo.record.visible134, bool).mean())
            # 🚨 WARNING: app6.stage2.expression_qc.detect_expression() ожидает
            # анатомически осмысленную топологию 106 точек (индексы рта/челюсти
            # заданы для реального лица). На синтетическом гауссовом облаке
            # точек demo_data эти индексы ничего не означают анатомически, и
            # реальная функция давала бы систематические ложные срабатывания.
            # Поэтому здесь используется отдельный помеченный illustrative-флаг,
            # НЕ настоящий expression QC (тот применяется только в Stage 1/2 на
            # подлинной 3DDFA-реконструкции — см. app6/stage1/engine.py).
            expression_active = bool(np.random.default_rng(abs(hash((photo.id, "expr"))) % (2**32)).random() < 0.12)

            if comparison is not None and comparison.status == "measured":
                rmse = comparison.metrics["ldm134_rmse"]
                scored = calibrated_score(rmse, reference, [])
                ratio = float(scored["robust_z"]) if np.isfinite(scored["robust_z"]) else 0.0
                ratio = max(0.0, ratio / 3.0 + 1.0)  # rescale robust-z into an SNR-like ratio
                alpha_id_l2 = comparison.metrics.get("alpha_id_l2")
                zone_rmse = _zone_rmse_lookup(comparison)
            else:
                ratio = 1.0
                alpha_id_l2 = None
                zone_rmse = {}

            probs, dominant = _bayesian_projection(ratio, alpha_id_l2)
            fuzzy = _fuzzy_label(ratio, expression_active, visibility_ratio)

            zone_values = list(zone_rmse.values()) or [0.02]
            bone_score = float(np.clip(1.0 - min(ratio, 5.0) / 5.0, 0.0, 1.0))
            texture = _illustrative_texture_channel(photo)

            flags: list[str] = []
            if fuzzy == "IDENTITY_ANOMALY":
                flags.append("IDENTITY_ANOMALY")
            if expression_active:
                flags.append("EXPRESSION_ACTIVE")
            if visibility_ratio < 0.5:
                flags.append("LOW_VISIBILITY")

            row = {
                "id": photo.id,
                "date": photo.date,
                "t": _date_to_ms(photo.date),
                "era": photo.era,
                "bucket": photo.pose_bin,
                "quality": round(0.55 + 0.4 * visibility_ratio, 4),
                "hidden": False,
                "boneScore": round(bone_score, 4),
                "orbit": round(_zone_metric(zone_values, 0), 4),
                "chin": round(_zone_metric(zone_values, 1), 4),
                "jaw": round(_zone_metric(zone_values, 2), 4),
                "cheek": round(_zone_metric(zone_values, 3), 4),
                "symmetry": round(_zone_metric(zone_values, 4), 4),
                "yaw": round(float(photo.record.angles[1]), 2),
                **texture,
                "p0": round(probs["H0"], 4), "p1": round(probs["H1"], 4), "p2": round(probs["H2"], 4),
                "dominant": dominant,
                "fuzzy": fuzzy,
                "confidence": round(float(np.clip(visibility_ratio, 0.0, 1.0)), 4),
                "flags": flags,
                "exifAnomaly": False,
                "zOrbitDepth": round(_z_metric(zone_values, 0, ratio), 3),
                "zChinProj": round(_z_metric(zone_values, 1, ratio), 3),
                "zJawWidth": round(_z_metric(zone_values, 2, ratio), 3),
                "zCheek": round(_z_metric(zone_values, 3, ratio), 3),
                "geometrySnrRatio": round(ratio, 4),
                "visibilityRatio134": round(visibility_ratio, 4),
                "expressionActive": bool(expression_active),
                "sourceMode": "demo",
            }
            rows.append(row)

    return {
        "schema": TIMELINE_SCHEMA,
        "source_mode": "demo",
        "not_a_verdict": True,
        "note": (
            "Иллюстративный синтетический датасет: геометрия (boneScore, orbit, "
            "chin, jaw, cheek, symmetry, P(H0..H2)) вычислена реальным кодом "
            "app6.stage2.core на синтетических облаках точек. Текстурные каналы "
            "(силикон, specular, LBP, frangi, wrinkle, subsurface) — иллюстративные "
            "placeholder-значения без анализа изображений, т.к. текстурный анализ "
            "требует весов 3DDFA_V3 и настоящих фотографий."
        ),
        "era_meta": era_meta,
        "pose_bins": list(POSE_BINS),
        "photos": rows,
    }


def _illustrative_texture_channel(photo: DemoPhoto) -> dict[str, float]:
    """🔬 EXPERIMENTAL → Помеченные placeholder-значения текстурных каналов.

    🚨 WARNING: не основаны на анализе пикселей — реальный текстурный анализ
    (FFT/LBP/альбедо/frangi) требует Stage 1 с весами 3DDFA_V3 и подлинных
    фотографий. Значения детерминированы по photo.id, чтобы UI-демо было
    воспроизводимым, но их numeric drift не является наблюдением.
    """
    seed = abs(hash((photo.id, "texture"))) % (2**32)
    rng = np.random.default_rng(seed)
    carrier_bias = photo.carrier * 0.08
    return {
        "siliconeProb": round(float(np.clip(rng.beta(2, 6) + carrier_bias, 0, 1)), 4),
        "specular": round(float(np.clip(rng.beta(2, 5) + carrier_bias * 0.5, 0, 1)), 4),
        "lbpEntropy": round(float(np.clip(rng.beta(5, 2) - carrier_bias * 0.3, 0, 1)), 4),
        "frangi": round(float(np.clip(rng.beta(3, 4), 0, 1)), 4),
        "wrinkle": round(float(np.clip(rng.beta(3, 5), 0, 1)), 4),
        "subsurface": round(float(np.clip(rng.beta(4, 3) - carrier_bias * 0.2, 0, 1)), 4),
        "visualAge": round(45.0 + rng.normal(0, 4), 2),
        "calendarAge": round(_calendar_age(photo.date), 2),
    }


def _calendar_age(date_iso: str) -> float:
    from datetime import date
    birth = date(1952, 10, 7)
    d = date.fromisoformat(date_iso)
    return (d - birth).days / 365.25


def _zone_metric(values: list[float], offset: int) -> float:
    if not values:
        return 0.0
    v = values[offset % len(values)]
    return float(np.clip(1.0 - min(v, 0.3) / 0.3, 0.0, 1.0))


def _z_metric(values: list[float], offset: int, ratio: float) -> float:
    if not values:
        return 0.0
    base = values[offset % len(values)]
    return float((base * 40.0) * (ratio / 1.5))


def _date_to_ms(date_iso: str) -> int:
    from datetime import date, timezone, datetime
    d = date.fromisoformat(date_iso)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)
