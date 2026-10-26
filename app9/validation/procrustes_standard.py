#!/usr/bin/env python
"""Стандартизация ГЕОМЕТРИИ лендмарок к общему стандарту (Generalized Procrustes).

Вопрос: метрики по 106 точкам зависят от остаточного наклона головы? Сравниваем
двеcoordinate-системы для одних и тех же геометрических метрик:
  (A) как сейчас: center+scale (aligner), без ротационной подгонки;
  (B) GP: каждая сетка 106 точек жёстко (rotation+scale+translation, без отражений)
      доведена до общего референса = среднее по жёстко-фронтальным кадрам (|yaw|<=7).
Считаем CV-LDA accuracy по стратам (strict/light/off) и хрупкость. Если (B)
уменьшает разброс по ракурсам — стандартизация Procrustes полезна для геометрии.

Только cached pts106 (recon не нужен).
"""
from __future__ import annotations
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r = _load("robustness_check")   # load_all / strat_masks / metric_columns / lda_acc / cov
from morphing.backend import identity as I

IDS = ("put", "vas", "udmurt")


def procrustes_to(target: np.ndarray, src: np.ndarray) -> np.ndarray:
    """Жёсткая подгонка src (106,3) к target (Kabsch: центр, масштаб, поворот)."""
    a = src - src.mean(0)
    b = target - target.mean(0)
    sa = np.sqrt((a * a).sum() + 1e-12)
    sb = np.sqrt((b * b).sum() + 1e-12)
    a = a / sa
    b = b / sb
    H = a.T @ b
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    Rm = Vt.T @ D @ U.T
    return (Rm @ b.T).T  # src, повёрнутый в кад target, масштаб 1


def main() -> None:
    store = r.load_all()
    cols, meta = r.metric_columns(store)
    label = np.array(meta["label"])
    yaw = np.array([0 if v is None else v for v in meta["yaw"]], float)
    masks = r.strat_masks(meta)

    # склеиваем все pts106 в общем порядке (ids -> store) как в metric_columns
    pts = np.vstack([store[i]["pts"] for i in IDS if i in store])  # (N,106,3)
    assert pts.shape[0] == len(label), (pts.shape, len(label))

    # референс = среднее по жёстко-фронтальным (|yaw|<=7), уже center+scale
    front = pts[np.abs(yaw) <= 7]
    ref = front.mean(0)

    # (A) текущая система: только center+scale (как в кэше)
    # (B) GP: довести каждую точку к ref
    pts_gp = np.stack([procrustes_to(ref, p) for p in pts])  # (N,106,3)

    def form17(arr):
        return np.vstack([np.array([I.form_vector(p) for p in chunk]) for chunk in [arr]])

    XA = np.array([I.form_vector(p) for p in pts])
    XB = np.array([I.form_vector(p) for p in pts_gp])

    strata = ["strict", "light", "off", "full"]
    print("=== 17 геометрических метрик: accuracy по стратам ===")
    print(f"{'stratum':8s} {'n':>4s} {'A center+scale':>15s} {'B Procrustes-GP':>16s} {'Δ':>7s}")
    rows = []
    for s in strata:
        mk = masks[s]
        a = r.lda_acc(XA[mk], label[mk])
        b = r.lda_acc(XB[mk], label[mk])
        da = None if (a != a or b != b) else round(b - a, 3)
        print(f"{s:8s} {int(mk.sum()):>4d} {str(round(a,3) if a==a else None):>15s} "
              f"{str(round(b,3) if b==b else None):>16s} {str(da):>7s}")
        rows.append((s, a, b))

    # хрупкость геометрии по ракурсам: разброс strict->off
    accA = {s: r.lda_acc(XA[masks[s]], label[masks[s]]) for s in strata}
    accB = {s: r.lda_acc(XB[masks[s]], label[masks[s]]) for s in strata}
    finA = [v for v in accA.values() if v == v]
    finB = [v for v in accB.values() if v == v]
    print(f"\nхрупкость (max-min acc по стратам):  A={max(finA) - min(finA):.3f}"
          f"   B={max(finB) - min(finB):.3f}")

    # насколько точки вообще «уехали» после GP — средняя евклидова сдвиг по 106
    shift = np.linalg.norm((pts_gp - pts), axis=2).mean()
    print(f"средний сдвиг точки после GP: {shift:.4f} (в единицах radius=1)")

    # отдельная проверка axis-зависимой метрики A8_chin_projection до/после
    def chin_proj(arr):
        ys = arr[:, 16, 1]  # menton y
        return ys
    off = masks["off"]
    print(f"\nA8-подобная menton-y: std off = A {pts[off][:,16,1].std():.4f} / B {pts_gp[off][:,16,1].std():.4f}")
    print(f"                         std strict = A {pts[np.abs(yaw)<=7][:,16,1].std():.4f} / B {pts_gp[np.abs(yaw)<=7][:,16,1].std():.4f}")


if __name__ == "__main__":
    main()
