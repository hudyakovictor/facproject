from __future__ import annotations
import cv2
import numpy as np


def skeletonize_probability(probability: np.ndarray, valid_mask: np.ndarray, threshold: float, min_px: int):
    binary=(probability>=float(threshold))&valid_mask
    n,labels,stats,_=cv2.connectedComponentsWithStats(binary.astype(np.uint8),8)
    keep=np.zeros_like(binary)
    for i in range(1,n):
        if int(stats[i,cv2.CC_STAT_AREA])>=int(min_px): keep|=labels==i
    binary=keep
    try:
        from skimage.morphology import skeletonize
        skeleton=skeletonize(binary)
    except Exception:
        work=(binary.astype(np.uint8)*255); skeleton=np.zeros_like(work); kernel=cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))
        while cv2.countNonZero(work):
            eroded=cv2.erode(work,kernel); opened=cv2.dilate(eroded,kernel)
            skeleton=cv2.bitwise_or(skeleton,cv2.subtract(work,opened)); work=eroded
        skeleton=skeleton>0
    return binary.astype(bool),skeleton.astype(bool)


def graph_summary(skeleton: np.ndarray) -> dict:
    if not skeleton.any(): return {"available":False,"branch_count":0,"skeleton_pixels":0}
    try:
        from skan import Skeleton, summarize
        table=summarize(Skeleton(skeleton.astype(np.uint8)),separator="_")
        lengths=np.asarray(table.get("branch_distance",[]),float)
        return {"available":True,"backend":"skan","branch_count":int(len(table)),"skeleton_pixels":int(skeleton.sum()),"total_length_px":float(lengths.sum()) if lengths.size else 0.0,"median_length_px":float(np.median(lengths)) if lengths.size else 0.0}
    except Exception as exc:
        n,_,stats,_=cv2.connectedComponentsWithStats(skeleton.astype(np.uint8),8)
        sizes=stats[1:,cv2.CC_STAT_AREA] if n>1 else np.array([])
        return {"available":True,"backend":"connected-components-fallback","branch_count":int(len(sizes)),"skeleton_pixels":int(skeleton.sum()),"total_length_px":float(sizes.sum()),"warning":str(exc)}


def comparison_metrics(a: np.ndarray,b: np.ndarray,mask: np.ndarray) -> dict:
    aa=a&mask; bb=b&mask
    if not aa.any() or not bb.any(): return {"status":"INCONCLUSIVE","reason":"empty common skeleton"}
    da=cv2.distanceTransform((~aa).astype(np.uint8),cv2.DIST_L2,5)
    db=cv2.distanceTransform((~bb).astype(np.uint8),cv2.DIST_L2,5)
    ab=float(np.median(da[bb])); ba=float(np.median(db[aa]))
    return {"status":"VISUAL_CANDIDATE_ONLY","median_symmetric_uv_distance_px":float((ab+ba)/2),"a_pixels":int(aa.sum()),"b_pixels":int(bb.sum()),"common_support_pixels":int(mask.sum())}
