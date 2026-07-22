from __future__ import annotations
import hashlib
from pathlib import Path
import cv2,numpy as np
from ...status_logger import log_status, log_blocker, log_warning
class FFHQWrinkleAdapter:
 def __init__(self,repo,checkpoint,device='cpu'):
  self.repo=Path(repo);self.checkpoint=Path(checkpoint);self.device=device;self.model=None;self.parser=None
  if not self.checkpoint.is_file():raise FileNotFoundError(self.checkpoint)
  self.weight_sha256=hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
  self.fp_cp=self.repo/'res/cp/face_segmentation.pth'
 def _load(self):
  if self.model is not None:return
  import torch,sys
  sys.path.insert(0,str(self.repo)) if str(self.repo) not in sys.path else None
  from unet import UNet
  self.model=UNet(3,1,bilinear=False,pretrained=False,freeze_encoder=False).to(self.device).eval();ck=torch.load(self.checkpoint,map_location=self.device,weights_only=True);self.model.load_state_dict(ck.get('model_state_dict',ck))
 def _load_parser(self):
  if self.parser is not None:return
  if not self.fp_cp.is_file():return
  import torch,sys
  pp=self.repo/'face-parsing.PyTorch'
  sys.path=[p for p in sys.path if not (Path(p)/'model').is_dir()]
  sys.path.insert(0,str(pp)) if str(pp) not in sys.path else None
  if 'model' in sys.modules:del sys.modules['model']
  from model import BiSeNet
  self.parser=BiSeNet(n_classes=19).to(self.device).eval();self.parser.load_state_dict(torch.load(self.fp_cp,map_location=self.device,weights_only=True))
 @staticmethod
 def _skin_mask(bgr,parser):
  if parser is None:return None
  import torch
  dev=next(parser.parameters()).device
  rgb=cv2.cvtColor(cv2.resize(bgr,(512,512)),cv2.COLOR_BGR2RGB).astype(np.float32)/255.;rgb=(rgb-[.485,.456,.406])/[.229,.224,.225];x=torch.from_numpy(rgb.transpose(2,0,1)[None].astype(np.float32)).to(dev)
  with torch.inference_mode():lab=parser(x)[0][0].argmax(0).cpu().numpy().astype(np.uint8)
  return cv2.resize(lab,(bgr.shape[1],bgr.shape[0]),interpolation=cv2.INTER_NEAREST)==1
 def predict(self,bgr,skin_mask=None):
  self._load();self._load_parser();import torch
  if skin_mask is None and self.parser is not None:
   skin_mask=self._skin_mask(bgr,self.parser)
  masked=bgr if skin_mask is None else np.where(skin_mask[...,None],bgr,0).astype(np.uint8)
  x=cv2.cvtColor(cv2.resize(masked,(512,512)),cv2.COLOR_BGR2RGB).astype(np.float32)/255.;x=(x-[.485,.456,.406])/[.229,.224,.225];x=torch.from_numpy(x.transpose(2,0,1)[None].astype(np.float32)).to(self.device)
  with torch.inference_mode():p=torch.sigmoid(self.model(x))[0,0].cpu().numpy()
  return cv2.resize(p,(bgr.shape[1],bgr.shape[0])).astype(np.float32)
 def metadata(self):return {'backend':'vendored_ffhq_unet+bisenet_skimmask','checkpoint_sha256':self.weight_sha256,'face_parsing_available':self.fp_cp.is_file(),'device':self.device,'domain_warning':'FFHQ web faces; no universal threshold'}
