"""🔄 CALLBACK (pytest) → архитектурные границы skin-слоя: single public render и пр.
"""
import ast,unittest
from pathlib import Path
class SkinArchitectureTests(unittest.TestCase):
 def test_stage2_skin_never_imports_reconstruction(self):
  root=Path(__file__).parents[1]/'stage2/skin'
  for p in root.glob('*.py'):
   tree=ast.parse(p.read_text())
   names=[]
   for n in ast.walk(tree):
    if isinstance(n,ast.Import):names += [x.name for x in n.names]
    elif isinstance(n,ast.ImportFrom):names.append(n.module or '')
   self.assertFalse(any('reconstruction' in x or '3ddfa' in x.lower() for x in names),p.name)
 def test_uv_generator_has_single_public_render(self):
  text=(Path(__file__).parents[2]/'uv_module/hd_uv_generator.py').read_text();self.assertNotIn('uv_tex_beauty',text);self.assertNotIn('uv_tex_analysis',text)
 def test_skin_pipeline_consumes_existing_face_mask(self):
  text=(Path(__file__).parents[1]/'stage1/skin/pipeline.py').read_text();self.assertIn("fm['mask_original']",text);self.assertNotIn('skin_segmentation=',text)
 def test_skin_extractors_do_not_import_uv_module(self):
  root=Path(__file__).parents[1]/'stage1/skin'
  for p in root.rglob('*.py'):
   text=p.read_text();self.assertNotIn('import uv_module',text,p.name);self.assertNotIn('from uv_module',text,p.name)
if __name__=='__main__':unittest.main()
