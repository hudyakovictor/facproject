#!/usr/bin/env python
"""Проверка утверждённых 30 метрик на подфронтальном ракурсе (|yaw| 10–25°).

Стадии: `extract-mp`, `extract-ldm` (делится на шарды), `compare`.

Зачем. Набор утверждён по фронтальным кадрам, а в прод он попадёт на все, включая
повёрнутые на 10–25°. Там 2D-мерки MediaPipe укорачиваются проекцией, а 3DMM
достраивает половину лица по одному краю, поэтому вопрос один: держится ли
разделение личностей на повороте и не уезжает ли абсолютный уровень метрики.

Сравниваются одни и те же определения и то же боевое выравнивание, но другие фото:
подфронтальная выборка (бины left_light/right_light, |yaw| 10–25°) не пересекается с
фронтальной ни по одному кадру. По каждой метрике смотрим:

* eta2 и попарную AUC на нейтральном по мимике подмножестве — те же гейты тира A
  (0.30 / 0.80 / |rho_jawopen| ≤ 0.55) и тот же перестановочный ноль, но с поправкой
  Бонферрони по 30 метрикам (q = 1 − 0.05/30 ≈ 0.99833), а не по 253;
* сдвиг уровня: медиана каждой личности на подфронте против фронта, в единицах MAD
  той же личности на фронте. Разделение может остаться, а уровень — уехать, и тогда
  порог, выставленный по фронту, на таком кадре врёт;
* порядок личностей: максимум и минимум по медианам остаются на своих местах;
* rho_yaw — корреляция с подписным yaw ВНУТРИ личности (иначе коррелят показывает
  разницу между людьми, а не влияние ракурса);
* перенос прототипов: центроиды по фронту, классификация подфронтальных кадров
  ближайшим центроидом. Это по смыслу то, что делает прод, и число показывает,
  держится ли набор целиком, а не только поодиночке.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app9.validation import metric_shortlist as ms  # noqa: E402
from morphing.backend import approved_metrics as A  # noqa: E402
from app9.validation.frontal_17_check import CSVS, subfrontal_files  # noqa: E402

SUB_STORE = ROOT / ".runtime" / "subfrontal_check"
FRONT_STORE = ms.STORE
REPORT_JSON = ROOT / "app9/validation/report/subfrontal_check.json"
REPORT_MD = ROOT / "app9/validation/report/subfrontal_check.md"
IDENTITIES = ms.IDENTITIES
NAMES = A.APPROVED_NAMES
# Те же гейты, что у тира A: решение по ним принимал владелец, менять их задним
# числом под новую выборку означало бы подгонять критерий под результат.
GATES = dict(ms.TIER_A_GATES)
# Сдвиг уровня больше этого — «уровень уехал»: 1.5 MAD — примерно «на глаз не видно».
LEVEL_SHIFT_MAX = 1.5
# Корреляция с поворотом внутри личности выше этого — метрика читает позу, а не лицо.
YAW_LEAK_MAX = 0.60
# Минимум живых метрик в строке, чтобы nearest-centroid вообще что-то решал: с
# меньшим числом предсказание — угадывание по двум-трём признакам.
MIN_ALIVE_COLS = 10

# Колонки матрицы метрик идут строго в этом порядке.
COL_OF = {name: j for j, name in enumerate(NAMES)}


def yaw_by_name(ident: str) -> dict[str, float]:
    """Подписной yaw по именам фото (знак = влево/вправо — нужно для утечки позы)."""
    out: dict[str, float] = {}
    with CSVS[ident].open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get("filename") or "").strip()
            try:
                out[name] = float(rec.get("yaw_deg"))
            except (TypeError, ValueError):
                continue
    return out


def _matrix(store: Path) -> dict[str, Any]:
    """{idents: {личность: {names, X (n,30), jaw, expr_ok, yaw}}} из кэша `store`."""
    rows, values, expr = ms.load_values(store=store)
    idents: dict[str, dict[str, Any]] = {}
    for ident in IDENTITIES:
        if ident not in rows:
            continue
        X = np.stack([values[ident].get(m, np.full(len(rows[ident]), np.nan))
                      for m in NAMES], axis=1)
        yaws = yaw_by_name(ident)
        idents[ident] = {
            "names": rows[ident],
            "X": X,
            "jaw": expr[ident]["jawOpen"],
            "expr_ok": expr[ident]["expr_ok"],
            "yaw": np.array([yaws.get(nm, math.nan) for nm in rows[ident]], dtype=float),
        }
    return {"idents": idents,
            "labels": np.concatenate([np.full(len(v["names"]), k)
                                      for k, v in enumerate(idents.values())])}


def _cat(mat: dict[str, Any], key: str) -> np.ndarray:
    return np.concatenate([v[key] for v in mat["idents"].values()])


def _regime_stats(mat: dict[str, Any], n_perm: int) -> tuple[dict[str, dict[str, Any]],
                                                             dict[str, Any]]:
    """Меры по каждой метрике + значимость на перестановочном нуле ЭТОГО режима."""
    idents = list(mat["idents"])
    labels = mat["labels"]
    jaw, yaw = _cat(mat, "jaw"), _cat(mat, "yaw")
    neutral = _cat(mat, "expr_ok") == 1.0
    X = _cat(mat, "X")
    perms = ms.make_label_perms(labels, n_perm) if n_perm > 0 else np.empty((0, labels.size))
    q = 1.0 - 0.05 / len(NAMES)
    stats: dict[str, dict[str, Any]] = {}
    for name in NAMES:
        col = X[:, COL_OF[name]]
        groups = [col[labels == k] for k in range(len(idents))]
        groups_neutral = [col[(labels == k) & neutral] for k in range(len(idents))]
        # rho_yaw: максимум |ρ| по отдельным личностям, на общем — личность вмешивается
        rho_yaw = [abs(ms.rank_correlation(groups[k], yaw[labels == k]))
                   for k in range(len(idents))]
        rho_yaw = max(rho_yaw) if any(r == r for r in rho_yaw) else float("nan")
        row: dict[str, Any] = {
            "n": int(np.isfinite(col).sum()),
            "eta2_neutral": ms._r(ms.eta2(groups_neutral)),
            "auc_neutral": ms._r(ms.pair_auc(groups_neutral)),
            "gap_over_mad": ms._r(ms.gap_over_mad(groups)),
            "rho_jawopen": ms._r(ms.spearman(col, jaw)),
            "rho_yaw": ms._r(rho_yaw),
            # медиана только там, где есть хотя бы одно живое значение: nanmedian по
            # столбцу из одних NaN — это предупреждение на каждую вторую метрику
            "medians": [ms._r(float(np.nanmedian(g))) if np.isfinite(g).sum() else None
                        for g in groups],
            "mad": [ms._r(float(ms.mad(g))) if g.size else None for g in groups],
        }
        if perms.shape[0]:
            row.update(ms.permutation_stats(col, labels, perms, q))
        stats[name] = row
    meta = {"photos": {i: len(mat["idents"][i]["names"]) for i in idents},
            "idents": idents, "neutral": int(neutral.sum()), "total": int(neutral.size),
            "bonferroni_q": round(q, 8), "n_perm": int(perms.shape[0])}
    return stats, meta


def _gate_pass(f: dict[str, Any]) -> bool:
    if any(f.get(k) is None for k in ("eta2_neutral", "auc_neutral", "rho_jawopen")):
        return False
    return (f["auc_neutral"] >= GATES["auc_neutral"]
            and f["eta2_neutral"] >= GATES["eta2_neutral"]
            and abs(f["rho_jawopen"]) <= GATES["abs_rho_jawopen"])


def _significant(f: dict[str, Any]) -> bool:
    return bool(f.get("perm_checked") and f.get("eta2_above_bonf") and f.get("auc_above_bonf"))


def _level_shift(f: dict[str, Any], s: dict[str, Any]) -> list[float | None]:
    """Сдвиг медианы личности на подфронте, в MAD той же личности на фронте."""
    out: list[float | None] = []
    for m_f, m_s, mad_f in zip(f["medians"], s["medians"], f["mad"], strict=True):
        ok = m_f is not None and m_s is not None and mad_f not in (None, 0.0)
        out.append(ms._r((m_s - m_f) / mad_f) if ok else None)  # type: ignore[operator]
    return out


def _order_kept(f: dict[str, Any], s: dict[str, Any]) -> str:
    """Тот же ли лидер и аутсайдер. «н/п» — на фронте личности почти не различаются."""
    m_f = [v for v in f["medians"] if v is not None]
    mads = [v for v in f["mad"] if v not in (None, 0.0)]
    if len(m_f) < 3 or not mads or (max(m_f) - min(m_f)) < 0.5 * float(np.mean(mads)):
        return "н/п"
    if any(v is None for v in s["medians"]):
        return "?"
    same = (int(np.argmax(s["medians"])), int(np.argmin(s["medians"]))) == \
        (int(np.argmax(f["medians"])), int(np.argmin(f["medians"])))
    return "да" if same else "НЕТ"


def _verdict(f: dict[str, Any], s: dict[str, Any], shift: list[float | None],
             order: str) -> str:
    if not s.get("perm_checked"):
        return "не проверено"
    if not _significant(s):
        return "не значимо"
    if not _gate_pass(s):
        return "деградирует"
    if order == "НЕТ":
        return "переставилась"
    if any(v is not None and abs(v) > LEVEL_SHIFT_MAX for v in shift):
        return "уровень уехал"
    if s.get("rho_yaw") is not None and s["rho_yaw"] > YAW_LEAK_MAX:
        return "течёт с позой"
    return "держится"


def _z(X: np.ndarray, center: np.ndarray, scale: np.ndarray, cols: list[int]) -> np.ndarray:
    """Значения подвыборки метрик `cols`, нормированные по фронту.

    `center`/`scale` уже посчитаны на этих же `cols` (см. `_normalize`), поэтому тут
    только срез колонок и вычитание — второй раз индексировать ими было бы ошибкой.
    Нормировка identity-agnostic (глобальные медиана и MAD по всем фронтовым кадрам
    сразу трёх личностей), иначе центроиды «знают» ответы. NaN остаётся NaN.
    """
    z = (X[:, cols] - center) / scale
    return np.where(np.isfinite(z), z, np.nan)


def _nanmed(arr: np.ndarray) -> np.ndarray:
    """Медиана по колонкам без предупреждения на «столбец целиком NaN»: отсутствие
    каркаса у половины выборки — законное «метрики нет», оно отпадает маской в
    `_nearest`, а сыпать RuntimeWarning на каждую такую колонку незачем."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(arr, axis=0)


