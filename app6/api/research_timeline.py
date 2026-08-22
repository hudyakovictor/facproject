"""🎯 CRITICAL → Проекция реального вывода Stage 2 в контракт `/api/v1/timeline`.

Читает `analysis_manifest.json` + `pair_metrics.csv` из `DEEPUTIN_STAGE2_ROOT`
(тот же формат, что производит `app6.stage2.engine.Stage2Engine.run()`) и
строит по одной строке на фото (`photo_b` каждой adjacent-пары, плюс первое
фото хронологии каждого pose bin из первой пары, где оно встречается).

🚨 WARNING: в отличие от старой проекционной заглушки, здесь используется evidence_state
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

from .photo_fields import merge_photo_fields
from .ui_fields import UI_FIELDS_SCHEMA, validate_ui_row
from datetime import UTC

RESEARCH_TIMELINE_SCHEMA = "deeputin-api-research-timeline-v1.0"

_EVIDENCE_TO_FUZZY = {
    "within_noise": "CONSISTENT",
    "not_measurable": "INSUFFICIENT_DATA",
    "insufficient_visibility": "INSUFFICIENT_DATA",
    "insufficient_calibration": "INSUFFICIENT_DATA",
    "elevated_uncertain": "WEAK_EVIDENCE",
    "quality_limited": "WEAK_EVIDENCE",
    "calibration_limited": "WEAK_EVIDENCE",
    "pose_leakage_limited":"WEAK_EVIDENCE","date_provenance_limited":"INSUFFICIENT_DATA","near_duplicate_limited":"INSUFFICIENT_DATA",
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
    from datetime import date, datetime
    try:
        d = date.fromisoformat(str(date_iso)[:10])
    except ValueError:
        return None
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def build_research_timeline(stage2_root: Path, stage1_root: Path | None = None) -> dict[str, Any]:
    """Построить хронологию из Stage 2, сохранив измерения кадра из Stage 1.

    Stage 2 хранит метрики пар, а не самостоятельные характеристики фото.
    Поэтому углы, покрытие и provenance берутся из ``main_timeline.csv``;
    результаты пар агрегируются отдельно и не выдаются за свойства кадра.
    """
    manifest_path = stage2_root / "analysis_manifest.json"
    pairs_path = stage2_root / "pair_metrics.csv"
    if not manifest_path.is_file() or not pairs_path.is_file():
        raise FileNotFoundError(f"incomplete Stage 2 output under {stage2_root}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with pairs_path.open(newline="", encoding="utf-8") as handle:
        pair_rows = [r for r in csv.DictReader(handle) if r.get("status") != "no_pairs"]

    stage1_by_id: dict[str, dict[str, str]] = {}
    if stage1_root is not None:
        timeline_path = stage1_root / "main_timeline.csv"
        if timeline_path.is_file():
            with timeline_path.open(newline="", encoding="utf-8") as handle:
                stage1_by_id = {
                    str(row.get("photo_id")): row
                    for row in csv.DictReader(handle) if row.get("photo_id")
                }

    photos_by_id: dict[str, dict[str, Any]] = {}

    def _optional_num(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number else None

    def _ensure_photo(photo_id: str, date_iso: str | None, pose_bin: str) -> dict[str, Any]:
        if photo_id not in photos_by_id:
            stage1 = stage1_by_id.get(photo_id, {})
            actual_date = stage1.get("date") or date_iso
            actual_pose = stage1.get("pose_bin") or pose_bin
            photos_by_id[photo_id] = {
                "id": photo_id, "date": actual_date, "t": _date_to_ms(actual_date), "bucket": actual_pose,
                "era": "STAGE2_RESEARCH",
                "quality": _optional_num(stage1.get("combined_visible_fraction")),
                "qualityBasis": "combined_visible_fraction", "hidden": False,
                "boneScore": None, "orbit": None, "chin": None, "jaw": None, "cheek": None, "symmetry": None,
                "yaw": _optional_num(stage1.get("yaw")), "pitch": _optional_num(stage1.get("pitch")),
                "roll": _optional_num(stage1.get("roll")),
                "siliconeProb": None, "specular": None, "lbpEntropy": None, "frangi": None,
                "wrinkle": None, "subsurface": None, "visualAge": None, "calendarAge": None,
                "p0": None, "p1": None, "p2": None, "dominant": None, "fuzzy": "INSUFFICIENT_DATA",
                "confidence": None, "flags": [], "exifAnomaly": False,
                "dateProvenanceStatus": stage1.get("date_provenance_status") or "unknown",
                "exifDate": stage1.get("exif_date") or None,
                "dateDeltaDays": _optional_num(stage1.get("date_delta_days")),
                "sourceClaimedDate": stage1.get("source_claimed_date") or None,
                "sourceClaimedDeltaDays": _optional_num(stage1.get("source_claimed_delta_days")),
                "dateConflictSources": [], "dateProvenanceLimited": False,
                "zOrbitDepth": None, "zChinProj": None, "zJawWidth": None, "zCheek": None,
                "sourceMode": "research", "analysisStage": "stage2_pairs",
                "bayesianProjectionAvailable": False, "measurementStatus": "compared",
                "stage2PairCount": 0, "stage2StatusCounts": {}, "stage2EvidenceCounts": {},
            }
            merge_photo_fields(photos_by_id[photo_id], stage1_root, photo_id)
        return photos_by_id[photo_id]

    for row in pair_rows:
        pose_bin = str(row.get("pose_bin") or "unknown")
        photo_a_id, photo_b_id = row.get("photo_a"), row.get("photo_b")
        if not photo_a_id or not photo_b_id:
            continue
        source=_ensure_photo(photo_a_id,row.get("date_a"),pose_bin);target=_ensure_photo(photo_b_id,row.get("date_b"),pose_bin)
        for photo,suffix in ((source,"a"),(target,"b")):
            photo["dateProvenanceStatus"]=row.get(f"date_provenance_status_{suffix}") or "unknown";photo["exifDate"]=row.get(f"exif_date_{suffix}") or None
            delta=row.get(f"date_delta_days_{suffix}");_dv=_optional_num(delta);photo["dateDeltaDays"]=int(_dv) if _dv is not None else None
            claimed=row.get(f"source_claimed_date_{suffix}");photo["sourceClaimedDate"]=claimed or None
            claimed_delta=row.get(f"source_claimed_delta_days_{suffix}");_cd=_optional_num(claimed_delta);photo["sourceClaimedDeltaDays"]=int(_cd) if _cd is not None else None
            raw_sources=row.get(f"date_conflict_sources_{suffix}")
            if isinstance(raw_sources,list):photo["dateConflictSources"]=raw_sources
            else:
                try:decoded=json.loads(str(raw_sources or "[]"));photo["dateConflictSources"]=decoded if isinstance(decoded,list) else []
                except json.JSONDecodeError:photo["dateConflictSources"]=[x.strip() for x in str(raw_sources or "").strip("[]").replace("'","").split(",") if x.strip()]
            photo["exifAnomaly"]=photo["dateProvenanceStatus"]=="conflict"
            if photo["exifAnomaly"]:photo["flags"].append("DATE_PROVENANCE_CONFLICT")

        evidence_state = str(row.get("evidence_state") or "")
        status = str(row.get("status") or "unknown")
        fuzzy = _EVIDENCE_TO_FUZZY.get(evidence_state, "INSUFFICIENT_DATA")
        for photo in (source, target):
            photo["stage2PairCount"] += 1
            photo["stage2StatusCounts"][status] = photo["stage2StatusCounts"].get(status, 0) + 1
            photo["stage2EvidenceCounts"][evidence_state] = photo["stage2EvidenceCounts"].get(evidence_state, 0) + 1
            photo["dateProvenanceLimited"] = photo["dateProvenanceLimited"] or str(row.get("date_provenance_limited", "")).lower() in {"true", "1", "yes"}
            # Pair evidence is only a review signal. Keep it explicitly separate
            # from an identity verdict and mark both endpoints symmetrically.
            if evidence_state in ("persistent_geometric_change", "persistent_rate_change_candidate") and "GEOMETRY_REVIEW_PAIR" not in photo["flags"]:
                photo["flags"].append("GEOMETRY_REVIEW_PAIR")
            if evidence_state == "same_day_conflict_candidate" and "TEMPORAL_REVIEW_PAIR" not in photo["flags"]:
                photo["flags"].append("TEMPORAL_REVIEW_PAIR")
            if evidence_state == "quality_limited" and "QUALITY_LIMITED_PAIR" not in photo["flags"]:
                photo["flags"].append("QUALITY_LIMITED_PAIR")
            if evidence_state == "calibration_limited" and "CALIBRATION_LIMITED_PAIR" not in photo["flags"]:
                photo["flags"].append("CALIBRATION_LIMITED_PAIR")
            if fuzzy != "INSUFFICIENT_DATA":
                photo["fuzzy"] = fuzzy

    # A photo can participate in many pair types. Expose complete aggregates;
    # never let the final CSV row silently overwrite its earlier pair states.
    for photo in photos_by_id.values():
        evidence_counts = photo["stage2EvidenceCounts"]
        photo["evidenceState"] = next(iter(evidence_counts)) if len(evidence_counts) == 1 else "mixed"

    rows = list(photos_by_id.values())
    rows.sort(key=lambda r: (r["date"] or "", r["id"]))
    ui_violations_by_field: dict[str, int] = {}
    for row in rows:
        row["uiContractViolations"] = validate_ui_row(row)
        row["uiFieldsSchema"] = UI_FIELDS_SCHEMA
        for fld in row["uiContractViolations"]:
            ui_violations_by_field[fld] = ui_violations_by_field.get(fld, 0) + 1

    # === Хронологические аномалии из манифеста Stage 2 =======================
    # Stage 2 уже считает возвраты к базовой линии, необратимые возвраты и
    # биологически невозможные скорости, но раньше НИЧЕГО из этого не доходило
    # до интерфейса. Пробрасываем сводки как есть (не пересчитывая) и
    # проставляем соответствующие флаги на затронутых кадрах.
    anomaly_summaries: dict[str, Any] = {}
    for key in ("irreversible_return", "baseline_return", "chronology_rate",
                "biological_rate", "cumulative_drift"):
        payload = manifest.get(key)
        if isinstance(payload, dict) and payload:
            anomaly_summaries[key] = payload

    # Годы, в которых Stage 2 зафиксировал возврат формы: помечаем кадры.
    return_years: set[int] = set()
    for key in ("irreversible_return", "baseline_return"):
        years = (anomaly_summaries.get(key) or {}).get("years")
        if isinstance(years, list):
            return_years.update(int(y) for y in years if isinstance(y, (int, float)))
    if return_years:
        for row in rows:
            date_iso = row.get("date")
            if not date_iso:
                continue
            try:
                year = int(str(date_iso)[:4])
            except ValueError:
                continue
            if year in return_years and "RETURN_TO_BASELINE" not in row["flags"]:
                row["flags"].append("RETURN_TO_BASELINE")

    # `era` для research-режима: сегменты строятся из фактических дат по годам,
    # иначе весь набор оказывается одним сегментом "STAGE2_RESEARCH" и
    # хронологическая раскладка теряется.
    era_meta: dict[str, dict[str, str]] = {}
    dated = [r for r in rows if r.get("date")]
    if dated:
        for row in dated:
            year = str(row["date"])[:4]
            era_id = f"STAGE2_{year}"
            row["era"] = era_id
            bounds = era_meta.setdefault(era_id, {"label": f"Stage 2 · {year}",
                                                  "start": str(row["date"])[:10],
                                                  "end": str(row["date"])[:10]})
            bounds["start"] = min(bounds["start"], str(row["date"])[:10])
            bounds["end"] = max(bounds["end"], str(row["date"])[:10])
    else:
        era_meta["STAGE2_RESEARCH"] = {"label": "Stage 2 research", "start": "", "end": ""}

    return {
        "schema": RESEARCH_TIMELINE_SCHEMA,
        "source_mode": "research",
        "not_a_verdict": True,
        "era_meta": era_meta,
        "chronology_anomalies": anomaly_summaries,
        "note": (
            "Реальный вывод Stage 2. P(H0..H2) не заполнены отдельным Байесовским "
            "полем в текущей реализации Stage 2 (bayesianProjectionAvailable=false "
            "для каждой записи) — используйте fuzzy/evidenceState/measurementStatus "
            "как основной evidence-сигнал."
        ),
        "analysis_manifest": manifest,
        "ui_fields_schema": UI_FIELDS_SCHEMA,
        "ui_field_contracts": {
            "boneScore": {
                "role": "derived_display_only",
                "source": "stage1_stage2_projection",
                "source_metric": "p95_point_z",
                "transform": "1/(1+max(z,0)/3)",
                "not_a_measurement": True,
                "not_a_verdict": True,
                "evidence_metric": False,
            },
        },
        "ui_fields_complete_photo_count": sum(1 for r in rows if not r.get("uiContractViolations")),
        "ui_fields_violations_by_field": ui_violations_by_field,
        "photos": rows,
    }
