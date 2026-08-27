#!/usr/bin/env python3
"""Build and validate the permanent function-verification control document.

Stdlib only. On first run, bootstraps the canonical JSON from the cleanup
register; later runs treat that JSON as the source of truth and regenerate only
marked Markdown sections, preserving the append-only Progress Ledger.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = PROJECT_ROOT / "docs/function_verification_master_checklist.json"
MARKDOWN_PATH = PROJECT_ROOT / "docs/FUNCTION_VERIFICATION_MASTER_CHECKLIST.md"
DEFAULT_REGISTER = Path("/Volumes/SDCARD/storage/function-closure-cleanup/function_register.json")
DEFAULT_HANDOFF = Path("/Volumes/SDCARD/storage/function-closure-cleanup/handoff_register.json")
DEFAULT_SUMMARY = Path("/Volumes/SDCARD/storage/function-closure-cleanup/UPDATED_SUMMARY.json")
GEN_BEGIN = "<!-- BEGIN GENERATED: function-checklist -->"
GEN_END = "<!-- END GENERATED: function-checklist -->"
LEDGER_BEGIN = "<!-- BEGIN MANUAL: progress-ledger (append-only) -->"
LEDGER_END = "<!-- END MANUAL: progress-ledger -->"
STATUSES = {
    "NOT_REVIEWED", "IN_PROGRESS", "FAILED", "BLOCKED_EXTERNAL",
    "CLOSED_BASIC", "CLOSED_STRONG",
}
STRONG_CRITERIA = [
    ("direct_positive_oracle", "direct positive oracle"),
    ("negative_fail_closed", "negative/fail-closed test"),
    ("boundary_property_metamorphic", "boundary/property/metamorphic test"),
    ("downstream_handoff_assertion", "downstream consumer/handoff assertion"),
    ("schema_finite_null_semantics", "schema/finite/null semantics"),
    ("deterministic_evidence", "deterministic evidence"),
    ("regression_test_present", "regression test committed/present"),
]

# Ordered by pipeline dependency. A function receives the first matching scope.
SCOPE_RULES = [
    ("input-provenance-date-duplicates", "Input, provenance, dates, duplicates", ["input_provenance", "date_provenance", "same_day", "temporal_axis", "archive_adapter", "provenance_ledger"]),
    ("image-decoding-orientation", "Image decoding and orientation", ["utils.py", "photo_fields.py", "authenticity/extract"]),
    ("stage1-geometry-pose-naming", "Stage1 geometry, pose, naming", ["stage1/geometry", "stage1/naming"]),
    ("reconstruction-assets-masks-visibility", "Reconstruction, assets, masks, visibility", ["stage1/reconstruction", "stage1/assets", "stage1/masks", "skin_zone_atlas"]),
    ("stage1-storage-schema-manifest", "Stage1 storage, schema, manifest", ["stage1/storage", "stage1/engine", "stage1/config", "stage1/validator", "run_stage1"]),
    ("calibration-loading-balance", "Calibration loading and balance", ["calibration", "noise_calibration", "angle_noise", "mesh_calibration", "calibration_index", "run_calibration"]),
    ("pair-planning-anchors", "Pair planning and anchors", ["pair_planner", "anchor_policy", "pair_row_patch", "hard_negative"]),
    ("coordinate-alignment-motion", "Coordinate alignment and motion", ["motion", "space_selection", "landmark_policy", "pose_policy", "pose_leakage"]),
    ("visibility-zones", "Visibility and zones", ["visibility_gate", "primary_zones", "generate_mesh_zones", "skin_zones"]),
    ("expression-quality-gates", "Expression and quality gates", ["expression", "quality_gate", "quality_integration", "quality_stratification", "analysis_policy"]),
    ("descriptors-mesh-texture", "Descriptors, mesh, texture", ["descriptor", "mesh_dense", "texture", "uv_comparison"]),
    ("statistics-ess-ci", "Statistics, ESS, confidence intervals", ["robustness", "core.py", "metric_registry", "calibration_sensitivity"]),
    ("fdr-multiple-testing", "FDR and multiple testing", ["fdr_control", "multiple_testing"]),
    ("chronology-return-change", "Chronology, return, change", ["chronology", "irreversible_return", "baseline_return", "alpha_chronology"]),
    ("evidence-candidate-corroboration", "Evidence, candidates, corroboration", ["evidence.py", "leads.py", "corroboration", "private_hypothesis"]),
    ("stage2-export-manifest", "Stage2 export and manifest", ["stage2/export", "run_manifest", "snapshot_canonical", "postprocess_reports", "technical_summary"]),
    ("stage2b", "Stage2B", ["stage2b", "run_stage2b"]),
    ("stage3-reporting-public-safety", "Stage3, reporting, public safety", ["stage3", "run_stage3", "api/report", "system_health"]),
    ("api-loaders-settings-jobs", "API loaders, settings, jobs", ["api/jobs", "api/settings", "bfm_topology", "key_catalog"]),
    ("api-compare-report-review-timeline", "API compare, review, timeline", ["api/compare", "api/review", "research_timeline", "stage1_timeline", "pair_metrics", "ui_fields"]),
    ("cross-stage-handoffs-determinism-resume-security", "Cross-stage handoffs, determinism, resume, security", ["loaders.py", "integrity", "validation", "golden_fixture", "legacy_bridge", "server.py", "run_preflight", "scenario_planner", "fetch_external_assets", "__init__.py"]),
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def scope_for(entry: dict[str, Any]) -> tuple[str, str]:
    text = (entry["relative_file"] + " " + entry["qualified_name"]).lower()
    for key, title, needles in SCOPE_RULES:
        if any(n.lower() in text for n in needles):
            return key, title
    stage = entry["stage_module"]
    fallback = {
        "Stage1": ("stage1-storage-schema-manifest", "Stage1 storage, schema, manifest"),
        "Stage2": ("cross-stage-handoffs-determinism-resume-security", "Cross-stage handoffs, determinism, resume, security"),
        "Stage2B": ("stage2b", "Stage2B"),
        "Stage3": ("stage3-reporting-public-safety", "Stage3, reporting, public safety"),
        "API": ("api-loaders-settings-jobs", "API loaders, settings, jobs"),
        "Calibration": ("calibration-loading-balance", "Calibration loading and balance"),
        "Orchestration/Shared": ("cross-stage-handoffs-determinism-resume-security", "Cross-stage handoffs, determinism, resume, security"),
    }
    return fallback[stage]


def evidence_state(src: dict[str, Any], handoffs: list[str]) -> dict[str, bool]:
    unit = list(src.get("unit_evidence") or [])
    neg = list(src.get("negative_boundary_evidence") or [])
    integ = list(src.get("integration_e2e_evidence") or [])
    all_text = " ".join(unit + neg + integ).lower()
    downstream = list(src.get("downstream_consumers") or [])
    return {
        "direct_positive_oracle": bool(unit),
        "negative_fail_closed": bool(neg),
        # Do not infer a property oracle from execution or symbol references.
        "boundary_property_metamorphic": any(w in all_text for w in ("property", "metamorphic", "boundary")),
        "downstream_handoff_assertion": bool(handoffs and integ) or bool(downstream and integ),
        "schema_finite_null_semantics": any(w in all_text for w in ("schema", "finite", "nan", "null")),
        "deterministic_evidence": any(w in all_text for w in ("determin", "reproduc", "hash")),
        "regression_test_present": any("test" in x.lower() for x in unit + neg),
    }


def make_packages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_scope: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    titles = {key: title for key, title, _ in SCOPE_RULES}
    for entry in entries:
        key, _ = scope_for(entry)
        by_scope[key].append(entry)
    packages: list[dict[str, Any]] = []
    carry: list[dict[str, Any]] = []
    carry_scopes: list[str] = []
    ordered_keys = [x[0] for x in SCOPE_RULES]
    for index, key in enumerate(ordered_keys):
        items = sorted(by_scope.get(key, []), key=lambda x: x["id"])
        if not items:
            continue
        combined = carry + items
        scopes = carry_scopes + [key]
        is_last_nonempty = not any(by_scope.get(k) for k in ordered_keys[index + 1:])
        if len(combined) < 10 and not is_last_nonempty:
            carry, carry_scopes = combined, scopes
            continue
        carry, carry_scopes = [], []
        chunks = max(1, math.ceil(len(combined) / 25))
        base, extra = divmod(len(combined), chunks)
        pos = 0
        for chunk_i in range(chunks):
            size = base + (1 if chunk_i < extra else 0)
            chunk = combined[pos:pos + size]
            pos += size
            chunk_scope_keys = []
            for e in chunk:
                sk, _ = scope_for(e)
                if sk not in chunk_scope_keys:
                    chunk_scope_keys.append(sk)
            packages.append({
                "package_id": f"PKG-{len(packages)+1:03d}",
                "scope": " + ".join(titles[s] for s in chunk_scope_keys),
                "scope_keys": chunk_scope_keys,
                "function_ids": [e["id"] for e in chunk],
                "prerequisites": ([packages[-1]["package_id"]] if packages else []),
                "test_command_template": "python3 -m pytest -q {targeted_test_paths} --maxfail=1",
                "required_fixture": "Immutable minimal fixture for this scope; synthetic boundary/null variants; no mutation of photo or calibration sources.",
                "expected_artifacts": ["pytest result/log", "oracle outputs or hashes", "handoff/schema assertions", "regression test path"],
                "closure_definition": "Every function satisfies all seven CLOSED_STRONG criteria; failures are fixed in production and covered by a committed regression test.",
                "status": "NOT_REVIEWED",
            })
    if carry:
        if not packages:
            raise ValueError("cannot package fewer than ten functions")
        packages[-1]["function_ids"].extend(e["id"] for e in carry)
        packages[-1]["scope"] += " + " + " + ".join(titles[s] for s in carry_scopes)
        packages[-1]["scope_keys"].extend(carry_scopes)
    return packages


def bootstrap(register_path: Path, handoff_path: Path, summary_path: Path) -> dict[str, Any]:
    register = read_json(register_path)
    handoffs_raw = read_json(handoff_path)
    summary = read_json(summary_path)
    if len(register) != 585:
        raise ValueError(f"expected 585 production callables, got {len(register)}")
    source_ids = [x["id"] for x in register]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source register contains duplicate IDs")
    data = [x for x in register if x.get("data_bearing")]
    source_counts = collections.Counter(x["closure_status"] for x in data)
    expected = {"CLOSED_BASIC": 213, "REVIEW_REQUIRED": 352, "BLOCKED_EXTERNAL": 2}
    if len(data) != 567 or dict(source_counts) != expected:
        raise ValueError(f"cleanup arithmetic mismatch: data={len(data)}, counts={dict(source_counts)}")
    handoff_by_function: dict[str, list[str]] = collections.defaultdict(list)
    handoff_details = []
    for h in handoffs_raw:
        handoff_details.append({
            "handoff_id": h["handoff_id"], "boundary": h["boundary"],
            "schema_invariants": h["schema_invariants"], "status": h["status"],
            "verification": h.get("verification", []),
        })
        for fid in set(h.get("producers", []) + h.get("consumers", [])):
            handoff_by_function[fid].append(h["handoff_id"])
    records = []
    source_to_status = {"REVIEW_REQUIRED": "NOT_REVIEWED", "CLOSED_BASIC": "CLOSED_BASIC", "BLOCKED_EXTERNAL": "BLOCKED_EXTERNAL"}
    for src in sorted(data, key=lambda x: x["id"]):
        expected_id = f'{src["relative_file"]}::{src["qualified_name"]}'
        if src["id"] != expected_id:
            raise ValueError(f"unstable source ID: {src['id']} != {expected_id}")
        hs = sorted(handoff_by_function.get(src["id"], []))
        state = evidence_state(src, hs)
        records.append({
            "id": src["id"],
            "relative_file": src["relative_file"],
            "qualified_name": src["qualified_name"],
            "stage_module": src["stage_module"],
            "data_role": src["data_role"],
            "risk": src["risk"],
            "status": source_to_status[src["closure_status"]],
            "batch_id": None,
            "handoffs": hs,
            "evidence_links": {
                "unit": src.get("unit_evidence", []),
                "negative_boundary": src.get("negative_boundary_evidence", []),
                "integration_e2e": src.get("integration_e2e_evidence", []),
                "enhanced_reachability": src.get("enhanced_reachability_evidence", []),
            },
            "required_checks": [label for _, label in STRONG_CRITERIA],
            "evidence_state": state,
            "missing_evidence": [label for key, label in STRONG_CRITERIA if not state[key]],
            "last_run": None,
            "last_run_date": None,
            "result": None,
            "blocker": src["closure_reason"] if src["closure_status"] == "BLOCKED_EXTERNAL" else None,
            "notes": src.get("closure_reason", ""),
            "source_lines": {"start": src.get("line_start"), "end": src.get("line_end")},
        })
    packages = make_packages(records)
    assignment = {}
    for package in packages:
        for fid in package["function_ids"]:
            if fid in assignment:
                raise ValueError(f"duplicate package assignment: {fid}")
            assignment[fid] = package["package_id"]
    for record in records:
        record["batch_id"] = assignment[record["id"]]
    return {
        "schema_version": "1.0",
        "document_type": "function-verification-master-checklist",
        "generated_at_utc": utc_now(),
        "policy": {
            "allowed_statuses": sorted(STATUSES),
            "closed_strong_criteria": [label for _, label in STRONG_CRITERIA],
            "rule": "CLOSED_STRONG requires all seven criteria. A green aggregate suite alone never closes a function.",
        },
        "source_metadata": {
            "production_callables": 585,
            "data_bearing": 567,
            "dead": 0,
            "register_path": str(register_path),
            "register_sha256": sha256(register_path),
            "handoff_register_path": str(handoff_path),
            "handoff_register_sha256": sha256(handoff_path),
            "updated_summary_path": str(summary_path),
            "updated_summary_sha256": sha256(summary_path),
            "cleanup_input_fingerprint_sha256": summary.get("input_fingerprint_sha256"),
        },
        "recommended_next_batch": packages[0]["package_id"],
        "packages": packages,
        "handoffs": handoff_details,
        "functions": records,
        "progress_runs": [],
    }


def validate(doc: dict[str, Any]) -> dict[str, Any]:
    functions = doc.get("functions", [])
    packages = doc.get("packages", [])
    errors = []
    ids = [f.get("id") for f in functions]
    if len(functions) != 567:
        errors.append(f"expected 567 functions, got {len(functions)}")
    if len(set(ids)) != len(ids):
        errors.append("function IDs are not unique")
    assignment = collections.Counter(fid for p in packages for fid in p.get("function_ids", []))
    for fid in ids:
        if assignment[fid] != 1:
            errors.append(f"{fid}: package membership={assignment[fid]}, expected 1")
    extras = sorted(set(assignment) - set(ids))
    if extras:
        errors.append(f"package list contains {len(extras)} unknown IDs")
    package_ids = {p.get("package_id") for p in packages}
    for f in functions:
        expected_id = f'{f.get("relative_file")}::{f.get("qualified_name")}'
        if f.get("id") != expected_id:
            errors.append(f"unstable ID: {f.get('id')}")
        if f.get("status") not in STATUSES:
            errors.append(f"{f.get('id')}: invalid status {f.get('status')}")
        if f.get("batch_id") not in package_ids or assignment[f.get("id")] != 1:
            errors.append(f"{f.get('id')}: invalid batch_id")
        if f.get("status") == "CLOSED_STRONG":
            state = f.get("evidence_state", {})
            missing = [label for key, label in STRONG_CRITERIA if not state.get(key)]
            if missing or f.get("missing_evidence"):
                errors.append(f"{f.get('id')}: CLOSED_STRONG lacks evidence: {missing}")
    counts = collections.Counter(f["status"] for f in functions)
    if sum(counts.values()) != 567:
        errors.append("status arithmetic does not total 567")
    if errors:
        raise ValueError("validation failed:\n- " + "\n- ".join(errors[:50]))
    return {
        "counts": dict(counts),
        "critical_remaining": sum(f["risk"] == "critical" and f["status"] not in {"CLOSED_BASIC", "CLOSED_STRONG"} for f in functions),
        "high_remaining": sum(f["risk"] == "high" and f["status"] not in {"CLOSED_BASIC", "CLOSED_STRONG"} for f in functions),
    }


def generated_markdown(doc: dict[str, Any], metrics: dict[str, Any]) -> str:
    c = collections.Counter(metrics["counts"])
    lines = [
        GEN_BEGIN,
        "## Dashboard",
        "",
        "| Metric | Count |",
        "|---|---:|",
        "| Total data-bearing | 567 |",
        f'| CLOSED_STRONG | {c["CLOSED_STRONG"]} |',
        f'| CLOSED_BASIC | {c["CLOSED_BASIC"]} |',
        f'| IN_PROGRESS | {c["IN_PROGRESS"]} |',
        f'| FAILED | {c["FAILED"]} |',
        f'| BLOCKED_EXTERNAL | {c["BLOCKED_EXTERNAL"]} |',
        f'| NOT_REVIEWED | {c["NOT_REVIEWED"]} |',
        f'| Critical remaining | {metrics["critical_remaining"]} |',
        f'| High remaining | {metrics["high_remaining"]} |',
        "",
        f'**Recommended next batch:** `{doc["recommended_next_batch"]}`.',
        "",
        "## Executable packages",
        "",
        "Run in listed dependency order. Commands are templates: replace `{targeted_test_paths}` with tests created/mapped for that package.",
        "",
    ]
    by_id = {f["id"]: f for f in doc["functions"]}
    for p in doc["packages"]:
        statuses = collections.Counter(by_id[fid]["status"] for fid in p["function_ids"])
        lines += [
            f'### {p["package_id"]} — {p["scope"]}',
            "",
            f'- **Status:** `{p["status"]}`; **functions:** {len(p["function_ids"])}; **prerequisites:** {", ".join(p["prerequisites"]) or "none"}',
            f'- **Command:** `{p["test_command_template"]}`',
            f'- **Fixture:** {p["required_fixture"]}',
            f'- **Expected artifacts:** {"; ".join(p["expected_artifacts"])}',
            f'- **Closure:** {p["closure_definition"]}',
            "",
            "| Done | Function ID | Risk | Current status | Missing strong evidence |",
            "|---|---|---|---|---:|",
        ]
        for fid in p["function_ids"]:
            f = by_id[fid]
            checked = "x" if f["status"] == "CLOSED_STRONG" else " "
            lines.append(f'| [{checked}] | `{fid}` | {f["risk"]} | {f["status"]} | {len(f["missing_evidence"])} |')
        lines.append("")
    blocked = [f for f in doc["functions"] if f["status"] == "BLOCKED_EXTERNAL"]
    lines += ["## BLOCKED_EXTERNAL", ""]
    for f in blocked:
        lines.append(f'- `{f["id"]}` — {f["blocker"]}')
    lines += ["", "## Arithmetic and integrity", "", f'- Production callables: {doc["source_metadata"]["production_callables"]}', '- Data-bearing: 567 = CLOSED_STRONG + CLOSED_BASIC + IN_PROGRESS + FAILED + BLOCKED_EXTERNAL + NOT_REVIEWED.', f'- Unique IDs: {len(set(by_id))}; exactly-one-package assignments: {sum(len(p["function_ids"]) for p in doc["packages"])}.', f'- Register SHA-256: `{doc["source_metadata"]["register_sha256"]}`', "", GEN_END]
    return "\n".join(lines)


def base_markdown(generated: str) -> str:
    return "\n".join([
        "# Function Verification Master Checklist",
        "",
        "> Permanent control document for gradual strict closure of every data-bearing production function. The canonical full records are in `docs/function_verification_master_checklist.json`.",
        "",
        "## Status workflow and strict closure policy",
        "",
        "`NOT_REVIEWED → IN_PROGRESS → FAILED | BLOCKED_EXTERNAL | CLOSED_BASIC → CLOSED_STRONG`.",
        "",
        "`CLOSED_STRONG` requires, for the individual function: direct positive oracle; negative/fail-closed test; boundary/property/metamorphic test; downstream consumer/handoff assertion; schema/finite/null semantics; deterministic evidence; and a committed/present regression test. **A green aggregate suite alone does not close a function.** Never promote without recorded evidence in JSON.",
        "",
        generated,
        "",
        "## Update procedure",
        "",
        "1. Before a batch, record baseline commit/worktree state and source/fixture hashes in the ledger.",
        "2. Mark the package/functions `IN_PROGRESS` in JSON; run the package command with immutable fixtures.",
        "3. For failures: identify root cause → fix production code → add focused regression. Do not weaken an oracle.",
        "4. Update each function record: evidence links/state, missing evidence, last run/date, result, blocker, notes and status.",
        "5. Run `python3 scripts/update_function_checklist.py`; it validates uniqueness, arithmetic, statuses and exactly-one batch membership, then refreshes generated Markdown.",
        "6. Run full regression, record result, then run `python3 scripts/update_function_checklist.py --check`.",
        "7. Commit JSON, Markdown, tests and any production fix together. Append a ledger row; never rewrite historical rows.",
        "",
        "Bootstrap only (if canonical JSON is absent):",
        "",
        "```bash",
        "python3 scripts/update_function_checklist.py --source-register /Volumes/SDCARD/storage/function-closure-cleanup/function_register.json",
        "python3 scripts/update_function_checklist.py --check",
        "```",
        "",
        "## Progress Ledger",
        "",
        LEDGER_BEGIN,
        "| UTC date | Batch | Baseline commit/state | Input/fixture hashes | Command | Result | Production fix | Regression/evidence | Operator/notes |",
        "|---|---|---|---|---|---|---|---|---|",
        "| YYYY-MM-DDTHH:MM:SSZ | PKG-NNN | commit + clean/dirty | sha256:… | `…` | PASS/FAIL/BLOCKED | paths/commit or none | test paths/artifacts | append only |",
        LEDGER_END,
        "",
    ])


def render(doc: dict[str, Any]) -> str:
    metrics = validate(doc)
    generated = generated_markdown(doc, metrics)
    if not MARKDOWN_PATH.exists():
        return base_markdown(generated)
    old = MARKDOWN_PATH.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(GEN_BEGIN) + r".*?" + re.escape(GEN_END), re.DOTALL)
    if not pattern.search(old):
        raise ValueError("existing Markdown lacks generated markers; refusing destructive overwrite")
    return pattern.sub(generated, old, count=1)


def serialized(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate and fail if generated files differ")
    parser.add_argument("--source-register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--handoff-register", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--updated-summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    if JSON_PATH.exists():
        doc = read_json(JSON_PATH)
    else:
        if args.check:
            raise SystemExit(f"missing canonical JSON: {JSON_PATH}")
        doc = bootstrap(args.source_register, args.handoff_register, args.updated_summary)
    metrics = validate(doc)
    expected_md = render(doc)
    if args.check:
        current_json = JSON_PATH.read_text(encoding="utf-8")
        if current_json != serialized(doc):
            raise SystemExit("canonical JSON formatting is not reproducible; run update mode")
        if not MARKDOWN_PATH.exists() or MARKDOWN_PATH.read_text(encoding="utf-8") != expected_md:
            raise SystemExit("generated Markdown is stale; run update mode")
        print(f"OK: 567 unique functions, {len(doc['packages'])} packages, arithmetic={metrics['counts']}")
        return 0
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(serialized(doc), encoding="utf-8")
    MARKDOWN_PATH.write_text(expected_md, encoding="utf-8")
    print(f"UPDATED: {JSON_PATH}")
    print(f"UPDATED: {MARKDOWN_PATH}")
    print(f"VALID: 567 unique functions in {len(doc['packages'])} exactly-one packages; {metrics['counts']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
