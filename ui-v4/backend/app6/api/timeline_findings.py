"""Timeline findings layer (Iteration 07b).

Aggregates the *forensic* findings of the active Stage 2 run for display on
the timeline — not quality metrics, but:

- pair anomalies / evidence states (shape displacement per adjacent pair),
- skin-texture displacement per pair (texture channel status + quality),
- change-point events (persistent / candidate),
- baseline-return events (return to a previous state of the face),
- dense-copy zones: stretches where many photos were taken within a short
  time, with *prune suggestions* — which photos inside the zone contribute
  the most noise (worst quality, most extreme pose, near-duplicates) and
  could be excluded without losing information.

The suggestions are advisory: nothing is excluded until the operator applies
the action in the UI.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .calibration import POSE_BINS
from .runtime_config import load_runtime_paths
from .stage1_timeline import build_stage1_inventory

TIMELINE_FINDINGS_SCHEMA = "deeputin-timeline-findings-v1.0"

# dense-zone heuristics (per pose bin)
DENSE_MIN_PHOTOS = 6        # zone must contain at least this many photos
DENSE_MAX_GAP_DAYS = 90     # gap between consecutive photos that breaks a zone
KEEP_AT_LEAST = 3           # never suggest removing more than count - this
REMOVE_FRACTION = 0.4       # suggest removing up to this fraction of a zone

# shape displacement: statuses that flag attention
ALERT_SHAPE_STATUSES = {
    "elevated",
    "persistent_geometric_change",
    "coherent_jump_candidate",
    "rate_change_candidate",
    "persistent_rate_change_candidate",
    "biologically_improbable_rate_candidate",
    "persistent_biologically_improbable_change",
    "rapid_change_candidate",
    "persistent_rapid_change_candidate",
    "elevated_but_uncertain",
}


def _active_stage2_run() -> Path | None:
    paths = load_runtime_paths()
    root = paths.stage2_root
    candidates: list[Path] = []
    if (root / "analysis_manifest.json").is_file():
        candidates.append(root)
    runs = root / "runs"
    if runs.is_dir():
        candidates.extend(
            item for item in runs.iterdir()
            if item.is_dir() and (item / "analysis_manifest.json").is_file()
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _ms(date_iso: str | None) -> int | None:
    if not date_iso:
        return None
    try:
        parsed = date.fromisoformat(str(date_iso)[:10])
    except (TypeError, ValueError):
        return None
    return int(datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc).timestamp() * 1000)


def _days_between(a_iso: str | None, b_iso: str | None) -> int | None:
    a_ms, b_ms = _ms(a_iso), _ms(b_iso)
    if a_ms is None or b_ms is None:
        return None
    return int(abs(b_ms - a_ms) / 86_400_000)


def _pair_shape(row: dict[str, str]) -> dict[str, Any]:
    """Shape displacement of one adjacent pair (from pair_metrics.csv)."""
    identity = _float(row.get("identity_only_motion_rmse"))
    ldm134 = _float(row.get("ldm134_rmse"))
    return {
        "rmse": identity if identity is not None else ldm134,
        "ldm134_rmse": ldm134,
        "p95_z": _float(row.get("p95_point_z")),
        "status": str(row.get("status") or "unknown"),
        "significant_fraction": _float(row.get("significant_point_fraction")),
        "coherent_fraction": _float(row.get("coherent_motion_fraction")),
        "rate_status": row.get("biological_rate_status"),
        "alert": str(row.get("status") or "") in ALERT_SHAPE_STATUSES,
    }


def _pair_texture(row: dict[str, str]) -> dict[str, Any]:
    """Skin-texture channel of the pair (texture_image_* columns)."""
    quality_a = _float(row.get("quality_texture_score_a"))
    quality_b = _float(row.get("quality_texture_score_b"))
    delta = abs(quality_a - quality_b) if quality_a is not None and quality_b is not None else None
    return {
        "status": row.get("texture_image_status"),
        "quality_a": quality_a,
        "quality_b": quality_b,
        "delta": delta,
    }


def _dense_zones(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find dense-copy zones in a pose bin and build prune suggestions.

    Zone = at least DENSE_MIN_PHOTOS photos where no gap between consecutive
    photos exceeds DENSE_MAX_GAP_DAYS.

    Suggestion score per photo:
      quality_rank   — lower quality is worse (within the zone)
      pose_dev_rank  — larger deviation from the zone median pose is worse
      near_duplicate — duplicates are always suggested first
    The worst REMOVE_FRACTION (but never more than count − KEEP_AT_LEAST)
    are suggested for removal.
    """
    ordered = sorted(
        [photo for photo in photos if photo.get("t") is not None],
        key=lambda photo: int(photo["t"]),
    )
    zones: list[dict[str, Any]] = []
    cluster: list[dict[str, Any]] = []
    for photo in ordered:
        if cluster and (_days_between(cluster[-1].get("date"), photo.get("date")) or 0) > DENSE_MAX_GAP_DAYS:
            zones.append(_finalize_zone(cluster))
            cluster = []
        cluster.append(photo)
    if cluster:
        zones.append(_finalize_zone(cluster))
    return [zone for zone in zones if zone is not None]


