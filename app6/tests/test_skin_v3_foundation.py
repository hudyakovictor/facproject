import tempfile,unittest
from pathlib import Path
import numpy as np
from app6.stage1.skin.contracts import EvidenceState,validate_missing
from app6.stage1.skin.projection import RasterResult, rasterize_surface, project_atlas
from app6.stage1.skin.atlas_registry import AtlasRegistry
from app6.stage1.skin.serialization import atomic_npz,validate_npz_no_pickle
from app6.stage1.skin.surface_geometry import SurfaceGeometry
from app6.stage1.skin.input_provenance import decode_oriented
from app6.stage1.skin.texture.basic import extract_basic
class SkinV3FoundationTests(unittest.TestCase):
 def test_background_barycentric_and_zbuffer(self):
  xy=np.array([[1,1],[8,1],[1,8],[1,1],[8,1],[1,8]],np.float32);z=np.array([2,2,2,1,1,1],np.float32);n=np.tile([0,0,1],(6,1));f=np.array([[0,1,2],[3,4,5]]);r=rasterize_surface(xy,z,n,f,(10,10));self.assertEqual(r.triangle_id[2,2],1);self.assertAlmostEqual(float(r.barycentric[2,2].sum()),1,places=5);self.assertEqual(r.triangle_id[9,9],-1);self.assertTrue(np.all(r.source_xy[9,9]==-1))
 def test_no_zero_missing_sentinel(self):
  with self.assertRaises(ValueError):validate_missing(0,EvidenceState.NOT_OBSERVED)
 def test_npz_no_pickle(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.npz';atomic_npz(p,a=np.arange(4));self.assertTrue(validate_npz_no_pickle(p));
   with self.assertRaises(TypeError):atomic_npz(p,b=np.array([{}],object))
 def test_exif_orientation_is_explicit(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'o.jpg';im=Image.new('RGB',(7,3),(10,20,30));ex=im.getexif();ex[274]=6;im.save(p,exif=ex);bgr,meta=decode_oriented(p);self.assertEqual(bgr.shape[:2],(7,3));self.assertTrue(meta['orientation_applied']);self.assertEqual(meta['exif_orientation'],6)
 def test_atlas_fails_loud_on_wrong_topology(self):
  atlas=AtlasRegistry(Path(__file__).parents[1]/'atlas/texture_zones_bfm35709_v3.npz')
  with self.assertRaises(ValueError):atlas.verify_topology(np.zeros((70789,3),np.int32))
 def test_atlas_projection_parent_and_w14_bits(self):
  atlas=AtlasRegistry(Path(__file__).parents[1]/'atlas/texture_zones_bfm35709_v3.npz');face=int(np.flatnonzero(atlas.skin)[0]);tid=np.array([[face,-1]],np.int32);r=RasterResult(tid,np.zeros((1,2,3),np.float32),np.zeros((1,2),np.float32),np.zeros((1,2,3),np.float32),np.ones((1,2),np.float32),np.ones((1,2),np.float32),np.ones((1,2),np.float32),np.zeros((1,2,2),np.int32));p=project_atlas(r,atlas,np.ones((1,2),bool));self.assertEqual(atlas.S_parent[p['zone_id_s40'][0,0]],p['zone_id_a20'][0,0]);self.assertEqual(p['zone_id_a20'][0,1],-1);self.assertEqual(p['wrinkle_bits_w14'].shape[0],2)
 def test_basic_texture_missing_is_nan_not_zero(self):
  im=np.full((8,8,3),128,np.uint8);A=np.full((8,8),-1,np.int8);S=A.copy();A[:,:]=0;S[:,:]=0;r=extract_basic(im,np.ones((8,8)),A,S,min_support=100);self.assertEqual(r[0]['state'],'not_measurable');self.assertTrue(np.isnan(r[0]['luminance_median']))
 def test_tangent_frame_orthonormal(self):
  v=np.array([[0,0,0],[1,0,0],[0,1,0]],float);f=np.array([[0,1,2]]);T,B,N=SurfaceGeometry(v,f,False).tangent_frames();self.assertTrue(np.allclose((T*N).sum(1),0,atol=1e-6));self.assertTrue(np.allclose(np.linalg.norm(B,axis=1),1))
if __name__=='__main__':unittest.main()
