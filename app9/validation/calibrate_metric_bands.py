#!/usr/bin/env python
"""Калибровка таблицы 30 утверждённых метрик: полосы совпадения + эталоны трёх личностей.

Пишет `morphing/backend/metric_bands.json` — единственный источник чисел, по которым прод
красит ячейку: в цвет какого человека смотрит значение метрики (и в какой пропорции, если
значение посередине между двумя лицами), плюс границы «снимки говорят одно / расходится».

Полоса = MAD значений метрики ВНУТРИ одной личности, отдельно для двух режимов съёмки:
фронт (|yaw| ≤ 15°, бин frontal) и подфронт (10–25°, бины left_light/right_light). Обе
выборки уже сняты в кэшах `metric_shortlist` и `subfrontal_check` — с фото ничего
заново не считается.

Эталоны (`ref`) — медиана и MAD каждой из трёх личностей по спокойным кадрам того же
режима: это три точки отсчёта, между которыми интерфейс делит цвет ячейки.

Границы вердикта пары берём не «на глаз», а по эмпирическим распределениям разностей:
* `k_same`   — 80-й перцентиль |A−B| по ВСЕМ парам кадров одного лица (в полосах).
               Ниже — разница обычна для одного лица: вердикт `same`;
* `k_differ` — 97.5-й перцентиль того же распределения. Выше — у одного лица в этой
               выборке так не бывает (2.5% пар по построению), поэтому вердикт `differ`
               честен; между ними — `border`;
* `signal_cross` — доля пар РАЗНЫХ личностей, у которых |A−B| > k_differ. Это мера
               полезности вердикта «расходится» именно для этой метрики: чем больше,
               тем сильнее он говорит «лица разные».

Берём именно внутриличностный разброс, а не межличностный: вопрос таблицы — «эти два
снимка говорят одно или разное», и ответ должен быть в единицах «насколько у ОДНОГО
человека гуляет эта метрика».

Ограничения, которые надо помнить (они же в JSON):
* три личности — полоса описывает этих людей, а не популяцию;
* внутриличностный MAD шире чистого шума пересъёмки: в него попадают освещение,
  причёска, годы съёмки и микроповороты головы внутри одного бина. Границы от этого
  консервативны: «расходится» помечается только заведомо большое, ложных тревог меньше,
  пропусков больше — и потому решение по одной метрике принимать нельзя, смотрят на
  набор (у устойчивых 9 signal_cross в 2–3 раза выше, чем у остальных);
* для |yaw| > 25° калибровки нет: прод берёт более мягкую границу и честно помечает
  строку как extrapolated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app9.validation import metric_shortlist as ms  # noqa: E402
from morphing.backend import approved_metrics as A  # noqa: E402
from morphing.backend import metric_registry as R  # noqa: E402

OUT = ROOT / "morphing/backend/metric_bands.json"
REGIMES = {"frontal": ms.STORE, "subfrontal": ROOT / ".runtime/subfrontal_check"}
SAME_Q, DIFFER_Q = 80.0, 97.5
MIN_SAME_PAIRS = 200   # меньше — перцентиль хвоста не оценить, границу не пишем
MIN_NEUTRAL_REF = 5    # спокойных кадров для эталона личности; меньше — берём все


def _same_pairs(v: np.ndarray) -> np.ndarray:
    """Все |A−B| по конечным значениям метрики внутри ОДНОЙ личности."""
    v = np.sort(np.asarray(v, dtype=float)[np.isfinite(v)])
    if v.size < 2:
        return np.array([], dtype=float)
    i, j = np.triu_indices(v.size, 1)
    return v[j] - v[i]


def _cross_pairs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Все |A−B| между двумя личностями (конечные значения)."""
    a = np.asarray(a, dtype=float)[np.isfinite(np.asarray(a, dtype=float))]
    b = np.asarray(b, dtype=float)[np.isfinite(np.asarray(b, dtype=float))]
    if a.size == 0 or b.size == 0:
        return np.array([], dtype=float)
    return np.abs(a[:, None] - b[None, :]).ravel()


def _reference(v: np.ndarray, ok: np.ndarray) -> dict[str, Any]:
    """Набор «как выглядит это лицо»: медиана и разброс по спокойным кадрам.

    Медианы — это те три точки, между которыми интерфейс делит ячейку цветом:
    значение посередине между медианами двух личностей даёт 50/50, ближе к
    одной — соответствующую долю. Мимика (открытая челюсть, улыбка, морщина
    бровей) сдвигает метрику, поэтому в эталон идут только кадры с `expr_ok`;
    если таких кадра мало, берём все — и честно пишем basis="all".
    """
    v = np.asarray(v, dtype=float)
    finite = np.isfinite(v)
    calm = np.asarray(ok, dtype=bool) & finite
    if int(calm.sum()) < MIN_NEUTRAL_REF:
        calm, basis = finite, "all"
    else:
        basis = "neutral"
    if not calm.any():
        return {"median": None, "mad": None, "n": 0, "basis": "none"}
    return {"median": ms._r(float(np.median(v[calm]))),
            "mad": ms._r(float(ms.mad(v[calm]))),
            "n": int(calm.sum()), "basis": basis}


