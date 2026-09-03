"""📊 METRIC → Движение точек после выравнивания + стабильность landmarks.
🚪 API: pose_motion_support(), aligned_point_motion(), landmark_stability_score(), score()
🚨 WARNING: поддержка по pose bin: profile_* = limited, out_of_range = unsupported
🔗 DEPENDS ON: anchor_policy.stable_anchor_mask() + core.robust_rigid_align()
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
import numpy as np
import warnings
from .anchor_policy import stable_anchor_mask
from .analysis_policy import pose_gap
from .core import Record,robust_rigid_align
from app6.stage1.status_logger import log_status

# 💡 NOTE (AUDIT-5): config.POSE_BINS не эмитит *_profile_soft — записи удалены как
# недостижимые; fallback `("profile" in p)` ниже покрывает любые будущие profile-названия.
PROFILE_POSE_BINS = {
    "left_profile", "right_profile",
}
UNSUPPORTED_POSE_BINS = {"out_of_supported_range", "unknown", ""}


# 🚧 Тир поддержки motion-утверждений по pose bin
def pose_motion_support(pose_bin: str) -> str:
    """Return support tier for point-motion claims on this pose bin."""
    p = str(pose_bin or "")
    if p in UNSUPPORTED_POSE_BINS:
        return "unsupported_pose"
    if p in PROFILE_POSE_BINS or "profile" in p:
        return "profile_limited"
    return "supported"


def aligned_point_motion(a:Record,b:Record,count:int,identity_only:bool=False)->dict[str,np.ndarray|int|str]:
    """🎯 CRITICAL → Вычисление движения точек между двумя фото.

    Использует raw object-normalized landmarks из канонического loader.
    Pairwise Kabsch alignment применяется для точного выравнивания.

    🔗 DEPENDS ON:
      - engine.run() — вызывается для каждой пары
      - Record.ldm134 — raw object-normalized coordinates

    APPLICABILITY:
      - Отклоняет разные pose bins и чрезмерный residual pose delta.
      - Pair-level reconstruction quality проверяется Stage2Engine до вызова.

    💡 NOTE:
      - Использует iteratively-trimmed Kabsch (15% trim)
      - Identity-only для expression-robust comparison
    """
    log_status("aligned_point_motion", "complete")
    if count not in (106, 134):
        raise ValueError("count must be 106 or 134")
    vectors=np.full((count,3),np.nan,np.float32);magnitude=np.full(count,np.nan,np.float32)
    if a.pose_bin != b.pose_bin:
        return {'status':'pose_mismatch','vectors':vectors,'magnitude':magnitude,'visible':np.zeros(count,bool),'point_count':0,'anchor_count':0,'anchor_policy':'pose_mismatch'}
    gap=pose_gap(a.angles,b.angles,pose_bin=a.pose_bin)
    pose_distance=float(np.linalg.norm((a.angles-b.angles)/np.array([15.,20.,15.])))
    if not gap.accepted:
        return {'status':'residual_pose_mismatch','vectors':vectors,'magnitude':magnitude,
                'visible':np.zeros(count,bool),'point_count':0,'anchor_count':0,
                'anchor_policy':'residual_pose_mismatch','pose_distance':pose_distance,
                'pose_gap_reason':gap.reason,'pitch_gap_deg':gap.pitch,
                'yaw_gap_deg':gap.yaw,'roll_gap_deg':gap.roll}
    if count==106:
        pa,pb=a.ldm106,b.ldm106;vis=np.asarray(a.visible106,bool)&np.asarray(b.visible106,bool)
        if identity_only: pa,pb=a.identity_only106,b.identity_only106
        minimum=24
    else:
        pa,pb=a.ldm134,b.ldm134;vis=np.asarray(a.visible134,bool)&np.asarray(b.visible134,bool)
        if identity_only: pa,pb=a.identity_only134,b.identity_only134
        minimum=30
    if pa is None or pb is None:return {'status':'unavailable','vectors':vectors,'magnitude':magnitude,'visible':vis,'point_count':int(vis.sum()),'anchor_count':0,'anchor_policy':'unavailable'}
    pa=np.asarray(pa,np.float32);pb=np.asarray(pb,np.float32)
    if pa.shape != (count,3) or pb.shape != (count,3):
        return {'status':'invalid_landmark_shape','vectors':vectors,'magnitude':magnitude,'visible':vis,'point_count':int(vis.sum()),'anchor_count':0,'anchor_policy':'invalid_landmark_shape'}
    if not (np.isfinite(pa[vis]).all() and np.isfinite(pb[vis]).all()):
        return {'status':'nonfinite_landmarks','vectors':vectors,'magnitude':magnitude,'visible':vis,'point_count':int(vis.sum()),'anchor_count':0,'anchor_policy':'nonfinite_landmarks'}
    if int(vis.sum())<minimum:return {'status':'insufficient_visibility','vectors':vectors,'magnitude':magnitude,'visible':vis,'point_count':int(vis.sum()),'anchor_count':0,'anchor_policy':'insufficient_visibility'}
    anchors,ameta=stable_anchor_mask(pa,vis,min_count=minimum)
    _,r,t,align_meta=robust_rigid_align(pb[anchors],pa[anchors]);aligned=pb@r+t;vectors[vis]=aligned[vis]-pa[vis];magnitude[vis]=np.linalg.norm(vectors[vis],axis=1)
    return {'status':'measured','vectors':vectors,'magnitude':magnitude,'visible':vis,'point_count':int(vis.sum()),'anchor_count':int(ameta.get('anchor_count',0)),'anchor_policy':str(ameta.get('anchor_policy','unknown')),'alignment_policy':str(align_meta.get('alignment_policy','unknown')),'alignment_trimmed_count':int(align_meta.get('trimmed_point_count',0)),'alignment_residual_before_median':float(align_meta.get('residual_before_median',0.0) or 0.0),'alignment_residual_after_median':float(align_meta.get('residual_after_median',0.0) or 0.0)}


@dataclass
class PointNoiseReference:
    median:np.ndarray;mad:np.ndarray;p95:np.ndarray;count:np.ndarray;template:np.ndarray


class PointNoiseModel:
    """Per-landmark same-person reconstruction noise by pose bin."""
    def __init__(self,records:list[Record]):
        self.records=records;self.references:dict[tuple[str,int],PointNoiseReference]={};self._build()
    @staticmethod
    def _pose_distance(a,b):return float(np.linalg.norm((a.angles-b.angles)/np.array([15.,20.,15.])))
    def _build(self):
        groups=defaultdict(list)
        for r in self.records:groups[(r.dataset_id,r.pose_bin)].append(r)
        values=defaultdict(lambda:defaultdict(list));templates=defaultdict(list)
        for (_,pose),rs in groups.items():
            rs=sorted(rs,key=lambda r:r.date or str(r.sequence))
            for r in rs:templates[(pose,106)].append(r.ldm106);templates[(pose,134)].append(r.ldm134)
            for off in (1,2,3,5,10,20,50):
                for a,b in zip(rs,rs[off:],strict=False):
                    if self._pose_distance(a,b)>2.5:continue
                    person=a.dataset_id
                    for count in (106,134):
                        m=aligned_point_motion(a,b,count)
                        if m['status']=='measured':values[(pose,count)][person].append(m['magnitude'])
        for key,person_dict in values.items():
            per_person_medians=[]
            person_ids=[]
            for person,arrs in person_dict.items():
                stack=np.stack(arrs)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',RuntimeWarning)
                    med=np.nanmedian(stack,axis=0)
                per_person_medians.append(med);person_ids.append(person)
            if len(per_person_medians)<3:continue
            agg=np.stack(per_person_medians)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning)
                median=np.nanmedian(agg,axis=0);mad=np.nanmedian(np.abs(agg-median),axis=0)
                p99_per_person=np.nanpercentile(agg,99,axis=0)
                p95=np.nanmedian(np.stack([np.nanpercentile(np.stack(arrs),95,axis=0) for arrs in person_dict.values()]),axis=0)
            n_persons=len(per_person_medians)
            cnt=np.full(len(median),n_persons,dtype=np.int32)
            template=np.nanmedian(np.stack(templates[key][:200]),axis=0)
            self.references[key]=PointNoiseReference(median.astype(np.float32),mad.astype(np.float32),p95.astype(np.float32),cnt,template.astype(np.float32))
    # 📊 Калиброванный motion-скор
    def score(self,pose:str,count:int,motion:dict[str,Any])->dict[str,Any]:
        support=pose_motion_support(pose)
        ref=self.references.get((pose,count));mag=np.asarray(motion['magnitude'],np.float32);z=np.full(count,np.nan,np.float32);sig=np.zeros(count,bool)
        if support=='unsupported_pose':return {'status':'unsupported_pose','pose_support':support,'z':z,'significant':sig,'summary':{'calibrated_point_count':0}}
        if ref is None:return {'status':'insufficient_calibration','pose_support':support,'z':z,'significant':sig,'summary':{'calibrated_point_count':0}}
        floor=max(float(np.nanmedian(ref.mad))*0.25,1e-6);den=np.maximum(1.4826*ref.mad,floor);valid=np.isfinite(mag)&(ref.count>=7)&np.isfinite(ref.p95);z[valid]=(mag[valid]-ref.median[valid])/den[valid];sig[valid]=(mag[valid]>ref.p95[valid])&(z[valid]>=3.0)
        coh=self._coherence(ref.template,np.asarray(motion['vectors']),valid,sig)
        zv=z[np.isfinite(z)];summary={'calibrated_point_count':int(valid.sum()),'significant_point_count':int(sig.sum()),'significant_fraction':float(sig.sum()/max(valid.sum(),1)),'coherent_fraction':float(coh),'median_point_z':float(np.median(zv)) if zv.size else 0.,'p95_point_z':float(np.percentile(zv,95)) if zv.size else 0.}
        if valid.sum()<max(30,int(count*.4)):status='insufficient_calibration'
        elif summary['significant_fraction']<.08:status='within_reconstruction_noise'
        elif summary['significant_fraction']>=.15 and coh>=.45 and summary['p95_point_z']>=3.5:status='coherent_jump_candidate'
        else:status='scattered_or_uncertain'
        if support=='profile_limited' and status in ('coherent_jump_candidate','scattered_or_uncertain'):
            # Profiles have weaker same-person null coverage; keep metrics but demote claim tier.
            status='profile_support_limited' if status=='scattered_or_uncertain' else status
            summary=dict(summary); summary['pose_support']=support; summary['profile_gate']='metrics_ok_claim_limited'
        else:
            summary=dict(summary); summary['pose_support']=support
        return {'status':status,'pose_support':support,'z':z,'significant':sig,'summary':summary}
    @staticmethod
    def landmark_stability_score(vectors: np.ndarray, valid: np.ndarray) -> float:
        """📊 METRIC → Landmark stability score (0-1).

        Measures how stable landmarks are across consecutive frames.
        High stability = landmarks move coherently (same direction).
        Low stability = random motion (noise).

        ⚠️ IN PROGRESS:
        - Simple heuristic based on vector coherence
        - No temporal smoothing yet

        Returns:
            float: stability score (0=unstable, 1=perfectly stable)
        """
        valid_ids = np.flatnonzero(valid)
        if len(valid_ids) < 10:
            return 0.0

        valid_vectors = vectors[valid_ids]
        magnitudes = np.linalg.norm(valid_vectors, axis=1)

        # Filter out zero-motion landmarks
        moving = magnitudes > 1e-6
        if moving.sum() < 5:
            return 1.0  # All landmarks stable

        # Compute direction coherence
        directions = valid_vectors[moving] / magnitudes[moving, np.newaxis]
        mean_direction = np.mean(directions, axis=0)
        mean_norm = np.linalg.norm(mean_direction)

        if mean_norm < 1e-8:
            return 0.0  # No coherent motion

        # Stability = how aligned are directions with mean
        coherence = np.mean(np.dot(directions, mean_direction / mean_norm))
        return float(np.clip(coherence, 0.0, 1.0))

    @staticmethod
    def _coherence(template,vectors,valid,significant,k=6):
        ids=np.flatnonzero(valid);sids=np.flatnonzero(significant)
        if len(sids)<3 or len(ids)<k+1:return 0.
        dist=np.sum((template[:,None,:]-template[None,:,:])**2,axis=2);scores=[]
        for i in sids:
            neigh=[j for j in np.argsort(dist[i]) if j!=i and valid[j]][:k]
            if not neigh:continue
            vi=vectors[i];ni=np.linalg.norm(vi)
            agree=[]
            for j in neigh:
                nj=np.linalg.norm(vectors[j]);cos=float(np.dot(vi,vectors[j])/(ni*nj)) if ni>0 and nj>0 else -1.
                agree.append(bool(significant[j] and cos>.25))
            scores.append(sum(agree)/len(agree))
        return float(np.mean(scores)) if scores else 0.