def _normalize(mat: dict[str, Any], cols: list[int]) -> tuple[np.ndarray, np.ndarray]:
    X = _cat(mat, "X")[:, cols]
    center = _nanmed(X)
    scale = np.array([ms.mad(X[:, j]) for j in range(X.shape[1])], dtype=float)
    scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
    center = np.where(np.isfinite(center), center, 0.0)
    return center, scale


def _nearest(row: np.ndarray, centroids: np.ndarray, min_cols: int) -> int | None:
    """Ближайший центроид по живым колонкам; недобор живых — отказ, а не угадывание.

    `centroids` — строки (личности), `row` — колонки (метрики): маска `ok` именно по
    метрикам, поэтому берётся `[:, ok]`, а не `[ok]`.
    """
    ok = np.isfinite(row) & np.isfinite(centroids).all(axis=0)
    if ok.sum() < max(min_cols, 3):
        return None
    return int(np.argmin(((centroids[:, ok] - row[ok]) ** 2).mean(axis=1)))


def _transfer(front: dict[str, Any], sub: dict[str, Any], cols: list[int],
              min_cols: int) -> dict[str, Any]:
    """Центроиды с фронта -> подфронт; на фронте — leave-one-out (кадр исключён из
    своего центроида), иначе accuracy был бы самоподтверждением."""
    center, scale = _normalize(front, cols)
    classes = list(front["idents"])
    z_f = {i: _z(front["idents"][i]["X"], center, scale, cols) for i in classes}
    z_s = {i: _z(sub["idents"][i]["X"], center, scale, cols) if i in sub["idents"]
           else np.empty((0, len(cols))) for i in classes}
    cen_full = {i: _nanmed(z_f[i]) for i in classes}
    hit_f = tot_f = hit_s = tot_s = 0
    for i in classes:
        k_i = classes.index(i)
        for r in range(z_f[i].shape[0]):
            # свой кадр выкидываем из своего центроида — иначе accuracy подтверждает себя сам
            cen = np.stack([_nanmed(np.delete(z_f[i], r, axis=0) if k == i else z_f[k])
                            for k in classes])
            pred = _nearest(z_f[i][r], cen, min_cols)
            tot_f += pred is not None
            hit_f += pred == k_i
        for r in range(z_s[i].shape[0]):
            pred = _nearest(z_s[i][r], np.stack([cen_full[k] for k in classes]), min_cols)
            tot_s += pred is not None
            hit_s += pred == k_i
    return {"frontal_loo": ms._r(hit_f / tot_f if tot_f else None),
            "sub": ms._r(hit_s / tot_s if tot_s else None),
            "sub_scored": tot_s, "sub_refused": int(_cat(sub, "X").shape[0] - tot_s)}


