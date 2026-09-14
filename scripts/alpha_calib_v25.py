"""Alpha-анализ 943 калибровочных кадров по протоколу A–G (v2.5).

Без нового inference: V_id/V_obj восстанавливаются из alpha_id/alpha_exp
через BFM-базисы assets/face_model.npy.
Выход — только в alpha_calib_v25/ (рядом со скриптом, НЕ в старый storage).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.model_selection import KFold, LeaveOneGroupOut
from sklearn.preprocessing import SplineTransformer

WORK = Path("/Users/victorkhudyakov/work")
CALIB = Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets")
OUT = WORK / "alpha_calib_v25"
OUT.mkdir(exist_ok=True)

# 106-схема 3DDFA_V3 (0-based внутри массива 106): см. app6/stage1/engine.py
EYE_L, EYE_R = 74, 77
L_CORNER, R_CORNER = 84, 90
UP_LIP, LOW_LIP = 87, 93


def load_bfm():
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    u = np.asarray(m["u"], np.float64).reshape(-1)
    bid = np.asarray(m["id"], np.float64)
    bexp = np.asarray(m["exp"], np.float64)
    assert u.shape[0] == bid.shape[0] == bexp.shape[0] == 35709 * 3, (u.shape, bid.shape, bexp.shape)
    return u, bid, bexp


def shape_flat(BID, BEXP, u, aid, aexp):
    return (u + BID @ aid + BEXP @ aexp).reshape(35709, 3)


def r2(y, yhat):
    ss = float(np.sum((y - y.mean()) ** 2))
    return float(1 - np.sum((y - yhat) ** 2) / ss) if ss > 0 else float("nan")


def ols(X, y):
    """OLS через lstsq/pinv (устойчив к вырожденным дамми в CV-фолдах) + SE/t/p."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(X.shape[0] - np.linalg.matrix_rank(X), 1)
    s2 = float(resid @ resid / dof)
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    t = beta / np.maximum(se, 1e-18)
    p = 2 * stats.t.sf(np.abs(t), dof)
    return beta, se, p, float(np.sqrt(np.mean(resid ** 2))), r2(y, X @ beta)


