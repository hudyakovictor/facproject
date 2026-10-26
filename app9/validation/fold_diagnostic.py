#!/usr/bin/env python
"""Диагностика yaw-only baseline: почему accuracy НИЖЕ шанса (0.02–0.05 при 1/7).

Проверяем три hypotheses советника и свои:
 H1 GroupKFold не стратифицирован по классам -> в части фолдов класс тестового кадра
    отсутствует в train -> LDA обязан ошибаться (структурные нули).
 H2 LDA priors = частоты классов в train-фолде; при 3 блоках на персону фолды
    дисбалансны -> систематическое смещение к «широким» классам.
 H3 Поза действительно кодирует персону (у каждого свой протокол углов) -> тогда
    честная оценка pose = nearest-centroid по ЗАВЕДОМО Известным классам, без LDA.
Сравниваем GroupKFold vs StratifiedGroupKFold и считаём accuracy отдельно на
подвыборке «класс виден в train» и «класс не виден».
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("hb", HERE / "honest_baseline.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

rows = hb.load()
y = np.array([r["person"] for r in rows])
g = np.array([f"{r['person']}#{int(r['frame_index']) // 60}" for r in rows])
P = np.array([hb.pose_design(r) for r in rows], float)
X17 = np.array([r["v17"] for r in rows], float)
people = sorted(set(y))
print(f"n={len(y)} классов={len(people)} групп={len(set(g))}")
print("блоков на персону:", {p: len(set(g[y == p])) for p in people})
print("кадров на персону:", {p: int((y == p).sum()) for p in people})


def prototype_acc(M, y, groups, folds):
    """nearest-centroid по z-норме, обученной на train: всегда может предсказать любой
    ИЗВЕСТНЫЙ класс — сравниваем с LDA, чтобы отделить эффект «невиданный класс»."""
    ok = np.full(len(y), np.nan)
    seen = np.zeros(len(y), bool)
    for tr, te in folds:
        mu, sd = M[tr].mean(0), M[tr].std(0) + 1e-9
        protos = np.stack([np.median(((M[tr] - mu) / sd)[y[tr] == c], 0) for c in people if (y[tr] == c).any()])
        labels = [c for c in people if (y[tr] == c).any()]
        Z = (M[te] - mu) / sd
        D = np.linalg.norm(Z[:, None, :] - protos[None, :, :], axis=2)
        pred = np.array([labels[i] for i in D.argmin(1)])
        ok[te] = (pred == y[te]).astype(float)
        seen[te] = np.isin(y[te], labels)
    return round(float(np.nanmean(ok)), 3), round(float(np.mean(~seen)), 3)


def lda_report(folds, tag):
    print(f"\n--- {tag} ---")
    unseen_total = 0
    n_tot = 0
    for i, (tr, te) in enumerate(folds):
        trc = np.unique(y[tr])
        unseen = int(np.sum(~np.isin(y[te], np.asarray(trc))))
        unseen_total += unseen
        n_tot += len(te)
        pri = np.bincount(np.unique(y[tr], return_inverse=True)[1], minlength=len(trc)) / len(tr)
        print(f" fold{i}: train n={len(tr)} классов={len(trc)} | test n={len(te)} "
              f"невиданных классов в тесте={unseen} ({unseen/len(te):.2f}) | priors min/max={pri.min():.3f}/{pri.max():.3f}")
    accs = {}
    for nm, M in [("yaw_only", P), ("v17", X17)]:
        res = hb.eval_cv(M, y, g, folds)
        seenmask = np.isfinite(res["ok"])
        # разбивка по «класс был виден в train»
        accs[nm] = {"acc": round(res["acc"], 3), "covered": int(seenmask.sum())}
    print(" LDA:", json.dumps(accs, ensure_ascii=False))
    print(f" доля тестовых кадров с невиданным классом: {unseen_total}/{n_tot} = {unseen_total/n_tot:.3f}")
    return accs


gk = list(GroupKFold(n_splits=5).split(np.zeros((len(y), 1)), groups=g))
sgk = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0).split(np.zeros((len(y), 2)), y, groups=g))
lda_report(gk, "GroupKFold(5) — как было")
lda_report(sgk, "StratifiedGroupKFold(5) — исправление")

print("\n--- pose как идентификация (nearest centroid, классы всегда известны) ---")
for tag, folds in [("GroupKFold", gk), ("StratifiedGroupKFold", sgk)]:
    a, unf = prototype_acc(P, y, g, folds)
    print(f" {tag:22s} pose-прототип acc={a} (шанс 0.143), невиданных={unf:.3f}")
    a17, _ = prototype_acc(X17, y, g, folds)
    print(f" {tag:22s} v17-прототип  acc={a17}")

print("\n--- прямой тест «поза кодирует персону» без CV-артефактов ---")
# оставляем по одному блоку на персону (train), остальные блоки = test
tr_idx, te_idx = [], []
for p in people:
    gp = sorted(set(g[y == p]))
    if len(gp) < 2:
        continue
    tr_idx += [i for i in np.where((y == p) & (g == gp[0]))[0]]
    te_idx += [i for i in np.where((y == p) & (g != gp[0]))[0]]
tr_idx, te_idx = np.array(tr_idx), np.array(te_idx)
for nm, M in [("pose", P), ("v17", X17)]:
    mu, sd = M[tr_idx].mean(0), M[tr_idx].std(0) + 1e-9
    protos = np.stack([np.median(((M[tr_idx] - mu) / sd)[y[tr_idx] == p], 0) for p in people])
    Z = (M[te_idx] - mu) / sd
    D = np.linalg.norm(Z[:, None, :] - protos[None, :, :], axis=2)
    pred = np.array(people)[D.argmin(1)]
    true = y[te_idx]
    print(f" {nm:6s} acc={float((pred == true).mean()):.3f} по персонам: " +
          " ".join(f"{p.split('_')[1]}={float((pred[true == p] == p).mean()):.2f}" for p in people if (true == p).any()))
