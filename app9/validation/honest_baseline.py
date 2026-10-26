#!/usr/bin/env python
"""Честная база идентификации по ФОРМЕ с контролированием позы (по методу советника).

Данные: /Volumes/SDCARD/calibration (7 персон, 792 готовых записи, реконструкция не нужна).
Что делаем, как он просил:
  1) балансировка по бинам: в каждой (person,bin) берём одинаковое число кадров (min cap);
  2) grouped CV по ВРЕМЕННЫМ БЛОКАМ (кадры одного видео автокоррелированы, rho 0.8-0.99);
  3) репорт: yaw-only, form-only, form+yaw — интересен только прирост над yaw-only;
  4) резидуализация metric ~ pose с pooled within-class slope: коэффициенты только из train,
     на тесте применяем только по yaw/|yaw|/yaw^2/pitch/roll (класс на тесте неизвестен);
  5) cluster bootstrap по группам для интервалов (n_eff ~70, а не 781).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
ROWS_P = ROOT / ".runtime" / "calib_cache" / "features.jsonl"
OUT = ROOT / ".runtime" / "honest_baseline.json"
BINS = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
        "left_deep", "right_deep", "left_profile", "right_profile")

spec = importlib.util.spec_from_file_location("hc", HERE / "hypotheses_check.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def load():
    rows = []
    for line in ROWS_P.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "fail" not in r and r.get("bin") in BINS:
                rows.append(r)
    return rows


def balanced(rows, cap=None):
    """Одинаковое число кадров на (person,bin) — убирает дисбаланс бинов/персон."""
    per = {}
    for r in rows:
        per.setdefault((r["person"], r["bin"]), []).append(r)
    keep = []
    caps = {}
    for key, v in per.items():
        c = min(len(v), cap) if cap else min(len(v), cap_of(per, key))
        caps[key] = c
    if cap is None:
        # общий cap = min по бинам между персонами (чтобы сравнение было честным)
        for b in BINS:
            sizes = [len(per[(p, b)]) for p in {k[0] for k in per} if (p, b) in per]
            if not sizes:
                continue
            c = max(3, min(sizes))
            for p in {k[0] for k in per}:
                if (p, b) in per:
                    caps[(p, b)] = min(c, len(per[(p, b)]))
    rng = np.random.default_rng(0)
    for (p, b), v in per.items():
        idx = rng.choice(len(v), size=caps[(p, b)], replace=False) if len(v) > caps[(p, b)] else np.arange(len(v))
        keep.extend(v[i] for i in idx)
    return keep


def cap_of(per, key):
    return len(per[key])


def pose_design(r):
    yaw, pitch, roll = r["yaw"], r["pitch"], r["roll"]
    return [yaw, abs(yaw), yaw ** 2, pitch, roll]


def lda(X, y, cv=None, shrink="auto"):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    X = np.asarray(X, float)
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return None, None
    if cv is None:
        cv = StratifiedKFold(n_splits=min(5, int(np.bincount(np.unique(y, return_inverse=True)[1]).min())))
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage=shrink)
    try:
        sc = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
    except Exception:  # noqa: BLE001
        return None, None
    return float(sc.mean()), sc


def grouped_folds(groups, n=5):
    from sklearn.model_selection import GroupKFold
    return list(GroupKFold(n_splits=n).split(np.zeros((len(groups), 1)), groups=groups))


def eval_cv(X, y, groups, folds, shrink="auto"):
    """Out-of-fold предсказания по кадрам (группы = временные блоки). Возвращает вектор
    1/0 правильности и массив групп -> дальше bootstrap идёт ПО КЛАСТЕРАМ, не по кадрам."""
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    X = np.asarray(X, float)
    y = np.asarray(y)
    pred = np.full(len(y), "", dtype=object)
    for tr, te in folds:
        if len(np.unique(y[tr])) < 2:
            continue
        try:
            clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage=shrink).fit(X[tr], y[tr])
            pred[te] = np.asarray(clf.predict(X[te]), dtype=object)
        except Exception:  # noqa: BLE001, S112 - вырожденный train-множество в фолде, молча пропускаем фолд
            continue
    ok_list = []
    for p, t in zip(pred, y, strict=False):
        if p == "":
            ok_list.append(np.nan)      # фолд не покрыт (недостаточно классов в train)
        elif p == t:
            ok_list.append(1.0)         # верно
        else:
            ok_list.append(0.0)         # неверно — обязательно 0, иначе accuracy завысится
    ok = np.array(ok_list, float)
    covered = np.isfinite(ok)
    if covered.sum() == 0:
        return None
    return {"acc": float(np.nanmean(ok)), "ok": ok, "cover": covered, "groups": np.asarray(groups)}


def boot_acc(res, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    ok, g = res["ok"], res["groups"]
    keep = np.isfinite(ok)
    ok, g = ok[keep], g[keep]
    uniq = np.unique(g)
    if len(uniq) < 3:
        return [round(res["acc"], 3), round(res["acc"], 3)]
    idx = {u: np.where(g == u)[0] for u in uniq}
    draws = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        w = np.concatenate([idx[p] for p in pick])
        draws.append(float(ok[w].mean()))
    return [round(float(np.percentile(draws, q)), 3) for q in (2.5, 97.5)]


def boot_delta(res_a, res_b, n=1000, seed=0):
    """Прирост accuracy A над B с bootstrap по кластерам (общие folds, покрытие по пересечению)."""
    rng = np.random.default_rng(seed)
    mask = np.isfinite(res_a["ok"]) & np.isfinite(res_b["ok"])
    a, b, g = res_a["ok"][mask], res_b["ok"][mask], res_a["groups"][mask]
    d = a - b
    uniq = np.unique(g)
    if len(uniq) < 3:
        return {"delta": round(float(d.mean()), 3), "ci95": [None, None]}
    idx = {u: np.where(g == u)[0] for u in uniq}
    draws = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        w = np.concatenate([idx[p] for p in pick])
        draws.append(float(d[w].mean()))
    return {"delta": round(float(d.mean()), 3),
            "ci95": [round(float(np.percentile(draws, 2.5)), 3), round(float(np.percentile(draws, 97.5)), 3)]}


def residualize(blocks, rows, folds):
    """Pooled within-class slope: метрика ~ pose + дummies класса (обучение на train-fold),
    на тесте вычитаем ТОЛЬКО позную часть (класс неизвестен)."""
    P = np.array([pose_design(r) for r in rows], float)
    classes = sorted({r["person"] for r in rows})
    D = np.array([[1.0 if r["person"] == c else 0.0 for c in classes] for r in rows], float)
    out = {}
    for name, X in blocks.items():
        X = np.asarray(X, float)
        R = X.copy()
        for tr, te in folds:
            A = np.hstack([np.ones((len(tr), 1)), P[tr], D[tr]])
            beta, *_ = np.linalg.lstsq(A, X[tr], rcond=None)
            pose_part = np.hstack([np.ones((len(te), 1)), P[te], np.zeros((len(te), len(classes)))])
            R[te] = X[te] - pose_part @ beta
        out[name + "_resid"] = R
    return out


def cluster_boot(score_per_fold, groups_per_fold, n=400, seed=0):
    """Bootstrap по группам (не по кадрам): n_eff учтён структурой."""
    rng = np.random.default_rng(seed)
    s = np.array(score_per_fold, float)
    g = np.array(groups_per_fold)
    uniq = np.unique(g)
    if len(uniq) < 3:
        return None
    draws = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        w = np.concatenate([np.where(g == p)[0] for p in pick])
        draws.append(float(s[w].mean()))
    return [round(float(np.percentile(draws, q)), 3) for q in (2.5, 50, 97.5)]


def main():
    rows = load()
    people = sorted({r["person"] for r in rows})
    univ_keys = sorted(rows[0]["univ"].keys())
    print(f"записей {len(rows)}, персон {len(people)}")

    report = {}
    for mode, cap in [("as_is", None), ("balanced_by_bin", 8)]:
        data = rows if mode == "as_is" else balanced(rows, cap)
        yy = np.array([r["person"] for r in data])
        gg = np.array([f"{r['person']}#{int(r['frame_index']) // 60}" for r in data])
        folds = grouped_folds(gg, 5)
        blocks = {"v17": [r["v17"] for r in data], "v17sym": [r["v17sym"] for r in data],
                  "canon": [r["canon"] for r in data], "canonsym": [r["canonsym"] for r in data],
                  "univ": [[r["univ"][k] for k in univ_keys] for r in data],
                  "alpha_id": [r["alpha_id"] for r in data]}
        blocks["yaw_only"] = [pose_design(r) for r in data]
        blocks["v17+yaw"] = (np.hstack([np.array(blocks["v17"], float),
                                        np.array(blocks["yaw_only"], float)])).tolist()
        blocks.update(residualize({k: v for k, v in blocks.items() if k not in ("yaw_only", "v17+yaw")},
                                  data, folds))
        results = {}
        for nm, X in blocks.items():
            res = eval_cv(X, yy, gg, folds)
            if res:
                results[nm] = {"acc": round(res["acc"], 3), "ci95": boot_acc(res),
                               "n_covered": int(np.isfinite(res["ok"]).sum()), "res": res}
        base = results.get("yaw_only", {}).get("res")
        for nm in list(results):
            if nm != "yaw_only" and base is not None:
                results[nm]["increment_over_yaw_only"] = boot_delta(results[nm]["res"], base)
        n_groups = int(len(np.unique(gg)))
        report[mode] = {"n": len(data), "n_groups": n_groups, "chance": round(1.0 / len(np.unique(yy)), 3),
                        "metrics": {nm: {k: v for k, v in d.items() if k != "res"} for nm, d in results.items()}}
        print(f"\n=== {mode}: n={len(data)} групп(блоков)={n_groups} шанс={1/len(np.unique(yy)):.3f} ===")
        for nm in ["yaw_only", "v17", "v17sym", "canon", "canonsym", "univ", "alpha_id", "v17+yaw",
                   "v17_resid", "v17sym_resid", "canon_resid", "canonsym_resid", "univ_resid", "alpha_id_resid"]:
            if nm not in results:
                continue
            d = results[nm]
            txt = f"  {nm:18s} acc={d['acc']:.3f} покрыто={d['n_covered']}"
            if d["ci95"][0] is not None:
                txt += f" CI[{d['ci95'][0]:.3f},{d['ci95'][1]:.3f}]"
            inc = d.get("increment_over_yaw_only")
            if inc and inc["ci95"][0] is not None:
                txt += f"  Δ={inc['delta']:+.3f} [{inc['ci95'][0]:+.3f},{inc['ci95'][1]:+.3f}]"
            print(txt)

    # --- per-bin: внутри бина персона == видеосессия, поэтому grouped-CV там невозможен
    #     (holdout группы = holdout человека, LDA не предсказывает невиданные классы).
    #     Делаем явную ВЕРХНЮЮ границy: StratifiedKFold по кадрам (утечка сессии есть,
    #     отмечаем это), и bootstrap по временным блокам для интервала.
    data = balanced(rows, 8)
    perbin = {}
    for b in BINS:
        sub = [r for r in data if r["bin"] == b]
        yy = np.array([r["person"] for r in sub])
        gg = np.array([f"{r['person']}#{int(r['frame_index']) // 60}" for r in sub])
        ncls = len(np.unique(yy))
        if ncls < 3 or min(np.bincount(np.unique(yy, return_inverse=True)[1])) < 4:
            perbin[b] = {"skipped": f"классов={ncls}, мин.кадров на класс мало"}
            continue
        from sklearn.model_selection import StratifiedKFold
        folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=0).split(np.zeros((len(sub), 1)), yy))
        blk = {"v17": [r["v17"] for r in sub], "v17sym": [r["v17sym"] for r in sub],
               "canon": [r["canon"] for r in sub], "canonsym": [r["canonsym"] for r in sub],
               "univ": [[r["univ"][k] for k in univ_keys] for r in sub],
               "alpha_id": [r["alpha_id"] for r in sub],
               "yaw_only": [pose_design(r) for r in sub]}
        ev = {nm: r for nm, r in ((nm, eval_cv(X, yy, gg, folds)) for nm, X in blk.items()) if r}
        if "yaw_only" not in ev:
            perbin[b] = {"skipped": "eval_cv вернул None"}
            continue
        perbin[b] = {"n": len(sub), "chance": round(1.0 / ncls, 3), "note": "upper bound, сессии не изолированы",
                     "metrics": {nm: {"acc": round(r["acc"], 3), "ci95": boot_acc(r),
                                      "delta": boot_delta(r, ev["yaw_only"])} for nm, r in ev.items()}}

    report["per_bin_upper_bound"] = perbin
    print("\n=== оценка ВНУТРИ бина, верхняя граница (kadры не сгруппированы по сессиям) ===")
    cols = ["yaw_only", "v17", "v17sym", "canon", "canonsym", "univ", "alpha_id"]
    print(f"{'bin':14s}{'n':>5s}{'chance':>8s}" + "".join(f"{c[:9]:>10s}" for c in cols))
    for b in BINS:
        d = perbin.get(b, {})
        if "metrics" not in d:
            print(f"{b:14s}  пропуск: {d.get('skipped', '')}")
            continue
        line = f"{b:14s}{d['n']:>5d}{d['chance']:>8.3f}"
        for c in cols:
            m = d["metrics"].get(c)
            line += f"{m['acc']:>10.3f}" if m else f"{'-':>10s}"
        print(line)

    # --- перенос идентичности с анфаса на другие бины (прототипы = медиана персоны) ---
    def get_block(nm, rs):
        if nm == "univ":
            return np.array([[r["univ"][k] for k in univ_keys] for r in rs], float)
        return np.array([r[nm] for r in rs], float)

    fr = [r for r in rows if r["bin"] == "frontal"]
    fy = np.array([r["person"] for r in fr])
    people = sorted({r["person"] for r in rows})
    transfer = {}
    for nm in ["v17", "v17sym", "canon", "canonsym", "univ", "alpha_id"]:
        Xf = get_block(nm, fr)
        mu, sd = Xf.mean(axis=0), Xf.std(axis=0) + 1e-9
        Zf = (Xf - mu) / sd                      # z-нормировка по анфасу, иначе одна метрика доминирует
        proto = {p: np.median(Zf[fy == p], axis=0) for p in people}
        for b in BINS[1:]:
            sub = [r for r in rows if r["bin"] == b]
            if len(sub) < 5:
                continue
            Zb = (get_block(nm, sub) - mu) / sd
            D = np.stack([np.linalg.norm(Zb - proto[p], axis=1) for p in people], axis=1)
            pred = np.array(people)[D.argmin(axis=1)]
            transfer.setdefault(b, {"n": len(sub), "chance": round(1.0 / len(people), 3)})[nm] = \
                round(float((pred == np.array([r["person"] for r in sub])).mean()), 3)
    report["transfer_from_frontal"] = transfer
    print("\n=== перенос: прототипы с анфаса -> другие бины (nearest centroid, z-норма, 7 персон) ===")
    tcols = ["v17", "v17sym", "canon", "canonsym", "univ", "alpha_id"]
    print(f"{'bin':14s}{'n':>5s}{'chance':>8s}" + "".join(f"{c[:9]:>10s}" for c in tcols))
    for b in BINS[1:]:
        d = transfer.get(b)
        if not d:
            continue
        print(f"{b:14s}{d['n']:>5d}{d['chance']:>8.3f}" + "".join(f"{d.get(c, float('nan')):>10.3f}" for c in tcols))

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    main()
