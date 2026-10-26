#!/usr/bin/env python
"""Метрики на подготовленной калибровке /Volumes/SDCARD/calibration (7 персон, 792 записи).

Зачем: это те же видео, что calibration_rakurs (frame_index совпадают на 100% для
person_01..06) + person_07, но точки уже извлечены — реконструкция не нужна. В
record.npz есть ldm106_object (объектные без позы = наш P0) и ldm106_canonical
(доворот к канон-yaw бина = P1), alpha_id/alpha_exp, нормали и флаги видимости.

Фаза A: по всем записям нормализуем центр+масштаб (как align_identity_mesh) и считаем
        блоки признаков: v17, v17sym, canon, canonsym, univ(22), alpha_id(80). Кэш jsonl.
Фаза B: шум/SNR/inflation по 9 бинам на 7 персонах, 7-way CV-LDA с ГРУППИРОВКОЙ ПО
        ВРЕМЕННЫМ БЛОКАМ (кадры одного видео автокоррелированы), перенос идентичности
        с анфаса на другие бины, и проверки советника (чётная протечка ~|yaw|/yaw^2,
        сохранение знака асимметрии между left/right).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
CAL = Path("/Volumes/SDCARD/calibration")
# Каталог кэша с меткой нормировки: rms106 (aligner.normalize_ldm106). Старый кэш собран
# в max-radius единицах, смешивать их нельзя — поэтому он не переиспользуется.
CACHE = ROOT / ".runtime" / "calib_cache_rms106"
ROWS = CACHE / "features.jsonl"
OUT = ROOT / ".runtime" / "calib_report.json"
BINS = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
        "left_deep", "right_deep", "left_profile", "right_profile")
BLOCK_FRAMES = 60  # временной блок для grouped CV (>=2 c исходного видео)

spec = importlib.util.spec_from_file_location("hc", HERE / "hypotheses_check.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
spec2 = importlib.util.spec_from_file_location("rn", HERE / "rakurs_noise.py")
rn = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(rn)
from morphing.backend import identity as I
from morphing.backend.aligner import normalize_ldm106


def norm_center_scale(p: np.ndarray) -> np.ndarray:
    """Та же нормировка, что в проде: aligner.normalize_ldm106 (центр и RMS по 106 точкам)."""
    return normalize_ldm106(np.asarray(p, float))[0]


def phase_a() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    done = set()
    if ROWS.exists():
        for line in ROWS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["person"], r["frame"]))
    fh = ROWS.open("a", encoding="utf-8")
    n_ok = n_skip = n_fail = 0
    for pdir in sorted(CAL.glob("person_*")):
        for rec in sorted(pdir.glob("frame_*")):
            if (pdir.name, rec.name) in done:
                n_skip += 1
                continue
            znp = rec / "record.npz"
            meta = rec / "metadata.json"
            if not znp.exists() or not meta.exists():
                n_fail += 1
                continue
            m = json.loads(meta.read_text(encoding="utf-8"))
            try:
                with np.load(znp, allow_pickle=False) as f:
                    obj = norm_center_scale(np.asarray(f["ldm106_object"], float))
                    can = norm_center_scale(np.asarray(f["ldm106_canonical"], float))
                    vis = np.asarray(f["ldm106_visible_original"], int)
                    a_id = np.asarray(f["alpha_id"], float)
                    a_exp = np.asarray(f["alpha_exp"], float)
                    ang = np.asarray(f["angle_deg_pitch_yaw_roll"], float)
                row = {"person": pdir.name, "frame": rec.name, "bin": m.get("pose_bin"),
                       "frame_index": int(m.get("frame_index", -1)),
                       "yaw": float(m["pose"]["yaw"]), "pitch": float(m["pose"]["pitch"]),
                       "roll": float(m["pose"]["roll"]), "canonical_yaw": float(m.get("canonical_yaw", 0.0)),
                       "n_vis": int(vis.sum()),
                       "v17": [float(x) for x in I.form_vector(obj)],
                       "v17sym": [float(x) for x in I.form_vector(rn.symmetrize(obj))],
                       "canon": [float(x) for x in I.form_vector(can)],
                       "canonsym": [float(x) for x in I.form_vector(rn.symmetrize(can))],
                       "univ": {k: float(v) for k, v in hc.univariate(obj).items()},
                       "alpha_id": [float(x) for x in a_id],
                       "exp_mag": float(np.sqrt((a_exp ** 2).sum())), "ang2": [float(x) for x in ang]}
            except Exception as exc:  # noqa: BLE001
                n_fail += 1
                row = {"person": pdir.name, "frame": rec.name, "fail": type(exc).__name__}
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if "fail" not in row:
                n_ok += 1
    fh.close()
    print(f"фаза A: ok={n_ok} skip={n_skip} fail={n_fail}", flush=True)


def load_rows():
    out = []
    if not ROWS.exists():
        return out
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "fail" not in r:
                out.append(r)
    return out


def lda_acc(X, y, groups, n_splits=5):
    """CV-LDA со шринком, фолды = группы (временные блоки), без утечки кадров одного видео."""
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import GroupKFold
    X = np.asarray(X, float)
    y = np.asarray(y)
    groups = np.asarray(groups)
    uniq = np.unique(y)
    if len(uniq) < 2 or X.shape[0] < 3 * len(uniq):
        return None
    accs = []
    gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
    for tr, te in gkf.split(X, y, groups):
        if len(np.unique(y[tr])) < len(uniq) or len(np.unique(y[te])) == 0:
            continue
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        try:
            clf.fit(X[tr], y[tr])
            accs.append(float(clf.score(X[te], y[te])))
        except Exception:  # noqa: BLE001, S112 - вырожденный train-множество в фолде, молча пропускаем фолд
            continue
    return round(float(np.mean(accs)), 3) if accs else None


def block_of(r):
    return f"{r['person']}#{r['frame_index'] // BLOCK_FRAMES}"


def phase_b():
    rows = load_rows()
    people = sorted({r["person"] for r in rows})
    print(f"фаза B: записей {len(rows)}, персон {len(people)}", flush=True)
    y = np.array([r["person"] for r in rows])
    g = np.array([block_of(r) for r in rows])
    print(f"временных блоков (group): {len(set(g))}", flush=True)

    keys17 = list(I.FEATURE_ORDER)
    univ_keys = sorted(rows[0]["univ"].keys())

    def mat(name):
        if name == "alpha_id":
            return [r["alpha_id"] for r in rows]
        if name == "univ":
            return [[r["univ"][k] for k in univ_keys] for r in rows]
        return [r[name] for r in rows]

    blocks = ["v17", "v17sym", "canon", "canonsym", "univ", "alpha_id"]
    MAT = {b: np.array(mat(b), float) for b in blocks}
    acc_all = {b: lda_acc(MAT[b], y, g) for b in blocks}
    acc_all["v17+alpha"] = lda_acc(np.hstack([MAT["v17"], MAT["alpha_id"]]), y, g)
    acc_all["canonsym+alpha"] = lda_acc(np.hstack([MAT["canonsym"], MAT["alpha_id"]]), y, g)
    print("\n=== 7-way CV-LDA (группировка по временным блокам) ===")
    for k, v in acc_all.items():
        print(f"  {k:16s} {v}")

    # по стратам по |yaw|
    strata = {"strict": lambda r: abs(r["yaw"]) <= 7, "light": lambda r: 7 < abs(r["yaw"]) <= 15,
              "off": lambda r: 15 < abs(r["yaw"]) <= 32, "hard": lambda r: abs(r["yaw"]) > 32,
              "all": lambda r: True}
    strat_tab = {}
    print("\n=== accuracy по стратам |yaw| ===")
    print(f"{'stratum':9s}" + "".join(f"{b[:9]:>11s}" for b in blocks))
    for sn, f in strata.items():
        idx = np.array([i for i, r in enumerate(rows) if f(r)])
        sub_y, sub_g = y[idx], g[idx]
        row = {b: lda_acc(MAT[b][idx], sub_y, sub_g) for b in blocks}
        strat_tab[sn] = {"n": int(len(idx)), **row}
        print(f"{sn:9s}" + "".join(f"{str(row[b]):>11s}" for b in blocks) + f"   n={len(idx)}")

    # шум/SNR по бинам для v17 и v17sym
    def noise_snr(getter):
        per = {}
        for r in rows:
            per.setdefault((r["person"], r["bin"]), []).append(getter(r))
        out = {}
        for b in BINS:
            ppl = [p for p in people if (p, b) in per]
            nz, sg = [], []
            for m in range(len(keys17)):
                w, means = [], []
                for p in ppl:
                    v = np.array([x[m] for x in per[(p, b)]], float)
                    v = v[np.isfinite(v)]
                    if len(v) >= 3:
                        w.append(float(np.std(v, ddof=1)))
                        means.append(float(np.mean(v)))
                nz.append(float(np.median(w)) if w else float("nan"))
                sg.append(float(np.std(means, ddof=1)) if len(means) >= 3 else float("nan"))
            out[b] = {"noise": nz, "signal": sg, "n_people": len(ppl)}
        return out

    ns_p0, ns_sym, ns_can = noise_snr(lambda r: r["v17"]), noise_snr(lambda r: r["v17sym"]), noise_snr(lambda r: r["canon"])

    def median_infl(ns):
        base = ns["frontal"]["noise"]
        return {b: round(float(np.median([ns[b]["noise"][i] / (base[i] + 1e-9) for i in range(len(base))])), 2) for b in BINS} if base else {}

    # проверка советника 1: чётная протечка (|yaw|, yaw^2) остаётся после симметризации
    def even_leak(getter):
        X = np.array([getter(r) for r in rows], float)
        yaw = np.array([r["yaw"] for r in rows], float)
        res = {}
        for m, nm in enumerate(keys17):
            v = X[:, m]
            ok = np.isfinite(v)
            if ok.sum() < 50:
                continue
            A = np.vstack([np.ones(ok.sum()), np.abs(yaw[ok]), yaw[ok] ** 2]).T
            beta, *_ = np.linalg.lstsq(A, v[ok], rcond=None)
            pred = A @ beta
            ss = float(((v[ok] - v[ok].mean()) ** 2).sum())
            res[nm] = round(float(1 - ((v[ok] - pred) ** 2).sum() / ss), 3) if ss > 0 else 0.0
        return res

    leaks = {"p0": even_leak(lambda r: r["v17"]), "p0sym": even_leak(lambda r: r["v17sym"]),
             "canon": even_leak(lambda r: r["canon"])}

    # проверка советника 2: сохранение ЗНАКА signed-асимметричных метрик left vs right
    SIGNED = [k for k in keys17 if "asym" in k or "bend" in k or "offset" in k]
    sign_tab = {}
    for p in people:
        L = [r for r in rows if r["person"] == p and r["bin"] in ("left_light", "left_mid")]
        R = [r for r in rows if r["person"] == p and r["bin"] in ("right_light", "right_mid")]
        if len(L) >= 3 and len(R) >= 3:
            d = {}
            for nm in SIGNED:
                i = keys17.index(nm)
                ml = float(np.median([r["v17"][i] for r in L]))
                mr = float(np.median([r["v17"][i] for r in R]))
                d[nm] = {"left": round(ml, 4), "right": round(mr, 4), "keep_sign": bool(ml * mr < 0),
                         "sym_range": round(float(np.ptp([r["v17sym"][i] for r in L + R])), 4)}
            sign_tab[p] = d

    # перенос идентичности: прототипы только с анфаса -> классификация прочих бинов
    fr = [r for r in rows if r["bin"] == "frontal"]
    tr_Y = np.array([r["person"] for r in fr])
    GET = {"v17": lambda r: r["v17"], "v17sym": lambda r: r["v17sym"],
           "canon": lambda r: r["canon"], "canonsym": lambda r: r["canonsym"]}
    proto = {}
    for name, getter in GET.items():
        Xf = np.array([getter(r) for r in fr], float)
        proto[name] = {p: np.median(Xf[tr_Y == p], axis=0) for p in people}
    transfer = {}
    for b in BINS[1:]:
        sub = [r for r in rows if r["bin"] == b]
        if len(sub) < 5:
            continue
        transfer[b] = {"n": len(sub)}
        true_y = np.array([r["person"] for r in sub])
        for name, getter in GET.items():
            Xb = np.array([getter(r) for r in sub], float)
            D = np.stack([np.linalg.norm(Xb - proto[name][p], axis=1) for p in people], axis=1)
            transfer[b][name] = round(float((np.array(people)[D.argmin(axis=1)] == true_y).mean()), 3)
    print("\n=== перенос: прототипы из frontal -> Accuracy по бинам (nearest centroid) ===")
    print(f"{'bin':14s}" + "".join(f"{b[:9]:>11s}" for b in GET) + "     n")
    for b, v in transfer.items():
        print(f"{b:14s}" + "".join(f"{str(v.get(k)):>11s}" for k in GET) + f"{v['n']:>7d}")

    report = {"n_rows": len(rows), "people": people, "n_groups": int(len(set(g))),
              "acc_grouped_cv": acc_all, "acc_by_stratum": strat_tab,
              "noise_median_infl_p0": median_infl(ns_p0), "noise_median_infl_sym": median_infl(ns_sym),
              "noise_median_infl_canon": median_infl(ns_can),
              "v17_noise_by_bin_p0": {nm: {b: round(ns_p0[b]["noise"][i], 4) for b in BINS if i < len(ns_p0[b]["noise"])} for i, nm in enumerate(keys17)},
              "v17_snr_by_bin": {nm: {b: (round(ns_p0[b]["signal"][i] / ns_p0[b]["noise"][i], 2) if ns_p0[b]["noise"][i] > 1e-9 else None) for b in BINS if i < len(ns_p0[b]["noise"])} for i, nm in enumerate(keys17)},
              "even_leak_R2_on_absyaw_yaw2": leaks, "signed_asym_left_right": sign_tab,
              "transfer_from_frontal": transfer}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== медианный inflation шума к frontal (7 персон) ===")
    print("p0      :", median_infl(ns_p0))
    print("p0+sym  :", median_infl(ns_sym))
    print("canon   :", median_infl(ns_can))
    print("\n=== чётная протечка: R^2 метрики на (|yaw|, yaw^2) ===")
    top = sorted(leaks["p0"].items(), key=lambda kv: -kv[1])[:8]
    print("p0     :", [(k, v) for k, v in top])
    top = sorted(leaks["p0sym"].items(), key=lambda kv: -kv[1])[:8]
    print("p0+sym :", [(k, v) for k, v in top])
    print("\n=== сохранение знака signed-асимметрии left vs right (доля per person) ===")
    for p, d in sign_tab.items():
        ks = [v["keep_sign"] for v in d.values()]
        print(f"  {p}: знак сохранён {sum(ks)}/{len(ks)} -> {d}")
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    phase_a()
    phase_b()
