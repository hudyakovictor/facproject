"""🔄 CALLBACK (pytest) → /uv_module: HD UV генератор (config guards, render contract).
"""
import unittest,numpy as np
from uv_module import HDUVConfig,HDUVTextureGenerator
class TestUVModule(unittest.TestCase):
 def setUp(self):
  y,x=np.mgrid[:96,:96];self.im=np.dstack((x*2%256,y*2%256,(x+y)*2%256)).astype(np.uint8);self.r={'vertices_2d':np.array([[12,12],[82,12],[82,82],[12,82]],np.float32),'vertices_3d':np.zeros((4,3),np.float32),'triangles':np.array([[0,1,2],[0,2,3]]),'uv_coords':np.array([[.15,.15],[.85,.15],[.85,.85],[.15,.85]],np.float32)}
 def test_single_render_and_provenance(self):
  render,obs,conf,aux=HDUVTextureGenerator(HDUVConfig(uv_size=256)).generate(self.im,self.r);self.assertEqual(render.shape,(256,256,3));self.assertFalse(np.any(aux['uv_synthetic_mask']&obs))
 def test_resolution_guard(self):
  with self.assertRaises(ValueError):HDUVConfig(uv_size=1001)
if __name__=='__main__':unittest.main()
