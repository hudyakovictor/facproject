#!/usr/bin/env python
"""Валидация гипотез новых метрик формы put/vas/udmurt на фронтальных фото.

Фаза A: боевым конвейером (reconstruct_image -> align_identity_mesh) снимает с каждого
фронтального кадра канонические 106 точек + alpha_id (3DMM-кодбук) и кэширует в npz/jsonl
(повторный запуск пропускает реконструкцию).
Фаза B: по кэшу считает дескрипторы гипотез и оценивает каждую
5-fold CV LDA accuracy (макро) + eta2. Балл = accuracy*100, база — текущие 17 метрик.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
DATA = Path("/Volumes/SDCARD/test_photos")
CACHE_DIR = ROOT / ".runtime" / "hyp_cache"
CACHE_INDEX = CACHE_DIR / "index.jsonl"
OUT = ROOT / ".runtime" / "hypotheses_check.json"
IDENTITIES = ("put", "vas", "udmurt")
CSVS = {n: ROOT / f"{n}_angles.csv" for n in IDENTITIES}

# Анатомия ldm106 (зафиксирована эмпирически: +y вверх, z вперёд).
C = dict(chin=16, chinL=14, chinR=18, gonL=8, gonR=24, jawL=6, jawR=26,
         zygL=3, zygR=29, templeL=0, templeR=32, nasion=51, bridge=52,
         nose_mid=53, tip=54, nose_base=60, alarL=58, alarR=62,
         mcL=84, mcR=90, ulip=87, dlip=93, lip_up_c=86, lip_dn_c=92)
BROW_L = [34, 35, 36, 37, 38, 39, 40]
BROW_R = [42, 43, 44, 45, 47, 48, 49, 50]
EYE_L = [67, 74, 104, 66, 68, 69]
EYE_R = [76, 78, 81, 83, 105, 79, 77]
MOUTH_RING = [84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95]
CONTOUR = list(range(0, 33))


def frontal_files(ident: str) -> list[Path]:
    keep: list[Path] = []
    with CSVS[ident].open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = (rec.get("filename") or "").strip()
            if not name or (rec.get("status") or "").strip() != "ok":
                continue
            if (rec.get("pose_bin") or "").strip() != "frontal":
                continue
            try:
                if abs(float(rec.get("yaw_deg"))) > 15:
                    continue
            except (TypeError, ValueError):
                continue
            path = DATA / ident / name
            if path.is_file():
                keep.append(path)
    return keep


def phase_a_recon() -> None:
    from app8.reconstruction import reconstruct_image
    from morphing.backend.aligner import align_identity_mesh

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    done = {}
    if CACHE_INDEX.exists():
        for line in CACHE_INDEX.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["key"]] = True
    out_fh = CACHE_INDEX.open("a", encoding="utf-8")
    started = time.time()
    n_new = n_skip = n_fail = 0
    for ident in IDENTITIES:
        for path in frontal_files(ident):
            key = f"{ident}/{path.name}"
            if key in done:
                n_skip += 1
                continue
            try:
                rec = reconstruct_image(path, device="cpu")
                _, pts, _ = align_identity_mesh(rec)
                alpha = np.asarray(rec["alpha_id"], dtype=np.float32)
            except Exception as exc:  # noqa: BLE001
                n_fail += 1
                print(f"FAIL {key}: {type(exc).__name__} {exc}", flush=True)
                continue
            arr = np.concatenate([pts.reshape(-1), alpha]).astype(np.float32)  # 106*3 + 80 = 398
            np.save(CACHE_DIR / (key.replace("/", "__") + ".npy"), arr)
            out_fh.write(json.dumps({"key": key}) + "\n")
            out_fh.flush()
            n_new += 1
            if (n_new + n_fail) % 25 == 0:
                print(f"recon new={n_new} fail={n_fail} {time.time() - started:.0f}s", flush=True)
    out_fh.close()
    print(f"фаза A: новых={n_new} пропущено(кэш)={n_skip} сбой={n_fail}", flush=True)


# ---------- helpers ----------
def _P(pts):
    return pts  # (106,3)

def _d(p, i, j):
    return float(np.linalg.norm(p[i] - p[j]))

def _dd(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))

def _cen(p, idxs):
    return p[np.array(idxs)].mean(0)

def _ang(a, b, c):  # угол при b
    u = a - b
    v = c - b
    den = max(np.linalg.norm(u) * np.linalg.norm(v), 1e-9)
    return float(np.degrees(np.arccos(np.clip(u @ v / den, -1, 1))))

def _scale(p):
    return _d(p, C["zygL"], C["zygR"])  # бизигаматическая как референс масштаба


def univariate(p: np.ndarray) -> dict[str, float]:
    """Одномерные дескрипторы гипотез из канонических 106 точек."""
    chin = p[C["chin"]]; nose_base = _cen(p, [C["nose_base"], C["alarL"], C["alarR"]])
    eyeL = _cen(p, EYE_L); eyeR = _cen(p, EYE_R)
    browL = _cen(p, BROW_L); browR = _cen(p, BROW_R)
    eye_mid = (eyeL + eyeR) / 2
    ul = _cen(p, [C["lip_up_c"], C["ulip"]]); dl = _cen(p, [C["lip_dn_c"], C["dlip"]])
    mcL = p[C["mcL"]]; mcR = p[C["mcR"]]
    zyg_w = _d(p, C["zygL"], C["zygR"])
    gon_w = _d(p, C["gonL"], C["gonR"])
    temple_w = _d(p, C["templeL"], C["templeR"])
    face_len = float(np.ptp(p[CONTOUR][:, 1]))  # размах y по контуру = высота лица
    width_ref = zyg_w + 1e-9
    out = {}
    # A1 гониальный угол (3D)
    out["A1_gonial_angle"] = np.mean([_ang(p[C["zygL"]], p[C["gonL"]], chin),
                                      _ang(p[C["zygR"]], p[C["gonR"]], chin)])
    # A6 нижняя вертикаль: (nose_base→chin)/(eye→chin)
    out["A6_lower_thirds"] = _dd(nose_base, chin) / (_dd(eye_mid, chin) + 1e-9)
    # A8 выпуклость подбородка (z) относительно губ
    out["A8_chin_projection"] = chin[2] - (ul[2] + dl[2]) / 2
    # A9 canthal tilt: наклон оси глаза L/R
    def tilt(e_out, e_in):
        v = p[e_out] - p[e_in]
        return float(np.degrees(np.arctan2(v[1], abs(v[0]) + 1e-9)))
    out["A9_canthal_tilt"] = np.mean([abs(tilt(67, 104)), abs(tilt(78, 105))])
    # A10 ширина лба/скул (виски/скулы)
    out["A10_forehead_flare"] = temple_w / width_ref
    # A11 alar flare: ширина основания к длине (tip->base)
    out["A11_alar_flare"] = _d(p, C["alarL"], C["alarR"]) / (_dd(p[C["tip"]], nose_base) + 1e-9)
    # A12 бровь-глаз (вертикаль) нормированная
    out["A12_brow_eye"] = (abs(browL[1] - eyeL[1]) + abs(browR[1] - eyeR[1])) / 2 / width_ref
    # A13 фильтрум / нижняя треть
    out["A13_philtrum"] = _dd(nose_base, ul) / (_dd(nose_base, chin) + 1e-9)
    # A15 nasolabial: угол нос-основание -> верхняя губа -> chin
    out["A15_nasolabial"] = _ang(nose_base, ul, chin)
    # A5 площадь красной каймы губ (полигон)
    ring = p[MOUTH_RING]
    poly = ring[:, :2] - ring[:, :2].mean(0)
    sh = poly[:, 0]; sv = np.roll(poly[:, 1], 1)
    out["A5_lip_area"] = abs(0.5 * np.sum(sh * sv - np.roll(sh, -1) * poly[:, 1])) / width_ref ** 2
    # B5 надбровный валик: z бровей минус z глаз
    out["B5_brow_ridge"] = (browL[2] + browR[2]) / 2 - (eyeL[2] + eyeR[2]) / 2
    # B6 ориентация ветви челюсти: отклонение gonion->chin от вертикали
    out["B6_ramus_orient"] = np.mean([
        float(np.degrees(np.arctan2(p[C["gonL"]][1] - chin[1], p[C["gonL"]][0] - chin[0]))),
        float(np.degrees(np.arctan2(p[C["gonR"]][1] - chin[1], p[C["gonR"]][0] - chin[0]))),
    ])
    # B7 вертикальность лица: скулы / высота лица
    out["B7_verticality"] = zyg_w / (face_len + 1e-9)
    # B8 bigonial-bizygomatic flare
    out["B8_jaw_flare"] = gon_w / width_ref
    # B11 межглазничная / межзрачковая (внутренние уголки к центрам)
    out["B11_interorbital"] = _d(p, 104, 105) / (_dd(eyeL, eyeR) + 1e-9)
    # B12 сужение спинки носа: ширина на bridge vs alar
    out["B12_dorsum_taper"] = _d(p, 55, 65) / (_d(p, C["alarL"], C["alarR"]) + 1e-9)
    # B13 вертикаль подбородка: lower-lip->chin / face_len
    out["B13_chin_length"] = _dd(dl, chin) / (face_len + 1e-9)
    # B14 sub-stomion / menton
    out["B14_lower_proportion"] = _dd(nose_base, ul) / (_dd(dl, chin) + 1e-9)
    # B15 bifrontal / eye span
    out["B15_bifrontal"] = temple_w / (_dd(eyeL, eyeR) + 1e-9)
    # B17 retraction уголков рта к линии ala->chin
    def retract(mc, ala):
        a = p[ala]; b = chin; m = mc
        ab = b - a; ab = ab / (np.linalg.norm(ab) + 1e-9)
        return float(np.linalg.norm((m - a) - np.dot(m - a, ab) * ab))
    out["B17_mouth_retraction"] = (retract(mcL, C["alarL"]) + retract(mcR, C["alarR"])) / 2 / width_ref
    # B20 malar vertical height: y скуловой дуги относительно линии глаз
    out["B20_malar_height"] = ((eyeL[1] + eyeR[1]) / 2 - (p[C["zygL"]][1] + p[C["zygR"]][1]) / 2) / width_ref
    # A2/B: центральная глубина (переносье vs орбиты) — уже сильный аналог
    out["central_depth_ref"] = p[C["bridge"]][2] - (eyeL[2] + eyeR[2]) / 2
    return out


def procrustes(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Возвращает Y, выровненный на X (центр+масштаб+поворот, Kabsch)."""
    mx, my = X.mean(0), Y.mean(0)
    Xc, Yc = X - mx, Y - my
    sx, sy = np.sqrt((Xc ** 2).sum()), np.sqrt((Yc ** 2).sum())
    Xc, Yc = Xc / sx, Yc / sy
    U, S, Vt = np.linalg.svd(Yc.T @ Xc)
    dsign = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, dsign])
    R = (Vt.T @ D @ U.T)
    return (Yc @ R) * sx + mx


