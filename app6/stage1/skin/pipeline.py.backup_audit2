"""Native-photo skin package orchestration; UV textures are never inputs."""
from __future__ import annotations
from pathlib import Path
import cv2,numpy as np
from .atlas_registry import AtlasRegistry
from .contracts import SCHEMAS
from .manifest import create_manifest,finalize_manifest
from .projection import rasterize_surface,project_atlas
from .quality import quality_maps,applicability
from .serialization import atomic_json,atomic_npz,sha256_file
from .texture.basic import extract_basic
from .texture.features import FEATURES,extract_texture_features
from .wrinkles.classical import detect as detect_wrinkles
from .wrinkles.ffhq_adapter import FFHQWrinkleAdapter
from .local_features.detector import detect as detect_local
from .material.evidence import build as material_evidence
from .sensitivity.degradation import benchmark
from .pose_policy import PosePolicy
from .contamination import FaceParsingAdapter
from .patch_sampler import sample_zone_patches
from .photometric import branches as photometric_branches
from .previews import save_previews

def build_skin_package(*,photo_id,input_path,bgr,out_dir,triangles,vertices_original_xy,vertices_depth,normals,surface_vertices,vertex_visibility,face_mask_data_path,atlas_path,coordinate_chain,models,config,pose):
 face_mask_data_path=Path(face_mask_data_path)
 if not face_mask_data_path.is_file():
  raise ValueError('face_mask.npz unavailable; refusing UV or resized fallback for skin evidence')
 with np.load(face_mask_data_path,allow_pickle=False) as fm:
  skin_mask_original=fm['mask_original'].astype(bool)
  if skin_mask_original.shape!=bgr.shape[:2]:raise ValueError('face_mask mask_original/source shape mismatch')
 root=Path(out_dir)/'skin';root.mkdir(parents=True,exist_ok=True);atlas=AtlasRegistry(atlas_path,triangles);manifest=create_manifest(photo_id,input_path,bgr,coordinate_chain=coordinate_chain,models=models,atlas=atlas.describe(),config=config,backend={'rasterizer':'numpy_cpu_zbuffer_v1'},warnings=['hair/external occlusion components unavailable until configured']);manifest['source_mask']={'path':'../face_mask.npz','preview':'../face_mask.png','sha256':sha256_file(face_mask_data_path),'array':'mask_original','semantics':'existing facial-skin mask; background/eyes/brows/lips excluded'}
 H,W=bgr.shape[:2];xy=np.asarray(vertices_original_xy,np.float32);x0=max(0,int(np.floor(xy[:,0].min()))-2);y0=max(0,int(np.floor(xy[:,1].min()))-2);x1=min(W,int(np.ceil(xy[:,0].max()))+3);y1=min(H,int(np.ceil(xy[:,1].max()))+3)
 if x1<=x0 or y1<=y0:raise ValueError('projected face outside original image')
 crop=bgr[y0:y1,x0:x1];seg=skin_mask_original[y0:y1,x0:x1];contamination_meta={'state':'weights_unavailable'};contamination_keep=np.ones(seg.shape,bool);repo=Path(atlas_path).resolve().parents[2]/'FFHQ-detect-face-wrinkles';fp=repo/'res/cp/face_segmentation.pth'
 if fp.is_file():
  parser=FaceParsingAdapter(repo,fp);cont=parser.predict(crop);contamination_keep=~(cont['hair']|cont['glasses']|cont['external_occlusion']);atomic_npz(root/'contamination_maps.npz',hair=cont['hair'],glasses=cont['glasses'],external_occlusion=cont['external_occlusion']);contamination_meta={'state':'complete',**parser.metadata()}
 # The canonical mask is the existing face_mask.npz/mask_original behind
 # face_mask.png. Contamination maps only gate features; they never rewrite it.
 cv2.imwrite(str(root/'analysis_mask.png'),(seg&contamination_keep).astype(np.uint8)*255);local_xy=xy-[x0,y0]
 r=rasterize_surface(local_xy,vertices_depth,normals,triangles,crop.shape,vertex_visibility);valid=r.triangle_id>=0;r.source_xy[...,0][valid]+=x0;r.source_xy[...,1][valid]+=y0
 p=project_atlas(r,atlas,seg);domain=p.pop('domain_mask');w14=p.pop('wrinkle_membership_w14');qm=quality_maps(crop,domain,r.incidence,r.projection_confidence,r.triangle_id);qm['contamination_keep']=contamination_keep;safe_tid=np.clip(r.triangle_id,0,len(atlas.skin)-1);mesh_skin=(r.triangle_id>=0)&atlas.skin[safe_tid];union=np.sum(seg|mesh_skin);qm['semantic_projection_iou']=np.array(float(np.sum(seg&mesh_skin)/union) if union else 0.,np.float32);qm['quality_weight']*=contamination_keep;qm['effective_resolution']*=contamination_keep;policy=PosePolicy(Path(atlas_path).with_name('pose_policy_v3_9bins.csv'));pw,pm=policy.weights(p['zone_id_a20'],pose.get('yaw',0));qm['pose_weight']=pw;qm['quality_weight']*=pw;qm['effective_resolution']*=np.sqrt(pw);ap=applicability(qm,domain,W,H)
 surface_area=.5*np.linalg.norm(np.cross(np.asarray(surface_vertices)[np.asarray(triangles)[:,1]]-np.asarray(surface_vertices)[np.asarray(triangles)[:,0]],np.asarray(surface_vertices)[np.asarray(triangles)[:,2]]-np.asarray(surface_vertices)[np.asarray(triangles)[:,0]]),axis=1);atomic_npz(root/'surface_observations.npz',schema=np.array(SCHEMAS['surface']),triangle_id=r.triangle_id,barycentric=r.barycentric.astype(np.float16),source_xy=r.source_xy,depth=r.depth,normal=r.normal.astype(np.float16),incidence=r.incidence.astype(np.float16),visibility=r.visibility.astype(np.float16),projection_confidence=r.projection_confidence.astype(np.float16),triangle_surface_area=surface_area.astype(np.float32),surface_vertices=np.asarray(surface_vertices,np.float32),triangles=np.asarray(triangles,np.int32),map_origin_xy=np.array([x0,y0]),original_shape=np.array([H,W]))
 atomic_npz(root/'atlas_projection.npz',schema=np.array(SCHEMAS['atlas']),**p);save_previews(root/'previews',crop,p['zone_id_a20'],domain,qm['quality_weight']);atomic_npz(root/'quality_maps.npz',schema=np.array(SCHEMAS['quality']),**qm);atomic_npz(root/'photometric_branches.npz',**photometric_branches(crop,domain));atomic_json(root/'quality.json',{'schema':SCHEMAS['quality'],'implementation_status':'experimental_heuristics','production_evidence_allowed':False,'applicability':ap,'components':{'domain_pixels':int(domain.sum()),'image_pixels':int(domain.size)},'missing_components':(['hair_probability','external_occlusion_probability'] if contamination_meta['state']!='complete' else []),'contamination':contamination_meta,'pose':pose,'pose_policy':pm})
 patches=[]
 for level,zmap,n in [('A20',p['zone_id_a20'],20),('S40',p['zone_id_s40'],40)]:
  for zi in range(n):
   for q in sample_zone_patches(zmap,zi,qm['quality_weight']):patches.append((level,zi,q['patch_id'],*q['bbox_xyxy'],q['pixel_count'],q['effective_support']))
 pd=np.dtype([('level','U3'),('zone','i2'),('patch_id','U24'),('x0','i4'),('y0','i4'),('x1','i4'),('y1','i4'),('pixels','i4'),('support','f4')]);atomic_npz(root/'patch_index.npz',schema=np.array('skin-patch-index-v1'),patches=np.array(patches,dtype=pd))
 basic=extract_basic(crop,qm['quality_weight'],p['zone_id_a20'],p['zone_id_s40']);atomic_npz(root/'features/basic_macro.npz',schema=np.array(SCHEMAS['features']),zone_level=np.array([x['zone_level'] for x in basic]),zone_id=np.array([x['zone_id'] for x in basic]),state=np.array([x['state'] for x in basic]),effective_support=np.array([x['effective_support'] for x in basic]),values=np.array([[x['luminance_median'],x['luminance_mad'],x['luminance_iqr']] for x in basic],np.float32),columns=np.array(['luminance_median','luminance_mad','luminance_iqr']),provenance_ref=np.array([f"atlas_projection.npz#{x['zone_level']}:{x['zone_id']}|surface_observations.npz:source_xy|../face_mask.npz:mask_original" for x in basic]))
 texture=extract_texture_features(crop,qm['quality_weight'],p['zone_id_a20'],p['zone_id_s40']);
 if ap['micro_texture']['state'] not in {'usable','coarse_only'}:
  for row in texture:row['values'][10]=np.nan
 if ap['pigmentation']['state'] not in {'usable','coarse_only'}:
  for row in texture:row['values'][12:18]=np.nan
 atomic_npz(root/'features/texture.npz',schema=np.array(SCHEMAS['features']),zone_level=np.array([x['zone_level'] for x in texture]),zone_id=np.array([x['zone_id'] for x in texture]),state=np.array([x['state'] for x in texture]),effective_support=np.array([x['effective_support'] for x in texture]),values=np.stack([x['values'] for x in texture]),columns=np.array(FEATURES),provenance_ref=np.array([f"atlas_projection.npz#{x['zone_level']}:{x['zone_id']}|surface_observations.npz:source_xy|../face_mask.npz:mask_original" for x in texture]));atomic_json(root/'features/summary.json',{'schema':SCHEMAS['features'],'state':'complete','implementation_status':'experimental_feature_subset','production_evidence_allowed':False,'implemented_families':['macro','LBP','masked_GLCM','Gabor','spectrum','structure_tensor','LoG','pigmentation_Lab'],'texture_matrix':'features/texture.npz','source':'original photo pixels gated by ../face_mask.npz:mask_original (the numeric source of ../face_mask.png)'})
 lr,lc,lm=detect_local(crop,qm['quality_weight'],r.triangle_id,r.barycentric,triangles,surface_vertices);atomic_npz(root/'features/local_candidates.npz',schema=np.array(SCHEMAS['features']),response=lr.astype(np.float16),candidates=lc);atomic_json(root/'features/local_candidates.json',{'schema':SCHEMAS['features'],'state':'complete','metadata':lm})
 ridge,sk,points,branches,wm=detect_wrinkles(crop,qm['quality_weight'],r.triangle_id,r.barycentric,triangles,surface_vertices,w14);atomic_npz(root/'wrinkles/classical.npz',schema=np.array(SCHEMAS['wrinkles']),ridge_probability=ridge.astype(np.float16),skeleton=sk,points=points);ffstate='not_run_weights_unavailable';ffmeta={};cpdir=Path(atlas_path).resolve().parents[2]/'FFHQ-detect-face-wrinkles/res/cp';cp=next((x for x in (cpdir/'wrinkle_model.pth',cpdir/'best_checkpoint_iou032.pth') if x.is_file()),cpdir/'wrinkle_model.pth')
 if cp.is_file():
  ad=FFHQWrinkleAdapter(cp.parents[2],cp);prob=ad.predict(crop);prob[~domain]=0;atomic_npz(root/'wrinkles/ffhq.npz',schema=np.array(SCHEMAS['wrinkles']),probability=prob.astype(np.float16));ffstate='complete';ffmeta=ad.metadata()
 atomic_json(root/'wrinkles/summary.json',{'schema':SCHEMAS['wrinkles'],'state':'complete' if ffstate=='complete' else 'partial','implementation_status':'experimental_uncalibrated','production_evidence_allowed':False,'classical':'complete','ffhq':ffstate,'classical_metadata':wm,'ffhq_metadata':ffmeta,'branches':branches,'surface_units':'canonical_surface_units_not_mm','detector_policy':'independent channels'})
 atomic_json(root/'material/evidence.json',material_evidence(texture,qm,ap))
 def focus(x,m):
  g=cv2.cvtColor(x,cv2.COLOR_BGR2GRAY);gx=cv2.Sobel(g,cv2.CV_32F,1,0);gy=cv2.Sobel(g,cv2.CV_32F,0,1);return float(np.median(np.hypot(gx[m],gy[m]))) if m.any() else None
 atomic_json(root/'sensitivity/degradation.json',benchmark(crop,domain,focus));return finalize_manifest(root,manifest,'success')
