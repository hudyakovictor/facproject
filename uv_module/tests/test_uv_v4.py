import tempfile, unittest
from pathlib import Path
import cv2, numpy as np
from uv_module import UVExtractionConfig, MorphCompletionConfig, UVGenerator, HDUVConfig, HDUVTextureGenerator, SkinAnalyzer, normalize_skin_mask, save_uv_result
from uv_module.completion import complete_morph_texture

class UVV4Tests(unittest.TestCase):
 def fixture(self):
  img=np.zeros((96,96,3),np.uint8); img[:]=(80,130,190); img[:,48:]=(110,155,215)
  uv=np.array([[.1,.1],[.9,.1],[.9,.9],[.1,.9]],np.float32)
  tri=np.array([[0,1,2],[0,2,3]],np.int64)
  p2=np.array([[16,80],[80,80],[80,16],[16,16]],np.float32)
  p3=np.array([[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],np.float32)
  n=np.tile([0,0,1],(4,1)).astype(np.float32)
  skin=np.zeros((96,96),np.uint8); skin[12:84,12:84]=255
  return img,{"uv_coords":uv,"triangles":tri,"vertices_2d":p2,"vertices_3d":p3,"normals_3d":n,"skin_mask":skin,"vertices_2d_origin":"top_left"}
 def test_binary_255_mask(self):
  m=np.zeros((10,10),np.uint8);m[2:8,2:8]=255
  self.assertEqual(int(normalize_skin_mask(m,m.shape).sum()),36)
 def test_two_masks_and_provenance(self):
  img,recon=self.fixture(); cfg=UVExtractionConfig(64,1,cache_dir=tempfile.mkdtemp())
  r=UVGenerator(cfg,MorphCompletionConfig()).generate(img,recon)
  self.assertEqual(r.analysis_bgr.shape,(64,64,3));self.assertFalse(np.any(r.synthetic_mask&r.observed_face_mask))
  self.assertTrue(np.array_equal(r.morph_bgr[r.observed_face_mask],np.clip(r.morph_bgr[r.observed_face_mask],0,255)))
  self.assertTrue(np.all(r.confidence[~r.observed_skin_mask]==0))
 def test_preview_is_not_morph_alias(self):
  img,recon=self.fixture(); r=UVGenerator(UVExtractionConfig(64,1,cache_dir=tempfile.mkdtemp())).generate(img,recon)
  with tempfile.TemporaryDirectory() as d:
   save_uv_result(r,d); a=cv2.imread(str(Path(d)/"uv_preview.png"));b=cv2.imread(str(Path(d)/"uv_synthetic.png"))
   self.assertFalse(np.array_equal(a,b))
 def test_legacy_stage1_contract(self):
  img,recon=self.fixture()
  cfg=HDUVConfig(uv_size=64,super_sample=1,cache_dir=tempfile.mkdtemp(),enable_delighting=False,force_all_triangles_visible=False,device="cpu")
  analysis,morph,observed,confidence,aux=HDUVTextureGenerator(cfg).generate(img,recon)
  self.assertEqual(analysis.shape,(64,64,3)); self.assertIn("uv_synthetic_mask",aux)
  self.assertFalse(SkinAnalyzer().analyze_uv_geometry()["available"])
 def test_soft_transition_mask(self):
  h=w=96
  tex=np.zeros((h,w,3),np.uint8)
  tex[:,48:]=(80,140,210)
  observed=np.zeros((h,w),bool); observed[:,48:]=True
  valid=np.ones((h,w),bool)
  cfg=MorphCompletionConfig(color_match=False,real_feather_px=8,hidden_feather_px=18)
  r=complete_morph_texture(tex,observed,valid,cfg)
  self.assertTrue(r.transition_mask.any())
  self.assertGreater(len(np.unique(np.round(r.transition_alpha*255))),16)
  self.assertTrue(np.array_equal(r.texture_bgr[r.trusted_real_core],tex[r.trusted_real_core]))
  self.assertTrue(np.all((r.transition_alpha>=0)&(r.transition_alpha<=1)))
 def test_old_config_object_uses_feather_defaults(self):
  from types import SimpleNamespace
  tex=np.zeros((64,64,3),np.uint8); tex[:,32:]=(80,140,210)
  obs=np.zeros((64,64),bool); obs[:,32:]=True
  cfg=SimpleNamespace(enabled=True,method="uv_mirror",color_match=False,
      small_hole_max_area=1200,inpaint_radius=3.0,background="black")
  r=complete_morph_texture(tex,obs,np.ones((64,64),bool),cfg)
  self.assertTrue(r.transition_mask.any())

if __name__=='__main__': unittest.main()
