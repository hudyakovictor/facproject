"""AST extraction without importing or executing observed source files."""
from __future__ import annotations

import ast
import copy
import hashlib
from pathlib import Path
import re
from typing import Iterable

from .models import CallRef, ClassRecord, FunctionRecord, ModuleRecord

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b[^\n]*", re.IGNORECASE)
STATUS_NAMES = {"log_status", "status_warning"}


def _text(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _module_id(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join((root.name, *parts)) if parts else root.name


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    pos = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(pos) - len(node.args.defaults)) + list(node.args.defaults)
    for index, (arg, default) in enumerate(zip(pos, defaults)):
        piece = arg.arg + (f": {_text(arg.annotation)}" if arg.annotation else "")
        if default is not None:
            piece += f" = {_text(default)}"
        args.append(piece)
        if node.args.posonlyargs and index + 1 == len(node.args.posonlyargs):
            args.append("/")
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg + (f": {_text(node.args.vararg.annotation)}" if node.args.vararg.annotation else ""))
    elif node.args.kwonlyargs:
        args.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        piece = arg.arg + (f": {_text(arg.annotation)}" if arg.annotation else "")
        if default is not None:
            piece += f" = {_text(default)}"
        args.append(piece)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg + (f": {_text(node.args.kwarg.annotation)}" if node.args.kwarg.annotation else ""))
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {_text(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({', '.join(args)}){returns}"


def _call_name(node: ast.Call) -> str:
    return _text(node.func) or "<dynamic>"


def _fingerprint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    clone = copy.deepcopy(node)
    clone.name = "<function>"
    for item in ast.walk(clone):
        for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
            if hasattr(item, attr):
                setattr(item, attr, None)
    return hashlib.sha256(ast.dump(clone, include_attributes=False).encode()).hexdigest()


def _function_record(module_id: str, node: ast.FunctionDef | ast.AsyncFunctionDef, parents: tuple[str, ...], source: str) -> FunctionRecord:
    qualified = ".".join((module_id, *parents, node.name))
    calls = tuple(CallRef(_call_name(x), int(x.lineno)) for x in ast.walk(node) if isinstance(x, ast.Call))
    raises = tuple(sorted({_text(x.exc) or "re-raise" for x in ast.walk(node) if isinstance(x, ast.Raise)}))
    status_events = tuple(sorted({_call_name(x) for x in ast.walk(node) if isinstance(x, ast.Call) and _call_name(x).split(".")[-1] in STATUS_NAMES}))
    broad = sum(1 for x in ast.walk(node) if isinstance(x, ast.ExceptHandler) and (x.type is None or _text(x.type) in {"Exception", "BaseException"}))
    segment = ast.get_source_segment(source, node) or ""
    todos = tuple(match.group(0).strip() for match in TODO_RE.finditer(segment))
    kind = "async_method" if isinstance(node, ast.AsyncFunctionDef) and parents else "method" if parents else "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
    return FunctionRecord(
        id=qualified,
        module_id=module_id,
        technical_name=node.name,
        qualified_name=qualified,
        kind=kind,
        signature=_signature(node),
        return_annotation=_text(node.returns),
        docstring=ast.get_docstring(node, clean=False),
        line_start=int(node.lineno),
        line_end=int(node.end_lineno or node.lineno),
        decorators=tuple(filter(None, (_text(x) for x in node.decorator_list))),
        raises=raises,
        calls=calls,
        status_events=status_events,
        has_pass=any(isinstance(x, ast.Pass) for x in ast.walk(node)),
        has_not_implemented=any(isinstance(x, ast.Name) and x.id == "NotImplementedError" for x in ast.walk(node)),
        todo_markers=todos,
        broad_exception_handlers=broad,
        fingerprint=_fingerprint(node),
    )


def _collect_functions(
    module_id: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parents: tuple[str, ...],
    source: str,
) -> list[FunctionRecord]:
    records = [_function_record(module_id, node, parents, source)]
    nested_parents = (*parents, node.name)
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            records.extend(_collect_functions(module_id, child, nested_parents, source))
    return records


def index_file(root: Path, path: Path) -> ModuleRecord:
    root, path = root.resolve(), path.resolve()
    source = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode()).hexdigest()
    module_id = _module_id(root, path)
    try:
        tree = ast.parse(source, filename=str(path), type_comments=True)
    except SyntaxError as exc:
        return ModuleRecord(module_id, path.relative_to(root).as_posix(), digest, None, (), (), (), (), f"{exc.msg} at {exc.lineno}:{exc.offset}")
    imports: list[str] = []
    constants: list[str] = []
    functions: list[FunctionRecord] = []
    classes: list[ClassRecord] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            imports.extend(f"{prefix}:{alias.name}" for alias in node.names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            constants.extend(x.id for target in targets for x in ast.walk(target) if isinstance(x, ast.Name) and x.id.isupper())
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.extend(_collect_functions(module_id, node, (), source))
        elif isinstance(node, ast.ClassDef):
            q = f"{module_id}.{node.name}"
            classes.append(ClassRecord(q, module_id, node.name, q, node.lineno, node.end_lineno or node.lineno, ast.get_docstring(node, clean=False), tuple(filter(None, (_text(x) for x in node.bases)))))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.extend(_collect_functions(module_id, child, (node.name,), source))
    return ModuleRecord(module_id, path.relative_to(root).as_posix(), digest, ast.get_docstring(tree, clean=False), tuple(imports), tuple(sorted(set(constants))), tuple(functions), tuple(classes))
