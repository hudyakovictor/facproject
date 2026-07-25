"""✅ Чекер инвариантов: сравнивает результат пайплайна с ожиданиями сценария.
Пары ищет по меткам pXXfYYYYYY внутри photo_id в pair_metrics.csv."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import RED_STATUSES


def _rows(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _measured_pairs(rows: list[dict]) -> list[dict]:
    """Exclude technical sentinel rows; a measured pair must name both inputs."""
    return [
        row for row in rows
        if str(row.get("status", "")).strip() != "no_pairs"
        and str(row.get("photo_a", "")).strip()
        and str(row.get("photo_b", "")).strip()
    ]


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes")


def _find_pairs(pairs: list[dict], tag_a: str, tag_b: str) -> list[dict]:
    out = []
    for r in pairs:
        pa, pb = str(r.get("photo_a", "")), str(r.get("photo_b", ""))
        if (tag_a in pa and tag_b in pb) or (tag_a in pb and tag_b in pa):
            out.append(r)
    return out


def _skip_detail(skipped: list[dict], tag_a: str, tag_b: str) -> str:
    found = _find_pairs(skipped, tag_a, tag_b)
    if not found:
        return "not found in pair_metrics.csv or skipped_pairs.csv"
    parts = []
    for r in found[:5]:
        parts.append(
            f"skipped:{r.get('skip_reason') or r.get('status')} "
            f"{r.get('photo_a')}→{r.get('photo_b')} "
            f"expr=({r.get('expression_magnitude_a')},{r.get('expression_magnitude_b')}) "
            f"align=({r.get('alignment_quality_a')},{r.get('alignment_quality_b')})"
        )
    return "; ".join(parts)


def run_checks(manifest: dict, run_dir: Path) -> dict:
    s2 = run_dir / "stage2"
    raw_pairs = _rows(s2 / "pair_metrics.csv")
    pairs = _measured_pairs(raw_pairs)
    skipped = _rows(s2 / "skipped_pairs.csv")
    tags = {fr["n"]: fr["tag"] for fr in manifest["frames"]}
    results: list[dict] = []

    def add(name, ok, detail="", state=None):
        state = state or ("passed" if ok else "failed")
        results.append({"check": name, "ok": bool(ok), "state": state, "detail": str(detail)[:400]})

    val = _json(s2 / "analysis_validation.json")
    add("pipeline_complete", val.get("status") == "complete",
        val.get("errors") or ("нет analysis_validation.json" if not val else ""))

    for exp in manifest["scenario"].get("expect", []):
        t = exp["type"]
        if t == "no_red_pairs":
            skip = {frozenset(x) for x in exp.get("except_frames", [])}
            bad = []
            ks = sorted(tags)
            for i in ks:
                for j in ks:
                    if i < j and frozenset((i, j)) not in skip:
                        for r in _find_pairs(pairs, tags[i], tags[j]):
                            if str(r.get("status")) in RED_STATUSES:
                                bad.append((i, j, r))
            if not pairs:
                real_skips = [r for r in skipped if str(r.get("skip_reason", "")).strip()]
                reasons = sorted({str(r["skip_reason"]) for r in real_skips})
                detail = (
                    "pair_metrics.csv contains no measured pairs; "
                    f"raw_rows={len(raw_pairs)} skipped_pairs={len(real_skips)} "
                    f"skip_reasons={reasons}"
                )
                add(t, False, detail)
            else:
                reportable = []
                limited = []
                for i, j, row in bad:
                    item = (i, j, row.get("status"), row.get("evidence_state"))
                    is_limited = (
                        str(row.get("evidence_state", "")) in {
                            "quality_limited", "calibration_limited", "pose_leakage_limited"
                        }
                        or _truthy(row.get("quality_limited"))
                        or _truthy(row.get("calibration_limited"))
                        or _truthy(row.get("pose_leakage_limited"))
                    )
                    (limited if is_limited else reportable).append(item)
                if reportable:
                    add(t, False, {"reportable": reportable, "limited": limited}, "failed")
                elif limited:
                    add(t, False, {"blocked_limited_candidates": limited}, "blocked")
                else:
                    add(t, True, [])
        elif t == "pair_status":
            found = _find_pairs(pairs, tags[exp["frames"][0]], tags[exp["frames"][1]])
            stats = {str(r.get("status")) for r in found}
            detail = f"frames={exp['frames']} found={len(found)} statuses={sorted(stats)}"
            if not found:
                detail += " | " + _skip_detail(skipped, tags[exp["frames"][0]], tags[exp["frames"][1]])
            add(t, bool(found) and bool(stats & set(exp["any_of"])), detail)
        elif t == "pair_status_not":
            found = _find_pairs(pairs, tags[exp["frames"][0]], tags[exp["frames"][1]])
            stats = {str(r.get("status")) for r in found}
            detail = f"frames={exp['frames']} found={len(found)} statuses={sorted(stats)}"
            if not found:
                detail += " | " + _skip_detail(skipped, tags[exp["frames"][0]], tags[exp["frames"][1]])
            add(t, bool(found) and not (stats & set(exp["none_of"])), detail)
        elif t == "status_present":
            stats = {str(r.get("status")) for r in pairs}
            add(t, bool(pairs) and bool(stats & set(exp["any_of"])), sorted(stats))
        elif t == "status_absent":
            stats = {str(r.get("status")) for r in pairs}
            add(t, bool(pairs) and not (stats & set(exp["statuses"])), sorted(stats & set(exp["statuses"])))
        elif t == "baseline_return_events":
            br = _json(s2 / "baseline_return.json")
            n = int(br.get("event_count", len(br.get("events", []) or [])))
            ok = int(exp.get("min", 0)) <= n <= int(exp.get("max", 10 ** 9))
            add(t, ok, f"event_count={n}")
        elif t == "fdr_significant_fraction_max":
            tested = [r for r in pairs if str(r.get("mt_q_value", "")).strip() not in ("", "None")]
            sig = [r for r in tested if _truthy(r.get("mt_significant_fdr10"))]
            frac = (len(sig) / len(tested)) if tested else 0.0
            detail = f"significant={len(sig)}/{len(tested)} frac={frac:.3f}"
            if not tested:
                real_skips = [r for r in skipped if r.get('skip_reason')]
                detail += f" | no FDR-tested rows; skipped_pairs={len(real_skips)}"
            add(t, bool(tested) and frac <= float(exp["value"]), detail)
        elif t == "corroboration":
            found = _find_pairs(pairs, tags[exp["frames"][0]], tags[exp["frames"][1]])
            stats = {str(r.get("cross_bin_corroboration_status")) for r in found}
            detail = f"found={len(found)} statuses={sorted(stats)}"
            if not found:
                detail += " | " + _skip_detail(skipped, tags[exp["frames"][0]], tags[exp["frames"][1]])
            add(t, bool(found) and bool(stats & set(exp["any_of"])), detail)
        else:
            add(t, False, "неизвестный тип проверки")
    states = {str(r.get("state")) for r in results}
    outcome = "failed" if "failed" in states else ("blocked" if "blocked" in states else "passed")
    return {
        "scenario_id": manifest["scenario"]["id"],
        "outcome": outcome,
        "passed": outcome == "passed",
        "blocked": outcome == "blocked",
        "checks": results,
    }