def main():
    u, BID, BEXP = load_bfm()
    rows = list(csv.DictReader(open(CALIB / "all_calibration_index.csv")))
    print(f"frames: {len(rows)}", flush=True)

    recs = []
    aid_mat, aexp_mat = [], []
    for r in rows:
        z = np.load(CALIB / r["npz_file"], allow_pickle=False)
        aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
        aexp = np.asarray(z["alpha_exp"], np.float64).reshape(-1)
        idx106 = np.asarray(z["ldm106_vertex_indices"], np.int64).reshape(-1)
        idx134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
        V_id = shape_flat(BID, BEXP, u, aid, np.zeros_like(aexp))
        V_obj = shape_flat(BID, BEXP, u, aid, aexp)
        c_id, c_ob = V_id.mean(0), V_obj.mean(0)
        S_id = float(np.sqrt(np.mean(np.sum((V_id - c_id) ** 2, 1))))
        S_ob = float(np.sqrt(np.mean(np.sum((V_obj - c_ob) ** 2, 1))))
        # геометрия рта/улыбки на object (с мимикой) и identity
        L_ob, L_id = V_obj[idx106], V_id[idx106]
        ioc_ob = float(np.linalg.norm(L_ob[EYE_L] - L_ob[EYE_R])) or 1.0
        ioc_id = float(np.linalg.norm(L_id[EYE_L] - L_id[EYE_R])) or 1.0
        mc_ob = (L_ob[UP_LIP][1] + L_ob[LOW_LIP][1]) / 2
        jaw_ob = float(np.linalg.norm(L_ob[UP_LIP] - L_ob[LOW_LIP])) / ioc_ob
        smile_ob = float(((L_ob[L_CORNER][1] + L_ob[R_CORNER][1]) / 2 - mc_ob) / ioc_ob)
        mc_id = (L_id[UP_LIP][1] + L_id[LOW_LIP][1]) / 2
        jaw_id = float(np.linalg.norm(L_id[UP_LIP] - L_id[LOW_LIP])) / ioc_id
        smile_id = float(((L_id[L_CORNER][1] + L_id[R_CORNER][1]) / 2 - mc_id) / ioc_id)
        vis106 = int(np.sum(np.asarray(z["ldm106_visible_original"]).reshape(-1).astype(bool)))
        vis134 = int(np.sum(np.asarray(z["ldm134_visible_original"]).reshape(-1).astype(bool)))
        recs.append(dict(
            dataset_id=r["dataset_id"], record_id=r["record_id"], frame_index=int(r["frame_index"]),
            yaw=float(r["yaw"]), pitch=float(r["pitch"]), roll=float(r["roll"]), pose_bin=r["pose_bin"],
            S_id=S_id, S_obj=S_ob, ratio=S_ob / S_id, delta=S_ob - S_id, rel=S_ob / S_id - 1,
            exp_norm=float(np.linalg.norm(aexp)), aid_norm=float(np.linalg.norm(aid)),
            jaw_ob=jaw_ob, smile_ob=smile_ob, jaw_id=jaw_id, smile_id=smile_id,
            ioc_id=ioc_id, vis106=vis106, vis134=vis134,
        ))
        aid_mat.append(aid)
        aexp_mat.append(aexp)
    df = pd.DataFrame(recs)
    AID = np.stack(aid_mat)
    AEXP = np.stack(aexp_mat)
    df.to_csv(OUT / "table1_scale_decomposition.csv", index=False)

    # ---- E: PCA alpha_exp, PC alpha_id ----
    pca_exp = PCA(n_components=5).fit(AEXP)
    pca_id = PCA(n_components=5).fit(AID)
    EXP_PC = pca_exp.transform(AEXP)
    ID_PC = pca_id.transform(AID)
    for k in range(5):
        df[f"expPC{k+1}"] = EXP_PC[:, k]
        df[f"idPC{k+1}"] = ID_PC[:, k]
    print("expPCA var:", np.round(pca_exp.explained_variance_ratio_, 3), flush=True)
    print("idPCA var:", np.round(pca_id.explained_variance_ratio_, 3), flush=True)

    # ---- дизайн: сплайны позы + person dummies ----
    persons = pd.get_dummies(df["dataset_id"], prefix="ps", drop_first=True).to_numpy(float)
    spl = SplineTransformer(n_knots=4, degree=3, include_bias=False)
    POSE_SPL = spl.fit_transform(df[["yaw", "pitch", "roll"]].to_numpy(float))
    n = len(df)

    def design(extra_cols):
        X = [np.ones((n, 1)), POSE_SPL, persons]
        names = ["const"] + [f"spl{i}" for i in range(POSE_SPL.shape[1])] + list(
            pd.get_dummies(df["dataset_id"], prefix="ps", drop_first=True).columns)
        for c in extra_cols:
            X.append(df[c].to_numpy(float).reshape(-1, 1))
            names.append(c)
        return np.hstack(X), names

    # ---- B: scale_ratio модель ----
    y = df["ratio"].to_numpy(float)
    Xb, nb = design(["exp_norm", "jaw_ob", "smile_ob", "vis106"])
    beta, se, p, rmse, r2f = ols(Xb, y)
    # partial R2 позы: full vs без сплайнов
    Xn, _ = design(["exp_norm", "jaw_ob", "smile_ob", "vis106"])
    keep = [i for i, nm in enumerate(nb) if not nm.startswith("spl")]
    _, _, _, _, r2n = ols(Xn[:, keep], y)
    partial_pose = (r2f - r2n) / max(1 - r2n, 1e-12)
    rows_b = [dict(term=nm, beta=float(b), se=float(s), p=float(pp)) for nm, b, s, pp in zip(nb, beta, se, p)]
    rows_b += [dict(term="MODEL", beta=float(r2f), se=float(rmse), p=float("nan")),
               dict(term="partialR2_pose_splines", beta=float(partial_pose), se=float("nan"), p=float("nan"))]
    pd.DataFrame(rows_b).to_csv(OUT / "table3_expression_effect_ratio.csv", index=False)
    # отдельные эффекты на S_id / S_obj
    for target in ("S_id", "S_obj"):
        yt = df[target].to_numpy(float)
        b2, s2, p2, _, r2t = ols(Xb, yt)
        pd.DataFrame([dict(term=nm, beta=float(b_), se=float(s_), p=float(p_))
                      for nm, b_, s_, p_ in zip(nb, b2, s2, p2)]).to_csv(
            OUT / f"table3_effect_on_{target}.csv", index=False)
    print(f"B: ratio R2={r2f:.3f} partialR2_pose={partial_pose:.3f}", flush=True)

    # ---- C: pose leakage в alpha_id ----
    # outcomes: idPC1-5, S_id, ioc_id, Procrustes residual V_id(134) vs person mean
    idx_cache, V134 = {}, []
    for r in rows:
        z = np.load(CALIB / r["npz_file"], allow_pickle=False)
        i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
        aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
        aexp = np.asarray(z["alpha_exp"], np.float64).reshape(-1)
        V134.append(shape_flat(BID, BEXP, u, aid, np.zeros_like(aexp))[i134])  # identity, без expression
    V134 = np.stack(V134)
    person = df["dataset_id"].to_numpy()
    procr = np.zeros(n)
    for ps in np.unique(person):
        m = person == ps
        mu = V134[m].mean(0)
        muc = mu - mu.mean(0)
        for i in np.flatnonzero(m):
            x = V134[i] - V134[i].mean(0)
            U, _, Vt = np.linalg.svd(x.T @ muc)
            R = U @ Vt
            if np.linalg.det(R) < 0:
                Vt[-1] *= -1
                R = U @ Vt
            procr[i] = float(np.sqrt(np.mean(np.sum((x @ R - muc) ** 2, 1))))
    df["procr_id134"] = procr

    groups = pd.factorize(df["dataset_id"])[0]
    logo = LeaveOneGroupOut()
    kf = KFold(n_splits=5, shuffle=True, random_state=0)
    leak_rows = []
    for outcome in ["idPC1", "idPC2", "idPC3", "idPC4", "idPC5", "S_id", "ioc_id", "procr_id134"]:
        y = df[outcome].to_numpy(float)
        Xf, nf = design(["exp_norm", "jaw_ob", "smile_ob", "vis106"])
        _, _, _, _, r2f = ols(Xf, y)
        keep = [i for i, nm in enumerate(nf) if not nm.startswith("spl")]
        _, _, _, _, r2n = ols(Xf[:, keep], y)
        partial = (r2f - r2n) / max(1 - r2n, 1e-12)
        # CV: инкремент R2 сплайнов out-of-sample, leave-person-out + 5fold
        def cv_gain(cv):
            gs = []
            for tr, te in cv.split(Xf, y, groups) if isinstance(cv, LeaveOneGroupOut) else cv.split(Xf):
                bf, *_ = ols(Xf[tr], y[tr])
                bn, *_ = ols(Xf[tr][:, keep], y[tr])
                gs.append(r2(y[te], Xf[te] @ bf) - r2(y[te], Xf[te][:, keep] @ bn))
            return float(np.mean(gs))
        leak_rows.append(dict(outcome=outcome, R2_full=round(r2f, 4), R2_noPose=round(r2n, 4),
                              partialR2_pose=round(partial, 4),
                              cv_gain_logo=round(cv_gain(logo), 4), cv_gain_kfold=round(cv_gain(kf), 4)))
    pd.DataFrame(leak_rows).to_csv(OUT / "table2_pose_leakage.csv", index=False)
    print(pd.DataFrame(leak_rows).to_string(), flush=True)

    # ---- C2: leakage, обобщающаяся на новых людей ----
    # Убираем уровень identity (person-mean), предсказываем остаток по позе.
    # Дизайн без person-dummies; LOGO = настоящий тест генерализации.
    Xp = np.hstack([np.ones((n, 1)), POSE_SPL,
                    df[["exp_norm", "jaw_ob", "smile_ob", "vis106"]].to_numpy(float)])
    keep_np = list(range(1 + POSE_SPL.shape[1], Xp.shape[1]))  # без сплайнов
    gen_rows = []
    for outcome in ["idPC1", "idPC2", "idPC3", "idPC4", "idPC5", "S_id", "ioc_id", "procr_id134"]:
        y = df[outcome].to_numpy(float)
        ydm = y - pd.Series(y).groupby(person).transform("mean").to_numpy()
        if float(np.sum(ydm ** 2)) < 1e-18:
            continue
        def gain(cv, grouped):
            gs = []
            splitter = cv.split(Xp, ydm, groups) if grouped else cv.split(Xp)
            for tr, te in splitter:
                bf, *_ = ols(Xp[tr], ydm[tr])
                bn, *_ = ols(Xp[tr][:, [0] + keep_np], ydm[tr])
                gs.append(r2(ydm[te], Xp[te] @ bf) - r2(ydm[te], Xp[te][:, [0] + keep_np] @ bn))
            return float(np.mean(gs))
        bf, *_ = ols(Xp, ydm)
        bn, *_ = ols(Xp[:, [0] + keep_np], ydm)
        gen_rows.append(dict(outcome=outcome + "_demeaned",
                             R2_full=round(r2(ydm, Xp @ bf), 4),
                             R2_noPose=round(r2(ydm, Xp[:, [0] + keep_np] @ bn), 4),
                             partialR2_pose=round((r2(ydm, Xp @ bf) - r2(ydm, Xp[:, [0] + keep_np] @ bn)) / max(1 - r2(ydm, Xp[:, [0] + keep_np] @ bn), 1e-12), 4),
                             cv_gain_logo=round(gain(logo, True), 4),
                             cv_gain_kfold=round(gain(kf, False), 4)))
    pd.DataFrame(gen_rows).to_csv(OUT / "table2b_pose_leakage_generalizes.csv", index=False)
    print(pd.DataFrame(gen_rows).to_string(), flush=True)

    # ---- D: артефакт знаменателя ----
    # стабильные пары 106: глаза, нос, рот, брови (индексы схемы)
    PAIRS = [(74, 77, "interocular"), (84, 90, "mouth_width"), (87, 93, "mouth_open"),
             (72, 75, "eyeL_width"), (76, 79, "eyeR_width"), (46, 52, "nose_len")]
    Lraw, out_d = [], []
    for r, rec in zip(rows, recs):
        z = np.load(CALIB / r["npz_file"], allow_pickle=False)
        i106 = np.asarray(z["ldm106_vertex_indices"], np.int64).reshape(-1)
        aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
        aexp = np.asarray(z["alpha_exp"], np.float64).reshape(-1)
        V = shape_flat(BID, BEXP, u, aid, np.zeros_like(aexp))[i106]  # identity raw, только 106 точек
        row = dict(record_id=r["record_id"], dataset_id=r["dataset_id"])
        for a, b, nm in PAIRS:
            d = float(np.linalg.norm(V[a] - V[b]))
            row[nm + "_raw"] = d
            row[nm + "_divSid"] = d / rec["S_id"]
            row[nm + "_divSobj"] = d / rec["S_obj"]
        out_d.append(row)
    dd = pd.DataFrame(out_d)
    dd.to_csv(OUT / "table4_metric_sensitivity.csv", index=False)
    # сводка: доля однонаправленных знаков попарных корреляций трендов
    sens = []
    for suf in ("_raw", "_divSid", "_divSobj"):
        cols = [c for c in dd.columns if c.endswith(suf)]
        M = dd[cols].to_numpy(float)
        C = np.corrcoef(M.T)
        iu = C[np.triu_indices(len(cols), 1)]
        sens.append(dict(space=suf, mean_pair_corr=round(float(np.mean(iu)), 3),
                         frac_positive=round(float(np.mean(iu > 0)), 3)))
    pd.DataFrame(sens).to_csv(OUT / "table4_space_summary.csv", index=False)
    print(pd.DataFrame(sens).to_string(), flush=True)

    # ---- env-фиксация ----
    import torch, cv2, PIL
    from PIL import Image  # noqa
    env = dict(
        numpy=np.__version__, torch=torch.__version__, scipy="1.15.3",
        opencv=cv2.__version__, sklearn="1.7.2", pandas=pd.__version__,
        bfm_sha256=hashlib.sha256(open(WORK / "assets" / "face_model.npy", "rb").read()).hexdigest()[:16],
        weights_sha256={w: hashlib.sha256(open(WORK / "assets" / w, "rb").read()).hexdigest()[:16]
                        for w in ("net_recon.pth", "large_base_net.pth")},
    )
    json.dump(env, open(OUT / "env_fixation.json", "w"), indent=2, ensure_ascii=False)
    print("DONE ->", OUT, flush=True)


if __name__ == "__main__":
    sys.exit(main())
