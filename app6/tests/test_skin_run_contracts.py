"""🔄 CALLBACK (pytest) → контракты skin-run: manifest finalize, run_manager guard.
"""
import json,tempfile,unittest
from pathlib import Path
from app6.stage1.skin.config_loader import load_config
from app6.stage1.skin.migrations import require_current,migrate
from app6.stage1.skin.run_manager import SkinRunManager
class SkinRunContractTests(unittest.TestCase):
 def test_config_merge_hash_is_deterministic(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a.json';b=Path(d)/'b.json';a.write_text('{"x":{"a":1},"y":2}');b.write_text('{"x":{"b":3}}');q,h=load_config(a,b);r,k=load_config(a,b);self.assertEqual((q,h),(r,k));self.assertEqual(q['x'],{'a':1,'b':3})
 def test_unknown_schema_fails_loud(self):
  with self.assertRaises(ValueError):require_current('skin-old-v0')
  with self.assertRaises(NotImplementedError):migrate({'schema':'x'},'skin-manifest-v1')
 def test_run_freeze_prevents_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'run';asset=Path(d)/'a';atlas=Path(d)/'z';asset.write_bytes(b'a');atlas.write_bytes(b'z');m=SkinRunManager(root);m.initialize({'a':1},[asset],atlas);m.finalize();self.assertTrue((root/'IMMUTABLE').is_file());
   with self.assertRaises(PermissionError):m.assert_mutable()
if __name__=='__main__':unittest.main()
