"""Приёмка раунда 6. Запуск:
    python3 tools/acceptance_round6.py --frames <путь к calibration_frames>
Печатает PASS/FAIL по каждому пункту и итог. Код возврата 0 только при полном PASS.
"""
from __future__ import annotations
import argparse, ast, itertools, json, pathlib, sys, collections
import numpy as np

ROOTDIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOTDIR))

from app6.stage2.analysis_policy import pose_gap
from app6.stage2.expression_pair_gate import expression_gate, JAW_DEGREE_GAP_ENFORCED
from app6.stage2 import landmark_policy as lp
from app6.stage2.anchor_policy import per_bin_anchor_mask
from app6.stage2.pose_policy import BIN_NAME_TO_YAW

RESULTS: list[tuple[str, bool, str]] = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))

# ---------- F1: ни одного вызова pose_gap без pose_bin ----------
bare = []
for path in sorted((ROOTDIR / "app6" / "stage2").rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "pose_gap":
            if not any(k.arg == "pose_bin" for k in node.keywords):
                bare.append(f"{path.name}:{node.lineno}")
check("F1 нет вызовов pose_gap без pose_bin", not bare, ", ".join(bare) or "ok")

# ---------- F2: limited и разведение полей ----------
g_ok = pose_gap([0, 60.0, 0], [0, 61.5, 0], pose_bin="right_profile")
g_mm = pose_gap([0, 60.0, 0], [0, 70.5, 0], pose_bin="right_profile")
g_lp = pose_gap([0, -60.0, 0], [0, -61.0, 0], pose_bin="left_profile")
check("F2 right_profile limited=True", g_ok.limited is True, f"limited={g_ok.limited}")
check("F2 pose_bin канонический", g_ok.pose_bin == "right_profile", g_ok.pose_bin)
check("F2 sub_bin заполнен", getattr(g_ok, "sub_bin", "") == "right_profile_60_70",
      getattr(g_ok, "sub_bin", "<нет поля>"))
check("F2 mismatch сохраняет канонический бин", g_mm.pose_bin == "right_profile"
      and g_mm.reason == "profile_sub_bin_mismatch", f"{g_mm.pose_bin}/{g_mm.reason}")
check("F2 left_profile не limited", g_lp.limited is False and g_lp.accepted is True,
      f"limited={g_lp.limited} accepted={g_lp.accepted}")

# ---------- F3: normalized_weights fail-closed ----------
u = np.random.RandomState(0).rand(9, 134) + 0.1
u[4, :] = np.nan
w_nan = lp.normalized_weights(u, 4)
w_good = lp.normalized_weights(u, 0)
check("F3 all-NaN бин -> равномерные веса", np.allclose(w_nan, 1.0), f"min={w_nan.min():.4f} max={w_nan.max():.4f}")
check("F3 нормальный бин не тронут", not np.allclose(w_good, 1.0), "ok")

# ---------- регресс F1-предыдущего раунда: fallback_cross_bin ----------
sel = lp.subset_for_bin(u, 4, count=91, visibility=np.ones(134), min_count=30)
check("R1 subset_for_bin -> fallback_cross_bin",
      sel["status"] == "fallback_cross_bin" and sel["sufficient"] is False, sel["status"])
pts = np.random.RandomState(1).rand(134, 3).astype(np.float32)
mask, meta = per_bin_anchor_mask(pts, np.ones(134, bool), pose_bin="frontal", utility=u,
                                 visibility_prior=np.ones((9, 134)), min_count=24,
                                 bin_names=list(BIN_NAME_TO_YAW))
check("R1 откат даёт рабочие якоря",
      meta.get("anchor_source") == "fallback_cross_bin" and int(mask.sum()) >= 24,
      f"source={meta.get('anchor_source')} anchors={int(mask.sum())}")

# ---------- F4/F5: гейт мимики ----------
A = {"jaw_open_detected": True, "jaw_open_degree": 16.0, "smile_detected": False}
B = {"jaw_open_detected": False, "jaw_open_degree": 1.0, "smile_detected": False}
C = {"jaw_open_detected": False, "jaw_open_degree": 5.4, "smile_detected": False}
D = {"jaw_open_detected": False, "jaw_open_degree": 53.2, "smile_detected": False}
same = expression_gate(A, B, era_a="2002", era_b="2002")
cross = expression_gate(A, B, era_a="2001", era_b="2006")
degr = expression_gate(C, D, era_a="2005", era_b="2005")
check("F4 одна эпоха -> исключение",
      same["accepted"] is False and same["reason"] == "jaw_state_mismatch", str(same.get("reason")))
check("F4 разные эпохи -> страта",
      cross["accepted"] is True and cross.get("stratum") == "jaw_state_mismatch_cross_era"
      and cross.get("confidence") == "limited", str(cross.get("stratum")))
check("F5 порог по градусам приостановлен",
      JAW_DEGREE_GAP_ENFORCED is False and degr["accepted"] is True
      and degr.get("jaw_degree_gap_exceeded") is True, str(degr.get("accepted")))

# ---------- эмпирика на 212 кадрах ----------
ap = argparse.ArgumentParser()
ap.add_argument("--frames", required=True)
frames = pathlib.Path(ap.parse_args().frames)
rows = []
for d in sorted(frames.iterdir()):
    ij = d / "info.json"
    if not ij.exists():
        continue
    i = json.loads(ij.read_text(encoding="utf-8"))
    p, c = i.get("pose") or {}, i.get("chronology") or {}
    rows.append(dict(bin=p.get("pose_bin"), a=np.array([p["pitch"], p["yaw"], p["roll"]], float),
                     date=str(i.get("date")), jaw=bool(c.get("jaw_open_detected")),
                     deg=float(c.get("jaw_open_degree") or 0.0),
                     smile=bool(c.get("smile_detected"))))
check("данные: 212 кадров", len(rows) == 212, f"{len(rows)}")

EXPECT_BINS = {"frontal": 276, "left_deep": 30, "left_light": 24, "left_mid": 8,
               "left_profile": 159, "right_deep": 5, "right_mid": 2, "right_profile": 234}
acc = [(x, y) for x, y in itertools.combinations(rows, 2)
       if x["bin"] == y["bin"] and pose_gap(x["a"], y["a"], pose_bin=x["bin"]).accepted]
by_bin = dict(collections.Counter(x["bin"] for x, _ in acc))
check("E1 гейт принимает 738 пар", len(acc) == 738, f"{len(acc)} (было 1349 без pose_bin)")
check("E2 распределение по бинам", by_bin == EXPECT_BINS, json.dumps(by_bin, sort_keys=True))

cls = collections.Counter()
for x, y in acc:
    r = expression_gate({"jaw_open_detected": x["jaw"], "jaw_open_degree": x["deg"],
                         "smile_detected": x["smile"]},
                        {"jaw_open_detected": y["jaw"], "jaw_open_degree": y["deg"],
                         "smile_detected": y["smile"]},
                        era_a=x["date"][:4], era_b=y["date"][:4])
    if not r["accepted"]:
        cls["excluded"] += 1
    elif r.get("stratum") == "jaw_state_mismatch_cross_era":
        cls["stratum"] += 1
    elif r.get("jaw_degree_gap_exceeded"):
        cls["degree_kept"] += 1
    else:
        cls["clean"] += 1
check("E3 исключено по челюсти внутри эпохи = 50", cls["excluded"] == 50, str(cls["excluded"]))
check("E4 кросс-эпохальная страта = 14", cls["stratum"] == 14, str(cls["stratum"]))
check("E5 сохранено по приостановленному порогу = 34", cls["degree_kept"] == 34, str(cls["degree_kept"]))
check("E6 чистых пар = 640", cls["clean"] == 640, str(cls["clean"]))
check("E7 пригодно к анализу = 688", cls["clean"] + cls["degree_kept"] + cls["stratum"] == 688,
      str(cls["clean"] + cls["degree_kept"] + cls["stratum"]))

cross_total = sum(1 for x, y in acc if x["date"][:4] != y["date"][:4])
cross_kept = 0
for x, y in acc:
    if x["date"][:4] == y["date"][:4]:
        continue
    r = expression_gate({"jaw_open_detected": x["jaw"], "jaw_open_degree": x["deg"],
                         "smile_detected": x["smile"]},
                        {"jaw_open_detected": y["jaw"], "jaw_open_degree": y["deg"],
                         "smile_detected": y["smile"]},
                        era_a=x["date"][:4], era_b=y["date"][:4])
    cross_kept += int(r["accepted"])
check("E8 временная ось цела: 20/20 кросс-годовых",
      cross_total == 20 and cross_kept == 20, f"{cross_kept}/{cross_total} (было 5/20)")

# ---------- итог ----------
width = max(len(n) for n, _, _ in RESULTS)
for name, ok, detail in RESULTS:
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}}  {detail}")
failed = [n for n, ok, _ in RESULTS if not ok]
print()
print(f"ACCEPTANCE: {'PASS' if not failed else 'FAIL'}  ({len(RESULTS) - len(failed)}/{len(RESULTS)})")
sys.exit(0 if not failed else 1)
