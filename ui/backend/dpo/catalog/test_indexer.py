"""Static test discovery and conservative test-to-function bindings."""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import yaml

from dpo.indexer.project_index import ProjectIndex


@dataclass(frozen=True)
class TestRecord:
    id: str; source_path: str; line: int; framework: str
    imports: tuple[str, ...]; calls: tuple[str, ...]; expected_exceptions: tuple[str, ...]
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class TestBinding:
    test_id: str; function_id: str; confidence: str; source: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)


def _text(node: ast.AST | None) -> str:
    try: return ast.unparse(node) if node is not None else ""
    except Exception: return ""


def index_tests(root: str | Path) -> list[TestRecord]:
    root = Path(root).resolve()
    records: list[TestRecord] = []
    for path in sorted(root.rglob("test*.py")):
        source = path.read_text(encoding="utf-8")
        try: tree = ast.parse(source, filename=str(path))
        except SyntaxError: continue
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import): imports.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom): imports.extend(f"{node.module or ''}.{a.name}" for a in node.names)
        for parent in tree.body:
            nodes = parent.body if isinstance(parent, ast.ClassDef) else [parent]
            for node in nodes:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"): continue
                owner = f".{parent.name}" if isinstance(parent, ast.ClassDef) else ""
                test_id = f"{path.relative_to(root).with_suffix('').as_posix().replace('/', '.')}{owner}.{node.name}"
                calls = tuple(sorted({_text(x.func) for x in ast.walk(node) if isinstance(x, ast.Call)}))
                exceptions: set[str] = set()
                for item in ast.walk(node):
                    if isinstance(item, ast.With):
                        for w in item.items:
                            if isinstance(w.context_expr, ast.Call) and _text(w.context_expr.func).split(".")[-1] in {"assertRaises", "assertRaisesRegex", "raises"} and w.context_expr.args:
                                exceptions.add(_text(w.context_expr.args[0]))
                framework = "unittest" if isinstance(parent, ast.ClassDef) else "pytest_or_function"
                records.append(TestRecord(test_id, path.relative_to(root).as_posix(), node.lineno, framework, tuple(imports), calls, tuple(sorted(exceptions))))
    return records


def bind_tests(tests: list[TestRecord], project: ProjectIndex, overrides_path: str | Path | None = None) -> list[TestBinding]:
    by_short: dict[str, list[str]] = {}
    for f in project.functions: by_short.setdefault(f.technical_name, []).append(f.id)
    bindings: dict[tuple[str, str], TestBinding] = {}
    ignored = {"assertEqual", "assertTrue", "assertFalse", "assertIn", "assertNotIn", "assertRaises", "assertRaisesRegex", "TemporaryDirectory", "Path", "array", "zeros", "ones", "len", "list", "str", "float", "int", "print"}
    for test in tests:
        imported = {item.split(".")[-1]: item for item in test.imports}
        for expression in test.calls:
            short = expression.split(".")[-1]
            if short in ignored: continue
            candidates = by_short.get(short, [])
            if len(candidates) == 1:
                confidence = "confirmed_static" if short in imported else "heuristic_static"
                binding = TestBinding(test.id, candidates[0], confidence, f"call:{expression}")
                bindings[(test.id, candidates[0])] = binding
    if overrides_path and Path(overrides_path).exists():
        data = yaml.safe_load(Path(overrides_path).read_text(encoding="utf-8")) or {}
        valid_tests, valid_functions = {x.id for x in tests}, {x.id for x in project.functions}
        for row in data.get("bindings", []):
            if row.get("test_id") not in valid_tests or row.get("function_id") not in valid_functions: continue
            binding = TestBinding(row["test_id"], row["function_id"], "manual_override", "test_bindings.yaml")
            bindings[(binding.test_id, binding.function_id)] = binding
    return sorted(bindings.values(), key=lambda x: (x.test_id, x.function_id))
