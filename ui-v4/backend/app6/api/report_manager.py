"""Stage 3 Report Manager (Iteration 06).

Creates versioned reports from a specific Stage 2 run, re-runs Stage 3
rendering on demand, and exports the report in several formats
(JSON/CSV/HTML). A report is always linked to exactly one Stage 2 run and one
Stage 2 run can support several reports (different modes, labels, dates).

Report layout under ``<storage>/stage3/reports/``:

    report_YYYYMMDD_HHMMSS/
      report_config.json   — frozen config (run_id, mode, label, created_at)
      report_data.json     — Stage 3 engine output (data)
      index.html           — Stage 3 engine HTML report
      report_validation.json
      exports/
        pairs.csv          — pair metrics projection (public-mode filtered)
        exclusions.csv     — skipped pairs / exclusion reasons
        provenance.csv     — date provenance of every compared photo
        report.json        — same content as report_data.json (convenience copy)
        summary.json       — counters
      public_lint.json     — public-safety lint result (public mode only)

Modes:
- technical — full measurement detail (internal expert use)
- internal  — evidence states + zones + leads (investigative team)
- public    — observation-only wording; runs the public-safety lint and
              refuses to include identity verdicts (engine already guarantees
              `not_a_verdict`; lint is a belt-and-braces gate).
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_config import RuntimePaths, ensure_runtime_write_dirs, load_runtime_paths

REPORT_MANAGER_SCHEMA = "deeputin-report-manager-v1.0"
REPORT_CONFIG_SCHEMA = "deeputin-report-config-v1.0"

# Terms that must never appear in a public report.
FORBIDDEN_PUBLIC_TERMS = (
    "двойник", "подмена", "замена личности", "пластика", "маска", "имитатор",
    "body double", "doppelganger", "replacement", "impostor", "clone",
    "вердикт", "доказано", "точно этот человек",
)

_PUBLIC_MODE_WITHHELD_PREFIXES = ("texture_", "uv_")


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------
def reports_root(paths: RuntimePaths | None = None) -> Path:
    current = paths or load_runtime_paths()
    ensure_runtime_write_dirs(current)
    root = current.stage3_root / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def report_dir(report_id: str, paths: RuntimePaths | None = None) -> Path:
    root = reports_root(paths)
    directory = (root / report_id).resolve()
    if root.resolve() not in directory.parents:
        raise ValueError(f"invalid report_id: {report_id}")
    return directory


def _next_report_id(paths: RuntimePaths | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    root = reports_root(paths)
    candidate = f"report_{stamp}"
    counter = 1
    while (root / candidate).exists():
        candidate = f"report_{stamp}_{counter:02d}"
        counter += 1
    return candidate


# --------------------------------------------------------------------------
# listing
# --------------------------------------------------------------------------
def list_reports(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    current = paths or load_runtime_paths()
    out: list[dict[str, Any]] = []
    root = current.stage3_root
    if (root / "report_data.json").is_file() and not (root / "reports").is_dir():
        out.append(_report_summary("legacy", root, legacy=True))
    reports_dir = root / "reports"
    if reports_dir.is_dir():
        for item in sorted(reports_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if item.is_dir() and item.name.startswith("report_"):
                out.append(_report_summary(item.name, item, legacy=False))
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out


def _report_summary(report_id: str, directory: Path, legacy: bool) -> dict[str, Any]:
    config = _read_json(directory / "report_config.json") or {}
    validation = _read_json(directory / "report_validation.json")
    data = _read_json(directory / "report_data.json")
    summary = data.get("summary") if data else None
    lint = _read_json(directory / "public_lint.json")
    exports_dir = directory / "exports"
    exports = sorted(p.name for p in exports_dir.iterdir()) if exports_dir.is_dir() else []
    return {
        "schema": REPORT_MANAGER_SCHEMA,
        "report_id": report_id,
        "legacy": legacy,
        "label": config.get("label") or report_id,
        "mode": config.get("mode") or "technical",
        "run_id": config.get("run_id"),
        "created_at": config.get("created_at"),
        "valid": bool(validation and validation.get("status") == "complete"),
        "validation_status": (validation or {}).get("status") if validation else None,
        "pair_count": (summary or {}).get("pair_count"),
        "change_count": (summary or {}).get("change_count"),
        "status_counts": (summary or {}).get("status_counts"),
        "files": sorted(p.name for p in directory.iterdir() if p.is_file()),
        "exports": exports,
        "public_lint": lint,
        "directory": str(directory),
    }


def get_report(report_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    if report_id == "legacy":
        directory = current.stage3_root
        if not (directory / "report_data.json").is_file():
            raise FileNotFoundError("legacy Stage 3 report not found")
        return _report_summary("legacy", directory, legacy=True)
    directory = report_dir(report_id, current)
    if not directory.is_dir():
        raise FileNotFoundError(f"report not found: {report_id}")
    return _report_summary(report_id, directory, legacy=False)


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------
#: Negation markers: a forbidden term inside a disclaimer sentence
#: ("X не доказывает маску") is a *safety statement*, not a claim. The lint
#: only flags affirmative uses.
_NEGATION_MARKERS = (
    "не доказывает", "не является", "не означает", "не доказано", "не подтвержда",
    "не устанавливает", "не свидетельствует", "не говорит", "no evidence",
    "does not prove", "not a verdict", "не выносит", "не утвержда",
    "не идентифициру", "не заменяет", "не может доказать", "не служит",
    "do not establish", "does not establish", "do not indicate", "does not indicate",
)


def _is_negated(text: str, start: int, term_len: int) -> bool:
    window = text[max(0, start - 90): min(len(text), start + term_len + 90)]
    return any(marker in window for marker in _NEGATION_MARKERS)


def _public_lint(data: dict[str, Any]) -> dict[str, Any]:
    """Public-safety lint over every string in the report payload."""
    violations: list[dict[str, str]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            lowered = value.lower()
            for term in FORBIDDEN_PUBLIC_TERMS:
                needle = term.lower()
                index = lowered.find(needle)
                while index != -1:
                    if not _is_negated(lowered, index, len(needle)):
                        violations.append({"path": path, "term": term})
                        break  # one violation per (string, term)
                    index = lowered.find(needle, index + 1)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else key)

    walk(data, "")
    return {
        "schema": "deeputin-public-lint-v1.0",
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations[:100],
        "forbidden_terms": list(FORBIDDEN_PUBLIC_TERMS),
    }


def _write_exports(report_dir_path: Path, run_dir: Path, data: dict[str, Any], mode: str) -> list[str]:
    exports = report_dir_path / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # pair metrics projection
    pairs_path = run_dir / "pair_metrics.csv"
    if pairs_path.is_file():
        rows = _read_csv_rows(pairs_path)
        if mode == "public":
            rows = [
                {k: v for k, v in row.items() if not str(k).startswith(_PUBLIC_MODE_WITHHELD_PREFIXES)}
                for row in rows
            ]
        if rows:
            with (exports / "pairs.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            written.append("pairs.csv")

    # exclusions
    skipped = run_dir / "skipped_pairs.csv"
    if skipped.is_file():
        rows = _read_csv_rows(skipped)
        if rows:
            with (exports / "exclusions.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            written.append("exclusions.csv")

    # provenance: date provenance of all involved photos from the timeline
    provenance_path = run_dir / "date_provenance.csv"
    if provenance_path.is_file():
        rows = _read_csv_rows(provenance_path)
        if rows:
            with (exports / "provenance.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            written.append("provenance.csv")

    with (exports / "report.json").open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    written.append("report.json")

    summary = {
        "schema": "deeputin-report-export-summary-v1.0",
        "pair_count": (data.get("summary") or {}).get("pair_count"),
        "exported_at": _utc(),
        "files": written,
    }
    with (exports / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=1)
    written.append("summary.json")
    return written


def _render_report(report_id: str, directory: Path, run_directory: Path, run_id: str,
                   mode: str, label: str | None, created_at: str,
                   paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Run the Stage 3 engine into an (empty) report dir, then write the
    report metadata ON TOP of the engine output.

    The Stage 3 engine wipes its output directory when overwrite=True, so any
    file placed in the report dir BEFORE the engine runs is destroyed — the
    config must be written after rendering.
    """
    from app6.stage3 import Stage3Config, Stage3Engine
    Stage3Engine(Stage3Config(run_directory, directory, overwrite=True)).run()

    data = _read_json(directory / "report_data.json")
    if data is None:
        raise RuntimeError("Stage 3 engine produced no report_data.json")

    config: dict[str, Any] = {
        "schema": REPORT_CONFIG_SCHEMA,
        "report_id": report_id,
        "label": label or f"Report · {mode} · {run_id}",
        "mode": mode,
        "run_id": run_id,
        "run_directory": str(run_directory),
        "created_at": created_at,
        "not_a_verdict": True,
    }
    _atomic_json(directory / "report_config.json", config)

    lint: dict[str, Any] | None = None
    if mode == "public":
        lint = _public_lint(data)
        _atomic_json(directory / "public_lint.json", lint)
        if lint["status"] != "pass":
            raise RuntimeError(f"public-safety lint failed with {lint['violation_count']} violations")

    exports = _write_exports(directory, run_directory, data, mode)
    return get_report(report_id, paths)


