#!/usr/bin/env python
"""Проверка УСТОЙЧИВОСТИ метрик-гипотез по условиям съёмки (не сокращаем список).

Идея: на отдельных кадрах метрики падают по-разному (поза, размытие, выражение).
Для каждой метрики смотрим CV-LDA accuracy не только на всём анфасе, но и по
стратам — жёсткий/лёгкий ракурс, резко/мыло, нейтрально/выражение. Отдельно
тестируем expression-нормализованную геометрию (вычесть jaw/smile) и ансамбль
(alpha_id + нормализованные метрики) против базы из 17 метрик.

Фаза A: реконструкция всех кадров |yaw|<=32 -> pts106+alpha_id в hyp_cache (общий
       кэш) и скаляры (yaw, grp, blur, expression_qc) в rob_cache/scalars.jsonl.
Фаза B: стратифицированная валидация + ансамбль.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
DATA = Path("/Volumes/SDCARD/test_photos")
HYP = ROOT / ".runtime" / "hyp_cache"
ROB = ROOT / ".runtime" / "rob_cache"
SCALARS = ROB / "scalars.jsonl"
OUT = ROOT / ".runtime" / "robustness_check.json"
IDENTITIES = ("put", "vas", "udmurt")
CSVS = {n: ROOT / f"{n}_angles.csv" for n in IDENTITIES}
MAX_YAW = 32.0

import importlib.util  # noqa: E402  (после констант, чтобы не тянуть recon на import)
_spec = importlib.util.spec_from_file_location("hc", HERE / "hypotheses_check.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)


def eligible(ident: str) -> list[tuple[Path, dict]]:
    rows: list[tuple[Path, dict]] = []
    with CSVS[ident].open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get("filename") or "").strip()
            if not name or (rec.get("status") or "").strip() != "ok":
                continue
            try:
                yaw = float(rec.get("yaw_deg"))
            except (TypeError, ValueError):
                continue
            if abs(yaw) > MAX_YAW:
                continue
            path = DATA / ident / name
            if path.is_file():
                rows.append((path, {"yaw": yaw, "grp": "frontal" if abs(yaw) <= 15 else "light"}))
    return rows


def blur_var(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return float("nan")
    s = 512.0 / max(img.shape)
    if s < 1:
        img = cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)))
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def phase_a() -> None:
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh

    ROB.mkdir(parents=True, exist_ok=True)
    HYP.mkdir(parents=True, exist_ok=True)
    have_scalar = set()
    if SCALARS.exists():
        for line in SCALARS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                have_scalar.add(json.loads(line)["key"])
    fh = SCALARS.open("a", encoding="utf-8")
    started = time.time()
    new = skip = fail = 0
    for ident in IDENTITIES:
        for path, meta in eligible(ident):
            key = f"{ident}/{path.name}"
            if key in have_scalar:
                skip += 1
                continue
            npy = HYP / (key.replace("/", "__") + ".npy")
            try:
                rec = reconstruct_image(path, device="cpu")
                _, pts, _ = align_identity_mesh(rec)
                alpha = np.asarray(rec["alpha_id"], dtype=np.float32)
                if not npy.exists():
                    np.save(npy, np.concatenate([pts.reshape(-1), alpha]).astype(np.float32))
                eqc = rec.get("expression_qc", {}) or {}
                row = {
                    "key": key, "yaw": meta["yaw"], "grp": meta["grp"],
                    "blur": blur_var(path),
                    "jaw_open_ratio": eqc.get("jaw_open_ratio"),
                    "corner_lift": eqc.get("corner_lift_ioc"),
                    "smile_bs": eqc.get("smile_blendshape"),
                    "jaw_bs": eqc.get("jaw_blendshape"),
                    "expr_mag": eqc.get("expression_magnitude"),
                    "is_smiling": eqc.get("is_smiling"),
                    "is_open": eqc.get("is_mouth_open"),
                }
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"FAIL {key}: {type(exc).__name__} {exc}", flush=True)
                continue
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            new += 1
            if (new + fail) % 25 == 0:
                print(f"A new={new} fail={fail} {time.time() - started:.0f}s", flush=True)
    fh.close()
    print(f"фаза A: новых={new} пропуск={skip} сбой={fail}", flush=True)


def load_all() -> dict[str, dict[str, np.ndarray]]:
    pts: dict[str, list] = {i: [] for i in IDENTITIES}
    alpha: dict[str, list] = {i: [] for i in IDENTITIES}
    meta: dict[str, list] = {i: [] for i in IDENTITIES}
    for line in SCALARS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ident = row["key"].split("/")[0]
        npy = HYP / (row["key"].replace("/", "__") + ".npy")
        if ident not in pts or not npy.exists():
            continue
        arr = np.load(npy)
        pts[ident].append(arr[:318].reshape(106, 3))
        alpha[ident].append(arr[318:])
        meta[ident].append(row)
    return {i: {"pts": np.array(pts[i], np.float32), "alpha": np.array(alpha[i], np.float32),
                "meta": meta[i]} for i in IDENTITIES if pts[i]}


def metric_columns(store) -> tuple[dict, dict]:
    """univariate-колонки и метаданные (yaw/blur/expr/label) по всем кадрам."""
    cols: dict[str, list] = {}
    meta = {k: [] for k in ("yaw", "grp", "blur", "expr_mag", "smile_bs", "jaw_bs",
                            "jaw_open_ratio", "corner_lift", "is_smiling", "is_open", "label")}
    ids = ["put", "vas", "udmurt"]
    for li, ident in enumerate(ids):
        if ident not in store:
            continue
        for j, p in enumerate(store[ident]["pts"]):
            u = hc.univariate(p)
            for name, val in u.items():
                cols.setdefault(name, []).append(val)
            m = store[ident]["meta"][j]
            for k, kk in [("yaw", "yaw"), ("grp", "grp"), ("blur", "blur"), ("expr_mag", "expr_mag"),
                          ("smile_bs", "smile_bs"), ("jaw_bs", "jaw_bs"), ("jaw_open_ratio", "jaw_open_ratio"),
                          ("corner_lift", "corner_lift"), ("is_smiling", "is_smiling"), ("is_open", "is_open")]:
                meta[k].append(m.get(kk))
            meta["label"].append(li)
    return cols, meta


def lda_acc(X: np.ndarray, y: np.ndarray) -> float:
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    if X.ndim == 1:
        X = X[:, None]
    if X.shape[0] < 30 or len(set(y.tolist())) < 3 or min(np.bincount(y, minlength=3)[np.bincount(y, minlength=3) > 0]) < 5:
        return float("nan")
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    try:
        return float(cross_val_score(LinearDiscriminantAnalysis(), Xs, y,
                                     cv=StratifiedKFold(5, shuffle=True, random_state=0),
                                     scoring="accuracy").mean())
    except Exception:  # noqa: BLE001
        return float("nan")


def normalize_expr(values: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Вычесть линейный вклад выражения (cov столбцы) из метрики — residual."""
    good = np.isfinite(values) & np.isfinite(cov).all(1)
    if good.sum() < 30:
        return values
    A = np.column_stack([np.ones(good.sum()), cov[good]])
    beta, *_ = np.linalg.lstsq(A, values[good], rcond=None)
    full = np.column_stack([np.ones(len(values)), np.nan_to_num(cov)])
    pred = full @ beta
    out = values - pred
    return out


