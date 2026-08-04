"""Recommendation engine (Iteration 13).

Aggregates advisory suggestions from the current state of the workstation so
the operator always sees what could be done next — and every suggestion can
be tuned or switched off (settings are stored per-type with enable flags,
limits and thresholds).

Every recommendation is *advisory*: it never changes data by itself and
always carries an action that the operator explicitly confirms.

Recommendation types (all tunable):
  stage1_integrity  — Stage 1 evidence unchanged vs baseline (or violated!)
  no_stage2         — no completed Stage 2 run yet
  stale_profile_run — profile filters changed after the last frozen manifest
  run_invalid       — latest run failed; retry or delete
  report_missing    — completed run without any report
  public_report     — reports exist but no public-mode report
  dense_zones       — dense-copy zones with prune suggestions
  coverage_gap      — pose bins with long date gaps (weak evidence periods)
  calibration_gap   — pose bins with weak calibration support
  exceedance_cluster— bins where many adjacent pairs exceed calibrated p95
  return_events     — baseline-return events present
  duplicate_heavy   — selection contains many near-duplicates
  findings_unviewed — bins with change points/returns (check the findings layer)
  log_errors        — recent error-level events in the journal
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .calibration import POSE_BINS
from .runtime_config import RuntimePaths, ensure_runtime_write_dirs, load_runtime_paths, stage1_integrity_snapshot

RECOMMENDATIONS_SCHEMA = "deeputin-recommendations-v1.0"
RECOMMENDATIONS_SETTINGS_SCHEMA = "deeputin-recommendations-settings-v1.0"

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema": RECOMMENDATIONS_SETTINGS_SCHEMA,
    "max_total": 12,
    "types": {
        "stage1_integrity": {"enabled": True, "limit": 1},
        "no_stage2": {"enabled": True, "limit": 1},
        "stale_profile_run": {"enabled": True, "limit": 2},
        "run_invalid": {"enabled": True, "limit": 2},
        "report_missing": {"enabled": True, "limit": 1},
        "public_report": {"enabled": True, "limit": 1},
        "dense_zones": {"enabled": True, "limit": 3},
        "coverage_gap": {"enabled": True, "limit": 3},
        "calibration_gap": {"enabled": True, "limit": 3},
        "exceedance_cluster": {"enabled": True, "limit": 2},
        "return_events": {"enabled": True, "limit": 2},
        "duplicate_heavy": {"enabled": True, "limit": 1},
        "findings_unviewed": {"enabled": True, "limit": 2},
        "log_errors": {"enabled": True, "limit": 2},
    },
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "coverage_gap_days": 180,      # min gap length to report in a pose bin
    "calibration_min_persons": 3,  # below this → weak calibration support
    "exceedance_min_pairs": 3,     # min alert pairs in a bin to report
    "duplicate_min_ratio": 0.10,   # near-duplicate share of selection
    "coverage_min_photos_per_year": 2,
}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _settings_path(paths: RuntimePaths) -> Path:
    ensure_runtime_write_dirs(paths)
    directory = paths.registry_root / "recommendations"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "settings.json"


def load_settings(paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    path = _settings_path(current)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("schema") == RECOMMENDATIONS_SETTINGS_SCHEMA:
                # merge with defaults so new types appear enabled
                merged = json.loads(json.dumps(DEFAULT_SETTINGS))
                for key, value in payload.get("types", {}).items():
                    if key in merged["types"]:
                        merged["types"][key].update(value)
                if isinstance(payload.get("max_total"), (int, float)):
                    merged["max_total"] = int(payload["max_total"])
                return merged
        except (OSError, json.JSONDecodeError):
            pass
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(payload: dict[str, Any], paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    merged = load_settings(current)
    if isinstance(payload.get("max_total"), (int, float)):
        merged["max_total"] = max(1, min(int(payload["max_total"]), 50))
    for key, value in (payload.get("types") or {}).items():
        if key in merged["types"] and isinstance(value, dict):
            for field in ("enabled", "limit"):
                if field in value:
                    merged["types"][key][field] = bool(value[field]) if field == "enabled" else max(0, int(value[field]))
    _settings_path(current).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _latest_run_info() -> dict[str, Any] | None:
    paths = load_runtime_paths()
    root = paths.stage2_root
    entries: list[tuple[float, Path]] = []
    if (root / "analysis_manifest.json").is_file():
        entries.append((root.stat().st_mtime, root))
    runs = root / "runs"
    if runs.is_dir():
        for item in runs.iterdir():
            if item.is_dir() and (item / "analysis_manifest.json").is_file():
                entries.append((item.stat().st_mtime, item))
    if not entries:
        return None
    entries.sort(key=lambda item: item[0], reverse=True)
    directory = entries[0][1]
    manifest = _read_json(directory / "analysis_manifest.json") or {}
    validation = _read_json(directory / "analysis_validation.json") or {}
    return {
        "directory": directory,
        "run_id": directory.name,
        "manifest": manifest,
        "valid": validation.get("status") == "complete" and manifest.get("status") == "complete",
        "created": manifest.get("created_at_utc"),
    }


def _pair_csv_rows(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "pair_metrics.csv"
    if not path.is_file():
        return []
    import csv
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def recommend() -> dict[str, Any]:
    """Build the current list of recommendations (advisory, ordered by priority)."""
    paths = load_runtime_paths()
    settings = load_settings(paths)
    enabled = {key: cfg.get("enabled", True) for key, cfg in settings["types"].items()}
    limits = {key: cfg.get("limit", 5) for key, cfg in settings["types"].items()}
    recommendations: list[dict[str, Any]] = []

    def add(rec_type: str, priority: int, title: str, body: str, action: dict[str, Any] | None) -> None:
        if not enabled.get(rec_type, True):
            return
        if sum(1 for rec in recommendations if rec["type"] == rec_type) >= limits.get(rec_type, 5):
            return
        recommendations.append({
            "type": rec_type,
            "priority": priority,
            "title": title,
            "body": body,
            "action": action,
        })

    # --- stage1 integrity ---
    try:
        integrity = stage1_integrity_snapshot(paths)
        if integrity["unchanged"]:
            add("stage1_integrity", 90, "Stage 1 не изменён ✓",
                "Хэш evidence-датасета совпадает с базовым — откат и повторные прогоны гарантированы.",
                None)
        else:
            add("stage1_integrity", 99, "⚠ Stage 1 ИЗМЕНЁН",
                "Хэш evidence-датасета отличается от базового. Оригинальные данные первого этапа не должны меняться — проверьте, кто их модифицировал.",
                {"kind": "open_integrity"})
    except Exception:  # noqa: BLE001
        pass

    # --- no stage2 ---
    run_info = _latest_run_info()
    if run_info is None:
        add("no_stage2", 95, "Запустите Stage 2",
            "Завершённых прогонов анализа нет. Запустите Stage 2 из профиля (или по всему Stage 1), чтобы получить сравнения, калиброванные пороги и находки.",
            {"kind": "open_runs"})
    else:
        if not run_info["valid"]:
            add("run_invalid", 94, f"Прогон {run_info['run_id']} не завершён",
                "Последний Stage 2 run невалиден. Можно повторить с тем же конфигом (retry) или удалить и запустить заново — Stage 1 при этом не затрагивается.",
                {"kind": "open_run", "run_id": run_info["run_id"]})
        else:
            # reports missing?
            stage3 = paths.stage3_root
            reports: list[Path] = []
            reports_dir = stage3 / "reports"
            if reports_dir.is_dir():
                reports = [item for item in reports_dir.iterdir() if item.is_dir() and (item / "report_config.json").is_file()]
            if (stage3 / "report_data.json").is_file():
                reports.append(stage3)
            if not reports:
                add("report_missing", 85, "Сформируйте отчёт Stage 3",
                    f"Run {run_info['run_id']} завершён, но отчётов ещё нет. Сформируйте technical/internal/public отчёт — это можно повторять без пересчёта Stage 2.",
                    {"kind": "open_reports", "run_id": run_info["run_id"]})
            else:
                public_exists = any((item / "report_config.json").is_file() and
                                    (_read_json(item / "report_config.json") or {}).get("mode") == "public"
                                    for item in reports)
                if not public_exists:
                    add("public_report", 80, "Нет public-отчёта",
                        "Для публикации нужен observation-only отчёт с public-safety lint. Сформируйте его из завершённого run.",
                        {"kind": "open_reports", "run_id": run_info["run_id"]})

            # exceedance clusters from the run
            rows = _pair_csv_rows(run_info["directory"])
            per_bin: dict[str, int] = {}
            for row in rows:
                status = row.get("status")
                if status in ("elevated", "persistent_geometric_change", "coherent_jump_candidate",
                              "rate_change_candidate", "persistent_rate_change_candidate",
                              "rapid_change_candidate", "persistent_rapid_change_candidate"):
                    per_bin[row.get("pose_bin", "?")] = per_bin.get(row.get("pose_bin", "?"), 0) + 1
            for pose, count in sorted(per_bin.items(), key=lambda item: item[1], reverse=True):
                if count >= DEFAULT_THRESHOLDS["exceedance_min_pairs"]:
                    add("exceedance_cluster", 75, f"{count} тревожных пар в бине {pose}",
                        "Соседние пары с превышением калиброванного шума. Откройте Landmark Comparison и проверьте вручную.",
                        {"kind": "open_landmarks", "pose": pose})

            # return events
            returns = _read_json(run_info["directory"] / "baseline_return.json") or {}
            return_count = int(returns.get("event_count", 0))
            if return_count > 0:
                add("return_events", 70, f"{return_count} событий возврата к состоянию",
                    "Форма возвращалась к предыдущим состояниям. Включите слой «Аномалии» на таймлайне (↩) и проверьте даты.",
                    {"kind": "open_timeline"})

            # findings unviewed
            changes = _read_json(run_info["directory"] / "change_points.json") or {}
            change_count = len(changes.get("change_points", []))
            if change_count > 0:
                add("findings_unviewed", 72, f"{change_count} change-point в хронологии",
                    "Stage 2 зафиксировал устойчивые изменения. Включите флаги ⚑ на таймлайне.",
                    {"kind": "open_timeline"})

    # --- stale profile vs run ---
    try:
        from .analysis_profiles import list_profiles as _list_profiles
        profiles = _list_profiles(paths)
        for profile in profiles[:2]:
            if profile.get("locked"):
                continue
            if run_info and run_info.get("created"):
                updated = profile.get("updated_at")
                if updated and updated > run_info["created"]:
                    add("stale_profile_run", 78, f"Профиль «{profile.get('name')}» изменён после прогона",
                        "Фильтры/курация менялись после последнего Stage 2. Запустите новый run из профиля, чтобы результаты соответствовали выборке.",
                        {"kind": "open_profile", "profile_id": profile.get("id")})
    except Exception:  # noqa: BLE001
        pass

    # --- dense zones (stage1-based) ---
    try:
        from .timeline_findings import _dense_zones
        from .stage1_timeline import build_stage1_inventory
        inventory = build_stage1_inventory(paths.stage1_root)
        for pose in POSE_BINS:
            zones = _dense_zones([photo for photo in inventory["photos"] if photo.get("bucket") == pose])
            for zone in zones:
                add("dense_zones", 82, f"Зона перекопирования в {pose}: {zone['count']} фото за {zone['days']} дн",
                    f"Предлагается исключить {len(zone['remove'])} шумных фото (плохое качество, крайние позы, дубликаты).",
                    {"kind": "open_dense_zone", "pose": pose})
    except Exception:  # noqa: BLE001
        pass

    # --- coverage gaps ---
    try:
        from .stage1_timeline import build_stage1_inventory
        inventory = build_stage1_inventory(paths.stage1_root)
        for pose in POSE_BINS:
            dates = sorted(
                photo["date"] for photo in inventory["photos"]
                if photo.get("bucket") == pose and photo.get("date")
            )
            gaps: list[tuple[str, str, int]] = []
            for a, b in zip(dates, dates[1:]):
                days = (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
                if days > DEFAULT_THRESHOLDS["coverage_gap_days"]:
                    gaps.append((a, b, days))
            for a, b, days in gaps[:1]:
                add("coverage_gap", 68, f"Пропуск {days} дн в бине {pose}",
                    f"Между {a} и {b} нет фото. Выводы по этому периоду ограничены.",
                    {"kind": "open_timeline", "pose": pose})
    except Exception:  # noqa: BLE001
        pass

    # --- calibration gaps ---
    try:
        from .calibration_workspace import workspace_dashboard
        workspace = workspace_dashboard()
        if workspace.get("status") == "ready":
            for row in workspace.get("pose_bins", []):
                if row["persons_with_frames"] < DEFAULT_THRESHOLDS["calibration_min_persons"]:
                    add("calibration_gap", 66, f"Слабая калибровка бина {row['pose']}",
                        f"Только {row['persons_with_frames']}/7 персон имеют кадры в этом ракурсе — калиброванные пороги ненадёжны.",
                        {"kind": "open_calibration"})
    except Exception:  # noqa: BLE001
        pass

    # --- duplicates in selection ---
    try:
        photos = []
        if (paths.stage1_root / "main_timeline.csv").is_file():
            import csv as _csv
            with (paths.stage1_root / "main_timeline.csv").open(newline="", encoding="utf-8-sig") as handle:
                photos = list(_csv.DictReader(handle))
        dup_count = sum(1 for photo in photos if photo.get("near_duplicate_of"))
        if photos and dup_count / len(photos) >= DEFAULT_THRESHOLDS["duplicate_min_ratio"]:
            add("duplicate_heavy", 74, f"{dup_count} near-дубликатов в датасете",
                "Дубликаты искажают пары и выборку. Исключите их через фильтр «Исключить near duplicates» или вручную в профиле.",
                {"kind": "open_profiles"})
    except Exception:  # noqa: BLE001
        pass

    # --- log errors ---
    try:
        from .event_log import list_events
        errors = [event for event in list_events(limit=500) if event.get("level") == "error"]
        if errors:
            add("log_errors", 88, f"{len(errors)} ошибок в журнале",
                "Откройте панель логирования и проверьте последние ошибки (стек, путь).",
                {"kind": "open_logs"})
    except Exception:  # noqa: BLE001
        pass

    recommendations.sort(key=lambda rec: rec["priority"], reverse=True)
    return {
        "schema": RECOMMENDATIONS_SCHEMA,
        "generated_at": _utc(),
        "count": len(recommendations),
        "max_total": settings["max_total"],
        "recommendations": recommendations[: settings["max_total"]],
        "not_a_verdict": True,
    }
