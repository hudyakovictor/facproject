from __future__ import annotations
import json
from pathlib import Path
import cv2
import numpy as np
from .config import LabConfig
from .records import load_record, to_original_image
from .mesh_patches import build_vertex_patches, vertex_patch_to_uv, uv_mask_to_image
from .graphs import skeletonize_probability, graph_summary, comparison_metrics
from .identity import compare_pair


def _json_default(x):
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,np.ndarray): return x.tolist()
    raise TypeError(type(x).__name__)

def _overlay(base, prob, skel, support):
    out=(base.astype(np.float32)*.55).astype(np.uint8)
    heat=cv2.applyColorMap(np.round(np.clip(prob,0,1)*255).astype(np.uint8),cv2.COLORMAP_TURBO)
    a=(np.clip(prob,0,1)*.55)[...,None]
    out=np.where(support[...,None],np.clip(out*(1-a)+heat*a,0,255).astype(np.uint8),out)
    out[skel]=(255,255,255)
    return out

def _image_overlay(bgr, prob, skel, support):
    out = bgr.copy()
    heat = cv2.applyColorMap(np.round(np.clip(prob, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    a = (np.clip(prob, 0, 1) * .60)[..., None]
    out = np.where(support[..., None], np.clip(out * (1 - a) + heat * a, 0, 255).astype(np.uint8), out)
    out[skel] = (255, 255, 255)
    return out

def process_record(record_dir: str|Path, output_dir: str|Path, backend, cfg: LabConfig) -> dict:
    from uv_module import UVGenerator, UVExtractionConfig, MorphCompletionConfig
    rec=load_record(record_dir); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    r=rec.reconstruction
    recon={"vertices_2d":to_original_image(r["vertices_image_224"],r["trans_params"]),"vertices_3d":r["vertices_camera"],"triangles":r["triangles"],"uv_coords":r["uv_coords"],"normals_3d":r["normals_posed"],"skin_mask":rec.skin_mask,"vertices_2d_origin":"top_left"}
    uv=UVGenerator(UVExtractionConfig(uv_size=cfg.uv_size,super_sample=cfg.super_sample),MorphCompletionConfig(enabled=False,method="disabled")).generate(rec.image_bgr,recon)
    if cfg.analysis_region == "skin_only":
        analysis_mask = rec.skin_mask
        uv_support = uv.observed_skin_mask
        uv_base = uv.analysis_bgr
        support_confidence = uv.confidence
    else:
        # For first-pass FFHQ QA we intentionally do NOT remove eyes/lips from
        # the input. The network must be inspected on the whole visible face;
        # later filters decide which lines are valid evidence.
        analysis_mask = np.ones(rec.image_bgr.shape[:2], bool)
        uv_support = uv.observed_face_mask
        uv_base = uv.morph_bgr
        support_confidence = np.clip(uv.incidence, 0, 1).astype(np.float32)
    prob=backend.predict(rec.image_bgr,analysis_mask)
    model_input = getattr(backend, "last_input_bgr", None)
    if model_input is None:
        model_input = rec.image_bgr
    binary,skel=skeletonize_probability(prob,analysis_mask,cfg.probability_threshold,cfg.min_component_px)
    uv_prob=cv2.remap(prob,uv.source_x,uv.source_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    uv_skel=cv2.remap(skel.astype(np.uint8),uv.source_x,uv.source_y,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT).astype(bool)
    uv_prob[~uv_support]=0; uv_skel&=uv_support
    vertex_patches,patch_meta=build_vertex_patches(r["vertices_object_normalized"],r["triangles"],cfg.patch_radius)
    patches={}; patch_masks={}
    for name,vmask in vertex_patches.items():
        umask=vertex_patch_to_uv(vmask,r["triangles"],uv.triangle_id)
        imask=uv_mask_to_image(umask,uv.source_x,uv.source_y,uv_support,rec.image_bgr.shape[:2])&analysis_mask
        observed=umask&uv_support&(support_confidence>=cfg.confidence_threshold)
        canonical=max(1,int(umask.sum())); coverage=float(observed.sum()/canonical)
        pskel=skel&imask
        patches[name]={**patch_meta[name],"canonical_uv_pixels":canonical,"observed_uv_pixels":int(observed.sum()),"coverage":coverage,"measurable":bool(coverage>=cfg.min_patch_coverage),"graph":graph_summary(pskel)}
        patch_masks[name]=umask
        cv2.imwrite(str(out/f"patch_{name}_support.png"),observed.astype(np.uint8)*255)
    cv2.imwrite(str(out/"image_wrinkle_probability.png"),np.round(prob*255).astype(np.uint8))
    cv2.imwrite(str(out/"image_wrinkle_skeleton.png"),skel.astype(np.uint8)*255)
    cv2.imwrite(str(out/"image_model_input.png"),model_input)
    cv2.imwrite(str(out/"image_model_input_overlay.png"),_image_overlay(model_input,prob,skel,analysis_mask))
    cv2.imwrite(str(out/"image_wrinkle_overlay.png"),_image_overlay(rec.image_bgr,prob,skel,analysis_mask))
    cv2.imwrite(str(out/"uv_observed_preview.png"),uv_base)
    cv2.imwrite(str(out/"uv_observed_skin_preview.png"),uv.analysis_bgr)
    cv2.imwrite(str(out/"uv_observed_face_preview.png"),uv.morph_bgr)
    cv2.imwrite(str(out/"uv_wrinkle_probability.png"),np.round(uv_prob*255).astype(np.uint8))
    cv2.imwrite(str(out/"uv_wrinkle_skeleton.png"),uv_skel.astype(np.uint8)*255)
    cv2.imwrite(str(out/"uv_wrinkle_overlay.png"),_overlay(uv_base,uv_prob,uv_skel,uv_support))
    report={"schema":"surface-evidence-lab-1","record":Path(record_dir).name,"wrinkle_backend":backend.name,"analysis_region":cfg.analysis_region,"detail_mode":getattr(backend,"detail_mode","none"),"warning":"Experimental candidate visualization; not identity evidence.","image_graph":graph_summary(skel),"patches":patches}
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=_json_default),encoding="utf-8")
    np.savez_compressed(out/"surface_evidence.npz",image_probability=prob.astype(np.float16),image_skeleton=skel,uv_probability=uv_prob.astype(np.float16),uv_skeleton=uv_skel,uv_observed=uv_support,uv_confidence=support_confidence.astype(np.float16),triangle_id=uv.triangle_id,barycentric=uv.barycentric.astype(np.float16),source_x=uv.source_x.astype(np.float32),source_y=uv.source_y.astype(np.float32),patch_names=np.asarray(list(patch_masks)),patch_masks=np.stack(list(patch_masks.values())))
    return report

def compare_records(a_dir: str|Path,b_dir: str|Path,out_dir: str|Path):
    a=np.load(Path(a_dir)/"surface_evidence.npz",allow_pickle=False); b=np.load(Path(b_dir)/"surface_evidence.npz",allow_pickle=False)
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    names=[str(x) for x in a["patch_names"]]; result={"schema":"surface-comparison-lab-1","warning":"UV visualization only; final distances must be mesh-geodesic.","patches":{}}
    common=a["uv_observed"]&b["uv_observed"]&(a["uv_confidence"]>=.4)&(b["uv_confidence"]>=.4)
    aa=a["uv_skeleton"]; bb=b["uv_skeleton"]
    canvas=np.zeros((*common.shape,3),np.uint8); canvas[aa&common]=(0,0,255); canvas[bb&common]=(255,255,0); canvas[aa&bb&common]=(255,255,255); canvas[~common]=(30,30,30)
    cv2.imwrite(str(out/"uv_wrinkle_comparison.png"),canvas)
    for i,name in enumerate(names): result["patches"][name]=comparison_metrics(aa,bb,common&a["patch_masks"][i]&b["patch_masks"][i])
    (out/"comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    # Also write the newer identity-consistency report expected by the
    # multi-photo lab workflow.  The older comparison.json is kept for
    # backward-compatible visual debugging.
    compare_pair(a_dir, b_dir, out_dir)
    return result
