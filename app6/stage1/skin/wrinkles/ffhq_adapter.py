from __future__ import annotations
import hashlib,sys
from pathlib import Path
import cv2,numpy as np
class FFHQWrinkleAdapter:
 def __init__(self,repo,checkpoint,device='cpu'):
  self.repo=Path(repo);self.checkpoint=Path(checkpoint);self.device=device;self.model=None
  if not self.checkpoint.is_file():raise FileNotFoundError(self.checkpoint)
  self.weight_sha256=hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
 def _load(self):
  if self.model is not None:return
  import torch
  sys.path.insert(0,str(self.repo)) if str(self.repo) not in sys.path else None
  from unet import UNet
  self.model=UNet(3,1,bilinear=False,pretrained=False,freeze_encoder=False).to(self.device).eval();ck=torch.load(self.checkpoint,map_location=self.device,weights_only=True);self.model.load_state_dict(ck.get('model_state_dict',ck))
 def predict(self,bgr):
  self._load();import torch
  x=cv2.cvtColor(cv2.resize(bgr,(512,512)),cv2.COLOR_BGR2RGB).astype(np.float32)/255.;x=(x-[.485,.456,.406])/[.229,.224,.225];x=torch.from_numpy(x.transpose(2,0,1)[None].astype(np.float32)).to(self.device)
  with torch.inference_mode():p=torch.sigmoid(self.model(x))[0,0].cpu().numpy()
  return cv2.resize(p,(bgr.shape[1],bgr.shape[0])).astype(np.float32)
 def metadata(self):return {'backend':'vendored_ffhq_unet','checkpoint_sha256':self.weight_sha256,'device':self.device,'domain_warning':'FFHQ web faces; no universal threshold'}