def strat_masks(meta) -> dict[str, np.ndarray]:
    yaw = np.array([0 if v is None else v for v in meta["yaw"]], float)
    blur = np.array([np.nan if v is None else v for v in meta["blur"]], float)
    emag = np.array([np.nan if v is None else v for v in meta["expr_mag"]], float)
    label = np.array(meta["label"])
    bmed = np.nanmedian(blur)
    emed = np.nanmedian(emag)
    sharp = blur >= bmed
    off = np.abs(yaw) > 15
    expressive = emag >= emed  # data-driven: верхняя половина силы мимики
    return {
        "full": np.ones(len(label), bool),
        "strict": np.abs(yaw) <= 7,
        "light": (np.abs(yaw) > 7) & (np.abs(yaw) <= 15),
        "off": off,
        "sharp": sharp,
        "blurry": ~sharp,
        "neutral": ~expressive,
        "expressive": expressive,
        "hard": off | ~sharp,  # составной провал: ушёл в ракурс ИЛИ мыло
    }


def phase_b() -> None:
    store = load_all()
    cols, meta = metric_columns(store)
    label = np.array(meta["label"])
    masks = strat_masks(meta)
    n_by_stratum = {k: int(v.sum()) for k, v in masks.items()}
    print("размеры страт:", n_by_stratum, flush=True)

    cov = np.column_stack([
        np.nan_to_num([v if v is not None else 0 for v in meta["smile_bs"]], nan=0.0).astype(float),
        np.nan_to_num([v if v is not None else 0 for v in meta["jaw_bs"]], nan=0.0).astype(float),
        np.nan_to_num([v if v is not None else 0 for v in meta["jaw_open_ratio"]], nan=0.0).astype(float),
        np.nan_to_num([v if v is not None else 0 for v in meta["corner_lift"]], nan=0.0).astype(float),
    ])

    strata = ["full", "strict", "light", "off", "sharp", "blurry", "neutral", "expressive", "hard"]
    rows = []
    for name, vals in cols.items():
        v = np.array(vals, float)
        vn = normalize_expr(v, cov)
        raw = {s: lda_acc(v[masks[s]], label[masks[s]]) for s in strata}
        nor = {s: lda_acc(vn[masks[s]], label[masks[s]]) for s in strata}
        finite = [x for x in raw.values() if x == x]
        drop = (max(finite) - min(finite)) if finite else float("nan")
        rows.append({"metric": name, "raw": {s: (round(raw[s], 3) if raw[s] == raw[s] else None) for s in strata},
                     "expr_norm": {s: (round(nor[s], 3) if nor[s] == nor[s] else None) for s in strata},
                     "fragility": round(drop, 3) if drop == drop else None})
    rows.sort(key=lambda r: (-(r["raw"]["full"] or 0)))

    # --- ансамбли vs база ---
    ids = ["put", "vas", "udmurt"]
    Xalpha = np.vstack([store[i]["alpha"] for i in ids if i in store])
    alab = np.concatenate([np.full(store[i]["alpha"].shape[0], k) for k, i in enumerate(ids) if i in store])
    from morphing.backend import identity as I
    X17 = np.vstack([np.array([I.form_vector(p) for p in store[i]["pts"]]) for i in ids if i in store])
    Xnorm = np.column_stack([normalize_expr(np.array(cols[nm], float), cov) for nm in cols])
    ens1 = np.hstack([Xalpha, Xnorm])
    ens17a = np.hstack([X17, Xalpha])  # практический ансамбль: база17 + кодбук
    combo_acc = {}
    for s in strata:
        combo_acc[s] = {
            "baseline17": _round(lda_acc(X17[masks[s]], alab[masks[s]])),
            "alpha_only": _round(lda_acc(Xalpha[masks[s]], alab[masks[s]])),
            "alpha+exprnorm": _round(lda_acc(ens1[masks[s]], alab[masks[s]])),
            "17+alpha": _round(lda_acc(ens17a[masks[s]], alab[masks[s]])),
        }

    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "n_by_stratum": n_by_stratum, "strata": strata,
              "combos": combo_acc, "metrics": rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Ансамбль vs база по стратам (CV-LDA acc) ===")
    print(f"{'stratum':11s} {'n':>4s} {'base17':>7s} {'alpha':>7s} {'a+norm':>7s} {'17+alpha':>9s}")
    for s in strata:
        c = combo_acc[s]
        print(f"{s:11s} {n_by_stratum[s]:>4d} {str(c['baseline17']):>7s} {str(c['alpha_only']):>7s} "
              f"{str(c['alpha+exprnorm']):>7s} {str(c['17+alpha']):>9s}")
    print("\n=== Топ метрик: raw full/expressive/off + хрупкость ===")
    for r in rows[:20]:
        rr = r["raw"]; nn = r["expr_norm"]
        print(f"  {r['metric']:20s} full={rr['full']} expr={rr['expressive']} off={rr['off']} "
              f"| normed full={nn['full']} expr={nn['expressive']} | frag={r['fragility']}")
    print(f"\nОтчёт: {OUT}")


def _round(x):
    return round(x, 3) if x == x else None


if __name__ == "__main__":
    phase_a()
    phase_b()
