""" Внутрисессионная повторяемость реконструкции по ракурсам для morphing.

Читает `pose_noise_calibration.json` (его строит `calibrate_pose_noise.py` по
/Volumes/SDCARD/calibration_rakurs) и отвечает на один вопрос: не слишком ли
измеренная 3D-девиация велика, чтобы считаться различием лиц *в этом ракурсе*.

ВАЖНО О СТАТУСЕ ПОЛОС: калибровка собрана на видеокадрах одной сессии (10 кадров
на бин, разнесённых linspace по ~25–50 кадрам серии). Это означает:
— общая ошибка сессии (камера, свет, обработка) сокращается в парной разности;
— соседние по времени кадры имеют коррелированные ошибки, Var(e_t − e_{t+h}) =
  2σ²(1 − ρ(h)), что при малом h искусственно сужает полосу;
— поэтому полосы дают **внутрисессионную повторяемость** конвейера, а НЕ
  универсальный шум для независимых пересъёмок.

Вердикт «выше полосы» означает: девиация превышает эмпирический p95 *этих*
видеокадров при данном |Δyaw|, но НЕ доказывает, что лица разные.

Переносимость этой полосы измерена (`assess_band_transfer.py`, 4336 пар одного
человека по фотоархивам трёх других людей): 78% пар того же человека в том же бине,
но на разных съёмках, легли выше видео-p95; среди снятых в пределах недели — 72%.
Оперативной для реальных фото становится полоса «разброс двух независимых съёмок
одного человека» (`reshoot_bands.json`), и только там, где набрано >= 20 ближних пар
(пока — фронтальный бин). Для остальных бинов эта полоса отдаётся ориентиром по
страте `spread`, но границей вердикта не является.

Разделимость на уровне отдельных фото тоже измерена честно: AUC по бинам 0.56–0.74
(медиана 0.68), а не 0.98, как обещает расстояние между центроидами видео-групп.

Ничего из «сырых» метрик не вычитается молча: сюда приходят за справкой, а
решение о том, показывать ли разницу как шум, принимает вызывающий код.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CALIBRATION_PATH = Path(__file__).resolve().parent / "pose_noise_calibration.json"
# Полосы «два независимых снимка одного человека»: их строит
# `assess_band_transfer.py --emit-bands` по фотоархивам трёх людей, не входивших
# в видеокалибровку. Там, где пар достаточно, именно эта полоса оперативная.
RESHOOT_PATH = Path(__file__).resolve().parent / "reshoot_bands.json"

VERDICT_LABELS = {
    # Ключи `*_noise` исторические; в формулировках — «повторяемость», потому что
    # измерено она на видеокадрах одной сессии (см. BAND_STATUS), а не на пересъёмках.
    "within_noise": "в пределах повторяемости (≤ p50)",
    "near_noise": "на границе повторяемости (≤ p95)",
    "above_noise": "выше полосы (> p95)",
    "unknown": "полоса не откалибрована",
}
# Когда оперативная полоса измерена на независимых снимках одного человека, слово
# «повторяемость» (внутри серии) врёт: говорим «разброс двух съёмок».
RESHOOT_LABELS = {
    "within_noise": "в пределах разброса двух съёмок одного человека (≤ p50)",
    "near_noise": "на границе разброса двух съёмок (≤ p95)",
    "above_noise": "выше разброса двух съёмок (> p95)",
    "unknown": "полоса не откалибрована",
}
# Карман дрейфа с меньшим числом пар не используется как граница: на 5 выборках
# 95-й квантиль — это практически максимум.
MIN_BUCKET_PAIRS = 10
# Порог полезности опоры «типичное различие между людьми»: если доля пар одного
# человека выше медианы разных людей больше этой величины, опора — не граница
# личностей, а просто уровень шума пересъёмки (измерено: 0.17 во фронтале против
# 0.40 в правом профиле).
SEPARABLE_SHARE = 0.25
# Статус полос, который нельзя терять по дороге в UI: источник данных — видеокадры
# одной сессии на (человек, бин), поэтому это повторяемость конвейера, а не шум
# независимой пересъёмки.
BAND_STATUS = (
    "повторяемость на видеокадрах одной сессии (6 человек × 9 ракурсов), условно по |Δyaw|"
)
# Измеренная переносимость видео-полосы на независимые снимки
# (`assess_band_transfer.py`, 4336 пар одного человека в том же бине):
TRANSFER_NOTE = (
    "переносимость проверена на независимых съёмках: 78% пар одного человека (тот же ракурс) "
    "легли выше видео-p95, среди снятых в пределах недели — 72%; видео-полоса занижает разброс "
    "в ~2–3 раза и годится как нижняя оценка, а не как граница «это не шум»"
)
# Что именно даёт разброс пересъёмок: контроль чувствительности входа
# (`probe_input_sensitivity.py`, 54 кадра × 12 вариантов света/резкости/джипега при
# фиксированной геометрии, медианный |Δyaw| вариантов ≤ 0.3°).
ATTRIBUTION_NOTE = (
    "из чего складывается разброс пересъёмки: 54 кадра × 12 вариантов света/резкости/JPEG "
    "при неизменной геометрии (медианный |Δyaw| 0.15°) дают медианы 0.0015–0.0046, и до "
    "уровня полосы 0.016 дотягивает 0.8% таких пар — исключение сильное сжатие q40 (20%). "
    "Значит основную часть разброса двух снимков одного лица дают не условия съёмки, а "
    "различие позы и работы детектора/лендмарков; но пережатое до q40 фото способно "
    "имитировать разницу лиц само по себе"
)


@lru_cache(maxsize=1)
def load_calibration(path: Path | str = CALIBRATION_PATH) -> dict[str, Any] | None:
    """Шум-модель с диска; None — если калибровка ещё не собрана."""
    file = Path(path)
    if not file.exists():
        return None
    try:
        payload = json.loads(file.read_text())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) and payload.get("bins") else None


def bins_available(path: Path | str = CALIBRATION_PATH) -> list[str]:
    model = load_calibration(path)
    return sorted(model["bins"].keys()) if model else []


@lru_cache(maxsize=1)
def load_reshoot_bands(path: Path | str = RESHOOT_PATH) -> dict[str, Any] | None:
    """Полосы разброса двух независимых съёмок одного человека; None — если не измерены."""
    file = Path(path)
    if not file.exists():
        return None
    try:
        payload = json.loads(file.read_text())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) and payload.get("bins") else None


def reshoot_reference(pose_bin: str, path: Path | str = RESHOOT_PATH) -> dict[str, Any]:
    """Полосы «две независимые съёмки одного человека» в этом бине (schema v2).

    Две страты нельзя смешивать:
    — `near` (интервал съёмки ≤ near_days): морфология та же, это почти чистый шум
      конвейера и условий съёмки — только она может быть границей вердикта
      (`operative` True, если пар >= `min_pairs_to_use`);
    — `spread` (любой интервал, вплоть до лет): включает настоящее изменение лица,
      поэтому это ориентир, а не доказательство «лица совпадают».
    """
    model = load_reshoot_bands(path)
    data = ((model or {}).get("bins") or {}).get(pose_bin) if pose_bin else None
    if not data:
        return {"available": False}
    near = data.get("near") or {}
    spread = data.get("spread") or {}
    return {
        "available": True,
        "operative": bool(data.get("operative")),
        "min_pairs": int((model or {}).get("min_pairs_to_use") or 20),
        "near_days": (model or {}).get("near_days"),
        "near": near,
        "spread": spread,
        # Удобство для вызывающего кода: оперативные числа — это near, если его хватает.
        "p50": near.get("p50") if data.get("operative") else None,
        "p95": near.get("p95") if data.get("operative") else None,
        "median_abs_dyaw_deg": near.get("median_dyaw"),
        "between_photos_p50": (data.get("between_photos") or {}).get("p50"),
        "between_photos_p95": (data.get("between_photos") or {}).get("p95"),
        "auc_near": data.get("auc_near"),
        "auc_spread": data.get("auc_spread"),
        # Цена фразы «выше типичного различия между людьми» в этом бине: какая доля
        # пар ОДНОГО человека (разные даты) тоже лежит выше медианы разных людей.
        "spread_above_between_share": data.get("share_spread_above_between_p50"),
        "near_above_between_share": data.get("share_near_above_between_p50"),
        "population": (model or {}).get("population"),
        "meaning": (model or {}).get("meaning"),
        "schema_version": (model or {}).get("schema_version"),
    }


def _operative_band(bin_data: dict[str, Any], yaw_spread_deg: float | None) -> tuple[float, float, dict[str, Any]]:
    """Рабочая полоса: по карману |Δyaw| либо плоская по бину.

    Внутри бина девиация сильно растёт с |Δyaw| (корреляция Пирсона 0.64–0.81),
    поэтому для пары с разбросом поз 3° сравнивать её с полосой «почти одинаковых»
    кадров значило бы приписать конвейеру больше устойчивости, чем он показал.

    Это условный квантиль q(D | один человек, бин, |Δyaw|), а не разложение ошибки:
    |Δyaw| и D считаются одной и той же сетью, так что карман объясняет наблюдаемый
    разброс, но не доказывает, что именно реальный поворот головы его вызывает.
    """
    within = bin_data["within"]
    info: dict[str, Any] = {"band_source": "bin_flat"}
    if yaw_spread_deg is None:
        return float(within["p50"]), float(within["p95"]), info
    for bucket in (bin_data.get("drift") or {}).get("buckets", []):
        if not bucket.get("n") or int(bucket.get("pairs") or 0) < MIN_BUCKET_PAIRS:
            continue
        if bucket["lo_deg"] <= float(yaw_spread_deg) < bucket["hi_deg"]:
            return (
                float(bucket["p50"]),
                float(bucket["p95"]),
                {"band_source": "drift_bucket", "band_dyaw_deg": [bucket["lo_deg"], bucket["hi_deg"]],
                 "band_pairs": bucket.get("pairs")},
            )
    return float(within["p50"]), float(within["p95"]), info


def _band_status(model: dict[str, Any] | None, reshoot: dict[str, Any]) -> str:
    """Описание активной полосы — единая формулировка для UI.

    Когда оперативна near-полоса независимых съёмок, описываем её выборку. Когда её
    нет (бин с малым числом ближних пар), к видео-полосе обязательна оговорка об
    измеренной заниженности: иначе «выше полосы» читают как «лица разные».
    """
    if reshoot.get("operative"):
        near = reshoot.get("near") or {}
        return (
            f"разброс двух независимых съёмок одного человека: {reshoot.get('population')}"
            f" · ближних пар (≤{reshoot.get('near_days')} дн.) n={near.get('pairs')}"
            f" · по |Δyaw| не стратифицировано (медианный |Δyaw| выборки "
            f"{near.get('median_dyaw')}°)"
        )
    video = (model or {}).get("band_status") or BAND_STATUS
    parts = [video, TRANSFER_NOTE]
    spread = reshoot.get("spread") or {}
    if spread.get("pairs"):
        parts.append(
            f"ориентир по независимым съёмкам этого ракурса (разный интервал дат, "
            f"n={spread['pairs']}): p50 {spread.get('p50')} · p95 {spread.get('p95')} — "
            "в него входит настоящее изменение лица, границей вердикта он не является"
        )
    return "; ".join(parts)


def noise_reference(
    pose_bin: str,
    mean_delta: float,
    yaw_spread_deg: float | None = None,
    path: Path | str = CALIBRATION_PATH,
    reshoot_path: Path | str = RESHOOT_PATH,
) -> dict[str, Any]:
    """Сравнить девиацию пары с полосой её ракурса.

    Полоса выбирается так: если для бина измерен разброс двух независимых съёмок
    одного человека и пар достаточно — он; иначе видео-повторяемость серии, которая
    на пересъёмках занижена (см. `transfer_note`). Результат — справка, а не вывод
    о личности.

    Args:
        pose_bin: бин POSE_BINS, в котором выровнены сетки (общий канон пары).
        mean_delta: средняя попарная девиация вершин в долях RMS-масштаба по 106
            ландмаркам (патч 04; раньше — доли краниометрического радиуса).
        yaw_spread_deg: разброс yaw внутри пары; если задан и калибровка содержит
            карманы дрейфа, полоса берётся условно по нему.
    """
    model = load_calibration(path)
    bin_data = (model or {}).get("bins", {}).get(pose_bin) if pose_bin else None
    if not bin_data or not bin_data.get("within"):
        return {
            "available": False,
            "pose_bin": pose_bin,
            "verdict": "unknown",
            "verdict_label": VERDICT_LABELS["unknown"],
            "calibrated": bool(model),
        }
    within = bin_data["within"]
    noise_p50, noise_p95, band = _operative_band(bin_data, yaw_spread_deg)
    video_p50, video_p95 = noise_p50, noise_p95
    video_band_source = band.get("band_source")
    delta = float(mean_delta)

    # Оперативная полоса: если измерен разброс двух независимых съёмок одного человека
    # и пар достаточно, вердикт даётся по нему, а не по видео-повторяемости серии.
    reshoot = reshoot_reference(pose_bin, path=reshoot_path)
    if reshoot.get("operative"):
        noise_p50, noise_p95 = float(reshoot["p50"]), float(reshoot["p95"])
        band = {
            "band_source": "reshoot_photos",
            "band_pairs": (reshoot.get("near") or {}).get("pairs"),
            "band_median_dyaw_deg": reshoot.get("median_abs_dyaw_deg"),
        }

    if delta <= noise_p50:
        verdict = "within_noise"
    elif delta <= noise_p95:
        verdict = "near_noise"
    else:
        verdict = "above_noise"
    between = bin_data.get("between") or {}
    centroid_p50 = float(between["p50"]) if between.get("p50") is not None else None
    # Опора «дотягивает ли до различия людей»: сначала настоящие межличностные пары
    # фото, только если их нет — расстояние центроидов видео-групп (оно оптимистичнее).
    photos_p50 = reshoot.get("between_photos_p50") if reshoot.get("available") else None
    between_p50 = photos_p50 or centroid_p50
    between_basis = (
        "пары фото разных людей в этом бине" if photos_p50
        else "расстояния между центроидами видео-групп"
    )
    labels = RESHOOT_LABELS if reshoot.get("operative") else VERDICT_LABELS
    label = labels[verdict]
    # Насколько «медиана разных людей» вообще отделяет людей в этом бине: измерено,
    # что доля пар одного человека выше этой медианы доходит до 40% (правый профиль).
    # Пока она выше `SEPARABLE_SHARE`, фраза «выше различия между людьми» ничего не
    # утверждает, и писать её нельзя — даже когда девиация формально больше опоры.
    overlap = reshoot.get("spread_above_between_share")
    if verdict == "above_noise" and between_p50 and between_p50 > 0:
        # «Выше полосы» — ещё не «разные люди»: важно, дотягивает ли девиация до
        # типичного различия между личностями в этом же ракурсе.
        if delta <= between_p50:
            label = "выше полосы, но меньше типичного различия людей"
        elif overlap is not None and overlap > SEPARABLE_SHARE:
            label = (f"выше типичного различия людей, но метрика их не разделяет "
                     f"(в этом ракурсе {overlap:.0%} пар одного человека тоже выше)")
        else:
            label = "выше типичного различия между людьми"
    close = bin_data.get("within_close_pose") or {}
    vertex = bin_data.get("within_vertex_p95") or {}
    signal_vertex = bin_data.get("between_vertex_p95") or {}
    drift = bin_data.get("drift") or {}
    return {
        "available": True,
        "pose_bin": pose_bin,
        "units": (model or {}).get("units", ""),
        "within_p50": round(float(within["p50"]), 8),
        "within_p95": round(float(within["p95"]), 8),
        # Рабочая полоса: та, по которой вынесен вердикт (разброс независимых съёмок,
        # либо — если он не измерен — карман |Δyaw| / плоская полоса видео-серии).
        "expected_p50": round(noise_p50, 8),
        "expected_p95": round(noise_p95, 8),
        **band,
        # Видео-полоса остаётся рядом: она нижняя оценка, и полезно видеть, насколько
        # оперативная полоса шире неё.
        "video_p50": round(video_p50, 8),
        "video_p95": round(video_p95, 8),
        "video_band_source": video_band_source,
        "video_band_ratio_p95": round(delta / video_p95, 4) if video_p95 > 0 else None,
        "reshoot": reshoot,
        "between_p50": round(between_p50, 8) if between_p50 is not None else None,
        "between_photos_p50": round(photos_p50, 8) if photos_p50 else None,
        "between_centroid_p50": round(centroid_p50, 8) if centroid_p50 is not None else None,
        "between_basis": between_basis,
        # Доля пар одного человека (разные даты) выше `between_photos_p50`: цена опоры.
        # Выше SEPARABLE_SHARE — значит по этой метрике люди в данном ракурсе не
        # отделяются, и ярлык «выше различия между людьми» не выдаётся.
        "same_person_above_between_share": overlap,
        "person_baseline_separable": None if overlap is None else bool(overlap <= SEPARABLE_SHARE),
        # Пол: пары того же человека с |Δyaw| < порога, т.е. почти один и тот же
        # ракурс в соседних по времени кадрах. Это нижняя оценка вклада конвейера;
        # разность с полосой бина — наблюдаемый размах при дрейфе позы внутри папки,
        # а не измеренный «вклад позы» отдельно от «вклада шума».
        "floor_p50": close.get("p50"),
        "floor_p95": close.get("p95"),
        "floor_pairs": close.get("pairs"),
        # Девиация отдельной вершины: медиана по парам от 95-го квантиля внутри
        # каждой пары. Это НЕ индивидуальный порог данной вершины — просто опора
        # для нижней границы шкалы heatmap (сырой режим с фиксированной шкалой остаётся).
        "noise_vertex_p95": vertex.get("p50"),
        "signal_vertex_p95": signal_vertex.get("p50"),
        "median_abs_dyaw_deg": drift.get("median_abs_dyaw_deg"),
        "auc": bin_data.get("auc"),
        "photos": bin_data.get("photos"),
        "people": bin_data.get("people"),
        "mean_delta": round(delta, 8),
        # Девиация как доля от типичного различия людей в этом ракурсе: 1.0 = типичная
        # пара разных людей. Источник — межличностные пары фото, при их отсутствии
        # центроиды видео-групп (см. between_basis).
        "delta_vs_between_p50": round(delta / between_p50, 4) if between_p50 else None,
        "excess_over_noise_p50": round(max(delta - noise_p50, 0.0), 8),
        # Во сколько раз девиация больше верхней границы рабочей полосы. >1 означает
        # «реже 5% внутриличностных сравнений этого типа», но не «лица разные»:
        # по построению ~5% сравнений одного человека лежат выше p95, а на малом числе
        # пар хвост оценивается плохо.
        "band_ratio_p95": round(delta / noise_p95, 4) if noise_p95 > 0 else None,
        # Статус полосы — то, что нельзя потерять по дороге в UI. Когда оперативна
        # полоса независимых съёмок, описываем её выборку; иначе — видео-полосу и
        # обязательную оговорку о том, что на настоящих пересъёмках она занижена.
        "band_status": _band_status(model, reshoot),
        "transfer_note": TRANSFER_NOTE,
        "attribution_note": ATTRIBUTION_NOTE,
        "verdict": verdict,
        "verdict_label": label,
        "zones": {
            zone: {
                "within_p50": data.get("p50"),
                "within_p95": data.get("p95"),
            }
            for zone, data in (bin_data.get("zones") or {}).items()
        },
        "calibration_version": (model or {}).get("schema_version"),
        "calibration_source": (model or {}).get("source"),
    }


def pair_noise_reference(
    pose: dict[str, Any],
    metrics: dict[str, Any],
    yaw_spread_deg: float | None = None,
    path: Path | str = CALIBRATION_PATH,
    reshoot_path: Path | str = RESHOOT_PATH,
) -> dict[str, Any]:
    """Шум-справка для пары/группы из отчёта `aligner.pose_alignment_report`.

    Шум откалиброван только для сравнения внутри одного бина; при несовпадении
    ракурсов дельта включает разницу поз, и сравнивать её с шумом нельзя.

    Args:
        pose: отчёт `pose_alignment_report`.
        metrics: `similarity_metrics` сравниваемой пары (или двух ключевых кадров).
        yaw_spread_deg: разброс yaw именно между сравниваемыми кадрами; по умолчанию
            берётся из отчёта по группе.
    """
    if not pose.get("same_pose_bin"):
        return {
            "available": False,
            "reason": "pose_mismatch",
            "pose_bin": None,
            "distinct_bins": pose.get("distinct_bins", []),
            "verdict": "unknown",
            "verdict_label": "ракурсы не совпадают — шум не применим",
        }
    spread = pose.get("yaw_spread_deg") if yaw_spread_deg is None else yaw_spread_deg
    reference = noise_reference(
        pose.get("canonical_bin", ""),
        float(metrics["euclidean_mean"]),
        yaw_spread_deg=spread,
        path=path,
        reshoot_path=reshoot_path,
    )
    zone_deltas = {name: data["mean_delta"] for name, data in (metrics.get("zones") or {}).items()}
    reference["zones_detail"] = zone_noise_reference(pose.get("canonical_bin", ""), zone_deltas, path=path)
    return reference


def zone_noise_reference(
    pose_bin: str,
    zone_deltas: dict[str, float],
    path: Path | str = CALIBRATION_PATH,
) -> dict[str, dict[str, Any]]:
    """То же для зон: вердикт по каждой зоне против её собственного шума."""
    model = load_calibration(path)
    zones = ((model or {}).get("bins", {}).get(pose_bin, {}) or {}).get("zones", {})
    out: dict[str, dict[str, Any]] = {}
    for zone, delta in zone_deltas.items():
        data = zones.get(zone)
        if not data:
            continue
        p50, p95 = float(data["p50"]), float(data["p95"])
        value = float(delta)
        verdict = "within_noise" if value <= p50 else ("near_noise" if value <= p95 else "above_noise")
        out[zone] = {
            "mean_delta": round(value, 8),
            "within_p50": round(p50, 8),
            "within_p95": round(p95, 8),
            "excess_over_noise_p50": round(max(value - p50, 0.0), 8),
            "verdict": verdict,
            "verdict_label": VERDICT_LABELS[verdict],
        }
    return out