def _finalize_zone(cluster: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(cluster) < DENSE_MIN_PHOTOS:
        return None
    # median pose of the zone
    def _median(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    yaws = [float(photo.get("yaw")) for photo in cluster if isinstance(photo.get("yaw"), (int, float))]
    pitches = [float(photo.get("pitch")) for photo in cluster if isinstance(photo.get("pitch"), (int, float))]
    rolls = [float(photo.get("roll")) for photo in cluster if isinstance(photo.get("roll"), (int, float))]
    med_yaw = _median(yaws) if yaws else 0.0
    med_pitch = _median(pitches) if pitches else 0.0
    med_roll = _median(rolls) if rolls else 0.0

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for photo in cluster:
        reasons: list[str] = []
        quality = photo.get("quality")
        quality_score = 0.0
        if isinstance(quality, (int, float)):
            quality_score = float(quality)
        else:
            reasons.append("quality_unavailable")
        yaw = float(photo.get("yaw") or 0.0)
        pitch = float(photo.get("pitch") or 0.0)
        roll = float(photo.get("roll") or 0.0)
        pose_dev = abs(yaw - med_yaw) / 12.0 + abs(pitch - med_pitch) / 6.0 + abs(roll - med_roll) / 8.0
        dup = photo.get("near_duplicate_of")
        if dup:
            reasons.append(f"near_duplicate_of_{dup}")
        # noise score: worse quality + extreme pose
        noise = (1.0 - quality_score) * 1.2 + min(2.0, pose_dev)
        if reasons and "quality_unavailable" in reasons:
            noise += 0.5
        scored.append((noise, photo, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    remove_count = min(max(1, int(round(len(cluster) * REMOVE_FRACTION))), max(0, len(cluster) - KEEP_AT_LEAST))
    remove_entries = scored[:remove_count]
    keep_ids = [photo["id"] for _, photo, _ in scored[remove_count:]]

    remove: list[dict[str, Any]] = []
    for noise, photo, reasons in remove_entries:
        if isinstance(photo.get("yaw"), (int, float)) and isinstance(photo.get("pitch"), (int, float)):
            yaw_dev = float(photo["yaw"]) - med_yaw
            reasons.append(f"pose_yaw_{yaw_dev:+.1f}°")
        if isinstance(photo.get("quality"), (int, float)) and photo.get("quality") is not None:
            reasons.append(f"quality_{float(photo['quality']):.2f}")
        remove.append({"id": photo["id"], "noise_score": round(noise, 4), "reasons": reasons})

    days = _days_between(cluster[0].get("date"), cluster[-1].get("date")) or 0
    return {
        "start": cluster[0].get("date"),
        "end": cluster[-1].get("date"),
        "count": len(cluster),
        "days": days,
        "remove": remove,
        "keep": keep_ids,
    }


def timeline_findings() -> dict[str, Any]:
    """Aggregate forensic findings for the timeline (read-only)."""
    paths = load_runtime_paths()
    stage1_root = paths.stage1_root
    if not (stage1_root / "main_timeline.csv").is_file():
        raise FileNotFoundError(f"Stage 1 not ready: {stage1_root}/main_timeline.csv")

    inventory = build_stage1_inventory(stage1_root)
    photos = inventory["photos"]
    by_id = {photo["id"]: photo for photo in photos}

    bins: dict[str, dict[str, Any]] = {
        pose: {"pairs": [], "change_points": [], "returns": [], "zones": []}
        for pose in POSE_BINS
    }

    run = _active_stage2_run()
    has_stage2 = run is not None
    run_id: str | None = None

    if run is not None:
        run_id = run.name
        for row in _read_csv_rows(run / "pair_metrics.csv"):
            pose = row.get("pose_bin")
            if pose not in bins:
                continue
            if row.get("pair_type") != "adjacent":
                continue
            bins[pose]["pairs"].append({
                "a": row.get("photo_a"),
                "b": row.get("photo_b"),
                "date_a": row.get("date_a"),
                "date_b": row.get("date_b"),
                "days_delta": _days_between(row.get("date_a"), row.get("date_b")),
                "shape": _pair_shape(row),
                "texture": _pair_texture(row),
            })

        change_points = _read_json(run / "change_points.json") or {}
        for entry in change_points.get("change_points", []):
            pose = entry.get("pose_bin")
            if pose not in bins:
                continue
            bins[pose]["change_points"].append({
                "date": entry.get("date") or entry.get("date_b"),
                "status": entry.get("status"),
                "pair": entry.get("pair_id") or f"{entry.get('photo_a')} → {entry.get('photo_b')}",
                "days_delta": _float(entry.get("days_delta")),
                "p95_z": _float(entry.get("p95_point_z")),
                "rate_status": entry.get("biological_rate_status"),
            })

        baseline_return = _read_json(run / "baseline_return.json") or {}
        for entry in baseline_return.get("events", []):
            photo_id = entry.get("photo_id") or entry.get("photo_b")
            pose = entry.get("pose_bin")
            if not pose and photo_id and photo_id in by_id:
                pose = by_id[photo_id].get("bucket")
            if pose not in bins:
                continue
            strength = _float(entry.get("opposite_fraction"))
            if strength is None:
                strength = _float(entry.get("magnitude_ratio"))
            bins[pose]["returns"].append({
                "date": entry.get("date") or entry.get("date_b"),
                "photo_id": photo_id,
                "baseline_photo_id": entry.get("baseline_photo_id") or entry.get("baseline_id"),
                "kind": entry.get("kind") or entry.get("status") or "baseline_return",
                "strength": strength,
            })

    # dense-copy zones + prune suggestions (per bin, from Stage 1 inventory)
    for pose in bins:
        bins[pose]["zones"] = _dense_zones([photo for photo in photos if photo.get("bucket") == pose])

    return {
        "schema": TIMELINE_FINDINGS_SCHEMA,
        "not_a_verdict": True,
        "run_id": run_id,
        "has_stage2": has_stage2,
        "bins": bins,
    }