def fourier_contour(p: np.ndarray) -> np.ndarray:
    """Нормированные Fourier-амплитуды замкнутого контура лица (idx 0..32)."""
    c = p[CONTOUR][:, :2]
    c = c - c.mean(0)
    r = np.hypot(c[:, 0], c[:, 1])
    r = r / (r.mean() + 1e-9)
    fft = np.abs(np.fft.rfft(r))[:10]
    return (fft[1:] / (fft[0] + 1e-9))[:8]  # амплитуды 2..9 гармоник


def mirror_rms(p: np.ndarray) -> float:
    from scipy.spatial import cKDTree
    q = p.copy()
    q[:, 0] *= -1.0  # зеркало по x
    tree = cKDTree(p[:, :2])
    dd, _ = tree.query(q[:, :2], k=1)
    return float(np.sqrt((dd ** 2).mean()))


def cv_lda_acc(X: np.ndarray, y: np.ndarray) -> float:
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    if X.shape[0] != len(y) or X.shape[0] < 30:
        return float("nan")
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    clf = LinearDiscriminantAnalysis()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    try:
        sc = cross_val_score(clf, Xs, y, cv=cv, scoring="accuracy")
        return float(sc.mean())
    except Exception:  # noqa: BLE001
        return float("nan")


def eta2(groups: list[np.ndarray]) -> float:
    allv = np.concatenate(groups)
    if len(allv) < 3:
        return float("nan")
    grand = allv.mean()
    ss_b = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    ss_t = ((allv - grand) ** 2).sum()
    return float(ss_b / ss_t) if ss_t > 1e-12 else 0.0


