"""Incremental project index and conservative static call graph."""
from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from .ast_indexer import index_file
from .models import EdgeConfidence, GraphEdge, IndexDelta, ModuleRecord

IGNORE_PARTS = {"__pycache__", ".git", ".venv", "node_modules", ".data", "generated", "artifacts", "build", "dist", ".tox"}


class ProjectIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve(strict=False)
        self._modules: dict[str, ModuleRecord] = {}
        self._path_to_id: dict[str, str] = {}
        self._lock = RLock()

    def _files(self) -> list[Path]:
        return sorted(p for p in self.root.rglob("*.py") if not any(part in IGNORE_PARTS for part in p.relative_to(self.root).parts))

    def refresh(self) -> IndexDelta:
        delta = IndexDelta()
        with self._lock:
            current_paths = {p.relative_to(self.root).as_posix(): p for p in self._files()}
            for rel in sorted(set(self._path_to_id) - set(current_paths)):
                module_id = self._path_to_id.pop(rel)
                self._modules.pop(module_id, None)
                delta.removed.append(rel)
            for rel, path in current_paths.items():
                record = index_file(self.root, path)
                previous_id = self._path_to_id.get(rel)
                previous = self._modules.get(previous_id) if previous_id else None
                if previous and previous.content_hash == record.content_hash:
                    delta.unchanged.append(rel)
                    continue
                if previous_id and previous_id != record.id:
                    self._modules.pop(previous_id, None)
                self._modules[record.id] = record
                self._path_to_id[rel] = record.id
                (delta.changed if previous else delta.added).append(rel)
        return delta

    @property
    def modules(self) -> list[ModuleRecord]:
        with self._lock:
            return sorted(self._modules.values(), key=lambda x: x.id)

    @property
    def functions(self):
        return [f for m in self.modules for f in m.functions]

    def edges(self) -> list[GraphEdge]:
        functions = self.functions
        by_short: dict[str, list[str]] = {}
        by_qualified = {f.id for f in functions}
        for function in functions:
            by_short.setdefault(function.technical_name, []).append(function.id)
        edges: dict[tuple[str, str, int], GraphEdge] = {}
        for function in functions:
            class_prefix = function.id.rsplit(".", 1)[0]
            for call in function.calls:
                expression = call.expression
                short = expression.split(".")[-1]
                target = None
                confidence = EdgeConfidence.HEURISTIC
                local_method = f"{class_prefix}.{short}"
                local_module = f"{function.module_id}.{short}"
                if expression.startswith(("self.", "cls.")) and local_method in by_qualified:
                    target, confidence = local_method, EdgeConfidence.CONFIRMED
                elif local_module in by_qualified:
                    target, confidence = local_module, EdgeConfidence.CONFIRMED
                elif len(by_short.get(short, ())) == 1:
                    target = by_short[short][0]
                if target and target != function.id:
                    edge = GraphEdge(function.id, target, confidence, expression, call.line)
                    edges[(edge.source, edge.target, edge.line)] = edge
        return sorted(edges.values(), key=lambda x: (x.source, x.line, x.target))

    def snapshot(self) -> dict[str, Any]:
        modules = self.modules
        edges = self.edges()
        return {
            "root": str(self.root),
            "module_count": len(modules),
            "function_count": sum(len(m.functions) for m in modules),
            "class_count": sum(len(m.classes) for m in modules),
            "parse_error_count": sum(1 for m in modules if m.parse_error),
            "modules": [m.to_dict() for m in modules],
            "edges": [e.to_dict() for e in edges],
        }
