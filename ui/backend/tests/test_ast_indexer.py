from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dpo.indexer.ast_indexer import index_file
from dpo.indexer.models import EdgeConfidence
from dpo.indexer.project_index import ProjectIndex


SOURCE = '''"""module docs"""
import math
from pathlib import Path

LIMIT = 3

def helper(value: float) -> float:
    """Понятное описание helper."""
    return math.sqrt(value)

async def pipeline(x: float = 4.0) -> float:
    # TODO verify real photos
    def nested(y: float) -> float:
        return helper(y)
    log_status("pipeline", "complete")
    try:
        return nested(x)
    except Exception:
        raise RuntimeError("bad")

class Worker:
    def run(self, value: float) -> float:
        return self.prepare(value)

    def prepare(self, value: float) -> float:
        pass
'''


class AstIndexerTests(unittest.TestCase):
    def test_extracts_module_classes_functions_and_contract_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            path = root / "sample.py"
            path.write_text(SOURCE, encoding="utf-8")
            module = index_file(root, path)
            self.assertEqual(module.id, "app6.sample")
            self.assertEqual(module.docstring, "module docs")
            self.assertIn("LIMIT", module.constants)
            self.assertEqual(len(module.classes), 1)
            names = {f.qualified_name for f in module.functions}
            self.assertIn("app6.sample.pipeline.nested", names)
            pipeline = next(f for f in module.functions if f.technical_name == "pipeline")
            self.assertEqual(pipeline.kind, "async_function")
            self.assertIn("TODO verify real photos", pipeline.todo_markers)
            self.assertIn("RuntimeError('bad')", pipeline.raises)
            self.assertEqual(pipeline.broad_exception_handlers, 1)
            self.assertIn("log_status", pipeline.status_events)
            prepare = next(f for f in module.functions if f.technical_name == "prepare")
            self.assertTrue(prepare.has_pass)

    def test_scan_never_imports_or_executes_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            sentinel = Path(tmp) / "executed.txt"
            path = root / "danger.py"
            path.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\ndef safe():\n    return 1\n", encoding="utf-8")
            module = index_file(root, path)
            self.assertIsNone(module.parse_error)
            self.assertFalse(sentinel.exists())

    def test_parse_error_is_recorded_without_stopping_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            bad = root / "bad.py"
            bad.write_text("def broken(:\n", encoding="utf-8")
            record = index_file(root, bad)
            self.assertIsNotNone(record.parse_error)
            self.assertEqual(record.functions, ())

    def test_incremental_refresh_only_reindexes_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            a, b = root / "a.py", root / "b.py"
            a.write_text("def a():\n    return 1\n", encoding="utf-8")
            b.write_text("def b():\n    return 2\n", encoding="utf-8")
            index = ProjectIndex(root)
            first = index.refresh()
            self.assertEqual(first.added, ["a.py", "b.py"])
            second = index.refresh()
            self.assertEqual(second.unchanged, ["a.py", "b.py"])
            a.write_text("def a():\n    return 3\n", encoding="utf-8")
            third = index.refresh()
            self.assertEqual(third.changed, ["a.py"])
            self.assertEqual(third.unchanged, ["b.py"])
            b.unlink()
            fourth = index.refresh()
            self.assertEqual(fourth.removed, ["b.py"])

    def test_graph_distinguishes_confirmed_and_heuristic_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            (root / "flow.py").write_text(SOURCE, encoding="utf-8")
            index = ProjectIndex(root)
            index.refresh()
            edges = index.edges()
            prepare = next(e for e in edges if e.expression == "self.prepare")
            self.assertEqual(prepare.confidence, EdgeConfidence.CONFIRMED)
            helper = next(e for e in edges if e.expression == "helper")
            self.assertIn(helper.confidence, {EdgeConfidence.CONFIRMED, EdgeConfidence.HEURISTIC})

    def test_dynamic_call_is_never_marked_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            (root / "dynamic.py").write_text(
                "def choose(name):\n    return globals()[name]()\n\ndef target():\n    return 1\n",
                encoding="utf-8",
            )
            index = ProjectIndex(root)
            index.refresh()
            self.assertFalse(any(e.confidence == EdgeConfidence.CONFIRMED for e in index.edges()))

    def test_repeat_scan_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            (root / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
            index = ProjectIndex(root)
            index.refresh()
            first = index.snapshot()
            delta = index.refresh()
            second = index.snapshot()
            self.assertEqual(first, second)
            self.assertEqual(delta.unchanged, ["a.py"])

    def test_fingerprint_survives_file_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            a = root / "a.py"
            a.write_text("def stable(x: int) -> int:\n    return x + 1\n", encoding="utf-8")
            first = index_file(root, a).functions[0]
            sub = root / "moved"
            sub.mkdir()
            b = sub / "b.py"
            a.rename(b)
            second = index_file(root, b).functions[0]
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(first.fingerprint, second.fingerprint)


if __name__ == "__main__":
    unittest.main()
