"""Append-only manual QA and face-selection decisions."""
from __future__ import annotations
import json,os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
def append_review(project_root:Path,payload:dict[str,Any])->dict[str,Any]:
 required={"photo_id","decision","reviewer"};missing=required-set(payload)
 if missing:raise ValueError("missing review fields: "+",".join(sorted(missing)))
 if payload["decision"] not in {"approve","reject","needs_recrop","select_face"}:raise ValueError("invalid decision")
 row={**payload,"schema":"deeputin-manual-qa-v1","created_at":datetime.now(UTC).isoformat()}
 root=Path(os.environ.get("DEEPUTIN_STATE_ROOT",str(project_root/"runs")));root.mkdir(parents=True,exist_ok=True)
 with (root/"manual_qa.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(row,ensure_ascii=False)+"\n")
 return row
