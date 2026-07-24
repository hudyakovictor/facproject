from __future__ import annotations
from pathlib import Path
import tempfile,time,unittest
from dpo.canvas import LayoutStore,build_canvas_graph
from dpo.catalog import build_catalog
from dpo.indexer import ProjectIndex
class CanvasTests(unittest.TestCase):
 def test_graph_is_deterministic_and_accessible(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)/'app6';(r/'stage1').mkdir(parents=True);(r/'stage1'/'a.py').write_text('def save_result():\n return 1\ndef run():\n return save_result()\n')
   p=ProjectIndex(r);p.refresh();c=build_catalog(p,[],[]);a=build_canvas_graph(p,c);b=build_canvas_graph(p,c)
   self.assertEqual(a,b);self.assertTrue(all(n['title'] and n['technical_name'] and n['kind'] for n in a['nodes']));self.assertTrue(any(n['kind']=='artifact' for n in a['nodes']))
 def test_layout_store_stays_under_control_root(self):
  with tempfile.TemporaryDirectory() as t:
   s=LayoutStore(Path(t)/'.data'/'layouts');p=s.save('Full',{'a':{'x':1,'y':2}});self.assertTrue(p.is_file());self.assertEqual(s.load('Full')['positions']['a']['x'],1.0)
   with self.assertRaises(ValueError):s.save('../escape',{})
 def test_full_app6_graph_exceeds_500_nodes_quickly(self):
  root=Path(__file__).resolve().parents[3]/'app6';p=ProjectIndex(root);p.refresh();start=time.perf_counter();g=build_canvas_graph(p,build_catalog(p,[],[]));elapsed=time.perf_counter()-start
  self.assertGreaterEqual(len(g['nodes']),500);self.assertLess(elapsed,2.0)
if __name__=='__main__':unittest.main()
