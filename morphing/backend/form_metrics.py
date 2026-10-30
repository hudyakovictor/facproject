"""Боевой расчёт 30 утверждённых метрик формы: цвет ячейки — на кого из трёх людей она.

Что здесь происходит.
1. `photo_bundle` — одно фото проходит ровно тот же канон, что и прогон отбора:
   `app8.reconstruction.reconstruct_image` → `align_identity_mesh` (центр и RMS по 106
   ландмаркам) → срез 134 точек и 9 базисов `ANAT_VERTS` с той же нормированной сетки,
   плюс 478 точек MediaPipe из отдельного процесса-воркера (`mp_worker`). Значения
   считает `metric_registry.compute_all` — тот же вызов, что и в валидации.
2. `pair_rows` — сравнение двух фото по каждой метрике. Цвет ячейки отвечает на другой
   вопрос: «на какого из трёх человек смотрит это значение». В `metric_bands.json`
   (калибровка `app9/validation/calibrate_metric_bands.py`) лежит медиана метрики по
   каждой личности; значение сравнивается с двумя ближайшими эталонами и делит цвет
   пропорционально близости — ровно посередине между двумя лицами даёт 50/50.
   Второй слой той же строки — обычная полоса совпадения: `k_same`/`k_differ` из
   эмпирических разностей |A−B| кадров ОДНОГО лица (80-й и 97.5-й перцентили в полосах),
   чтобы видеть, согласны ли два снимка между собой.
3. `trusted` — 9 метрик, устойчивых к подфронтальному повороту (проверено на 177 кадрах
   |yaw| 10–25°, отчёт `app9/validation/report/subfrontal_check.md`). Считаем все 30,
   но интерфейс выделяет эти девять: им можно верить при большем угле головы.

Пороги сравнения двух снимков калибруются эмпирически (`metric_bands.json`), а не
выдумываются здесь: по всем парам кадров ОДНОГО лица считается распределение |A−B| в
единицах полосы, и `k_same` = 80-й перцентиль (ниже — обычная гулянка одного лица),
`k_differ` = 97.5-й (выше — у одного лица так не бывает, 2.5% пар по построению).
Запас сознательный: внутриличностная полоса включает не только шум конвейера
(освещение, причёска, годы съёмки, микроповороты внутри бина), поэтому «расходится»
помечается только заведомо больше обычной гулянки — меньше ложных тревог, больше
пропусков. Для каждой метрики вместе с границей хранится `signal_cross` — как часто
её «расходится» встречается у РАЗНЫХ лиц (у устойчивых 9 он в 2–3 раза информативнее).

Честные ограничения: калибровка сделана по трём личностям и 257/177 кадрам; для
|yaw| > 25° калибровки нет — границы берутся из более мягкого режима, и строка
помечается `extrapolated`. Без MediaPipe 14 метрик из 30 не считаются: они уходят как
null с причиной, а не как ноль. Доли цвета — близость к двум ближайшим эталонам, а не
вероятность личности; если медианы личностей по метрике стоят плотнее полосу
(`min_gap`), делить там почти нечего и ячейка будет мутной — это видно в подсказке.
"""
from __future__ import annotations

import functools
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from morphing.backend import approved_metrics as A
from morphing.backend import metric_registry as R
from morphing.backend import mp_worker

BANDS_PATH = Path(__file__).resolve().parent / "metric_bands.json"
FRONTAL_YAW_MAX = 15.0     # бин frontal в калибровке: |yaw| ≤ 15°
SUBFRONTAL_YAW_MAX = 25.0  # выше — калибровки нет, границы экстраполируются
# Пороги «кадр с мимикой» — те же, что при отборе (metric_shortlist.EXPR_MAX): боевая
# отметка в тех же единицах, чтобы красные ячейки рта и глаз можно было объяснить
# выражением, а не формой.
EXPR_MAX = {"jawOpen": 0.12, "mouthSmileLeft": 0.25, "mouthSmileRight": 0.25,
            "browInnerUp": 0.30, "eyeBlinkLeft": 0.35, "eyeBlinkRight": 0.35}
