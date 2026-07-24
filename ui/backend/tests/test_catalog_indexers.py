from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dpo.catalog import bind_tests, build_catalog, index_tests, parse_status_audit
from dpo.indexer import ProjectIndex


class CatalogIndexerTests(unittest.TestCase):
    def fixture(self, root: Path) -> ProjectIndex:
        (root / "stage1").mkdir(parents=True)
        (root / "test_module").mkdir()
        (root / "stage1" / "geometry.py").write_text('def classify_pose(yaw: float) -> str:\n    """Assign a pose bin."""\n    return "front"\n\ndef dynamic(name):\n    return globals()[name]()\n', encoding='utf-8')
        (root / "STATUS_AUDIT.py").write_text('STAGE1_STATUS={"geometry.py":{"classify_pose":{"status":"✅ COMPLETE","blocker":"✅ NO BLOCKER","note":"covered"},"old_name":{"status":"🔴 need_testing"}}}\nraise RuntimeError("must not execute")\n', encoding='utf-8')
        (root / "test_module" / "test_geometry.py").write_text('from app6.stage1.geometry import classify_pose\nimport unittest\nclass T(unittest.TestCase):\n def test_pose(self):\n  self.assertEqual(classify_pose(0.0), "front")\n def test_error(self):\n  with self.assertRaises(ValueError):\n   raise ValueError()\n', encoding='utf-8')
        index = ProjectIndex(root); index.refresh(); return index

    def test_status_parser_is_literal_only_and_maps_known_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'app6'; root.mkdir(); index=self.fixture(root)
            statuses=parse_status_audit(root/'STATUS_AUDIT.py', index)
            known=next(x for x in statuses if x.symbol_ref=='classify_pose')
            unknown=next(x for x in statuses if x.symbol_ref=='old_name')
            self.assertEqual(known.status,'complete'); self.assertEqual(known.confidence,'confirmed_static')
            self.assertIsNone(unknown.target_id)

    def test_test_index_and_bindings_include_expected_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'app6'; root.mkdir(); index=self.fixture(root)
            tests=index_tests(root); bindings=bind_tests(tests,index)
            self.assertEqual(len(tests),2)
            self.assertIn('ValueError', next(x for x in tests if x.id.endswith('test_error')).expected_exceptions)
            binding=next(x for x in bindings if x.function_id.endswith('classify_pose'))
            self.assertEqual(binding.confidence,'confirmed_static')

    def test_manual_binding_rejects_unknown_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'app6'; root.mkdir(); index=self.fixture(root)
            override=Path(tmp)/'bindings.yaml'; override.write_text('bindings:\n - test_id: missing\n   function_id: missing\n',encoding='utf-8')
            bindings=bind_tests(index_tests(root),index,override)
            self.assertFalse(any(x.confidence=='manual_override' for x in bindings))

    def test_catalog_has_journalist_fields_and_p2_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'app6'; root.mkdir(); index=self.fixture(root)
            statuses=parse_status_audit(root/'STATUS_AUDIT.py',index); tests=index_tests(root); bindings=bind_tests(tests,index)
            catalog=build_catalog(index,statuses,bindings)
            entry=next(x for x in catalog if x.technical_name=='classify_pose')
            self.assertTrue(entry.title and entry.description and entry.why_important and entry.failure_impact)
            dynamic=next(x for x in catalog if x.technical_name=='dynamic')
            self.assertEqual(dynamic.task_priority,'P2')


if __name__=='__main__': unittest.main()