def _regime(store: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, np.ndarray]],
                                  dict[str, dict[str, np.ndarray]]]:
    """(сводка по метрике, значения по личностям, маска спокойной мимики) для режима."""
    rows, values, expr = ms.load_values(store)
    idents = [i for i in ms.IDENTITIES if i in rows]
    out: dict[str, dict[str, Any]] = {}
    for name in A.APPROVED_NAMES:
        per_ident: dict[str, float | None] = {}
        ref: dict[str, dict[str, Any]] = {}
        pooled: list[np.ndarray] = []
        for ident in idents:
            v = np.asarray(values[ident].get(name), dtype=float)
            if v is None or not np.isfinite(v).any():
                per_ident[ident] = None
                ref[ident] = {"median": None, "mad": None, "n": 0, "basis": "none"}
                continue
            mad = ms.mad(v)
            per_ident[ident] = ms._r(float(mad)) if mad == mad else None
            ref[ident] = _reference(v, expr[ident]["expr_ok"])
            if per_ident[ident] is not None:
                # отклонения от медианы СВОЕЙ личности: три личности с разными
                # уровнями складываются в один разброс без межличностного сдвига
                pooled.append(v - float(np.nanmedian(v)))
        flat = np.concatenate(pooled) if pooled else np.array([np.nan])
        out[name] = {
            "mad_pooled": ms._r(float(ms.mad(flat))),
            "mad_by_identity": per_ident,
            "ref": ref,
            "n": int(sum(int(np.isfinite(np.asarray(values[i].get(name), dtype=float)).sum())
                          for i in idents)),
        }
    return out, values, expr


def _cuts(name: str, values: dict[str, dict[str, np.ndarray]], band: float | None) -> dict[str, Any]:
    """Границы вердиктов по эмпирическим разностям: в полосах, плюс полезность «расходится»."""
    absent = {"k_same": None, "k_differ": None, "signal_cross": None,
              "n_same_pairs": 0, "n_cross_pairs": 0}
    if not band:
        return absent
    idents = list(values)
    same = np.concatenate([_same_pairs(values[i].get(name, np.array([np.nan]))) for i in idents]) \
        if idents else np.array([], dtype=float)
    blocks = [_cross_pairs(values[a].get(name, np.array([np.nan])),
                           values[b].get(name, np.array([np.nan])))
              for i, a in enumerate(idents) for b in idents[i + 1:]]
    cross_arr = np.concatenate(blocks) if blocks else np.array([], dtype=float)
    if same.size < MIN_SAME_PAIRS:
        return {"k_same": None, "k_differ": None, "signal_cross": None,
                "n_same_pairs": int(same.size), "n_cross_pairs": int(cross_arr.size)}
    r = same / band
    k_same = ms._r(float(np.percentile(r, SAME_Q)))
    k_differ = ms._r(float(np.percentile(r, DIFFER_Q)))
    signal = round(float((cross_arr / band > k_differ).mean()), 4) if cross_arr.size else None
    return {"k_same": k_same, "k_differ": k_differ, "signal_cross": signal,
            "n_same_pairs": int(same.size), "n_cross_pairs": int(cross_arr.size)}


def _separation(name: str, stats: dict[str, Any], band: float | None) -> dict[str, Any]:
    """Насколько три эталона разведены по этой метрике — в полосах.

    Метрика с близкими медианами личностей физически не может раскрасить ячейку
    «за кого»: там доли всегда будут около 1/3, и это надо видеть, а не открывать
    таблицу вслепую. `min_gap` — самая близкая пара личностей в полосах.
    """
    med = {i: r["median"] for i, r in stats["ref"].items() if r["median"] is not None}
    if not band or len(med) < 2:
        return {"min_gap": None, "pairs": {}}
    pairs = {f"{a}~{b}": ms._r(abs(med[a] - med[b]) / band)
             for a in med for b in med if a < b}
    return {"min_gap": ms._r(min(pairs.values())), "pairs": pairs}


