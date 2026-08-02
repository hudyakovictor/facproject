"""🚪 ENTRY POINT → Движок Stage 2B: собирает payload пост-отчётов поверх Stage 2.
🚪 API: run(); helpers utc()/payload()
🔗 DEPENDS ON: stage2.postprocess_reports + сводные таблицы
Blind evidence states are consumed from the Stage 2 registry; prior leads never alter them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app6.stage2.leads import load_leads
from app6.stage2.evidence import EVIDENCE_SCHEMA, STATUS_TO_EVIDENCE_STATE
from app6.stage1.utils import atomic_json, digest_file, digest_json, write_csv

SCHEMA = "deeputin-stage2b-private-corroboration-v1.0"
SIGNIFICANT_STATES = {
    "persistent_geometric_change",
    "persistent_geometric_change_candidate",  # legacy: не эмитится текущим stage2
    "rate_change_candidate",
    "persistent_rate_change_candidate",
    "texture_line_change_candidate",  # legacy: не эмитится текущим stage2
    "reversible_change_candidate",
    "same_day_conflict_candidate",
    # 🔧 FIX (аудит, раунд 2): реальные evidence-состояния stage2, которые раньше
    # проваливались в insufficient_data.
    "coherent_jump_candidate",
    "alpha_id_change_candidate",
}
WEAK_STATES = {"elevated_uncertain", "quality_limited", "calibration_limited", "pose_leakage_limited", "expression_dominated"}
NO_SUPPORT_STATES = {"within_noise", "insufficient_visibility", "insufficient_calibration", "unsupported_pose", "inapplicable_pose"}
KNOWN_EVIDENCE_STATES=set(STATUS_TO_EVIDENCE_STATE.values())|{"calibration_limited","pose_leakage_limited"}
UNCLASSIFIED_EVIDENCE_STATES=KNOWN_EVIDENCE_STATES-(SIGNIFICANT_STATES|WEAK_STATES|NO_SUPPORT_STATES)


# 🔄 UTC-штамп
def utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Stage2BConfig:
    stage2_root: Path
    output_dir: Path
    prior_root: Path | None = None
    overwrite: bool = False

    def __post_init__(self) -> None:
        source=Path(self.stage2_root).resolve();output=Path(self.output_dir).resolve()
        if output == source or source in output.parents:
            raise ValueError("output_dir must not equal or be inside stage2_root")

    # 🏭 FACTORY → payload пост-отчётов
    def payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "policy": "private corroboration only; never modifies blind Stage2 measurements",
            "prior_root": str(self.prior_root) if self.prior_root else None,
        }


class Stage2BEngine:
    def __init__(self, cfg: Stage2BConfig):
        self.cfg = cfg

    # 🚪 ENTRY POINT Stage 2B
    def run(self) -> dict[str, Any]:
        out = self.cfg.output_dir
        if out.exists() and any(out.iterdir()) and not self.cfg.overwrite:
            raise FileExistsError(f"output exists: {out}")
        stage2_manifest_path = self.cfg.stage2_root / "analysis_manifest.json"
        stage2_validation_path = self.cfg.stage2_root / "analysis_validation.json"
        evidence_path = self.cfg.stage2_root / "evidence_packets.json"
        if not stage2_manifest_path.is_file():
            raise FileNotFoundError(stage2_manifest_path)
        if not evidence_path.is_file():
            raise FileNotFoundError(evidence_path)
        if not stage2_validation_path.is_file():
            raise FileNotFoundError(stage2_validation_path)
        stage2_validation = json.loads(stage2_validation_path.read_text(encoding="utf-8"))
        if stage2_validation.get("status") != "complete":
            raise RuntimeError(f"Stage2 analysis is not valid: {stage2_validation.get('errors')}")

        stage2_manifest = json.loads(stage2_manifest_path.read_text(encoding="utf-8"))
        if stage2_manifest.get("status") != "complete":
            raise RuntimeError("Stage2 manifest is not complete")
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence_payload.get("schema") != EVIDENCE_SCHEMA:
            raise RuntimeError(f"Unsupported Stage2 evidence schema: {evidence_payload.get('schema')}")
        evidence = evidence_payload.get("packets", [])
        if not isinstance(evidence, list):
            raise RuntimeError("Stage2 evidence packets must be a list")
        if self.cfg.prior_root:
            leads = load_leads(self.cfg.prior_root)
        else:
            lead_path = self.cfg.stage2_root / "lead_registry.json"
            leads = json.loads(lead_path.read_text(encoding="utf-8")) if lead_path.is_file() else {"status": "not_provided", "dates": {}}

        if out.exists() and self.cfg.overwrite:
            import shutil
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)

        date_registry = leads.get("dates", {}) or {}
        rows: list[dict[str, Any]] = []
        for pkt in evidence:
            dates = [d for d in (pkt.get("date_a"), pkt.get("date_b")) if d]
            matched = [(d, date_registry[d]) for d in dates if d in date_registry]
            if not matched:
                continue
            state = str(pkt.get("evidence_state") or "")
            priority = sum(int(x.get("priority", 0)) for _, x in matched)
            regions = sorted({r for _, x in matched for r in x.get("regions", [])})
            events = sorted({r for _, x in matched for r in x.get("events", [])})
            if state in SIGNIFICANT_STATES and priority >= 4:
                status = "confirmed_independently"
            elif state in SIGNIFICANT_STATES or state in WEAK_STATES:
                status = "partially_supported"
            elif state in NO_SUPPORT_STATES:
                status = "contradicted" if priority >= 10 and state == "within_noise" else "not_supported"
            else:
                status = "insufficient_data"
            rows.append({
                "pair_id": pkt.get("pair_id"),
                "corroboration_status": status,
                "evidence_state": state,
                "status": pkt.get("status"),
                "pose_bin": pkt.get("pose_bin"),
                "date_a": pkt.get("date_a"),
                "date_b": pkt.get("date_b"),
                "photo_a": pkt.get("photo_a"),
                "photo_b": pkt.get("photo_b"),
                "prior_dates": "|".join(d for d, _ in matched),
                "prior_priority": priority,
                "prior_regions": "|".join(regions),
                "prior_events": "|".join(events),
                "policy": "private_only_does_not_modify_blind_stage2",
            })

        counts: dict[str, int] = {}
        for r in rows:
            counts[r["corroboration_status"]] = counts.get(r["corroboration_status"], 0) + 1

        write_csv(out / "corroboration_results.csv", rows or [{"status": "no_prior_overlap"}])
        atomic_json(out / "private_summary.json", {
            "schema_version": SCHEMA,
            "created_at_utc": utc(),
            "stage2_manifest_digest": digest_file(stage2_manifest_path),
            "stage2_evidence_digest": digest_file(evidence_path),
            "stage2_schema": stage2_manifest.get("schema_version"),
            "prior_status": leads.get("status"),
            "prior_date_count": leads.get("date_count", len(date_registry)),
            "evidence_packet_count": len(evidence),
            "prior_overlap_pair_count": len(rows),
            "status_counts": counts,
            "policy": "This private module checks whether frozen blind Stage2 evidence overlaps prior leads. It never changes raw residuals, thresholds, or public conclusions.",
        })
        manifest = {
            "schema_version": SCHEMA,
            "status": "complete",
            "created_at_utc": utc(),
            "config_hash": digest_json(self.cfg.payload()),
            "stage2_manifest_digest": digest_file(stage2_manifest_path),
            "prior_status": leads.get("status"),
            "corroboration_row_count": len(rows),
            "outputs": ["corroboration_results.csv", "private_summary.json"],
        }
        atomic_json(out / "stage2b_manifest.json", manifest)
        return manifest