def phase_b_analyze() -> None:
    store: dict[str, dict[str, np.ndarray]] = {i: {"pts": [], "alpha": []} for i in IDENTITIES}
    for line in CACHE_INDEX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key = json.loads(line)["key"]
        ident = key.split("/")[0]
        if ident not in store or not (CACHE_DIR / (key.replace("/", "__") + ".npy")).exists():
            continue
        arr = np.load(CACHE_DIR / (key.replace("/", "__") + ".npy"))
        store[ident]["pts"].append(arr[:318].reshape(106, 3))
        store[ident]["alpha"].append(arr[318:])
    for i in IDENTITIES:
        store[i]["pts"] = np.array(store[i]["pts"], dtype=np.float32)
        store[i]["alpha"] = np.array(store[i]["alpha"], dtype=np.float32)
        print(f"{i}: {store[i]['pts'].shape[0]} фронтальных")

    y = np.concatenate([np.full(store[i]["pts"].shape[0], idx) for idx, i in enumerate(IDENTITIES)])

    # --- одномерные гипотезы ---
    uni_names = list(univariate(store["put"]["pts"][0]).keys())
    feats = {i: [univariate(p) for p in store[i]["pts"]] for i in IDENTITIES}
    uni_rows = []
    for name in uni_names:
        groups = [np.array([f[name] for f in feats[i]]) for i in IDENTITIES]
        X = np.concatenate(groups)[:, None]
        acc = cv_lda_acc(X, y)
        uni_rows.append({"hypo": name, "kind": "uni", "cv_lda_acc": round(acc, 3),
                         "score100": round(acc * 100, 1), "eta2": round(eta2(groups), 4),
                         "medians": {i: round(float(np.median(g)), 4) for i, g in zip(IDENTITIES, groups, strict=False)}})

    # --- многомерные гипотезы ---
    multi = []
    # B1 alpha_id кодбук
    Xal = np.vstack([store[i]["alpha"] for i in IDENTITIES])
    a = cv_lda_acc(Xal, y)
    multi.append({"hypo": "B1_alpha_id_codebook(80d)", "kind": "multi", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})
    # B2 полный Procrustes-shape (XY 2D координаты после выравнивания)
    allpts = np.vstack([store[i]["pts"] for i in IDENTITIES])
    ref = allpts[0]
    aligned = np.stack([procrustes(ref, p) for p in allpts])
    shape = aligned.reshape(len(aligned), -1)  # 3D после Procrustes
    a = cv_lda_acc(shape, y)
    multi.append({"hypo": "B2_procrustes_106(3d)", "kind": "multi", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})
    # B3 TPS-суммари: смещение каждой точки от ГЛОБАЛЬНОЙ средней формы (без утечки метки)
    resid = (aligned - allpts.mean(0)).reshape(len(aligned), -1)
    a = cv_lda_acc(resid, y)
    multi.append({"hypo": "B3_shape_vs_global_mean", "kind": "multi", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})
    # B19 конфигурация eye-eye-nose-nosebase (Procrustes-подмножество)
    sub = np.array([70, 80, C["tip"], C["nose_base"]])
    tri = np.stack([procrustes(ref, p)[sub] for p in allpts]).reshape(len(allpts), -1)
    a = cv_lda_acc(tri, y)
    multi.append({"hypo": "B19_eye_eye_nose_procrustes", "kind": "multi", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})
    # B4 Fourier-контур
    Xf = np.stack([fourier_contour(p) for p in allpts])
    a = cv_lda_acc(Xf, y)
    multi.append({"hypo": "B4_fourier_contour(8harm)", "kind": "multi", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})
    # A14 dense mirror RMS (скаляр, но асимметрия)
    Xm = np.array([[mirror_rms(p)] for p in allpts])
    a = cv_lda_acc(Xm, y)
    multi.append({"hypo": "A14_dense_mirror_rms", "kind": "uni", "cv_lda_acc": round(a, 3), "score100": round(a * 100, 1)})

    # --- база: текущие 17 метрик ---
    from morphing.backend import identity as I
    X17 = np.vstack([np.array([I.form_vector(p) for p in store[i]["pts"]]) for i in IDENTITIES])
    a17 = cv_lda_acc(X17, y)
    baseline = {"hypo": "BASELINE_17_metrics", "cv_lda_acc": round(a17, 3), "score100": round(a17 * 100, 1),
                "n": [int(store[i]["pts"].shape[0]) for i in IDENTITIES]}

    all_rows = sorted(uni_rows + multi, key=lambda r: r["cv_lda_acc"], reverse=True)
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "baseline": baseline,
              "n_per_identity": {i: int(store[i]["pts"].shape[0]) for i in IDENTITIES},
              "results": all_rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== Валидация гипотез (5-fold CV LDA accuracy, база={baseline['cv_lda_acc']}) ===")
    for r in all_rows:
        print(f"  score={r['score100']:5.1f} acc={r['cv_lda_acc']:.3f} {r['kind']:6s} {r['hypo']}")
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    phase_a_recon()
    phase_b_analyze()
