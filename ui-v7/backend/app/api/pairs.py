from fastapi import APIRouter, Path, Query
from typing import Optional
from app.api.timeline import get_photos


router = APIRouter()


@router.get("/pairs/{photo_a}/{photo_b}/metrics")
async def get_pair_metrics(
    photo_a: str = Path(..., description="First photo ID"),
    photo_b: str = Path(..., description="Second photo ID"),
):
    """Get comparison metrics for a photo pair."""
    photos = get_photos()
    
    photo_a_obj = next((p for p in photos if p.id == photo_a), None)
    photo_b_obj = next((p for p in photos if p.id == photo_b), None)
    
    if not photo_a_obj or not photo_b_obj:
        return {}
    
    return {
        "photo_a": photo_a,
        "photo_b": photo_b,
        "ldm_difference": None,
        "bone_difference": None,
        "texture_difference": None,
        "pose_alignment": None,
        "overall_similarity": None,
        "is_same_person_probability": None,
    }


@router.get("/pairs/{photo_id}/candidates")
async def get_pair_candidates(
    photo_id: str = Path(..., description="Photo ID"),
    limit: int = Query(10, ge=1, le=50),
):
    """Get candidate photos for pairing."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        return {"candidates": []}
    
    # Return photos from similar era/bucket
    candidates = [
        p for p in photos
        if p.id != photo_id and p.era == photo.era and p.bucket == photo.bucket
    ][:limit]
    
    return {"candidates": [c.id for c in candidates]}
