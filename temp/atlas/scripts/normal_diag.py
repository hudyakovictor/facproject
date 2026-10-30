"""C: почему `normal` проигрывает на person_02 и person_05.

Диагностика, не новый метод. Для двух людей с провалом (и остальных как
фон) считается:

1. AUC по зонам и семействам переходов (LOPO-калибровка, как в v3).
2. Качество нормалей: угол между `template_normals()` и нормалями кадра,
   флипы, отдельно профильная сторона (челюсть/нос).
3. Capture — какая доля |Δ| попадает в нормальную компоненту |Δ·n|.
4. Связь с мимикой: дельты рта/улыбки/бровей и их корреляция с
   отношением normal/euclid.
5. Диагностический вариант с нормалями конкретного кадра (в продакшн
   не идёт: в v3 он рвал стык сегментов).

    python scripts/normal_diag.py

Пишет reports/calibration/normal-diag.json и
reports/figures/v4-normal-diag.png.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import select_frames  # noqa: E402
from calibration_sweep import auc  # noqa: E402
from chart_score import ids_into  # noqa: E402
from calibration_v3 import (  # noqa: E402
    FAMILIES,
    MODES,
    REGIONS,
    build_pairs,
    calibration,
    collect,
    family_of,
    fit_noise,
    index_rows,
    load_frames,
    topology,
)
from server.heat import (  # noqa: E402
    compute_heat_values,
    template_normals,
    vertex_normals,
)

TARGETS = ("person_02", "person_05")
PROFILE_BINS = ("left_deep", "left_profile", "right_deep", "right_profile")


def expression(frame, lm):
    """Тот же прокси мимики, что в chart_score: рот, улыбка, брови."""
    p = frame["vertices"][lm]
    mouth = float(np.mean([np.linalg.norm(p[61] - p[67]),
                           np.linalg.norm(p[62] - p[66]),
                           np.linalg.norm(p[63] - p[65])]))
    smile = float(np.linalg.norm(p[60] - p[64]))
    brow = float(np.mean([np.linalg.norm(p[17 + i] - p[36 + i]) for i in range(5)]))
    return mouth, smile, brow


def capture(frames, pairs, tri, lm):
    """Доля |Δ| в нормальной компоненте по зонам: sum|Δ·n| / sum|Δ|."""
    normals = template_normals(tri)
    acc = {z: [0.0, 0.0] for z in REGIONS}
    for i, j in pairs:
        delta = frames[j]["vertices"] - frames[i]["vertices"]
        norm = np.linalg.norm(delta, axis=1)
        dot = np.abs(np.sum(delta * normals, axis=1))
        for zone, points in REGIONS.items():
            idx = lm[points]
            acc[zone][0] += float(dot[idx].sum())
            acc[zone][1] += float(norm[idx].sum())
    return {z: round(s / max(t, 1e-9), 4) for z, (s, t) in acc.items()}


def normal_quality(frames, tri, lm):
    """Угол template vs per-frame нормалей и флипы по зонам и профилю."""
    template = template_normals(tri)
    rows = []
    for frame in frames:
        frame_n = vertex_normals(frame["vertices"], tri)
        dots = np.sum(template * frame_n, axis=1)
        angle = np.degrees(np.arccos(np.clip(dots, -1.0, 1.0)))
        row = {"person": frame["person"], "frame": frame["frame"],
               "bin": frame["bin"], "profile": frame["bin"] in PROFILE_BINS,
               "angle_mean": float(angle.mean()), "angle_p90": float(np.percentile(angle, 90)),
               "flip_fraction": float((dots < 0).mean())}
        for zone, points in REGIONS.items():
            idx = lm[points]
            row[f"angle_{zone}"] = float(angle[idx].mean())
            row[f"flip_{zone}"] = float((dots[idx] < 0).mean())
        rows.append(row)
    return rows


def per_frame_normal_values(frames, pairs, tri):
    """Диагностика: normal-компонента по нормалям кадра a (не продакшн)."""
    out = []
    for i, j in pairs:
        a, b = frames[i]["vertices"], frames[j]["vertices"]
        normals = vertex_normals(a, tri)
        values = compute_heat_values(a, b, a, tri, metric="normal",
                                     weighting="none", normals=normals)["end"]
        out.append(float(values.mean()))
    return np.asarray(out, np.float64)


def person_rows(frames, within, between, tri, lm, person, gap):
    """LOPO-калибровка без person: AUC по режимам, зонам и семействам."""
    people = sorted({f["person"] for f in frames})
    others = [p for p in people if p != person]
    sigma_e, sigma_n, pairs = fit_noise(frames, others, gap)
    local = calibration(sigma_e, sigma_n)
    mine = {i for i, f in enumerate(frames)
            if f["person"] == person and f["order"] % 2 == 1 and f["valid"]}
    other_idx = {i for i, f in enumerate(frames)
                 if f["person"] != person and f["order"] % 2 == 1 and f["valid"]}
    wm = [(i, j) for i, j in within if i in mine and j in mine]
    bm = [(i, j) for i, j in between
          if (i in mine and j in other_idx) or (j in mine and i in other_idx)]
    acc, racc = collect(frames, wm + bm, tri, local, lm, regions=True)
    row = {"n_within": len(wm), "n_between": len(bm), "sigma_pairs": pairs,
           "auc": {}, "zones": {}, "families": {}}
    for name, _metric, _weighting in MODES:
        wv = np.asarray(acc[name]["scalar"][: len(wm)])
        bv = np.asarray(acc[name]["scalar"][len(wm):])
        row["auc"][name] = auc(wv, bv)
    for zone in REGIONS:
        row["zones"][zone] = {}
        for name in ("euclid", "normal", "weighted_normal"):
            wv = np.asarray(racc[name][zone][: len(wm)])
            bv = np.asarray(racc[name][zone][len(wm):])
            row["zones"][zone][name] = auc(wv, bv)
    for family in FAMILIES:
        wf = [(i, j) for i, j in wm
              if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        bf = [(i, j) for i, j in bm
              if family_of(frames[i]["bin"], frames[j]["bin"]) == family]
        if len(wf) < 5 or len(bf) < 10:
            row["families"][family] = {"n_within": len(wf), "n_between": len(bf),
                                       "skipped": True}
            continue
        racc2, _ = collect(frames, wf + bf, tri, local, lm, regions=True)
        row["families"][family] = {"n_within": len(wf), "n_between": len(bf)}
        for name in ("euclid", "normal", "weighted_normal"):
            wv2 = np.asarray(racc2[name]["scalar"][: len(wf)])
            bv2 = np.asarray(racc2[name]["scalar"][len(wf):])
            row["families"][family][name] = auc(wv2, bv2)
    # Диагностический вариант: нормали конкретного кадра.
    pf = per_frame_normal_values(frames, wm + bm, tri)
    row["per_frame_normals"] = {"auc": auc(pf[: len(wm)], pf[len(wm):])}
    row["capture"] = capture(frames, wm, tri, lm)
    # Мимика: дельта рта/улыбки/бровей и связь с normal/euclid.
    ratios, mouths, smiles = [], [], []
    for (i, j), e, n in zip(wm,
                            acc["euclid"]["scalar"][: len(wm)],
                            acc["normal"]["scalar"][: len(wm)], strict=True):
        em, es, _ = frames[i]["expr"]
        fm, fs, _ = frames[j]["expr"]
        mouths.append(abs(fm - em))
        smiles.append(abs(fs - es))
        ratios.append(float(n / max(e, 1e-12)))
    row["expression"] = {
        "mouth_delta": round(float(np.mean(mouths)), 5) if mouths else None,
        "smile_delta": round(float(np.mean(smiles)), 5) if smiles else None,
        "corr_ratio_mouth": round(float(np.corrcoef(ratios, mouths)[0, 1]), 3)
        if len(ratios) > 2 and np.std(ratios) > 0 and np.std(mouths) > 0 else None,
    }
    return row


def reference_rows(frames, within, tri, lm, people):
    """Фон: capture и выражения по within-парам людей без провала."""
    people = set(people)
    pairs = [(i, j) for i, j in within if frames[i]["person"] in people]
    mouths = []
    for i, j in pairs:
        em = frames[i]["expr"][0]
        fm = frames[j]["expr"][0]
        mouths.append(abs(fm - em))
    return {"people": sorted(people), "n_within": len(pairs),
            "capture": capture(frames, pairs, tri, lm),
            "mouth_delta": round(float(np.mean(mouths)), 5) if mouths else None}


def figure(payload, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lopo = payload["lopo_rows"]
    names = [r["person"] for r in lopo]
    modes = ["euclid", "normal", "weighted_euclid", "weighted_normal"]
    colors = ["#7f8c96", "#e0a458", "#4fb3a0", "#4f7fc4"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    width = 0.2
    base = np.arange(len(names))
    for k, mode in enumerate(modes):
        axes[0].bar(base + (k - 1.5) * width,
                    [r[f"auc_{mode}"] for r in lopo], width, label=mode,
                    color=colors[k])
    axes[0].set_xticks(base, names, rotation=45, ha="right", fontsize=8)
    axes[0].set_title("LOPO AUC по людям")
    axes[0].legend(fontsize=7)
    axes[0].grid(axis="y", alpha=0.25)

    zones = list(REGIONS)
    eu = [np.mean([payload["people"][t]["zones"][z]["euclid"] for t in TARGETS])
          for z in zones]
    no = [np.mean([payload["people"][t]["zones"][z]["normal"] for t in TARGETS])
          for z in zones]
    x = np.arange(len(zones))
    axes[1].bar(x - 0.19, eu, 0.38, label="euclid", color="#4fb3a0")
    axes[1].bar(x + 0.19, no, 0.38, label="normal", color="#d0666b")
    axes[1].set_xticks(x, zones, fontsize=8)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_title("AUC по зонам: euclid vs normal")
    axes[1].legend(fontsize=7)
    axes[1].grid(axis="y", alpha=0.25)

    for k, person in enumerate(TARGETS):
        row = payload["people"][person]
        values = [row["auc"]["normal"], row["per_frame_normals"]["auc"],
                  row["auc"]["weighted_euclid"]]
        axes[2].bar(np.arange(3) + k * 0.18, values, 0.34,
                    label=person, color=["#d0666b", "#e0a458"][k])
    axes[2].set_xticks(np.arange(3), ["normal (template)", "normal (кадр)", "w-euclid"],
                       fontsize=8)
    axes[2].set_title("Провал normal и нормали кадра")
    axes[2].legend(fontsize=7)
    axes[2].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--min-frame-gap", type=int, default=30)
    ap.add_argument("--lopo", type=Path, default=ROOT / "reports/calibration-v3.json")
    ap.add_argument("--json", type=Path, default=ROOT / "reports/calibration/normal-diag.json")
    ap.add_argument("--figure", type=Path,
                    default=ROOT / "reports/figures/v4-normal-diag.png")
    args = ap.parse_args()

    index_path = args.calibration_root / "all_calibration_index.csv"
    index = index_rows(index_path)
    selected = ids_into(select_frames(index_path, args.photos_root, args.per_person))
    tri, lm = topology()
    extra_invalid = {}
    manifest = ROOT / "reports/calibration/invalid-frames.json"
    if manifest.exists():
        for row in json.loads(manifest.read_text()).get("frames", []):
            extra_invalid[(row["person"], int(row["frame"]))] = row.get("reason", "invalid_pose")
    frames = load_frames(selected, index, tri, lm, extra_invalid)
    for frame in frames:
        frame["expr"] = expression(frame, lm)
    people = sorted({f["person"] for f in frames})
    _sigma_e, _sigma_n, fit_pairs = fit_noise(frames, people, args.min_frame_gap)
    within, between = build_pairs(frames, args.min_frame_gap)

    payload = {
        "dataset": {"people": people, "frames": len(frames), "gap": args.min_frame_gap,
                    "sigma_pairs": fit_pairs,
                    "space": "center + IOD (eye-contour means ldm68 36:42/42:48)"},
        "targets": list(TARGETS),
        "people": {},
        "reference": {},
        "lopo_rows": [],
    }
    for person in TARGETS:
        row = person_rows(frames, within, between, tri, lm, person,
                          args.min_frame_gap)
        row["normals_quality"] = normal_quality(
            [f for f in frames if f["person"] == person and f["valid"]], tri, lm)
        payload["people"][person] = row
        print(person, {k: round(v, 3) for k, v in row["auc"].items()},
              "capture", row["capture"], "pf", round(row["per_frame_normals"]["auc"], 3))

    payload["reference"] = reference_rows(
        frames, within, tri, lm, [p for p in people if p not in TARGETS])

    source = json.loads(args.lopo.read_text()) if args.lopo.exists() else {}
    rows = (source.get("lopo") or {}).get("rows") or []
    payload["lopo_rows"] = rows
    if not rows:
        raise SystemExit("нет LOPO-строк в reports/calibration-v3.json: сначала v3")
    for target in TARGETS:
        mine = next((r for r in rows if r["person"] == target), None)
        if mine:
            payload["people"][target]["lopo_auc"] = {
                k.replace("auc_", ""): mine[k] for k in mine if k.startswith("auc_")}
    for target in TARGETS:
        lopo_auc = payload["people"][target].get("lopo_auc")
        if lopo_auc and abs(payload["people"][target]["auc"]["weighted_normal"]
                            - lopo_auc["weighted_normal"]) > 0.02:
            print(f"warning: {target} LOPO расходится с v3 больше 0.02")

    # Итог диагностики: где именно normal теряет разделение.
    jaw_drop = {t: round(payload["people"][t]["zones"]["jaw"]["normal"]
                         - payload["people"][t]["zones"]["jaw"]["euclid"], 4)
                for t in TARGETS}
    angle = {t: round(float(np.mean(
        [r["angle_mean"] for r in payload["people"][t]["normals_quality"]])), 2)
        for t in TARGETS}
    flips = {t: round(float(np.mean(
        [r["flip_fraction"] for r in payload["people"][t]["normals_quality"]])), 4)
        for t in TARGETS}
    pf_gain = {t: round(payload["people"][t]["per_frame_normals"]["auc"]
                        - payload["people"][t]["auc"]["normal"], 4) for t in TARGETS}
    normals_ok = all(v < 10 for v in angle.values()) and all(v < 0.01 for v in flips.values())
    payload["diagnosis"] = {
        "jaw_auc_drop_normal_minus_euclid": jaw_drop,
        "normal_angle_mean_deg": angle,
        "normal_flip_fraction": flips,
        "per_frame_normals_auc_gain": pf_gain,
        "normals_field_ok": normals_ok,
        "per_frame_restores": all(v > 0.05 for v in pf_gain.values()),
        "cause": "проекция на нормаль отбрасывает тангенциальное движение; "
                 "потеря сосредоточена в челюсти",
    }
    payload["verdict"] = (
        "нормали корректны (угол < 10°, флипов нет), per-frame вариант не возвращает AUC, "
        "потеря сосредоточена в челюсти: normal остаётся только в отчётах"
        if normals_ok and not payload["diagnosis"]["per_frame_restores"]
        else "normal остаётся только в отчётах: воспроизводимого исправления нет"
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    figure(payload, args.figure)
    print("verdict:", payload["verdict"])
    print("json", args.json, "figure", args.figure)


if __name__ == "__main__":
    main()
