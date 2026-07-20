import unittest,numpy as np,cv2
from pathlib import Path
from app6.stage1.skin.texture.features import extract_texture_features,FEATURES
from app6.stage1.skin.quality import quality_maps
from app6.stage1.skin.wrinkles.classical import response_map
from app6.stage1.skin.pose_policy import PosePolicy
class NativeSkinTests(unittest.TestCase):
 def test_features(self):
  y,x=np.mgrid[:64,:64];im=np.dstack((x*4%256,y*4%256,(x+y)*2%256)).astype(np.uint8);z=np.zeros((64,64),np.int8);r=extract_texture_features(im,np.ones((64,64),np.float32),z,z);self.assertEqual((len(r),len(r[0]['values'])),(60,len(FEATURES)))
 def test_mask_limits_wrinkles(self):
  g=np.ones((64,64),np.float32)*.5;g[:,31:33]=.1;m=np.zeros_like(g,bool);m[8:56,8:56]=1;r=response_map(g,m);self.assertTrue(np.all(r[~m]==0))
 def test_blur_reduces_effective_resolution(self):
  y,x=np.mgrid[:64,:64];g=(127+60*np.sin(x/3)+30*np.sin(y/5)).clip(0,255).astype(np.uint8);im=np.dstack((g,g,g));d=np.ones((64,64),bool);o=np.ones((64,64),np.float32);t=np.zeros((64,64),np.int32);a=quality_maps(im,d,o,o,t);b=quality_maps(cv2.GaussianBlur(im,(0,0),4),d,o,o,t);self.assertGreater(np.median(a['effective_resolution']),np.median(b['effective_resolution']))
 def test_pose_policy(self):
  p=PosePolicy(Path(__file__).parents[1]/'atlas/pose_policy_v3_9bins.csv');w,m=p.weights(np.arange(20,dtype=np.int8)[None],0);self.assertEqual(m['selected_center_deg'],0);self.assertTrue(np.all((w>=0)&(w<=1)))
if __name__=='__main__':unittest.main()
