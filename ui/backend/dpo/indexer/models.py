from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EdgeConfidence(StrEnum):
    CONFIRMED = "confirmed_static"
    HEURISTIC = "heuristic_static"
    RUNTIME = "runtime_observed"
    MANUAL = "manual_override"


@dataclass(frozen=True)
class CallRef:
    expression: str
    line: int


@dataclass(frozen=True)
class FunctionRecord:
    id: str
    module_id: str
    technical_name: str
    qualified_name: str
    kind: str
    signature: str
    return_annotation: str | None
    docstring: str | None
    line_start: int
    line_end: int
    decorators: tuple[str, ...]
    raises: tuple[str, ...]
    calls: tuple[CallRef, ...]
    status_events: tuple[str, ...]
    has_pass: bool
    has_not_implemented: bool
    todo_markers: tuple[str, ...]
    broad_exception_handlers: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["calls"] = [asdict(x) for x in self.calls]
        return data


@dataclass(frozen=True)
class ClassRecord:
    id: str
    module_id: str
    technical_name: str
    qualified_name: str
    line_start: int
    line_end: int
    docstring: str | None
    bases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModuleRecord:
    id: str
    source_path: str
    content_hash: str
    docstring: str | None
    imports: tuple[str, ...]
    constants: tuple[str, ...]
    functions: tuple[FunctionRecord, ...]
    classes: tuple[ClassRecord, ...]
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["functions"] = [x.to_dict() for x in self.functions]
        data["classes"] = [x.to_dict() for x in self.classes]
        return data


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    confidence: EdgeConfidence
    expression: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = self.confidence.value
        return data


@dataclass
class IndexDelta:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return asdict(self)
