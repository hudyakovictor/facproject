"""Probe candidate NEW face-form metrics for put/vas/udmurt separation.

Reads cached canonical landmarks (.runtime/identity_lmk/{name}.npy), builds the
existing 17-metric vector (morphing.backend.identity) plus a battery of candidate
metrics for eye-aperture, jaw/chin, facial proportions and nose, then:
  1) prints per-identity medians and a separability score for every candidate;
  2) runs a held-out prototype classifier on '17 only' vs '17 + top-K new'.
"""
import pathlib
import numpy as np
import sys

sys.path.insert(0, "/Users/victorkhudyakov/work")
from morphing.backend import identity as ID

CACHE = pathlib.Path("/Users/victorkhudyakov/work/.runtime/identity_lmk")
NAMES = ("put", "vas", "udmurt")
EPS = 1e-9


def d(q, i, j):
    return float(np.linalg.norm(q[i] - q[j]))


def new_metrics(q):
    """q: (106,3) canonical. Returns dict of candidate metrics (scale-normalized)."""
    f = {}
    # ---- EYE APERTURE (разрез глаз) ----
    le_up, le_lo, le_out, le_in = 68, 72, 66, 70
    re_up, re_lo, re_out, re_in = 77, 81, 79, 75
    le_ctr = q[[66, 67, 68, 69, 70, 71, 72, 73]].mean(0)
    re_ctr = q[[75, 76, 77, 78, 79, 80, 81, 82]].mean(0)
    f["eye_open_L"] = d(q, le_up, le_lo)
    f["eye_open_R"] = d(q, re_up, re_lo)
    f["eye_wid_L"] = d(q, le_out, le_in)
    f["eye_wid_R"] = d(q, re_out, re_in)
    f["eye_aspect_L"] = f["eye_wid_L"] / (f["eye_open_L"] + EPS)
    f["eye_aspect_R"] = f["eye_wid_R"] / (f["eye_open_R"] + EPS)
    f["eye_open_asym"] = abs(f["eye_open_L"] - f["eye_open_R"])
    f["eye_wid_asym"] = abs(f["eye_wid_L"] - f["eye_wid_R"])
    f["eye_separation"] = float(np.linalg.norm(le_ctr - re_ctr))
    f["eye_rel_open"] = (f["eye_open_L"] + f["eye_open_R"]) / (f["eye_wid_L"] + f["eye_wid_R"] + EPS)
    # ---- JAW / CHIN (челюсть/подбородок) ----
    chin = 16
    l_go, r_go = 10, 22        # gonion-ish (углы челюсти)
    f["lower_face_h"] = abs(q[60][1] - q[chin][1])          # нос-основание -> подбородок
    f["bigonial"] = d(q, l_go, r_go)                          # ширина нижней трети
    f["mandible_L"] = d(q, chin, l_go)
    f["mandible_R"] = d(q, chin, r_go)
    f["mandible_asym"] = abs(f["mandible_L"] - f["mandible_R"])
    f["chin_proj"] = float(q[chin][2] - 0.5 * (q[l_go][2] + q[r_go][2]))
    f["jaw_to_mouth"] = f["bigonial"] / (d(q, 84, 90) + EPS)  # челюсть vs ширина рта
    f["lower_upper_ratio"] = f["lower_face_h"] / (abs(q[35][1] - q[60][1]) + EPS)
    # ---- PROPORTIONS (пропорции лица) ----
    brow_top = max(q[35][1], q[44][1])
    f["face_height"] = abs(brow_top - q[chin][1])
    f["bizygomatic"] = d(q, 0, 32)                            # ширина скул/висков
    f["face_wh"] = f["bizygomatic"] / (f["face_height"] + EPS)
    eye_mid = 0.5 * (le_ctr + re_ctr)
    nb = q[[58, 59, 60, 61, 62]].mean(0)
    f["upper_mid_ratio"] = abs(eye_mid[1] - nb[1]) / (f["lower_face_h"] + EPS)
    f["eye_to_chin_frac"] = abs(eye_mid[1] - q[chin][1]) / (f["face_height"] + EPS)
    f["ioc_over_bizyg"] = f["eye_separation"] / (f["bizygomatic"] + EPS)
    # ---- NOSE (нос, расширенно) ----
    f["nose_length"] = d(q, 51, 60)
    f["nose_bridge_up"] = d(q, 55, 65)
    f["nose_bridge_mid"] = d(q, 56, 64)
    f["nose_alar"] = d(q, 57, 63)
    f["nose_len_to_face"] = f["nose_length"] / (f["face_height"] + EPS)
    f["nose_wid_to_face"] = f["nose_alar"] / (f["bizygomatic"] + EPS)
    return f


