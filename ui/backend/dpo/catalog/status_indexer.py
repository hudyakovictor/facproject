"""Read STATUS_AUDIT.py as data without importing or executing it."""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from dpo.indexer.project_index import ProjectIndex


@dataclass(frozen=True)
class StatusEntry:
    source_group: str
    module_ref: str
    symbol_ref: str
    status: str
    raw_status: str
    blocker: str | None
    note: str | None
    target_id: str | None
    confidence: str

    def to_dict(self) -> dict[str, Any]: return asdict(self)


def _clean_status(value: object) -> str:
    text = re.sub(r"[^A-Za-z_ ]", "", str(value)).strip().lower().replace(" ", "_")
    aliases = {"complete": "complete", "closed": "closed", "need_testing": "need_testing", "in_progress": "in_progress", "deprecated": "deprecated", "waiting": "waiting", "blocked": "blocked"}
    return aliases.get(text, text or "unknown")


def parse_status_audit(path: str | Path, project: ProjectIndex | None = None) -> list[StatusEntry]:
    path = Path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    raw_groups: list[tuple[str, dict]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id.endswith("_STATUS"):
                try: payload = ast.literal_eval(value)
                except (ValueError, TypeError, SyntaxError): continue
                if isinstance(payload, dict): raw_groups.append((target.id, payload))
    functions = project.functions if project else []
    modules = project.modules if project else []
    entries: list[StatusEntry] = []
    for group, module_map in raw_groups:
        for module_ref, symbols in module_map.items():
            if not isinstance(symbols, dict): continue
            candidate_modules = [m for m in modules if m.source_path.endswith(str(module_ref))]
            for symbol_ref, metadata in symbols.items():
                if not isinstance(metadata, dict): metadata = {"status": metadata}
                short = str(symbol_ref).split(".")[-1]
                owner = str(symbol_ref).split(".")[-2] if "." in str(symbol_ref) else None
                candidates = [f for f in functions if f.technical_name == short and (not candidate_modules or f.module_id in {m.id for m in candidate_modules})]
                if owner: candidates = [f for f in candidates if f".{owner}." in f.id]
                target = candidates[0].id if len(candidates) == 1 else None
                confidence = "confirmed_static" if target else "unresolved"
                entries.append(StatusEntry(group, str(module_ref), str(symbol_ref), _clean_status(metadata.get("status")), str(metadata.get("status", "")), metadata.get("blocker"), metadata.get("note"), target, confidence))
    return sorted(entries, key=lambda x: (x.source_group, x.module_ref, x.symbol_ref))
