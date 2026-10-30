"""Тест выравнивания позы по всем 9 ракурсам (temp/atlas, свежее извлечение).

Выравнивает каждое фото к канону своего pose_bin, строит эталон внутри ракурса
(фото с минимальным |yaw - canon|), считает M1/M2/M3 по трём областям лица.
Четыре обязательных контроля, пороговый вердикт по группам ракурсов.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python scripts/alignment_all_poses.py \
        --persons person_01,person_02 --smoke
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import ingest_and_process, mean_vertex_distance, purge_records  # noqa: E402
from server.models.tddfa import (  # noqa: E402
    VERSION,
    POSE_BINS,
    classify_pose_bin,
    full_pose_correction_matrix,
    row_rotation_matrix,
)

# ── Constants ──────────────────────────────────────────────────────────────────
BIN_NAMES = [b[0] for b in POSE_BINS]
BIN_CANON = {b[0]: b[3] for b in POSE_BINS}
BIN_BOUNDS = {b[0]: (b[1], b[2]) for b in POSE_BINS}

EXPRESSION_CORNER_LIFT = 0.005
EXPRESSION_JAW_OPEN = 0.28
CONFIDENCE_MIN = 0.5
EYE_L, EYE_R = (36, 42), (42, 48)
L_CORNER, R_CORNER = 48, 54
UP_LIP, LOW_LIP = 62, 66

# ldm68 group → region
JAW_LANDMARKS = list(range(0, 17))          # jawline
CORE_LANDMARKS = list(range(27, 48))        # nose + eyes

# Thresholds by group
THRESHOLDS = {
    "light": {"median_m1": 0.03, "p95_m1": 0.06, "frac_m3_gt0": 0.80},
    "mid":   {"median_m1": 0.05, "p95_m1": 0.09, "frac_m3_gt0": 0.75},
}
GROUP_MAP = {
    "frontal": "light", "left_light": "light", "right_light": "light",
    "left_mid": "mid", "right_mid": "mid", "left_deep": "mid", "right_deep": "mid",
    "left_profile": None, "right_profile": None,  # report only
}
LIGHT_BINS = [b for b in BIN_NAMES if GROUP_MAP[b] == "light"]
MID_BINS = [b for b in BIN_NAMES if GROUP_MAP[b] == "mid"]
PROFILE_BINS = [b for b in BIN_NAMES if GROUP_MAP[b] is None]
NEGATIVE_CONTROL_OFFSET = 15.0  # degrees


# ── Region masks ───────────────────────────────────────────────────────────────
def compute_region_masks():
    """Assign each of 35709 vertices to 'jaw'/'core'/None via nearest ldm68."""
    data = json.loads((ROOT / "data/topology.json").read_text())
    lm68_idx = np.asarray(data["landmarks"]["ldm68"], np.int32)
    template = np.asarray(data["mean"], np.float64)  # (35709, 3)
    # landmark positions
    lm_pts = template[lm68_idx]  # (68, 3)
    # for each vertex, find nearest landmark
    # do in chunks to save memory
    n_verts = template.shape[0]
    regions = np.full(n_verts, -1, dtype=np.int8)  # -1=other, 0=jaw, 1=core
    jaw_mask_set = set(JAW_LANDMARKS)
    core_mask_set = set(CORE_LANDMARKS)
    # classify each landmark
    lm_region = np.full(68, -1, dtype=np.int8)
    for i in jaw_mask_set:
        lm_region[i] = 0
    for i in core_mask_set:
        lm_region[i] = 1
    # nearest landmark per vertex
    chunk = 5000
    for start in range(0, n_verts, chunk):
        end = min(start + chunk, n_verts)
        diff = template[start:end, None, :] - lm_pts[None, :, :]  # (chunk, 68, 3)
        dists = np.linalg.norm(diff, axis=2)  # (chunk, 68)
        nearest = dists.argmin(axis=1)  # landmark indices
        for i, nl in enumerate(nearest):
            regions[start + i] = lm_region[nl]
    jaw_mask = regions == 0
    core_mask = regions == 1
    full_mask = np.ones(n_verts, dtype=bool)
    return {"full": full_mask, "core": core_mask, "jaw": jaw_mask}


# ── Geometry helpers ──────────────────────────────────────────────────────────
def pitch_bin_label(p):
    ap = abs(float(p))
    if ap < 5: return "0-5"
    elif ap < 10: return "5-10"
    elif ap < 15: return "10-15"
    else: return ">15"


def load_ldm68():
    data = json.loads((ROOT / "data/topology.json").read_text())
    return np.asarray(data["landmarks"]["ldm68"], np.int32)


def eye_center_iod(mesh, lm68):
    eye = mesh[lm68]
    left = eye[list(range(*EYE_L))].mean(axis=0)
    right = eye[list(range(*EYE_R))].mean(axis=0)
    center = (left + right) / 2.0
    iod = max(float(np.linalg.norm(left - right)), 1e-8)
    return center.astype(np.float32), iod


def normalize(mesh, lm68):
    center, iod = eye_center_iod(mesh, lm68)
    return ((mesh - center) / iod).astype(np.float32)


def posed_mesh(identity, pitch, yaw, roll):
    return (np.asarray(identity, np.float32) @ row_rotation_matrix(pitch, yaw, roll)).astype(np.float32)


def canonicalize(posed, pitch, yaw, roll, canon_yaw):
    r_corr = full_pose_correction_matrix([pitch, yaw, roll], [0.0, canon_yaw, 0.0])
    return (posed @ r_corr).astype(np.float32)


def region_distance(a, b, mask):
    """Mean per-vertex distance restricted to mask."""
    d = np.linalg.norm(a[mask] - b[mask], axis=1)
    return float(d.mean()) if d.size else None


def expression_flags(lmk68):
    pts = lmk68
    iod = eye_center_iod_from_landmarks(pts)
    if iod <= 1e-8:
        return True, {"corner_lift": 999, "jaw_open": 999}  # flag as expressive if iod broken
    mouth_center_y = (pts[UP_LIP][1] + pts[LOW_LIP][1]) / 2.0
    corner_avg_y = (pts[L_CORNER][1] + pts[R_CORNER][1]) / 2.0
    corner_lift = float((corner_avg_y - mouth_center_y) / iod)
    jaw_open = float(np.linalg.norm(pts[UP_LIP] - pts[LOW_LIP]) / iod)
    return (corner_lift > EXPRESSION_CORNER_LIFT or jaw_open > EXPRESSION_JAW_OPEN), \
           {"corner_lift": round(corner_lift, 5), "jaw_open": round(jaw_open, 5)}


def eye_center_iod_from_landmarks(pts68):
    left = pts68[list(range(*EYE_L))].mean(axis=0)
    right = pts68[list(range(*EYE_R))].mean(axis=0)
    return float(np.linalg.norm(left - right))


# ── File enumeration ──────────────────────────────────────────────────────────
def enumerate_selected(photos_root, persons, per_person_limit):
    from PIL import Image
    selected = {}
    corrupt_files = []
    for pdir in sorted(photos_root.glob("person_*")):
        if persons and pdir.name not in persons:
            continue
        rows = []
        for i, jpg in enumerate(sorted(pdir.iterdir())):
            if jpg.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
                continue
            if jpg.name.startswith("._"):
                continue
            try:
                img = Image.open(jpg)
                img.verify()
                img = Image.open(jpg)
                img.load()
            except Exception as exc:
                corrupt_files.append((pdir.name, jpg.name, f"нечитаемый файл: {exc}"))
                continue
            digits = re.findall(r"\d+", jpg.stem)
            frame = int(digits[-1]) if digits else i
            rows.append({"frame": frame, "bin": "?", "path": jpg})
        if per_person_limit and 0 < per_person_limit < len(rows):
            idx = np.linspace(0, len(rows) - 1, per_person_limit).round().astype(int)
            rows = [rows[j] for j in sorted(set(idx.tolist()))]
        if len(rows) >= 2:
            selected[pdir.name] = rows
    return selected, corrupt_files


# ── Feature reading ───────────────────────────────────────────────────────────
def read_feature(photo_id):
    from server import storage
    record = storage.photo(photo_id)
    path = storage.feature_path(record)
    with np.load(path) as handle:
        identity = np.asarray(handle["identity"], np.float32)
        lmk68 = np.asarray(handle["landmarks_render_ldm68"], np.float32)
        alpha = np.ravel(np.asarray(handle["alpha"], np.float32))
    pitch = float(np.degrees(alpha[224]))
    yaw = float(np.degrees(alpha[225]))
    roll = float(np.degrees(alpha[226]))
    meta_path = path.with_name("meta.json")
    conf = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        conf = (meta.get("alignment") or {}).get("confidence")
    return {
        "identity": identity, "lmk68": lmk68,
        "pose_bin": classify_pose_bin(yaw)[0],
        "pitch": pitch, "yaw": yaw, "roll": roll, "confidence": conf,
    }


# ── Photo selection (§2) ─────────────────────────────────────────────────────
def select_photos_by_pose(frames_for_person, pose_bin):
    """Select up to 5 photos for (person, pose_bin) deterministically.

    frames_for_person: list of dicts with 'name', 'yaw', 'crc' keys.
    Returns list of (role, frame_dict).
    """
    canon = BIN_CANON[pose_bin]
    lo, hi = BIN_BOUNDS[pose_bin]
    # filter to this pose_bin
    in_bin = [f for f in frames_for_person if lo <= f["yaw"] < hi]
    if len(in_bin) < 3:
        return [], len(in_bin)
    # sort by |yaw - canon| for ideal selection
    in_bin.sort(key=lambda f: (abs(f["yaw"] - canon), f["crc"]))
    picked = {}  # name -> role

    # 1. ideal
    ideal = in_bin[0]
    picked[ideal["name"]] = ("ideal", ideal)

    # 2. edges
    by_yaw = sorted(in_bin, key=lambda f: (f["yaw"], f["crc"]))
    edge_lo = by_yaw[0]
    edge_hi = by_yaw[-1]
    if edge_lo["name"] not in picked:
        picked[edge_lo["name"]] = ("edge_lo", edge_lo)
    if edge_hi["name"] not in picked:
        picked[edge_hi["name"]] = ("edge_hi", edge_hi)

    # 3. mid_1, mid_2 at 1/3 and 2/3 between edges
    yaw_lo = by_yaw[0]["yaw"]
    yaw_hi = by_yaw[-1]["yaw"]
    span = yaw_hi - yaw_lo
    targets = [yaw_lo + span / 3.0, yaw_lo + 2.0 * span / 3.0]
    for i, t in enumerate(targets):
        role = f"mid_{i + 1}"
        # find nearest unclaimed
        candidates = sorted(
            [f for f in in_bin if f["name"] not in picked],
            key=lambda f: (abs(f["yaw"] - t), f["crc"]),
        )
        if candidates:
            picked[candidates[0]["name"]] = (role, candidates[0])

    result = [(role, fr) for (role, fr) in sorted(picked.values(), key=lambda x: x[1]["crc"])]
    # reorder: ideal first, then rest by role
    order = {"ideal": 0, "edge_lo": 1, "edge_hi": 2, "mid_1": 3, "mid_2": 4}
    result.sort(key=lambda x: order.get(x[0], 9))
    return result, len(in_bin)


# ── Main logic ────────────────────────────────────────────────────────────────
def run(args):
    photos_root = args.photos_root
    if not photos_root.is_dir():
        raise SystemExit(f"нет фото: {photos_root}")
    persons = set(p.strip() for p in args.persons.split(",") if p.strip())
    selected, corrupt = enumerate_selected(photos_root, persons, args.per_person or args.limit)
    if corrupt:
        print(f"пропущено битых файлов: {len(corrupt)}", flush=True)
    if not selected:
        raise SystemExit("нет людей с >=2 фото")
    print("кадров на человека:", {p: len(r) for p, r in sorted(selected.items())}, flush=True)

    # fresh extraction
    targets, info = ingest_and_process(selected, refresh_stale=False)
    if args.reforce:
        from server import storage
        job = type("J", (), {"check": lambda s: None, "update": lambda *a, **k: None})()
        for rec in targets:
            fp = storage.feature_path(rec)
            fp.unlink(missing_ok=True)
            fp.with_name("meta.json").unlink(missing_ok=True)
        info = storage.process(job, [r["id"] for r in targets])
    print(f"process: photos={info['photos']} hits={info['cache_hits']} errors={len(info['errors'])}", flush=True)

    lm68 = load_ldm68()
    masks = compute_region_masks()

    # build per-person frame data
    skipped = list(corrupt)
    person_pose_frames = defaultdict(list)  # person -> [{name, yaw, pitch, roll, ...}]
    for person, rows in selected.items():
        for row in rows:
            fname = row["path"].name
            try:
                fr = read_feature(row["id"])
            except Exception:
                skipped.append((person, fname, "inference error / no cache"))
                continue
            # filters
            if fr["confidence"] is None or fr["confidence"] < CONFIDENCE_MIN:
                skipped.append((person, fname, f"confidence={fr['confidence']}"))
                continue
            expressive, exp = expression_flags(fr["lmk68"])
            if expressive:
                skipped.append((person, fname, f"expression {exp}"))
                continue
            fr["name"] = fname
            fr["crc"] = zlib.crc32(f"{person}/{fname}".encode())
            fr["row"] = row
            person_pose_frames[person].append(fr)

    # per (person, pose_bin): select and compute
    all_results = []
    per_person_pose = []
    coverage_rows = []
    person_refs = {}  # (person, pose_bin) -> normalized reference mesh

    for person in sorted(person_pose_frames):
        frames = person_pose_frames[person]
        # count raw per bin
        bin_counts = defaultdict(int)
        for f in frames:
            bin_counts[f["pose_bin"]] += 1
        for pose_bin in BIN_NAMES:
            selected_set, total_in_bin = select_photos_by_pose(frames, pose_bin)
            raw_count = bin_counts.get(pose_bin, 0)
            coverage_rows.append({
                "person": person, "pose_bin": pose_bin,
                "raw_in_bin": raw_count, "after_filters": total_in_bin,
                "selected": len(selected_set),
                "excluded": total_in_bin < 3,
            })
            if len(selected_set) < 3:
                continue  # pair excluded from verdict
            # find ideal (reference)
            ideal_frame = None
            for role, fr in selected_set:
                if role == "ideal":
                    ideal_frame = fr
                    break
            canon = BIN_CANON[pose_bin]
            # compute reference vector (aligned ideal)
            ref_posed = posed_mesh(ideal_frame["identity"], ideal_frame["pitch"],
                                   ideal_frame["yaw"], ideal_frame["roll"])
            ref_aligned = canonicalize(ref_posed, ideal_frame["pitch"], ideal_frame["yaw"],
                                       ideal_frame["roll"], canon)
            ref_norm = normalize(ref_aligned, lm68)
            person_refs[(person, pose_bin)] = ref_norm
            ideal_yaw_offset = abs(ideal_frame["yaw"] - canon)
            # test frames
            for role, fr in selected_set:
                if role == "ideal":
                    continue
                posed = posed_mesh(fr["identity"], fr["pitch"], fr["yaw"], fr["roll"])
                aligned = canonicalize(posed, fr["pitch"], fr["yaw"], fr["roll"], canon)
                norm_aligned = normalize(aligned, lm68)
                norm_posed = normalize(posed, lm68)
                m1_full = region_distance(norm_aligned, ref_norm, masks["full"])
                m1_core = region_distance(norm_aligned, ref_norm, masks["core"])
                m1_jaw = region_distance(norm_aligned, ref_norm, masks["jaw"])
                m2_full = region_distance(norm_posed, ref_norm, masks["full"])
                m2_core = region_distance(norm_posed, ref_norm, masks["core"])
                m2_jaw = region_distance(norm_posed, ref_norm, masks["jaw"])
                m3_full = (m2_full - m1_full) if m1_full and m2_full else None
                m3_core = (m2_core - m1_core) if m1_core and m2_core else None
                m3_jaw = (m2_jaw - m1_jaw) if m1_jaw and m2_jaw else None
                all_results.append({
                    "person": person, "file": fr["name"], "pose_bin": pose_bin,
                    "role": role, "yaw": round(fr["yaw"], 3),
                    "pitch": round(fr["pitch"], 3), "roll": round(fr["roll"], 3),
                    "pitch_bin": pitch_bin_label(fr["pitch"]),
                    "confidence": fr["confidence"],
                    "ideal_yaw_offset": round(ideal_yaw_offset, 3),
                    "M1_full": round(m1_full, 6) if m1_full else None,
                    "M1_core": round(m1_core, 6) if m1_core else None,
                    "M1_jaw": round(m1_jaw, 6) if m1_jaw else None,
                    "M2_full": round(m2_full, 6) if m2_full else None,
                    "M2_core": round(m2_core, 6) if m2_core else None,
                    "M2_jaw": round(m2_jaw, 6) if m2_jaw else None,
                    "M3_full": round(m3_full, 6) if m3_full is not None else None,
                    "M3_core": round(m3_core, 6) if m3_core is not None else None,
                    "M3_jaw": round(m3_jaw, 6) if m3_jaw is not None else None,
                    "_norm_aligned": norm_aligned,  # kept for controls
                    "_masks": masks,
                })

    # store ideal references for controls (compute norm for all test rows already done)
    return all_results, person_refs, coverage_rows, skipped, masks, person_pose_frames, lm68, targets, info


# ── Controls (§5) ─────────────────────────────────────────────────────────────
def run_controls(all_results, person_refs, person_pose_frames, masks, lm68, args):
    """Returns dict with control_1 through control_4 results."""
    controls = {}

    # Control 1: identity discrimination (per test photo, find nearest ref among 7 persons)
    persons_in_data = sorted(set(r["person"] for r in all_results))
    ctrl1_correct = 0
    ctrl1_total = 0
    for row in all_results:
        pb = row["pose_bin"]
        own_person = row["person"]
        vec = row["_norm_aligned"]
        best_dist = float("inf")
        best_person = None
        for p in persons_in_data:
            ref = person_refs.get((p, pb))
            if ref is None:
                continue
            d = region_distance(vec, ref, masks["full"])
            if d < best_dist:
                best_dist = d
                best_person = p
        if best_person is not None:
            ctrl1_total += 1
            ctrl1_correct += int(best_person == own_person)
    controls["control_1_discrimination"] = {
        "n": ctrl1_total,
        "accuracy": round(ctrl1_correct / max(ctrl1_total, 1), 4),
        "threshold": 0.95,
        "passed": ctrl1_total > 0 and (ctrl1_correct / ctrl1_total) >= 0.95,
    }

    # Control 1b: aligned, excluding person_06/07 (diagnostic)
    EXCL_PAIR = {"person_06", "person_07"}
    c1b_total = c1b_correct = 0
    for row in all_results:
        pb = row["pose_bin"]
        own = row["person"]
        if own in EXCL_PAIR:
            continue
        vec = row["_norm_aligned"]
        best_d, best_p = float("inf"), None
        for p in persons_in_data:
            if p in EXCL_PAIR:
                continue
            ref = person_refs.get((p, pb))
            if ref is None:
                continue
            d = region_distance(vec, ref, masks["full"])
            if d < best_d:
                best_d, best_p = d, p
        if best_p is not None:
            c1b_total += 1
            c1b_correct += int(best_p == own)
    controls["control_1b_aligned_excl_pair"] = {
        "diagnostic_only": True,
        "n": c1b_total,
        "accuracy": round(c1b_correct / max(c1b_total, 1), 4),
        "note": "person_06/07 excluded",
    }

    # Control 1c: raw (posed, unaligned) discrimination (diagnostic)
    # build raw posed refs and test vectors from person_pose_frames
    raw_refs = {}  # (person, pb) -> normalized posed ideal
    for person in sorted(person_pose_frames):
        for pb_name in BIN_NAMES:
            canon = BIN_CANON[pb_name]
            lo, hi = BIN_BOUNDS[pb_name]
            in_bin = [f for f in person_pose_frames[person] if lo <= f["yaw"] < hi]
            if len(in_bin) < 3:
                continue
            in_bin.sort(key=lambda f: (abs(f["yaw"] - canon), f["crc"]))
            ideal = in_bin[0]
            posed = posed_mesh(ideal["identity"], ideal["pitch"], ideal["yaw"], ideal["roll"])
            raw_refs[(person, pb_name)] = normalize(posed, lm68)
    c1c_total = c1c_correct = 0
    for row in all_results:
        pb = row["pose_bin"]
        own = row["person"]
        person_data = {f["name"]: f for f in person_pose_frames[own]}
        fr = person_data.get(row["file"])
        if fr is None:
            continue
        posed = posed_mesh(fr["identity"], fr["pitch"], fr["yaw"], fr["roll"])
        vec_raw = normalize(posed, lm68)
        best_d, best_p = float("inf"), None
        for p in persons_in_data:
            ref = raw_refs.get((p, pb))
            if ref is None:
                continue
            d = region_distance(vec_raw, ref, masks["full"])
            if d < best_d:
                best_d, best_p = d, p
        if best_p is not None:
            c1c_total += 1
            c1c_correct += int(best_p == own)
    controls["control_1c_raw_discrimination"] = {
        "diagnostic_only": True,
        "n": c1c_total,
        "accuracy": round(c1c_correct / max(c1c_total, 1), 4),
        "note": "posed (unaligned) discrimination. If < aligned, alignment helps.",
    }

    # Control 2: negative (align to wrong canon +15°)
    ctrl2_grew = 0
    ctrl2_total = 0
    for row in all_results:
        pb = row["pose_bin"]
        vec_correct = row["_norm_aligned"]
        # recompute with offset target
        # need original frame data; we stored yaw/pitch/roll in row
        # reconstruct
        person_data = {f["name"]: f for f in person_pose_frames[row["person"]]}
        fr = person_data.get(row["file"])
        if fr is None:
            continue
        canon_wrong = BIN_CANON[pb] + NEGATIVE_CONTROL_OFFSET
        posed = posed_mesh(fr["identity"], fr["pitch"], fr["yaw"], fr["roll"])
        aligned_wrong = canonicalize(posed, fr["pitch"], fr["yaw"], fr["roll"], canon_wrong)
        norm_wrong = normalize(aligned_wrong, lm68)
        ref = person_refs[(row["person"], pb)]
        m1_wrong = region_distance(norm_wrong, ref, masks["full"])
        m1_correct = row["M1_full"]
        if m1_correct is not None and m1_wrong is not None:
            ctrl2_total += 1
            ctrl2_grew += int(m1_wrong > m1_correct)
    controls["control_2_negative"] = {
        "n": ctrl2_total,
        "frac_grew": round(ctrl2_grew / max(ctrl2_total, 1), 4),
        "threshold": 0.90,
        "passed": ctrl2_total > 0 and (ctrl2_grew / ctrl2_total) >= 0.90,
    }

    # Control 3: null (reference aligned to itself → M1 ~ 0)
    ctrl3_max = 0.0
    for (person, pb), ref_vec in person_refs.items():
        # ref_vec is already normalized aligned ideal; distance to itself = 0
        d = region_distance(ref_vec, ref_vec, masks["full"])
        ctrl3_max = max(ctrl3_max, d if d else 0.0)
    controls["control_3_null"] = {
        "max_self_distance": ctrl3_max,
        "threshold": 1e-4,
        "passed": ctrl3_max < 1e-4,
    }

    # Control 4: determinism — hash results_per_photo.csv content
    csv_hash = hashlib.sha256(
        json.dumps([{k: v for k, v in r.items() if not k.startswith("_")} for r in all_results],
                   sort_keys=True).encode()
    ).hexdigest()[:16]
    controls["control_4_determinism"] = {
        "results_hash": csv_hash,
        "note": "run twice and compare",
    }

    return controls


# ── Verdict (§6) ──────────────────────────────────────────────────────────────
def compute_verdict(all_results, controls):
    """Per-group verdict based on thresholds."""
    verdicts = {}
    for group_name, bins, thresh in [
        ("light", LIGHT_BINS, THRESHOLDS["light"]),
        ("mid", MID_BINS, THRESHOLDS["mid"]),
    ]:
        rows = [r for r in all_results if r["pose_bin"] in bins]
        if not rows:
            verdicts[group_name] = {"status": "no_data", "passed": False, "reason": "нет данных"}
            continue
        m1_vals = [r["M1_full"] for r in rows if r["M1_full"] is not None]
        m3_vals = [r["M3_full"] for r in rows if r["M3_full"] is not None]
        median_m1 = float(np.median(m1_vals)) if m1_vals else None
        p95_m1 = float(np.percentile(m1_vals, 95)) if len(m1_vals) >= 2 else median_m1
        frac_m3 = float(np.mean([m > 0 for m in m3_vals])) if m3_vals else None
        gates = {
            "median_m1": median_m1 is not None and median_m1 <= thresh["median_m1"],
            "p95_m1": p95_m1 is not None and p95_m1 <= thresh["p95_m1"],
            "frac_m3_gt0": frac_m3 is not None and frac_m3 >= thresh["frac_m3_gt0"],
        }
        verdicts[group_name] = {
            "n_photos": len(rows), "median_M1": round(median_m1, 6) if median_m1 else None,
            "p95_M1": round(p95_m1, 6) if p95_m1 else None,
            "frac_M3_gt0": round(frac_m3, 4) if frac_m3 else None,
            "thresholds": thresh, "gates": gates,
            "passed": all(gates.values()),
        }
    # profile: report only
    profile_rows = [r for r in all_results if r["pose_bin"] in PROFILE_BINS]
    verdicts["profile"] = {"n_photos": len(profile_rows), "status": "report_only"}
    # controls pass/fail
    ctrl_pass = all(
        controls.get(k, {}).get("passed", False)
        for k in ("control_1_discrimination", "control_2_negative", "control_3_null")
    )
    all_passed = all(v.get("passed", True) for k, v in verdicts.items() if k != "profile") and ctrl_pass
    return all_passed, verdicts


# ── Pitch/roll binning and symmetry (§7) ──────────────────────────────────────
def extra_summaries(all_results):
    # pitch bins
    pitch_bins = {"<5": [], "5-15": [], ">15": []}
    for r in all_results:
        ap = abs(r["pitch"])
        if ap < 5:
            pitch_bins["<5"].append(r["M1_full"])
        elif ap < 15:
            pitch_bins["5-15"].append(r["M1_full"])
        else:
            pitch_bins[">15"].append(r["M1_full"])
    pitch_summary = {k: round(float(np.median([v for v in vals if v is not None])), 6)
                     if any(v is not None for v in vals) else None
                     for k, vals in pitch_bins.items()}
    # M3 vs |yaw - canon| correlation
    m3_and_offset = [(r["M3_full"], abs(r["yaw"] - BIN_CANON[r["pose_bin"]]))
                     for r in all_results if r["M3_full"] is not None]
    if len(m3_and_offset) >= 3:
        m3_arr = np.array([x[0] for x in m3_and_offset])
        off_arr = np.array([x[1] for x in m3_and_offset])
        corr = float(np.corrcoef(m3_arr, off_arr)[0, 1])
    else:
        corr = None
    # symmetry: left_X vs right_X median M1
    symmetry = {}
    for pair_name in ("light", "mid", "deep", "profile"):
        left_bin = f"left_{pair_name}"
        right_bin = f"right_{pair_name}"
        lm = [r["M1_full"] for r in all_results if r["pose_bin"] == left_bin and r["M1_full"]]
        rm = [r["M1_full"] for r in all_results if r["pose_bin"] == right_bin and r["M1_full"]]
        symmetry[pair_name] = {
            "left_median": round(float(np.median(lm)), 6) if lm else None,
            "right_median": round(float(np.median(rm)), 6) if rm else None,
            "left_n": len(lm), "right_n": len(rm),
        }
    return {"pitch_bins": pitch_summary, "m3_yaw_correlation": corr, "symmetry": symmetry}


# ── Output writing (§8) ──────────────────────────────────────────────────────
def write_outputs(args, all_results, person_refs, coverage_rows, skipped,
                  masks, controls, verdicts_passed, verdicts, extra, targets):
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    # results_per_photo.csv
    cols = ["person", "file", "pose_bin", "role", "yaw", "pitch", "pitch_bin", "roll",
            "confidence", "ideal_yaw_offset",
            "M1_full", "M1_core", "M1_jaw", "M2_full", "M2_core", "M2_jaw",
            "M3_full", "M3_core", "M3_jaw"]
    with (out / "results_per_photo.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in all_results:
            w.writerow(r)

    # results_per_person_pose.csv
    pp_stats = defaultdict(list)
    for r in all_results:
        pp_stats[(r["person"], r["pose_bin"])].append(r)
    with (out / "results_per_person_pose.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["person", "pose_bin", "n_test", "median_M1", "median_M3", "mean_M1"])
        for (p, pb), rows in sorted(pp_stats.items()):
            m1s = [r["M1_full"] for r in rows if r["M1_full"] is not None]
            m3s = [r["M3_full"] for r in rows if r["M3_full"] is not None]
            w.writerow([p, pb, len(rows),
                        round(float(np.median(m1s)), 6) if m1s else None,
                        round(float(np.median(m3s)), 6) if m3s else None,
                        round(float(np.mean(m1s)), 6) if m1s else None])

    # results_per_pose.csv
    pose_stats = defaultdict(list)
    for r in all_results:
        pose_stats[r["pose_bin"]].append(r)
    with (out / "results_per_pose.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["pose_bin", "n", "median_M1", "p95_M1", "median_M3", "frac_M3_gt0"])
        for pb in BIN_NAMES:
            rows = pose_stats.get(pb, [])
            m1s = [r["M1_full"] for r in rows if r["M1_full"] is not None]
            m3s = [r["M3_full"] for r in rows if r["M3_full"] is not None]
            w.writerow([pb, len(rows),
                        round(float(np.median(m1s)), 6) if m1s else None,
                        round(float(np.percentile(m1s, 95)), 6) if len(m1s) >= 2 else None,
                        round(float(np.median(m3s)), 6) if m3s else None,
                        round(float(np.mean([m > 0 for m in m3s])), 4) if m3s else None])

    # coverage.csv
    with (out / "coverage.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["person", "pose_bin", "raw_in_bin",
                                            "after_filters", "selected", "excluded"],
                           delimiter=";")
        w.writeheader()
        for row in coverage_rows:
            w.writerow(row)

    # skipped.csv
    with (out / "skipped.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["person", "file", "reason"])
        for item in skipped:
            w.writerow(item)

    # controls.json
    (out / "controls.json").write_text(
        json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8")

    # summary.json
    # build verdict_reason
    reasons = []
    for g in ("light", "mid"):
        vg = verdicts.get(g, {})
        if vg.get("passed") is False:
            failed_gates = {k: v for k, v in vg.get("gates", {}).items() if not v}
            reasons.append(f"группа {g}: {failed_gates}")
    for ck, cv in controls.items():
        if cv.get("passed") is False:
            reasons.append(f"{ck}: accuracy={cv.get('accuracy', cv.get('frac_grew', cv.get('max_self_distance')))} < порог")
    summary = {
        "verdict": "пройден" if verdicts_passed else "не пройден",
        "verdict_reason": "; ".join(reasons) if reasons else "все пороги выполнены",
        "verdict_passed": verdicts_passed,
        "people": len(set(r["person"] for r in all_results)),
        "test_photos": len(all_results),
        "skipped_rows": len(skipped),
        "pose_bin_coverage": {pb: len(pose_stats.get(pb, [])) for pb in BIN_NAMES},
        "group_verdicts": verdicts,
        "controls_summary": {k: v.get("passed", "n/a") for k, v in controls.items()},
        "extra": extra,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # config_snapshot.json
    import subprocess
    git_hash = "unknown"
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        pass
    snapshot = {
        "schema_version": VERSION, "git_hash": git_hash,
        "pose_bins": {b[0]: {"bounds": [b[1], b[2]], "canonical": b[3]} for b in POSE_BINS},
        "thresholds": {k: v for k, v in THRESHOLDS.items()},
        "group_map": GROUP_MAP,
        "expression": {"corner_lift": EXPRESSION_CORNER_LIFT, "jaw_open": EXPRESSION_JAW_OPEN},
        "confidence_min": CONFIDENCE_MIN,
        "normalization": "center eyes (ldm68 36:42/42:48) + IOD",
        "negative_control_offset": NEGATIVE_CONTROL_OFFSET,
        "seed": args.seed,
    }
    (out / "config_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    # worst_20 per pose_bin
    from server import storage
    by_key = {(t["group"], t["name"]): t for t in targets}
    for pb in BIN_NAMES:
        rows = [r for r in all_results if r["pose_bin"] == pb]
        if not rows:
            continue
        worst = sorted(rows, key=lambda r: (r["M1_full"] is None, -(r["M1_full"] or 0)))[:20]
        wd = out / "worst_20" / pb
        wd.mkdir(parents=True, exist_ok=True)
        for r in worst:
            base = f"{r['person']}__{Path(r['file']).stem}"
            src = args.photos_root / r["person"] / r["file"]
            if src.is_file():
                shutil.copy(src, wd / f"{base}__orig.jpg")
            rec = by_key.get((r["person"], r["file"]))
            if rec:
                crop = storage.feature_path(rec).with_name("aligned.jpg")
                if crop.exists():
                    shutil.copy(crop, wd / f"{base}__aligned.jpg")
            # write values
            (wd / f"{base}.txt").write_text(
                f"M1={r['M1_full']} M2={r['M2_full']} M3={r['M3_full']}\n")

    print(f"\nотчёт: {out}")
    print(f"вердикт: {summary['verdict']}")
    print(f"gates: {json.dumps({k: v.get('passed') for k, v in verdicts.items()}, ensure_ascii=False)}")


# ── Smoke mode ────────────────────────────────────────────────────────────────
def print_smoke(all_results, controls, verdicts, verdicts_passed):
    m1 = [r["M1_full"] for r in all_results if r["M1_full"] is not None]
    m3 = [r["M3_full"] for r in all_results if r["M3_full"] is not None]
    print(f"\nsmoke: {len(all_results)} test photos, {len(set(r['person'] for r in all_results))} persons, "
          f"{len(set(r['pose_bin'] for r in all_results))} pose_bins")
    print(f"  M1 med={np.median(m1):.5f} M3 med={np.median(m3):.5f} "
          f"M3>0={np.mean([m > 0 for m in m3]):.3f} verdict={'ПРОЙДЕН' if verdicts_passed else 'НЕ ПРОЙДЕН'}")
    for k, v in controls.items():
        if "passed" in v:
            print(f"  {k}: {v['passed']}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--persons", default="person_01,person_02,person_03,person_04,person_05,person_06,person_07")
    ap.add_argument("--per-person", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reforce", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/alignment-all-poses")
    args = ap.parse_args()

    all_results, person_refs, coverage_rows, skipped, masks, person_pose_frames, lm68, targets, info = run(args)
    # strip internal arrays before controls that don't need them
    controls = run_controls(all_results, person_refs, person_pose_frames, masks, lm68, args)
    verdicts_passed, verdicts = compute_verdict(all_results, controls)
    extra = extra_summaries(all_results)

    if args.smoke:
        print_smoke(all_results, controls, verdicts, verdicts_passed)
        if args.purge:
            print("purged", purge_records([t["id"] for t in targets]))
        return

    write_outputs(args, all_results, person_refs, coverage_rows, skipped,
                  masks, controls, verdicts_passed, verdicts, extra, targets)
    if args.purge:
        print("purged", purge_records([t["id"] for t in targets]))


if __name__ == "__main__":
    main()