def build_matrix(data, func):
    """data: dict name-> (n,106,3). Return dict name-> (n,F) and feature order."""
    rows = {}
    order = list(func(data["put"][0]).keys())
    for nm in NAMES:
        rows[nm] = np.array([[func(q)[k] for k in order] for q in data[nm]], np.float32)
    return rows, order


def separability(rows, order):
    """For each feature: robust between/within using medians & MADs across identities."""
    allv = np.concatenate([rows[nm] for nm in NAMES], 0)
    med = np.median(allv, 0)
    mad = 1.4826 * np.median(np.abs(allv - med), 0)
    mad[mad < 1e-8] = allv.std(0) + 1e-8
    scores = []
    for j in range(len(order)):
        ids_med = np.array([np.median(rows[nm][:, j] - med[j]) / mad[j] for nm in NAMES])
        between = ids_med.std()
        within = np.mean([np.median(np.abs(rows[nm][:, j] - np.median(rows[nm][:, j]))) * 1.4826 / mad[j] for nm in NAMES])
        scores.append(between / (within + 1e-6))
    return np.array(scores), med, mad, ids_med


def _acc_on_cols(rows, cols, med, mad):
    """Held-out prototype accuracy using only the given feature columns."""
    pred = {nm: 0 for nm in NAMES}; tot = {nm: 0 for nm in NAMES}; protos = {}
    for nm in NAMES:
        h = len(rows[nm]) // 2
        protos[nm] = np.median(rows[nm][:, cols][:h], 0)
    for nm in NAMES:
        h = len(rows[nm]) // 2
        for x in rows[nm][:, cols][h:]:
            z = (x - med[cols]) / mad[cols]
            dists = {o: np.mean(np.abs(z - (protos[o] - med[cols]) / mad[cols])) for o in NAMES}
            best = min(dists, key=dists.get); tot[nm] += 1; pred[nm] += (best == nm)
    per = {nm: 100.0 * pred[nm] / max(tot[nm], 1) for nm in NAMES}
    return per, 100.0 * sum(pred.values()) / max(sum(tot.values()), 1)


def heldout_acc(rows, order, med, mad, top_new):
    """top_new=None -> all features; [] -> base-17 only; list -> base-17 + those new."""
    base = set(ID.FEATURE_ORDER)
    if top_new is None:
        cols = list(range(len(order)))
    else:
        cols = [i for i, k in enumerate(order) if k in base] + \
               [i for i, k in enumerate(order) if k in set(top_new)]
    return _acc_on_cols(rows, cols, med, mad)


def main():
    data = {nm: np.load(CACHE / f"{nm}.npy") for nm in NAMES if (CACHE / f"{nm}.npy").exists()}
    if len(data) < 3:
        print("missing caches:", [nm for nm in NAMES if nm not in data]); return
    # combined feature function: 17 base + new
    def combined(q):
        m = dict(zip(ID.FEATURE_ORDER, ID.form_vector(q), strict=False))
        m.update(new_metrics(q))
        return m
    rows, order = build_matrix(data, combined)
    print("features:", len(order), "samples:", {nm: len(rows[nm]) for nm in NAMES})
    base_set = set(ID.FEATURE_ORDER)
    # separability only for NEW metrics
    new_idx = [i for i, k in enumerate(order) if k not in base_set]
    scores, med, mad, ids_med = separability(rows, order)
    print("\n=== SEPARABILITY (between/within, higher=more discriminative) ===")
    for i in sorted(new_idx, key=lambda i: -scores[i]):
        print(f"{order[i]:20s} sep={scores[i]:5.2f}  med_by_id="
              + " ".join(f"{nm}:{ids_med[j]:+.2f}" for j, nm in enumerate(NAMES)))
    top_new = [order[i] for i in sorted(new_idx, key=lambda i: -scores[i])][:12]
    print("\ntop-12 new:", top_new)
    print("\n=== HELD-OUT ACCURACY ===")
    per_base, o_base = heldout_acc(rows, order, med, mad, top_new=[])
    per_new, o_new = heldout_acc(rows, order, med, mad, top_new=top_new)
    per_all, o_all = heldout_acc(rows, order, med, mad, top_new=None)
    print(f"17 base only : overall={o_base:5.1f}%  " + " ".join(f"{nm}:{per_base[nm]:.0f}%" for nm in NAMES))
    print(f"17 + top12new: overall={o_new:5.1f}%  " + " ".join(f"{nm}:{per_new[nm]:.0f}%" for nm in NAMES))
    print(f"all features : overall={o_all:5.1f}%  " + " ".join(f"{nm}:{per_all[nm]:.0f}%" for nm in NAMES))


if __name__ == "__main__":
    main()
