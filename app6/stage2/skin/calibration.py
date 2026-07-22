"""Same-person calibration with group-safe holdout splitting.

📊 CONVENTIONS v2 → калибровка skin-каналов; статус: ⚠️ IN PROGRESS
"""
from __future__ import annotations
import csv, json, random, hashlib, time
from pathlib import Path
import numpy as np
from .chronology import load_records as _load


# 🔄 Загрузка референс-записей калибровки
def load_records(p):
    return _load(p)


# 🔄 Загрузка профиля калибровки
def load_profile(p):
    return json.loads(Path(p).read_text())


def _group_id(r):
    """Never separate duplicate/capture-event observations across splits."""
    return str(
        r.get("duplicate_cluster")
        or r.get("capture_event_id")
        or r.get("series_id")
        or r.get("photo_id")
        or r.get("event_id")
    )


def _split(records, test_fraction=.20, seed=0):
    grouped = {}
    for r in records:
        grouped.setdefault(_group_id(r), []).append(r)
    # Stratify groups by their dominant pose without breaking a group.
    strata = {}
    for gid, rows in grouped.items():
        poses = [str(x.get("pose_bin", "unknown")) for x in rows]
        pose = max(set(poses), key=poses.count) if poses else "unknown"
        strata.setdefault(pose, []).append(gid)
    rng = random.Random(seed)
    test_groups = set()
    for gids in strata.values():
        rng.shuffle(gids)
        if len(gids) <= 1:
            continue
        n_test = max(1, round(test_fraction * len(gids)))
        n_test = min(n_test, len(gids) - 1)
        test_groups.update(gids[:n_test])
    train, test = [], []
    for gid, rows in grouped.items():
        (test if gid in test_groups else train).extend(rows)
    if set(map(_group_id, train)) & set(map(_group_id, test)):
        raise AssertionError("capture/duplicate group leakage")
    return train, test


# 📊 Калибровка одного skin-канала
def calibrate(stage1_dir, output_dir, target_false_anomaly=.01):
    records = load_records(stage1_dir)
    tr, te = _split(records)
    counts, vals = {}, {}
    for r in tr:
        pose = str(r.get("pose_bin", "unknown"))
        counts[pose] = counts.get(pose, 0) + 1
        for z in r.get("zones", []):
            for k, v in z.items():
                if isinstance(v, (int, float)) and np.isfinite(v):
                    vals.setdefault("|".join((pose, str(z.get("zone", "")), k)), []).append(float(v))
    models = {
        k: {"n": len(x), "median": float(np.median(x)),
            "mad": float(1.4826 * np.median(abs(np.asarray(x) - np.median(x))) + 1e-9)}
        for k, x in vals.items() if len(x) >= 5
    }
    train_groups = sorted(set(map(_group_id, tr)))
    test_groups = sorted(set(map(_group_id, te)))
    reliable = sum(v >= 2 for v in counts.values())
    profile = {
        "schema": "skin-calibration-v1", "photo_count": len(records),
        "train_count": len(tr), "test_count": len(te), "pose_counts": counts,
        "train_group_count": len(train_groups), "test_group_count": len(test_groups),
        "split_unit": "duplicate_cluster_or_capture_event", "reliable_model_count": reliable,
        "models": models, "target_false_anomaly": target_false_anomaly, "frozen": False,
    }
    report = {
        "reliable_model_count": reliable, "metric_model_count": len(models),
        "acceptance": {"test_pass": bool(te and reliable >= 3), "held_out_count": len(te),
                       "held_out_group_count": len(test_groups), "target_false_anomaly": target_false_anomaly},
        "coverage": {"pose_bins": sorted(counts)},
        "leakage_check": {"ok": not bool(set(train_groups) & set(test_groups))},
    }
    o = Path(output_dir); o.mkdir(parents=True, exist_ok=True)
    (o / "calibration_profile.json").write_text(json.dumps(profile, indent=2))
    with open(o / "calibration_split.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["photo_id", "group_id", "pose_bin", "split"])
        for split, group in (("train", tr), ("test", te)):
            for r in group:
                w.writerow([r.get("photo_id"), _group_id(r), r.get("pose_bin"), split])
    return profile, report


# 🔒 Заморозка калибровки в sidecar
def freeze_calibration(profile_path, report, dataset_validation, out):
    if not report["acceptance"]["test_pass"] or not dataset_validation["ok"]:
        raise ValueError("calibration/dataset gate failed")
    if not report.get("leakage_check", {}).get("ok"):
        raise ValueError("calibration group leakage")
    p = json.loads(Path(profile_path).read_text()); p["frozen"] = True
    p["frozen_unix"] = time.time(); p["dataset_metadata_sha256"] = dataset_validation["metadata_sha256"]
    p["artifact_sha256"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
    Path(out).write_text(json.dumps(p, indent=2)); return p