def main() -> int:
    if not any(REGIMES["subfrontal"].glob("lmk_*.npz")):
        print(f"нет кэша подфронта в {REGIMES['subfrontal']} — сначала "
              "subfrontal_check extract-mp/extract-ldm")
        return 1
    stats = {regime: _regime(store)[:2] for regime, store in REGIMES.items()}
    metrics: dict[str, Any] = {}
    for name in A.APPROVED_NAMES:
        front, sub = stats["frontal"][0][name], stats["subfrontal"][0][name]
        # Ширина полосы в прод-выборе: режим подфронта шире почти всегда, и
        # сомнительные кадры (поворот > 25°) надо судить по более мягкой границе,
        # чтобы не пугать «расходится» там, где просто нет калибровки.
        candidates = [v["mad_pooled"] for v in (front, sub) if v["mad_pooled"]]
        metrics[name] = {
            "framework": A.framework(name),
            "group": A.group(name),
            "kind": R.meta(name)["kind"],
            "trusted": A.pose_stable(name),
            "description": R.describe(name),
            "frontal": {**front, **_cuts(name, stats["frontal"][1], front["mad_pooled"]),
                        **_separation(name, front, front["mad_pooled"])},
            "subfrontal": {**sub, **_cuts(name, stats["subfrontal"][1], sub["mad_pooled"]),
                           **_separation(name, sub, sub["mad_pooled"])},
            "max_band": ms._r(max(candidates)) if candidates else None,
        }
    # Сколько метрик вообще не способно разделить этих людей: их медианы стоят плотнее
    # полосу — там средний цвет по набору заведомо мутный.
    blind = [n for n, m in metrics.items()
             if (m["frontal"]["min_gap"] or 0) < 1.0
             and all(m["frontal"]["ref"][i]["median"] is not None for i in ms.IDENTITIES)]
    payload = {
        "schema_version": "morphing-metric-bands-v3",
        "identities": list(ms.IDENTITIES),
        "units": "в единицах самой метрики: отношения — доли RMS-106, углы — градусы",
        "meaning": {
            "band": ("mad_pooled — разброс метрики внутри ОДНОЙ личности (отклонения от "
                     "медианы своего лица, pooled по трём личностям)"),
            "ref": ("median — типичное значение метрики у этой личности по спокойным "
                    "(без мимики) кадрам; mad — его разброс; basis=all, если спокойных "
                    "кадров меньше 5. Три медианы — три точки отсчёта, между которыми "
                    "ячейка делится цветом: ровно посередине между двумя лицами даёт 50/50"),
            "min_gap": ("расстояние между самыми близкими медианами личностей в полосах: "
                        f"меньше 1 — метрика этих людей почти не различает (таких {len(blind)} "
                        "из 30), и её доля в общем цвете почти случайна"),
            "k_same": f"{SAME_Q:g}-й перцентиль |A−B| по всем парам кадров одного лица, в полосах: "
                      "ниже — вердикт same («снимки говорят одно»)",
            "k_differ": f"{DIFFER_Q:g}-й перцентиль того же распределения: выше — differ "
                        "(«расходится»); между ними — border",
            "signal_cross": "доля пар РАЗНЫХ личностей с вердиктом differ у данной метрики — "
                            "насколько вообще ценен её «расходится»",
        },
        "population": ("3 личности; фронт: put 150 / vas 76 / udmurt 31; подфронт "
                       "(|yaw| 10–25°): put 100 / vas 45 / udmurt 32; кадры выборок "
                       "не пересекаются"),
        "caveats": [
            "полоса шире чистого шума пересъёмки: в ней сидят освещение, годы, причёски "
            "и микроповороты внутри бина — граница консервативна (меньше ложных «разные»)",
            "три человека: переносить полосу на другие лица можно только как порядок величины",
            "для |yaw| > 25° калибровки нет — прод берёт max_band и помечает строку extrapolated",
            "по одной метрике решение не принимают: differ у разных лиц срабатывает "
            "4–28% метрик, смотрят набор; у 9 устойчивых signal_cross в 2–3 раза выше, "
            "поэтому они и обведены белой рамкой",
            "цвета ячейки — это доля близости к двум ближайшим эталонам, а не вероятность "
            "личности: вне трёх лиц ячейка всё равно поделится по ближайшей паре",
            f"средний цвет по всем 30 метрикам размыт: у {len(blind)} из 30 медианы личностей "
            "разнесены меньше чем на полосу, поэтому тренд читают по 9 устойчивым, а не по 30",
        ],
        "generated_by": "app9/validation/calibrate_metric_bands.py",
        "metrics": metrics,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    trusted = sum(1 for m in metrics.values() if m["trusted"])
    no_band = [n for n, m in metrics.items() if not m["max_band"]]
    no_cut = [n for n, m in metrics.items() if not m["frontal"]["k_differ"]]
    print(f"записано {OUT}: метрик {len(metrics)}, доверенных {trusted}, "
          f"без полосы {len(no_band)}{' — ' + ', '.join(no_band) if no_band else ''}, "
          f"без границ {len(no_cut)}{' — ' + ', '.join(no_cut) if no_cut else ''}")
    print(f"медианы личностей почти совпадают (min_gap < 1 полосы, красить нечем): "
          f"{len(blind)} — {', '.join(blind) if blind else 'нет'}")
    for name in A.APPROVED_NAMES:
        m = metrics[name]
        f, s = m["frontal"], m["subfrontal"]
        med = "/".join("—" if f["ref"][i]["median"] is None else str(f["ref"][i]["median"])
                       for i in ms.IDENTITIES)
        print(f"  {name:44s} {m['framework']:9s} эталоны[{med}] gap {str(f['min_gap']):7s} "
              f"|MAD {str(f['mad_pooled']):8s} k {str(f['k_same']):5s}/{str(f['k_differ']):6s} "
              f"sig {str(f['signal_cross']):6s} | подфронт gap {str(s['min_gap']):7s} "
              f"MAD {str(s['mad_pooled']):8s} k {str(s['k_same']):5s}/{str(s['k_differ']):6s} "
              f"sig {str(s['signal_cross']):6s} {'★' if m['trusted'] else ' '}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