def generate_report(run_id: str, *, mode: str = "technical", label: str | None = None,
                    paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Generate a Stage 3 report from a completed Stage 2 run."""
    if mode not in ("technical", "internal", "public"):
        raise ValueError("mode must be one of: technical, internal, public")

    from .run_manager import get_run
    run = get_run(run_id, paths)
    run_directory = Path(run["directory"])
    if not run.get("valid"):
        raise RuntimeError(f"Stage 2 run {run_id} is not valid (status={run.get('status')})")

    report_id = _next_report_id(paths)
    directory = report_dir(report_id, paths)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        return _render_report(report_id, directory, run_directory, run_id, mode, label, _utc(), paths)
    except Exception:
        # do not leave a half-written report behind
        shutil.rmtree(directory, ignore_errors=True)
        raise


def regenerate_report(report_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Re-render a report from its linked Stage 2 run (no re-analysis)."""
    current = paths or load_runtime_paths()
    directory = report_dir(report_id, current)
    if not directory.is_dir():
        raise FileNotFoundError(f"report not found: {report_id}")
    config = _read_json(directory / "report_config.json")
    if not config or not config.get("run_id"):
        raise RuntimeError("report has no run_id in config; cannot regenerate")
    mode = config.get("mode") or "technical"
    label = config.get("label")
    created_at = config.get("created_at") or _utc()
    run_id = str(config["run_id"])

    run_directory = Path(config["run_directory"]) if config.get("run_directory") else None
    if run_directory is None or not (run_directory / "analysis_manifest.json").is_file():
        from .run_manager import get_run
        run = get_run(run_id, current)
        run_directory = Path(run["directory"])

    # the engine wipes the dir; metadata is rewritten on top by _render_report
    return _render_report(report_id, directory, run_directory, run_id, mode, label, created_at, current)
