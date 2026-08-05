"""Каталог завершённых и активных прогонов анализа профилей (Iteration 06).

Хранилище — каталог ``<storage_root>/analysis_runs/<run_id>/`` с файлами:

- ``run_summary.json`` (финальная сводка, пишется runner'ом при успехе);
- ``selection_manifest.snapshot.json`` (копия манифеста, использованного в прогоне);
- ``stage2/`` (вывод Stage 2 с pair_metrics.csv и analysis_manifest.json);
- ``stage3/`` (отчёт Stage 3);
- ``STATUS.json`` (текущее состояние: running/pending/complete/failed/cancelled/blocked).

🚨 WARNING: модуль читает только публичные артефакты, никогда не пытается
запускать Stage 2/Stage 3. Если артефакта нет, метод возвращает HTTP 404.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_config import RuntimePaths, load_runtime_paths

RUN_SCHEMA = "deeputin-analysis-run-v1.0"
RUNS_DIRECTORY = "analysis_runs"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class _Pagination:
    offset: int
    limit: int

    @classmethod
    def build(cls, offset: int | None = None, limit: int | None = None, *, default: int = 100, maximum: int = 500) -> "_Pagination":
        return cls(
            offset=max(0, int(offset or 0)),
            limit=max(1, min(int(limit or default), maximum)),
        )


def _runs_root(paths: RuntimePaths | None = None) -> Path:
    return (paths or load_runtime_paths()).storage_root / RUNS_DIRECTORY


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run_status(run_dir: Path, summary: dict[str, Any] | None) -> dict[str, Any]:
    """Текущее состояние прогона по наличию артефактов."""
    status_path = run_dir / "STATUS.json"
    explicit = _read_json(status_path)
    if explicit:
        return explicit
    if summary is not None and (run_dir / "stage3" / "report_data.json").is_file():
        return {
            "schema": "deeputin-analysis-run-status-v1.0",
            "status": "complete",
            "updated_at": summary.get("frozen_at") or _utc(),
        }
    if (run_dir / "stage2" / "analysis_manifest.json").is_file():
        return {
            "schema": "deeputin-analysis-run-status-v1.0",
            "status": "stage2_done",
            "updated_at": _utc(),
        }
    return {
        "schema": "deeputin-analysis-run-status-v1.0",
        "status": "unknown",
        "updated_at": None,
    }


def _run_summary_block(run_dir: Path) -> dict[str, Any]:
    summary = _read_json(run_dir / "run_summary.json")
    status = _run_status(run_dir, summary)
    payload: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "not_a_verdict": True,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "status": status.get("status"),
        "status_updated_at": status.get("updated_at"),
        "selected_at": summary.get("selected_at") if isinstance(summary, dict) else None,
        "included_count": summary.get("included_count") if isinstance(summary, dict) else None,
        "profile_id": summary.get("profile_id") if isinstance(summary, dict) else None,
        "stage2_output": summary.get("stage2_output") if isinstance(summary, dict) else None,
        "stage3_output": summary.get("stage3_output") if isinstance(summary, dict) else None,
        "has_summary": bool(summary),
        "has_stage2": (run_dir / "stage2" / "analysis_manifest.json").is_file(),
        "has_stage3": (run_dir / "stage3" / "report_data.json").is_file(),
    }
    if summary is not None:
        payload["selection_manifest_digest"] = summary.get("selection_manifest_digest")
        # Phases из run_summary.json живут там же, где и в Job; в файл кладёт runner.
        payload["phases"] = list(summary.get("phases") or [])
    return payload


def list_analysis_runs(
    *, profile_id: str | None = None,
    offset: int | None = None, limit: int | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    """📚 Перечислить прогоны анализа профилей, отсортированные по времени (новые первые)."""
    root = _runs_root(paths)
    if not root.is_dir():
        return {"schema": RUN_SCHEMA, "not_a_verdict": True, "count": 0, "runs": []}
    entries: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not child.is_dir():
            continue
        record = _run_summary_block(child)
        if profile_id is not None and record.get("profile_id") != profile_id:
            continue
        entries.append(record)
    page = _Pagination.build(offset, limit)
    total = len(entries)
    sliced = entries[page.offset:page.offset + page.limit]
    return {
        "schema": RUN_SCHEMA, "not_a_verdict": True,
        "count": total, "offset": page.offset, "limit": page.limit,
        "has_more": page.offset + page.limit < total,
        "runs": sliced,
    }


def get_analysis_run(run_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    """📄 Детали одного прогона + его сводка."""
    safe_id = re.sub(r"[^A-Za-z0-9_\-]", "", run_id)
    if not safe_id or safe_id != run_id:
        raise ValueError(f"invalid run_id: {run_id}")
    root = _runs_root(paths)
    run_dir = root / safe_id
    if not run_dir.is_dir():
        raise FileNotFoundError(run_id)
    summary = _read_json(run_dir / "run_summary.json") or {}
    block = _run_summary_block(run_dir)
    if summary:
        block["summary"] = summary
    if summary.get("stage2") and isinstance(summary["stage2"], dict):
        block["stage2_manifest"] = summary["stage2"]
    return block


def _pair_metrics_path(run_dir: Path) -> Path | None:
    candidate = run_dir / "stage2" / "pair_metrics.csv"
    return candidate if candidate.is_file() else None


def list_analysis_run_pairs(
    run_id: str, *, offset: int | None = None, limit: int | None = None,
    pose_bin: str | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    """📑 Список пар из ``stage2/pair_metrics.csv`` с лёгкой пагинацией.

    🚨 Возвращаются только публичные метрики пар (id + статус + ключевые
    сводные числа), чтобы payload оставался компактным. Полная матрица
    метрик берётся через существующий ``/api/v1/pairs/{a}/{b}/metrics``.
    """
    safe_id = re.sub(r"[^A-Za-z0-9_\-]", "", run_id)
    if not safe_id or safe_id != run_id:
        raise ValueError(f"invalid run_id: {run_id}")
    root = _runs_root(paths)
    run_dir = root / safe_id
    if not run_dir.is_dir():
        raise FileNotFoundError(run_id)
    csv_path = _pair_metrics_path(run_dir)
    if csv_path is None:
        return {
            "schema": RUN_SCHEMA, "not_a_verdict": True, "run_id": safe_id,
            "count": 0, "offset": 0, "limit": 0, "has_more": False, "pairs": [],
            "missing": "stage2/pair_metrics.csv not found",
        }

    page = _Pagination.build(offset, limit, default=200, maximum=500)
    rows: list[dict[str, Any]] = []
    total = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row in reader:
            total += 1
            pair_bin = str(row.get("pose_bin_a") or row.get("pose_bin") or row.get("bucket") or "")
            if pose_bin is not None and pair_bin != pose_bin:
                continue
            entry = _summarize_pair_row(row, fieldnames)
            entry["pose_bin"] = pair_bin
            if page.offset <= total - 1 < page.offset + page.limit:
                rows.append(entry)
    return {
        "schema": RUN_SCHEMA, "not_a_verdict": True, "run_id": safe_id,
        "count": total, "offset": page.offset, "limit": page.limit,
        "has_more": page.offset + page.limit < total,
        "pairs": rows,
        "fields": _safe_pair_columns(fieldnames),
    }


def _safe_pair_columns(fieldnames: list[str]) -> list[str]:
    """Оставляем только публичные/безопасные колонки для сводки пар."""
    public = {"photo_a", "photo_b", "pose_bin", "pose_bin_a", "pose_bin_b", "status",
              "score", "landmark_distance", "landmark_distance_134", "landmark_distance_106",
              "mesh_distance", "texture_distance", "pair_id", "index_pose_bin"}
    return [c for c in fieldnames if c in public]


def _summarize_pair_row(row: dict[str, str], fieldnames: list[str]) -> dict[str, Any]:
    keys = _safe_pair_columns(fieldnames)
    summary: dict[str, Any] = {}
    for key in keys:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        if key in {"landmark_distance", "landmark_distance_106", "landmark_distance_134",
                   "mesh_distance", "texture_distance", "score"}:
            try:
                summary[key] = float(raw)
            except (TypeError, ValueError):
                summary[key] = raw
        else:
            summary[key] = raw
    if "photo_a" in summary and "photo_b" in summary:
        summary["pair"] = f"{summary['photo_a']}/{summary['photo_b']}"
    return summary


__all__ = [
    "RUN_SCHEMA",
    "list_analysis_runs",
    "get_analysis_run",
    "list_analysis_run_pairs",
]
