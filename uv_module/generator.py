from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import cv2
import numpy as np
from .config import UVExtractionConfig, MorphCompletionConfig
from .rasterizer import load_or_build_uv_raster, interpolate_vertex_attribute
from .visibility import compute_visibility
from .completion import complete_morph_texture

_INTERP={"linear":cv2.INTER_LINEAR,"cubic":cv2.INTER_CUBIC,"lanczos4":cv2.INTER_LANCZOS4}

@dataclass(frozen=True)
class UVResult:
    analysis_bgr: np.ndarray
    morph_bgr: np.ndarray
    observed_skin_mask: np.ndarray
    observed_face_mask: np.ndarray
    mirror_mask: np.ndarray
    inpaint_mask: np.ndarray
    synthetic_mask: np.ndarray
    unresolved_mask: np.ndarray
    transition_alpha: np.ndarray
    transition_mask: np.ndarray
    trusted_real_core: np.ndarray
    atlas_valid_mask: np.ndarray
    confidence: np.ndarray
    incidence: np.ndarray
    footprint: np.ndarray
    source_x: np.ndarray
    source_y: np.ndarray
    triangle_id: np.ndarray
    barycentric: np.ndarray
    tri_visibility: np.ndarray


def normalize_skin_mask(mask: np.ndarray, shape: tuple[int,int]) -> np.ndarray:
    a=np.asarray(mask)
    if a.ndim==3 and a.shape[-1]==8:
        x=a.astype(np.float32); x=x/(255.0 if x.max()>1.5 else 1.0)
        skin=np.maximum(x[...,7],x[...,4]); excluded=np.maximum.reduce([x[...,i] for i in (0,1,2,3,5,6)])
        a=np.clip(skin*(1-np.clip(excluded,0,1)),0,1)
    elif a.ndim==3 and a.shape[-1]==1: a=a[...,0]
    if a.ndim!=2 or a.shape!=shape: raise ValueError(f"skin_mask must have shape {shape}, got {a.shape}")
    if a.dtype==bool: return a.astype(np.float32)
    x=np.nan_to_num(a.astype(np.float32)); u=np.unique(x)
    if u.size<=2:
        return (x/(float(u.max()) or 1.0)).astype(np.float32)
    if x.max()>1.5: x/=255.0
    return np.clip(x,0,1)

