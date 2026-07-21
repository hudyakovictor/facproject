from __future__ import annotations
import cv2,numpy as np
from .contracts import Applicability,EvidenceState,ReasonCode
FAMILIES=('geometry','macro_texture','meso_texture','micro_texture','wrinkles','pigmentation','material_optics','local_feature_matching')
def _robust01(x,m):return np.clip(x/(float(np.percentile(x[m],90))+1e-6),0,1) if np.any(m) else np.zeros_like(x)
def _jpeg(g):
 o=np.zeros_like(g,np.float32)
 for x in range(8,g.shape[1],8):o[:,x-1:x+1]=abs(g[:,x:x+1]-g[:,x-1:x])
 for y in range(8,g.shape[0],8):o[y-1:y+1]=np.maximum(o[y-1:y+1],abs(g[y:y+1]-g[y-1:y]))
 return cv2.GaussianBlur(o,(0,0),1)
def _scale(t):
 v=t>=0;o=np.zeros(t.shape,np.float32)
 if np.any(v):ids,c=np.unique(t[v],return_counts=True);q=np.zeros(int(ids.max())+1,np.float32);q[ids]=np.sqrt(c);o[v]=q[t[v]]
 return o
def quality_maps(bgr,domain,incidence,projection_confidence,triangle_id):
 g=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY).astype(np.float32)/255.;d=np.asarray(domain,bool);gx=cv2.Sobel(g,cv2.CV_32F,1,0);gy=cv2.Sobel(g,cv2.CV_32F,0,1);ten=np.hypot(gx,gy);focus=_robust01(ten,d);med=cv2.medianBlur((g*255).astype(np.uint8),3)/255.;hp=abs(g-med);noise=float(1.4826*np.median(abs(hp[d]-np.median(hp[d])))) if np.any(d) else 1.;ns=np.full(g.shape,np.clip(1-noise/.12,0,1),np.float32);block=_jpeg(g);bs=float(np.mean(block[d])) if np.any(d) else 1.;proc=np.clip(1-block/(np.percentile(block[d],95)+1e-6)*.5,0,1) if np.any(d) else np.zeros_like(g);lap=cv2.Laplacian(g,cv2.CV_32F);halo=float(np.mean((abs(lap[d])>.15)&(ten[d]>.1))) if np.any(d) else 1.;local_var=cv2.GaussianBlur(g*g,(0,0),2)-cv2.GaussianBlur(g,(0,0),2)**2;denoise=float(np.mean(local_var[d]<1e-5)) if np.any(d) else 1.;F=abs(np.fft.rfft2((g-g.mean())*np.outer(np.hanning(g.shape[0]),np.hanning(g.shape[1]))));resize_periodicity=float(np.max(F[:,1:])/(np.mean(F[:,1:])+1e-8)) if F.shape[1]>1 else 0.;hsv=cv2.cvtColor(bgr,cv2.COLOR_BGR2HSV);spec=(hsv[...,2]>245)&(hsv[...,1]<35)&d;shadow=(g<.08)&d;clip=((g<.015)|(g>.985))&d;exp=np.clip(1-abs(g-.5)*2,0,1);inc=np.asarray(incidence,np.float32);proj=np.asarray(projection_confidence,np.float32);scale=_scale(triangle_id);eff=scale*focus*np.sqrt(np.clip(inc,0,1))*proc*ns;w=(focus*exp*proj*proc*ns*(~spec)*(~shadow)*d).astype(np.float32)
 return {'focus_transfer':focus.astype(np.float32),'tenengrad':ten,'noise_survival':ns,'jpeg_block_map':block,'processing_survival':proc,'exposure_weight':exp,'specular_mask':spec,'deep_shadow_mask':shadow,'clipping_mask':clip,'incidence_weight':inc,'projection_confidence':proj,'projected_scale_px_sqrt':scale,'effective_resolution':eff,'hair_probability_available':np.array(False),'external_occlusion_available':np.array(False),'quality_weight':w,'global_noise_level':np.array(noise,np.float32),'global_jpeg_block_score':np.array(bs,np.float32),'global_sharpening_halo_score':np.array(halo,np.float32),'global_denoise_flat_fraction':np.array(denoise,np.float32),'global_resize_periodicity_score':np.array(resize_periodicity,np.float32)}
def applicability(m,d,W,H):
 n=int(d.sum());base={'pixels':n,'coverage':float(n/d.size),'focus':float(np.median(m['focus_transfer'][d])) if n else 0.,'projection':float(np.mean(m['projection_confidence'][d])) if n else 0.,'incidence':float(np.mean(m['incidence_weight'][d])) if n else 0.,'specular_fraction':float(np.mean(m['specular_mask'][d])) if n else 0.,'effective_resolution_median':float(np.median(m['effective_resolution'][d])) if n else 0.,'noise_level':float(m['global_noise_level']),'jpeg_block_score':float(m['global_jpeg_block_score']),'sharpening_halo_score':float(m['global_sharpening_halo_score']),'denoise_flat_fraction':float(m['global_denoise_flat_fraction']),'resize_periodicity_score':float(m['global_resize_periodicity_score']),'effective_support':float(m['quality_weight'][d].sum())};out={}
 for fam in FAMILIES:
  r=[];s=EvidenceState.USABLE
  if n<100:s=EvidenceState.NOT_OBSERVED;r+=[ReasonCode.SELF_OCCLUDED.value]
  elif base['projection']<.2:s=EvidenceState.NOT_MEASURABLE;r+=[ReasonCode.PROJECTION_UNSTABLE.value]
  elif base['incidence']<.25:s=EvidenceState.COARSE_ONLY;r+=[ReasonCode.HIGH_INCIDENCE_ANGLE.value]
  if base['focus']<.12:s=EvidenceState.NOT_MEASURABLE;r+=[ReasonCode.EXCESSIVE_BLUR.value]
  if base['noise_level']>.08:r+=[ReasonCode.EXCESSIVE_NOISE.value];s=EvidenceState.COARSE_ONLY if s is EvidenceState.USABLE else s
  if fam in {'micro_texture','material_optics','local_feature_matching'} and (base['effective_resolution_median']<1.2 or min(W,H)<700):s=EvidenceState.NOT_MEASURABLE;r+=[ReasonCode.LOW_EFFECTIVE_RESOLUTION.value]
  out[fam]=Applicability(fam,s,base['effective_support'],tuple(dict.fromkeys(r)),base).to_dict()
 return out