def compare(n_perm: int) -> int:
    if not any(SUB_STORE.glob("lmk_*.npz")) and not any(SUB_STORE.glob("mp_*.npz")):
        print(f"нет кэша в {SUB_STORE} — сначала extract-mp и extract-ldm")
        return 1
    front, sub = _matrix(FRONT_STORE), _matrix(SUB_STORE)
    shared = [i for i in front["idents"] if i in sub["idents"]]
    if len(shared) < 3:
        print(f"личности не совпали: фронт {list(front['idents'])}, "
              f"подфронт {list(sub['idents'])}")
        return 1
    F, meta_f = _regime_stats(front, n_perm)
    S, meta_s = _regime_stats(sub, n_perm)

    table: list[dict[str, Any]] = []
    for name in NAMES:
        f, s = F[name], S[name]
        shift = _level_shift(f, s)
        order = _order_kept(f, s)
        keep = ("n", "eta2_neutral", "auc_neutral", "gap_over_mad", "rho_jawopen",
                "rho_yaw", "medians", "perm_checked", "eta2_above_bonf", "auc_above_bonf")
        table.append({"metric": name, "framework": A.framework(name),
                      "group": A.group(name),
                      "baseline": dict(zip(("eta2_neutral", "auc_neutral", "rho_jawopen"),
                                           A.baseline(name), strict=True)),
                      "frontal": {k: f[k] for k in keep}, "sub": {k: s[k] for k in keep},
                      "d_eta2_neutral": (ms._r(s["eta2_neutral"] - f["eta2_neutral"])
                                         if None not in (s["eta2_neutral"], f["eta2_neutral"])
                                         else None),
                      "d_auc_neutral": (ms._r(s["auc_neutral"] - f["auc_neutral"])
                                        if None not in (s["auc_neutral"], f["auc_neutral"])
                                        else None),
                      "level_shift_mad": shift, "order_kept": order,
                      "verdict": _verdict(f, s, shift, order)})

    cols_all = list(range(len(NAMES)))
    cols_3d = [j for j, n in enumerate(NAMES) if not A.requires_mediapipe(n)]
    cols_mp = [j for j, n in enumerate(NAMES) if A.requires_mediapipe(n)]
    # Поднабор «держится» — то, что реально можно брать в прод на повороте. Его
    # перенос считаем отдельно: решение о составе боевого вектора принимается по нему.
    cols_hold = [j for j, row in enumerate(table) if row["verdict"] == "держится"]
    transfer = {"all30": _transfer(front, sub, cols_all, MIN_ALIVE_COLS),
                "3ddfa_only": _transfer(front, sub, cols_3d, max(3, len(cols_3d) // 2)),
                "mp_dependent": _transfer(front, sub, cols_mp, max(3, len(cols_mp) // 2))}
    if cols_hold:
        transfer["only_holding"] = _transfer(front, sub, cols_hold,
                                             max(3, len(cols_hold) - 3))
        transfer["only_holding"]["metrics"] = [NAMES[j] for j in cols_hold]
    verdicts: dict[str, int] = {}
    for row in table:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({
        "frontal": meta_f, "sub": meta_s, "gates": GATES,
        "level_shift_max": LEVEL_SHIFT_MAX, "yaw_leak_max": YAW_LEAK_MAX,
        "verdicts": verdicts, "transfer": transfer, "metrics": table,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(table, meta_f, meta_s, verdicts, transfer)

    for label, meta in (("фронт   ", meta_f), ("подфронт", meta_s)):
        print(f"{label}: " + ", ".join(f"{i}={meta['photos'][i]}" for i in meta["idents"])
              + f" · нейтральных {meta['neutral']}/{meta['total']}"
              + f" · перестановок {meta['n_perm']} · q={meta['bonferroni_q']}", flush=True)
    print("\nприговоры: " + ", ".join(f"{k} {v}"
                                      for k, v in sorted(verdicts.items(), key=lambda kv: -kv[1])))
    total_sub = sum(meta_s["photos"].values())
    for fw in A.FRAMEWORKS:
        ns = [S[n]["n"] for n in NAMES if A.framework(n) == fw]
        print(f"покрытие {fw:9s}: {min(ns)}–{max(ns)} живых значений из {total_sub} кадров "
              f"(фронт: {min(F[n]['n'] for n in NAMES if A.framework(n) == fw)}"
              f"–{max(F[n]['n'] for n in NAMES if A.framework(n) == fw)})")
    print("\nперенос прототипов (центроиды с фронта -> подфронт):")
    for key, t in transfer.items():
        print(f"  {key:13s} фронт leave-one-out {t['frontal_loo']} -> подфронт {t['sub']} "
              f"(учтено {t['sub_scored']}, отказов {t['sub_refused']})")
    print(f"\nотчёты: {REPORT_JSON}\n        {REPORT_MD}")
    return 0


def _write_md(table: list[dict[str, Any]], meta_f: dict[str, Any], meta_s: dict[str, Any],
              verdicts: dict[str, int], transfer: dict[str, Any]) -> None:
    ph_f = ", ".join(f"{i} {meta_f['photos'][i]}" for i in meta_f["idents"])
    ph_s = ", ".join(f"{i} {meta_s['photos'][i]}" for i in meta_s["idents"])
    out: list[str] = [
        "# Утверждённые 30 метрик на подфронтальном ракурсе (|yaw| 10–25°)\n\n",
        f"Набор утверждён владельцем по фронтальным кадрам (`metric_shortlist.md`). Здесь "
        f"те же определения и то же боевое выравнивание, но другие кадры: фронт {ph_f} "
        f"(нейтральных {meta_f['neutral']}/{meta_f['total']}), подфронт {ph_s} "
        f"(нейтральных {meta_s['neutral']}/{meta_s['total']}); пересечения по фото нет "
        "ни одного. Перестановок "
        f"{meta_s['n_perm']}, порог Бонферрони q={meta_s['bonferroni_q']} — по 30 метрикам, "
        "поэтому он мягче, чем в основном отчёте (там 253).\n\n",
        f"Гейты те же, что у тира A: AUC(нейтр) ≥ {GATES['auc_neutral']}, "
        f"eta2(нейтр) ≥ {GATES['eta2_neutral']}, |rho_jawopen| ≤ {GATES['abs_rho_jawopen']}. "
        f"Плюс два подфронтальных контроля: сдвиг уровня ≤ {LEVEL_SHIFT_MAX} MAD и "
        f"|rho_yaw| внутри личности ≤ {YAW_LEAK_MAX}.\n\n",
        "## Итог\n\n",
        "· " + ", ".join(f"**{k}** — {v}"
                         for k, v in sorted(verdicts.items(), key=lambda kv: -kv[1])) + "\n\n",
        "Перенос прототипов: центроиды по фронту, кадр относится к ближайшему центроиду "
        "по нормированным метрикам (на фронте — leave-one-out, чтобы не подтверждать себя сам).\n\n",
        "| набор | фронт, leave-one-out | подфронт | учтено кадров | отказов (мало живых метрик) |\n",
        "|---|---|---|---|---|\n",
    ]
    for key, t in transfer.items():
        out.append(f"| {key} | {t['frontal_loo']} | {t['sub']} | {t['sub_scored']} | "
                   f"{t['sub_refused']} |\n")
    out.append(
        "\n`only_holding` — только те метрики, которым приговор «держится»; их состав "
        "приведён в JSON. Это и есть кандидат в боевой вектор на повороте.\n\n")
    flipped = [r for r in table if r["order_kept"] == "НЕТ"]
    if flipped:
        idents = "/".join(meta_f["idents"])
        out.append("## Кто переставился по личностям\n\n")
        out.append(f"Медианы в порядке {idents}; сравнение только по крайним — лидер "
                   "и аутсайдер.\n\n")
        for row in flipped:
            f, s = row["frontal"]["medians"], row["sub"]["medians"]
            out.append(f"- `{row['metric']}` ({row['framework']}): фронт {_fmt_list(f)} → "
                       f"подфронт {_fmt_list(s)}. Приговор: {row['verdict']}.\n")
        out.append("\n")
    out.append("## По метрикам\n\n")
    out.append("| метрика | каркас | eta2 нейтр (фр → под) | AUC нейтр (фр → под) | Δeta2 | "
               "rho_jaw (под) | rho_yaw (под) | сдвиг уровня, MAD (put/vas/udmurt) | "
               "порядок | приговор |\n|---|---|---|---|---|---|---|---|---|---|\n")
    for row in table:
        f, s = row["frontal"], row["sub"]
        shift = " / ".join("—" if v is None else f"{v:+.2f}" for v in row["level_shift_mad"])
        out.append(f"| `{row['metric']}` | {row['framework']} | "
                   f"{f['eta2_neutral']} → {s['eta2_neutral']} | "
                   f"{f['auc_neutral']} → {s['auc_neutral']} | "
                   f"{_fmt(row['d_eta2_neutral'])} | {s['rho_jawopen']} | {s['rho_yaw']} | "
                   f"{shift} | {row['order_kept']} | {row['verdict']} |\n")
    out.append("\n## Что означают приговоры\n\n")
    out.append(
        "Приговор — первое сработавшее сверху вниз: **не значимо** → **деградирует** → "
        "**переставилась** → **уровень уехал** → **течёт с позой** → **держится**. То "
        "есть у «деградирует» может быть и переставленный порядок, и уехавший уровень — "
        "первая причина уже дисквалифицирует метрику, остальные видны по колонкам таблицы.\n\n")
    out.append(
        "* **держится** — на подфронте метрика значима на перестановочном нуле, проходит "
        f"гейты тира A, порядок личностей не переставился, уровень ушёл не больше "
        f"{LEVEL_SHIFT_MAX} MAD и коррелят с поворотом слабее {YAW_LEAK_MAX};\n"
        "* **деградирует** — значимо, но один гейт не проходит (обычно AUC ниже "
        f"{GATES['auc_neutral']}: на повороте разброс внутри личности растёт);\n"
        "* **уровень уехал** — разделение есть, но абсолютное значение сместилось больше "
        "чем на 1.5 MAD: пороги и проценты, выставленные по фронту, на таком кадре "
        "врут (у MediaPipe-ветки это ожидаемо — 2D-расстояния укорачиваются проекцией);\n"
        "* **переставилась** — лидер и аутсайдер по медианам поменялись местами: на "
        "фронте метрика про одно лицо, на повороте про другое, в прод такую нельзя;\n"
        "* **течёт с позой** — |rho_yaw| внутри личности выше порога: признак отчасти "
        "ракурса, а не лица;\n"
        "* **не значимо** — наблюдаемое разделение не превосходит перестановочный ноль "
        "с поправкой Бонферрони;\n"
        "* **н/п** в графе «порядок» — на фронте медианы личностей ближе половины pooled "
        "MAD, сравнивать порядок нечего.\n\n")
    out.append("## Ограничения прогона\n\n")
    out.append(
        "* Три личности: каждый вывод — про этих конкретных людей. «Держится» = «не "
        "сломалась на повороте у этих троих», а не «переносится на популяцию».\n"
        "* Выборки разные по составу кадров (у подфронта иное распределение мимики и "
        "освещения), поэтому сравниваются нормированные меры разделения, а не сырые "
        "значения; сдвиг уровня — как раз про то, насколько сырьё переносимо.\n"
        "* MediaPipe на |yaw| 10–25° может терять точки (скрытый уголок глаза) и молча "
        "подменять их — уверенности детектор не отдаёт, отдельного контроля здесь нет.\n"
        "* Классификатор — nearest-centroid по утверждённым метрикам, а не боевой LDA: "
        "число показывает переносимость признаков, а не точность прода.\n"
        "* 134-точки и базисы вершин на повороте достраиваются моделью: метрика может "
        "выглядеть устойчивой просто потому, что 3DMM предсказывает одну и ту же "
        "анатомию независимо от кадра — это проверяется не здесь, а на резидуале.\n")
    REPORT_MD.write_text("".join(out), encoding="utf-8")


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:+.3f}"


def _fmt_list(vals: list[float | None]) -> str:
    return "[" + ", ".join("—" if v is None else f"{v:.4g}" for v in vals) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="stage", required=True)
    p_mp = subs.add_parser("extract-mp")
    p_mp.add_argument("--per-identity", type=int, default=0,
                      help="0 — вся подфронтальная выборка")
    p_ldm = subs.add_parser("extract-ldm")
    p_ldm.add_argument("--per-identity", type=int, default=0)
    p_ldm.add_argument("--shard", default="0/1", help="k/n: n-я часть фото")
    p_cmp = subs.add_parser("compare")
    p_cmp.add_argument("--n-perm", type=int, default=2000)
    args = parser.parse_args()

    files_for: Callable[[str], list[Path]] = subfrontal_files
    if args.stage == "extract-mp":
        started = time.time()
        ms.extract_mp(args.per_identity, files_for=files_for, store=SUB_STORE)
        print(f"MediaPipe (подфронт): {time.time() - started:.0f}s", flush=True)
    elif args.stage == "extract-ldm":
        k, n = (int(v) for v in args.shard.split("/"))
        ms.extract_ldm(args.per_identity, shard=(k, n), files_for=files_for, store=SUB_STORE)
    else:
        return compare(args.n_perm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