VERDICT_RU = {"same": "совпадает", "border": "на границе", "differ": "расходится",
              "unknown": "нет данных"}


class BandsMissing(RuntimeError):
    """Нет `metric_bands.json` — полос сравнения не из чего брать, эндпоинт отдаёт 503."""


@functools.lru_cache(maxsize=1)
def bands() -> dict[str, Any]:
    """Откалиброванные полосы целиком (со сводными заметками). Только чтение."""
    if not BANDS_PATH.is_file():
        raise BandsMissing(f"нет калибровки полос: {BANDS_PATH} (запусти app9/validation/calibrate_metric_bands.py)")
    payload = json.loads(BANDS_PATH.read_text(encoding="utf-8"))
    return payload


def _r(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def _regime(yaw_a: float | None, yaw_b: float | None) -> tuple[str, bool]:
    """Какой полосой судить пару — по самому повёрнутому кадру из двух.

    Returns: (regime, extrapolated). `extrapolated` — оба режима уже калиброваны, но
    кадр вышел за 25°, и полоса взята мягче (max из двух), чем надо бы.
    """
    yaws = [abs(v) for v in (yaw_a, yaw_b) if v is not None]
    worst = max(yaws) if yaws else 0.0
    if worst <= FRONTAL_YAW_MAX:
        return "frontal", False
    if worst <= SUBFRONTAL_YAW_MAX:
        return "subfrontal", False
    return "subfrontal", True


def _mp_scale(pts: np.ndarray) -> float:
    """RMS-радиус MP-каркаса вокруг центра — норма масштаба для probe-ветки."""
    xy = pts[:, :2] - pts[:, :2].mean(0)
    return float(np.sqrt((xy ** 2).sum(1).mean())) or 1.0


def _attribution(value: float | None, reg: dict[str, Any], band: float | None,
                 k_differ: float | None) -> dict[str, Any]:
    """На кого из трёх людей смотрит значение — в долях двух ближайших эталонов.

    Эталон = медиана метрики по спокойным кадрам личности (frontal или подфронт по углу
    СВОЕГО фото). Делим цвет только между двумя ближайшими медианами:
    `w_дальняя = d_ближняя / (d_ближняя + d_дальняя)` — это ровно 0.5 посередине между
    двумя лицами и 0 на самой медиане. Полоса на долю не влияет (обе разности в одних
    единицах), поэтому здесь нет ни одного выдуманного порога.

    `stray` — честная отметка «ни одно из трёх лиц так не выглядит»: ближайшая медиана
    дальше, чем 97.5-й перцентиль разностей кадров одного лица (уже откалиброван).
    """
    out: dict[str, Any] = {"who": None, "split": [], "medians": {}, "stray": None,
                           "distance": None, "reason": None}
    if value is None:
        return out
    ref = reg.get("ref") or {}
    med = {str(i): float(r["median"]) for i, r in ref.items() if r.get("median") is not None}
    out["medians"] = {i: _r(m) for i, m in sorted(med.items())}
    if len(med) < 2:
        out["reason"] = ("эталонов личностей меньше двух — делить цвет не между кем"
                         if med else "нет эталонных медиан — красить не по чему")
        return out
    dist = {i: abs(value - m) for i, m in med.items()}
    order = sorted(dist, key=lambda i: (dist[i], i))
    near, far = order[0], order[1]
    denom = dist[near] + dist[far]
    w_far = dist[near] / denom if denom else 0.5
    out["who"] = near
    out["split"] = [{"ident": near, "w": round(1.0 - w_far, 4)},
                    {"ident": far, "w": round(w_far, 4)}]
    if band:
        out["distance"] = _r(dist[near] / band, 3)
        out["stray"] = bool(k_differ is not None and dist[near] / band > k_differ)
    return out


def _expression(blend: dict[str, float]) -> dict[str, Any]:
    """Флаг мимики в кадре: без него красные ячейки рта/глаз легко принять за форму."""
    flags = [k for k, thr in EXPR_MAX.items() if float(blend.get(k, 0.0)) > thr]
    return {"neutral": not flags, "flags": flags}


def photo_bundle(raw: bytes, label: str) -> dict[str, Any]:
    """Одно фото: канон 3DMM + MediaPipe + все 30 значений и причины пропусков.

    `metrics` содержит только конечные числа; для всего отсутствующего `absent` хранит
    причину по имени метрики. Нулей вместо значений здесь нет намеренно.
    """
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh

    recon = reconstruct_image(io.BytesIO(raw), device="cpu")
    if recon is None:
        raise ValueError(f"На фото {label} не обнаружено лицо")
    v_aligned, pts106, _scale = align_identity_mesh(recon)
    if pts106 is None or pts106.shape != (106, 3):
        raise ValueError(f"Фото {label}: 106 ландмарков не сошлись")
    pts134 = v_aligned[np.asarray(recon["ldm134_indices"], dtype=np.int64)]
    refs = v_aligned[list(R.ANAT_VERTS)]
    if pts134.shape != (134, 3) or refs.shape != (9, 3):
        raise ValueError(f"Фото {label}: сетка не дала 134 точек и базисы")

    pmp, blend, mp_reason = None, {}, None
    try:
        found = mp_worker.client().detect(raw)
        pmp, blend = found["points"], found["blendshapes"]
    except mp_worker.MediaPipeUnavailable as exc:
        mp_reason = str(exc)

    values = R.compute_all(pts106, pmp, _mp_scale(pmp) if pmp is not None else 1.0,
                           q134=pts134, refs=refs)
    finite: dict[str, float] = {}
    absent: dict[str, str] = {}
    for name in A.APPROVED_NAMES:
        v = values.get(name)
        if v is not None and math.isfinite(v):
            finite[name] = round(float(v), 6)
        elif A.requires_mediapipe(name) and pmp is None:
            absent[name] = f"нужен MediaPipe, он недоступен: {mp_reason}"
        elif A.requires_ldm134(name):
            absent[name] = "нужен 134-срез сетки — он не посчитался на этом кадре"
        else:
            absent[name] = "значение не посчиталось (вырожденная геометрия кадра)"

    return {
        "label": label,
        "yaw": _r(float(np.asarray(recon["angles_deg"], dtype=np.float64)[1]), 2),
        "pose_bin": str(recon.get("pose_bin", "")),
        "mediapipe": {"available": pmp is not None, "reason": mp_reason},
        "expression": _expression(blend) if pmp is not None else None,
        "metrics": finite,
        "absent": absent,
    }


def pair_rows(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    """По каждой из 30 метрик: значения двух фото, цвет-доля по личностям, вердикт пары.

    `a`/`b` — отнесение каждого значения к эталонам личностей (по углу СВОЕГО фото:
    фронт судим по фронтальным медианам, подфронт — по подфронтовым). `verdict` — про
    другое: согласны ли два снимка между собой. Границы `k_same`/`k_differ` откалиброваны
    по эмпирическим разностям кадров ОДНОГО лица (80-й и 97.5-й перцентили |A−B| в
    полосах): same — разница обычна для одного лица, border — случается, differ — у
    одного лица так не бывает.
    """
    per_metric = bands()["metrics"]
    regime, extrapolated = _regime(a.get("yaw"), b.get("yaw"))
    photos = {"a": a, "b": b}
    rows: list[dict[str, Any]] = []
    for name in A.APPROVED_NAMES:
        meta = per_metric.get(name) or {}
        reg = meta.get(regime) or {}
        band = reg.get("mad_pooled") or meta.get("max_band")
        k_same, k_differ = reg.get("k_same"), reg.get("k_differ")
        if extrapolated:
            # За пределами калибровки (>25°) границы берём из более мягкого из двух
            # режимов: не красним кадр только потому, что такого угла не мерили.
            f, s = meta.get("frontal") or {}, meta.get("subfrontal") or {}
            pair = [(x.get("k_same"), x.get("k_differ")) for x in (f, s)]
            pair = [p for p in pair if p[0] and p[1]]
            if pair:
                k_same = min(p[0] for p in pair)
                k_differ = max(p[1] for p in pair)
        va, vb = a["metrics"].get(name), b["metrics"].get(name)
        att: dict[str, Any] = {}
        for side, photo in photos.items():
            own_regime, own_extra = _regime(photo.get("yaw"), None)
            own = meta.get(own_regime) or {}
            own_band = own.get("mad_pooled") or meta.get("max_band")
            value = va if side == "a" else vb
            att[side] = _attribution(value, own, own_band, own.get("k_differ"))
            if value is None:
                att[side]["reason"] = (photo["absent"].get(name)
                                       or "нет значения на этом фото")
            att[side]["regime"] = own_regime
            att[side]["extrapolated"] = own_extra
        row: dict[str, Any] = {
            "name": name,
            "description": meta.get("description") or R.describe(name),
            "framework": meta.get("framework") or A.framework(name),
            "group": meta.get("group") or A.group(name),
            "kind": meta.get("kind") or R.meta(name)["kind"],
            "trusted": bool(meta.get("trusted", A.pose_stable(name))),
            "value_a": va,
            "value_b": vb,
            "a": att["a"],
            "b": att["b"],
            "diff": None,
            "signed_diff": None,
            "band": _r(band),
            "ratio": None,
            "k_same": k_same,
            "k_differ": k_differ,
            "edge_same": _r(band * k_same) if band and k_same else None,
            "edge_differ": _r(band * k_differ) if band and k_differ else None,
            "signal_cross": reg.get("signal_cross"),
            "min_gap": reg.get("min_gap"),
            "verdict": "unknown",
            "verdict_ru": VERDICT_RU["unknown"],
            "regime": regime,
            "extrapolated": extrapolated,
            "reason": None,
        }
        row["other_people"] = bool(att["a"]["who"] and att["b"]["who"]
                                   and att["a"]["who"] != att["b"]["who"])
        if va is None or vb is None:
            parts = [att[s]["reason"] for s in ("a", "b") if att[s]["reason"]]
            row["reason"] = "; ".join(parts) or "нет значения на одном из фото"
        elif not band or not k_same or not k_differ:
            row["reason"] = "метрика без откалиброванных границ — сравнивать нечем"
        else:
            gap = abs(va - vb)
            row["diff"] = round(gap, 6)
            row["signed_diff"] = round(va - vb, 6)
            row["ratio"] = round(gap / band, 3)
            row["verdict"] = "same" if gap <= band * k_same else ("differ" if gap > band * k_differ else "border")
            row["verdict_ru"] = VERDICT_RU[row["verdict"]]
        rows.append(row)
    return rows


def _count(rows: list[dict[str, Any]], *, trusted: bool | None = None) -> dict[str, int]:
    sel = [r for r in rows if trusted is None or r["trusted"] is trusted]
    out = {v: 0 for v in VERDICT_RU}
    for row in sel:
        out[row["verdict"]] += 1
    out["total"] = len(sel)
    return out


def _dominance(rows: list[dict[str, Any]], identities: list[str],
               *, trusted: bool | None = None) -> dict[str, Any]:
    """Кто преобладает: средний цвет набора ячеек и кем выиграна каждая из них.

    `mix` складывает доли из `split`, поэтому ячейка «посередине между двумя лицами»
    даёт обоим по 0.5 — ровно то, что видно глазами. `count` считает только ближайшую
    личность. `stray` — сколько ячеек не похоже ни на одно из трёх лиц.
    """
    sel = [r for r in rows if trusted is None or r["trusted"] is trusted]
    out: dict[str, Any] = {}
    for side in ("a", "b"):
        mix = {str(i): 0.0 for i in identities}
        count = {str(i): 0 for i in identities}
        no_value = stray = 0
        for row in sel:
            att = row[side]
            if att["who"] is None:
                no_value += 1
            else:
                count[att["who"]] += 1
            if att["stray"]:
                stray += 1
            for part in att["split"]:
                mix[part["ident"]] = mix.get(part["ident"], 0.0) + float(part["w"])
        attributed = len(sel) - no_value
        lead = max(mix, key=lambda i: mix[i]) if attributed and mix else None
        out[side] = {
            "total": len(sel), "attributed": attributed, "no_value": no_value,
            "stray": stray,
            "mix": {i: round(mix[i] / attributed, 3) for i in mix} if attributed else {},
            "count": count,
            "lead": lead,
            "lead_share": round(mix[lead] / attributed, 3) if attributed and lead else None,
        }
    return out


def pair_report(raw_a: bytes, raw_b: bytes) -> dict[str, Any]:
    """Готовый ответ для интерфейса: два фото, 30 строк, средние цвета по личностям."""
    a = photo_bundle(raw_a, "A")
    b = photo_bundle(raw_b, "B")
    rows = pair_rows(a, b)
    payload = bands()
    identities = list(payload.get("identities") or [])
    regime, extrapolated = _regime(a.get("yaw"), b.get("yaw"))
    if regime == "frontal":
        note = f"оба кадра |yaw| ≤ {FRONTAL_YAW_MAX:g}° — границы фронтального режима"
    else:
        note = f"самый повёрнутый кадр > {FRONTAL_YAW_MAX:g}° — границы подфронта"
        if extrapolated:
            note += f", при |yaw| > {SUBFRONTAL_YAW_MAX:g}° взяты из более мягкого режима"
    return {
        "status": "ok",
        "schema_version": payload.get("schema_version", ""),
        "identities": identities,
        "metric_set": {"approved": len(A.APPROVED_NAMES), "trusted": len(A.POSE_STABLE),
                       "calibrated": len(payload.get("metrics", {}))},
        "regime": {"pair": regime, "extrapolated": extrapolated, "note": note},
        "meaning": {
            "cell_color": ("цвет ячейки = на кого из трёх людей смотрит значение: две "
                           "ближайших эталонных медианы делят её по близости, ровно "
                           "посередине между лицами — 50/50"),
            "mix": "средний цвет по набору ячеек (доли суммируются) — кто преобладает",
            "stray": "ячейка дальше от всех трёх эталонов, чем обычная гулянка одного лица",
            "same": "|A−B| ≤ k_same·полоса — разница обычна для двух снимков одного лица",
            "border": "k_same·полоса < |A−B| ≤ k_differ·полоса — больше обычного, но у одного лица ещё бывает",
            "differ": "|A−B| > k_differ·полоса — у одного лица так не бывает (≤2.5% пар в калибровке)",
            "unknown": "метрика не посчиталась (нет каркаса) или границы не откалиброваны",
            "trusted": f"{len(A.POSE_STABLE)} метрик держат подфронт (|yaw| 10–25°) — обведены белой рамкой",
            "per_metric": "medians/split у каждой ячейки, k_same/k_differ/edge_*, signal_cross и min_gap в строке",
        },
        "units": payload.get("units", ""),
        "population": payload.get("population", ""),
        "caveats": list(payload.get("caveats", [])),
        "photos": [a, b],
        "rows": rows,
        "summary": {"all": _count(rows), "trusted": _count(rows, trusted=True),
                    "pale": _count(rows, trusted=False),
                    "people": {"all": _dominance(rows, identities),
                               "trusted": _dominance(rows, identities, trusted=True),
                               "pale": _dominance(rows, identities, trusted=False)}},
    }
