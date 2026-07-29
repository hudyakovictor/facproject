"""🎯 CRITICAL → Проекция реального вывода Stage 2 в контракт `/api/v1/timeline`.

Читает `analysis_manifest.json` + `pair_metrics.csv` из `DEEPUTIN_STAGE2_ROOT`
(тот же формат, что производит `app6.stage2.engine.Stage2Engine.run()`) и
строит по одной строке на фото (`photo_b` каждой adjacent-пары, плюс первое
фото хронологии каждого pose bin из первой пары, где оно встречается).

🚨 WARNING: в отличие от `timeline.py` (демо), здесь используется evidence_state
из настоящего Stage 2 (`app6.stage2.evidence`), а не иллюстративная
Байесовская проекция. Если реального `evidence_state`/`p0..p2` в Stage 2
row нет (текущая реализация Stage 2 их не пишет как отдельные вероятности),
поля `p0/p1/p2` заполняются нейтрально и это явно помечается
`bayesian_projection_available: false`, чтобы UI не выдавал их за настоящий
Stage 2 Байесовский вывод.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

RESEARCH_TIMELINE_SCHEMA = "deeputin-api-research-timeline-v1.0"

_EVIDENCE_TO_FUZZY = {
    "within_noise": "CONSISTENT",
    "not_measurable": "INSUFFICIENT_DATA",
    "insufficient_visibility": "INSUFFICIENT_DATA",
    "insufficient_calibration": "INSUFFICIENT_DATA",
    "elevated_uncertain": "WEAK_EVIDENCE",
    "quality_limited": "WEAK_EVIDENCE",
    "calibration_limited": "WEAK_EVIDENCE",
    "pose_leakage_limited": "WEAK_EVIDENCE",
    "expression_dominated": "WEAK_EVIDENCE",
    "coherent_jump_candidate": "SUSPICIOUS_TEXTURE",
    "reversible_change_candidate": "SUSPICIOUS_TEXTURE",
    "alpha_id_change_candidate": "GEOMETRIC_MISMATCH",
    "persistent_geometric_change": "GEOMETRIC_MISMATCH",
    "rate_change_candidate": "GEOMETRIC_MISMATCH",
    "persistent_rate_change_candidate": "IDENTITY_ANOMALY",
    "same_day_conflict_candidate": "TEMPORAL_IMPOSSIBILITY",
    "unsupported_pose": "INSUFFICIENT_DATA",
    "inapplicable_pose": "INSUFFICIENT_DATA",
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result else default  # filter NaN
    except (TypeError, ValueError):
        return default


def _date_to_ms(date_iso: str | None) -> int | None:
    if not date_iso:
        return None
    from datetime import date, datetime, timezone
    try:
        d = date.fromisoformat(str(date_iso)[:10])
    except ValueError:
        return None
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def build_research_timeline(stage2_root: Path) -> dict[str, Any]:
    """🚪 ENTRY POINT (программный) → Построить timeline payload из реального Stage 2.

    Raises:
        FileNotFoundError: если обязательные артефакты Stage 2 отсутствуют.
    """
    manifest_path = stage2_root / "analysis_manifest.json"
    pairs_path = stage2_root / "pair_metrics.csv"
    if not manifest_path.is_file() or not pairs_path.is_file():
        raise FileNotFoundError(f"incomplete Stage 2 output under {stage2_root}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with pairs_path.open(newline="", encoding="utf-8") as handle:
        pair_rows = [r for r in csv.DictReader(handle) if r.get("status") != "no_pairs"]

    photos_by_id: dict[str, dict[str, Any]] = {}

    def _ensure_photo(photo_id: str, date_iso: str | None, pose_bin: str) -> dict[str, Any]:
        if photo_id not in photos_by_id:
            photos_by_id[photo_id] = {
                "id": photo_id, "date": date_iso, "t": _date_to_ms(date_iso), "bucket": pose_bin,
                "era": "STAGE2_RESEARCH", "quality": None, "hidden": False,
                "boneScore": None, "orbit": None, "chin": None, "jaw": None, "cheek": None, "symmetry": None,
                "yaw": None, "siliconeProb": None, "specular": None, "lbpEntropy": None, "frangi": None,
                "wrinkle": None, "subsurface": None, "visualAge": None, "calendarAge": None,
                "p0": None, "p1": None, "p2": None, "dominant": None, "fuzzy": "INSUFFICIENT_DATA",
                "confidence": None, "flags": [], "exifAnomaly": False,
                "zOrbitDepth": 0.0, "zChinProj": 0.0, "zJawWidth": 0.0, "zCheek": 0.0,
                "sourceMode": "research", "bayesianProjectionAvailable": False,
            }
        return photos_by_id[photo_id]

    for row in pair_rows:
        pose_bin = str(row.get("pose_bin") or "unknown")
        photo_a_id, photo_b_id = row.get("photo_a"), row.get("photo_b")
        if not photo_a_id or not photo_b_id:
            continue
        _ensure_photo(photo_a_id, row.get("date_a"), pose_bin)
        target = _ensure_photo(photo_b_id, row.get("date_b"), pose_bin)

        evidence_state = str(row.get("evidence_state") or "")
        fuzzy = _EVIDENCE_TO_FUZZY.get(evidence_state, "INSUFFICIENT_DATA")
        target["fuzzy"] = fuzzy
        target["quality"] = 1.0 if not row.get("quality_limited") else 0.3
        target["confidence"] = 1.0 - min(1.0, _num(row.get("primary_robust_z")) / 10.0)
        target["boneScore"] = 1.0 - min(1.0, _num(row.get("p95_point_z")) / 10.0)
        target["yaw"] = _num(row.get("angles_b_1"), _num(row.get("yaw_b")))
        if evidence_state in ("persistent_geometric_change", "persistent_rate_change_candidate"):
            target["flags"].append("IDENTITY_ANOMALY")
        if evidence_state == "same_day_conflict_candidate":
            target["flags"].append("TEMPORAL_IMPOSSIBILITY")
        target["evidenceState"] = evidence_state
        target["measurementStatus"] = row.get("status")

    rows = list(photos_by_id.values())
    rows.sort(key=lambda r: (r["date"] or "", r["id"]))

    return {
        "schema": RESEARCH_TIMELINE_SCHEMA,
        "source_mode": "research",
        "not_a_verdict": True,
        "note": (
            "Реальный вывод Stage 2. P(H0..H2) не заполнены отдельным Байесовским "
            "полем в текущей реализации Stage 2 (bayesianProjectionAvailable=false "
            "для каждой записи) — используйте fuzzy/evidenceState/measurementStatus "
            "как основной evidence-сигнал."
        ),
        "analysis_manifest": manifest,
        "photos": rows,
    }
