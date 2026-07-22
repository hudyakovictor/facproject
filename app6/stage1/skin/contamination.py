"""🔬 EXPERIMENTAL → Детектор загрязнений (борода/макияж/волосы) на skin-ROI.
🚪 API: predict(), metadata()
⚠️ IN PROGRESS: пороги подобраны на малой выборке — требуется калибровка.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import cv2,numpy as np
from ..status_logger import log_status, log_blocker, log_warning
class FaceParsingAdapter:
 def __init__(self,repo,checkpoint,device='cpu'):
  self.repo=Path(repo);self.checkpoint=Path(checkpoint);self.device=device;self.net=None
  if not self.checkpoint.is_file():raise FileNotFoundError(self.checkpoint)
  self.sha256=hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
 def _load(self):
  if self.net is not None:return
  import torch,sys
  pp=self.repo/'face-parsing.PyTorch'
  # remove any conflicting 'model' import (3ddfa_v3/model/ namespace package)
  sys.path=[p for p in sys.path if not (Path(p)/'model').is_dir()]
  sys.path.insert(0,str(pp)) if str(pp) not in sys.path else None
  if 'model' in sys.modules:del sys.modules['model']
  from model import BiSeNet
  self.net=BiSeNet(n_classes=19).to(self.device).eval();self.net.load_state_dict(torch.load(self.checkpoint,map_location=self.device,weights_only=True))
 # 🔬 EXPERIMENTAL → вероятности загрязнений по ROI
 def predict(self,bgr):
  self._load();import torch
  rgb=cv2.cvtColor(cv2.resize(bgr,(512,512)),cv2.COLOR_BGR2RGB).astype(np.float32)/255.;rgb=(rgb-[.485,.456,.406])/[.229,.224,.225];x=torch.from_numpy(rgb.transpose(2,0,1)[None].astype(np.float32)).to(self.device)
  with torch.inference_mode():lab=self.net(x)[0][0].argmax(0).cpu().numpy().astype(np.uint8)
  lab=cv2.resize(lab,(bgr.shape[1],bgr.shape[0]),interpolation=cv2.INTER_NEAREST);return {'labels':lab,'hair':lab==13,'glasses':lab==3,'external_occlusion':np.isin(lab,[14,15,16,17,18])}
 # 📤 Метаданные модели контаминации
 def metadata(self):return {'backend':'BiSeNet_19class','checkpoint_sha256':self.sha256,'device':self.device}
