"""Interface Contract Engine: single source of truth for backend/frontend contracts."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

CONTRACT_YAML = """
schema_version: "deeputin-contract-v1.0"
description: "Unified interface and artifact contract for Deeputin Pipeline Observatory"
entities:
  RunGroup:
    fields:
      id: {type: string, required: true}
      status: {type: string, enum: [draft, candidate, approved, rejected], required: true}
      members: {type: object, required: true}
      bundle_hash: {type: string, required: false, nullable: true}
  EvidencePacket:
    fields:
      pair_id: {type: string, required: true}
      evidence_state: {type: string, required: true}
      measurement_status: {type: string, required: true}
      p95_point_z: {type: float, required: true}
artifacts:
  - name: pair_metrics.csv
    format: csv
    required: true
  - name: analysis_manifest.json
    format: json
    required: true
"""

class InterfaceContract:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self.spec = yaml.safe_load(CONTRACT_YAML)

    def get_spec(self) -> dict[str, Any]:
        return self.spec

    def validate_payload(self, entity: str, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        entities = self.spec.get("entities", {})
        if entity not in entities:
            return [f"Unknown entity: {entity}"]
        fields = entities[entity].get("fields", {})
        for fname, fmeta in fields.items():
            if fmeta.get("required") and fname not in payload:
                errors.append(f"Missing required field '{fname}' in {entity}")
            elif fname in payload and payload[fname] is not None:
                val = payload[fname]
                ftype = fmeta.get("type")
                if ftype == "string" and not isinstance(val, str):
                    errors.append(f"Field '{fname}' must be string")
                elif ftype == "float" and not isinstance(val, (int, float)):
                    errors.append(f"Field '{fname}' must be float/number")
                elif ftype == "object" and not isinstance(val, dict):
                    errors.append(f"Field '{fname}' must be object/dict")
                allowed_enum = fmeta.get("enum")
                if allowed_enum and val not in allowed_enum:
                    errors.append(f"Field '{fname}' value '{val}' not in allowed enum {allowed_enum}")
        return errors
