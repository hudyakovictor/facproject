import unittest
import numpy as np
from surface_lab.graphs import skeletonize_probability
from surface_lab.mesh_patches import build_vertex_patches, vertex_patch_to_uv

class LabTests(unittest.TestCase):
 def test_skeleton_respects_mask(self):
  p=np.zeros((32,32),np.float32); p[16,4:28]=1
  m=np.zeros((32,32),bool); m[8:24,8:24]=True
  _,s=skeletonize_probability(p,m,.5,2)
  self.assertTrue(s.any()); self.assertFalse(s[:,:8].any()); self.assertFalse(s[:,24:].any())
 def test_patch_to_uv(self):
  v=np.array([[-1,0,0],[1,0,0],[1,1,0],[-1,1,0]],np.float32)
  f=np.array([[0,1,2],[0,2,3]],np.int64)
  patches,_=build_vertex_patches(v,f,2.1)
  tid=np.array([[0,1],[-1,0]])
  mask=vertex_patch_to_uv(next(iter(patches.values())),f,tid)
  self.assertFalse(mask[1,0]); self.assertEqual(mask.shape,tid.shape)

if __name__=="__main__": unittest.main()
