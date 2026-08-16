from fastapi import APIRouter
from app.api.timeline import get_photos


router = APIRouter()


@router.get("/calibration/health")
async def get_calibration_health():
    """Get calibration health statistics."""
    photos = get_photos()
    
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    buckets = {}
    
    for p in photos:
        conf = p.confidence or 0
        if conf >= 0.7:
            confidence_counts["high"] += 1
        elif conf >= 0.4:
            confidence_counts["medium"] += 1
        else:
            confidence_counts["low"] += 1
        
        bucket = p.bucket
        buckets[bucket] = buckets.get(bucket, 0) + 1
    
    return {
        "total_records": len(photos),
        "total_persons": 1,
        "confidence_counts": confidence_counts,
        "buckets": buckets,
    }