class UVGenerator:
    def __init__(self, extraction: UVExtractionConfig|None=None, completion: MorphCompletionConfig|None=None):
        self.cfg=extraction or UVExtractionConfig(); self.morph_cfg=completion or MorphCompletionConfig()

    def generate(self, bgr: np.ndarray, recon: dict[str,Any]) -> UVResult:
        img=np.asarray(bgr)
        if img.ndim==2: img=cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
        h,w=img.shape[:2]; S=self.cfg.uv_size; ss=self.cfg.super_sample
        uv=np.asarray(recon["uv_coords"],np.float32); tri=np.asarray(recon["triangles"],np.int64)
        p2=np.asarray(recon["vertices_2d"],np.float32)[:,:2]; p3=np.asarray(recon.get("vertices_3d",recon.get("vertices")),np.float32)
        normals=np.asarray(recon["normals_3d"],np.float32)
        raster=load_or_build_uv_raster(uv,tri,self.cfg.grid_size,self.cfg.resolved_cache_dir())
        pos=interpolate_vertex_attribute(raster,tri,p2); mx=pos[...,0].astype(np.float32); my=pos[...,1].astype(np.float32)
        origin=str(recon.get("vertices_2d_origin","top_left")).lower()
        if origin in {"bottom","bottom_left","bottom-origin"}: my=(h-1)-my
        elif origin not in {"top","top_left","top-origin"}: raise ValueError(f"unsupported origin {origin}")
        sample=cv2.remap(img,mx,my,_INTERP[self.cfg.interpolation],borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        inframe=raster.valid&(mx>=0)&(mx<=w-1)&(my>=0)&(my<=h-1)
        vis=compute_visibility(p2,p3[:,2],normals,tri,self.cfg.zbuffer_size,self.cfg.depth_tolerance,self.cfg.angle_soft_lo,self.cfg.angle_soft_hi)
        angle=interpolate_vertex_attribute(raster,tri,vis.angle_weight); occ=interpolate_vertex_attribute(raster,tri,vis.occlusion_visible.astype(np.float32))
        valid_ss=raster.valid&inframe; sample[~valid_ss]=0
        def down(a): return a if ss==1 else cv2.resize(a,(S,S),interpolation=cv2.INTER_AREA)
        cov=down(valid_ss.astype(np.float32)); tex=down(sample)/np.maximum(cov[...,None],1e-6); tex[cov<=1e-6]=0
        atlas=down(raster.valid.astype(np.float32))>.5; incidence=np.clip(down(angle),0,1); occf=np.clip(down(occ),0,1)
        face_score=incidence*occf*np.clip(down(inframe.astype(np.float32)),0,1)
        observed_face=atlas&(face_score>=self.cfg.observed_threshold)
        skin_src=recon.get("skin_mask")
        skinw=np.ones((S,S),np.float32)
        if skin_src is not None:
            sm=normalize_skin_mask(skin_src,(h,w)); skin_ss=cv2.remap(sm,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            skinw=down(skin_ss)
        observed_skin=observed_face&(skinw>=self.cfg.skin_mask_threshold)
        if self.cfg.observed_erode_px>0:
            k=2*self.cfg.observed_erode_px+1; se=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))
            observed_skin=cv2.erode(observed_skin.astype(np.uint8),se).astype(bool)
        gx=cv2.Sobel(mx,cv2.CV_32F,1,0)/8; gy=cv2.Sobel(mx,cv2.CV_32F,0,1)/8
        hx=cv2.Sobel(my,cv2.CV_32F,1,0)/8; hy=cv2.Sobel(my,cv2.CV_32F,0,1)/8
        foot=down(np.clip(np.sqrt(np.abs(gx*hy-gy*hx)*ss*ss/max(self.cfg.footprint_target_px,1e-6)),0,1))
        conf=np.clip(face_score*skinw*foot,0,1).astype(np.float32); conf[~observed_skin]=0
        face=np.clip(tex,0,255).astype(np.uint8); face[~observed_face]=0
        analysis=np.clip(tex,0,255).astype(np.uint8); analysis[~observed_skin]=0
        comp=complete_morph_texture(face,observed_face,atlas,self.morph_cfg)
        sx=down(mx); sy=down(my); sx[~atlas]=-1; sy[~atlas]=-1
        tri_id=raster.tri_map if ss==1 else cv2.resize(raster.tri_map.astype(np.float32),(S,S),interpolation=cv2.INTER_NEAREST).astype(np.int32)
        bary=raster.bary if ss==1 else cv2.resize(raster.bary,(S,S),interpolation=cv2.INTER_LINEAR)
        return UVResult(analysis,comp.texture_bgr,observed_skin,observed_face,comp.mirror_mask,comp.inpaint_mask,comp.synthetic_mask,comp.unresolved_mask,comp.transition_alpha,comp.transition_mask,comp.trusted_real_core,atlas,conf,incidence.astype(np.float32),foot.astype(np.float32),sx.astype(np.float32),sy.astype(np.float32),tri_id,bary.astype(np.float32),vis.tri_visibility)

class HDUVTextureGenerator(UVGenerator):
    """Legacy tuple adapter used by the existing app6 Stage-1 call site."""
    def generate(self, bgr: np.ndarray, recon: dict[str,Any]):
        r = super().generate(bgr, recon)
        synthetic_contribution = np.where(
            r.synthetic_mask | r.transition_mask,
            1.0 - r.transition_alpha,
            0.0,
        ).astype(np.float16)
        aux = {
            "uv_is_original": r.observed_skin_mask.copy(),
            "tri_visibility": r.tri_visibility,
            "uv_synthetic_mask": r.synthetic_mask,
            "uv_synthetic_valid": r.atlas_valid_mask & ~r.observed_skin_mask,
            # Existing Stage-1 already stores this field in uv.npz.  It now
            # carries the exact visual synthetic contribution (0..1), so the
            # feather mask survives without changing app6/stage1/assets.py.
            "uv_synthetic_confidence": synthetic_contribution,
            "synthetic_mask": r.synthetic_mask,
            "mirror_mask": r.mirror_mask,
            "inpaint_mask": r.inpaint_mask,
            "unresolved_mask": r.unresolved_mask,
            "transition_alpha": r.transition_alpha.astype(np.float16),
            "transition_mask": r.transition_mask,
            "trusted_real_core": r.trusted_real_core,
            "atlas_valid": r.atlas_valid_mask,
            "angle_weight": r.incidence.astype(np.float16),
            "footprint": r.footprint.astype(np.float16),
        }
        return r.analysis_bgr, r.morph_bgr, r.observed_skin_mask, r.confidence, aux
