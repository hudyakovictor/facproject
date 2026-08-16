from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from datetime import datetime
import json
import os
from pathlib import Path


router = APIRouter()

STORAGE_PATH = Path("/Volumes/SDCARD/storage/stage1")


class EraMeta(BaseModel):
    label: str
    start: str
    end: str


class TimelinePhoto(BaseModel):
    id: str
    date: Optional[str] = None
    t: Optional[int] = None
    bucket: str
    era: str
    quality: Optional[float] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    fuzzy: str = ""
    measurementStatus: str = "measured"
    flags: list[str] = []
    sourceMode: str = "research"
    analysisStage: str = "stage1_inventory"
    dateProvenanceStatus: Optional[str] = None

    alignmentQuality: Optional[float] = None
    poseConfidence: Optional[float] = None
    detectionConfidence: Optional[float] = None
    confidence: Optional[float] = None

    skinQuality: Optional[float] = None
    skinAuthenticity: Optional[float] = None
    siliconeProb: Optional[float] = None
    fillerProb: Optional[float] = None
    wrinkleDensity: Optional[float] = None
    subsurface: Optional[float] = None
    uvCoverage: Optional[float] = None

    boneScore: Optional[float] = None
    orbit: Optional[float] = None
    chin: Optional[float] = None
    jaw: Optional[float] = None
    cheek: Optional[float] = None
    symmetry: Optional[float] = None

    p0: Optional[float] = None
    p1: Optional[float] = None
    p2: Optional[float] = None

    zOrbitDepth: Optional[float] = None
    zChinProj: Optional[float] = None
    zJawWidth: Optional[float] = None
    zCheek: Optional[float] = None

    expressionMagnitude: Optional[float] = None
    jawOpenDegree: Optional[float] = None
    jawOpenRatio: Optional[float] = None
    jawOpenDetected: Optional[bool] = None
    smileDetected: Optional[bool] = None
    visualAge: Optional[float] = None
    calendarAge: Optional[float] = None
    faceAreaRatio: Optional[float] = None
    correctionMagnitude: Optional[float] = None
    residualYaw: Optional[float] = None
    residualPitch: Optional[float] = None
    residualRoll: Optional[float] = None

    ldmShapeDifference: Optional[float] = None
    ldm106Difference: Optional[float] = None
    ldm134Difference: Optional[float] = None
    visibleLdm106: Optional[int] = None
    visibleLdm134: Optional[int] = None

    canonicalYaw: Optional[float] = None
    exifAnomaly: Optional[bool] = None
    dateProvenanceLimited: Optional[bool] = None
    bayesianProjectionAvailable: Optional[bool] = None
    laplacianVariance: Optional[float] = None
    tenengradMean: Optional[float] = None
    noiseResidual: Optional[float] = None
    skinMaskCoverage: Optional[float] = None


class TimelineResponse(BaseModel):
    schema: str = "deeputin-api-stage1-inventory-v1.0"
    source_mode: str = "research"
    not_a_verdict: bool = True
    note: Optional[str] = None
    photos: list[TimelinePhoto]
    era_meta: dict[str, EraMeta]
    chronology_anomalies: Optional[dict] = None
    analysis_manifest: Optional[dict] = None
    analysis_stage: Optional[str] = None
    stage1_manifest: Optional[dict] = None


ERAS = {
    "era_early": {"label": "1999-2004", "start": "1999-01-01", "end": "2004-12-31"},
    "era_first": {"label": "2005-2008", "start": "2005-01-01", "end": "2008-12-31"},
    "era_second": {"label": "2009-2012", "start": "2009-01-01", "end": "2012-12-31"},
    "era_third": {"label": "2013-2016", "start": "2013-01-01", "end": "2016-12-31"},
    "era_fourth": {"label": "2017-2020", "start": "2017-01-01", "end": "2020-12-31"},
    "era_recent": {"label": "2021-2026", "start": "2021-01-01", "end": "2026-12-31"},
}


def get_era_for_year(year: int) -> str:
    if year < 2005:
        return "era_early"
    elif year < 2009:
        return "era_first"
    elif year < 2013:
        return "era_second"
    elif year < 2017:
        return "era_third"
    elif year < 2021:
        return "era_fourth"
    else:
        return "era_recent"


def parse_info_json(photo_dir: Path) -> Optional[TimelinePhoto]:
    info_path = photo_dir / "info.json"
    if not info_path.exists():
        return None
    
    try:
        with open(info_path) as f:
            data = json.load(f)
    except Exception:
        return None
    
    photo_id = data.get("photo_id", photo_dir.name)
    date_str = data.get("date")
    year = data.get("date_year")
    
    if not date_str or not year:
        return None
    
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        timestamp = int(dt.timestamp() * 1000)
    except Exception:
        return None
    
    chrono = data.get("chronology", {})
    pose = data.get("pose", {})
    quality_inputs = data.get("quality_inputs", {})
    skin = data.get("skin", {})
    uv = data.get("uv", {})
    normalization = data.get("normalization", {})
    
    # Determine silicone probability from skin authenticity
    # Low authenticity = high silicone probability
    skin_auth = data.get("skin_authenticity_score")
    silicone_prob = None
    if skin_auth is not None:
        # Normalize: score > 1.4 (q99) = low authenticity = high silicone
        silicone_prob = min(1.0, max(0.0, (skin_auth - 0.5) / 2.0))
    
    # LDM shape difference - not directly available, use 0 for now
    ldm_shape_diff = None
    
    return TimelinePhoto(
        id=photo_id,
        date=date_str,
        t=timestamp,
        bucket=chrono.get("pose_bin", "frontal"),
        era=get_era_for_year(year),
        quality=quality_inputs.get("face_bbox_area_ratio"),
        yaw=pose.get("yaw"),
        pitch=pose.get("pitch"),
        roll=pose.get("roll"),
        fuzzy="",
        measurementStatus="measured",
        flags=[],
        sourceMode="research",
        analysisStage="stage1_inventory",
        dateProvenanceStatus=data.get("date_provenance", {}).get("status"),
        
        alignmentQuality=chrono.get("alignment_quality"),
        poseConfidence=chrono.get("pose_confidence"),
        detectionConfidence=chrono.get("detection_confidence"),
        confidence=quality_inputs.get("face_bbox_area_ratio"),
        
        skinQuality=data.get("skin_quality_score"),
        skinAuthenticity=skin_auth,
        siliconeProb=silicone_prob,
        fillerProb=None,
        wrinkleDensity=None,
        subsurface=None,
        uvCoverage=uv.get("observed_coverage"),
        
        boneScore=None,
        orbit=None,
        chin=None,
        jaw=None,
        cheek=None,
        symmetry=None,
        
        p0=normalization.get("center", [None, None, None])[0],
        p1=normalization.get("center", [None, None, None])[1],
        p2=normalization.get("center", [None, None, None])[2],
        
        zOrbitDepth=None,
        zChinProj=None,
        zJawWidth=None,
        zCheek=None,
        
        expressionMagnitude=chrono.get("expression_magnitude"),
        jawOpenDegree=chrono.get("jaw_open_degree"),
        jawOpenRatio=chrono.get("jaw_open_ratio"),
        jawOpenDetected=chrono.get("jaw_open_detected"),
        smileDetected=chrono.get("smile_detected"),
        visualAge=None,
        calendarAge=year - 1970 if year else None,
        faceAreaRatio=quality_inputs.get("face_bbox_area_ratio"),
        correctionMagnitude=chrono.get("correction_magnitude_deg"),
        residualYaw=chrono.get("residual_yaw_deg"),
        residualPitch=chrono.get("residual_pitch_deg"),
        residualRoll=chrono.get("residual_roll_deg"),
        
        ldmShapeDifference=ldm_shape_diff,
        ldm106Difference=None,
        ldm134Difference=None,
        visibleLdm106=chrono.get("visible_landmarks_106"),
        visibleLdm134=chrono.get("visible_landmarks_134"),
        
        canonicalYaw=pose.get("canonical_yaw"),
        exifAnomaly=data.get("date_provenance", {}).get("requires_manual_review", False),
        dateProvenanceLimited=data.get("date_provenance", {}).get("status") != "filename_only",
        bayesianProjectionAvailable=False,
        laplacianVariance=quality_inputs.get("laplacian_variance"),
        tenengradMean=quality_inputs.get("tenengrad_mean"),
        noiseResidual=quality_inputs.get("noise_residual_mean"),
        skinMaskCoverage=quality_inputs.get("skin_mask_coverage"),
    )


def load_all_photos() -> list[TimelinePhoto]:
    photos = []
    if not STORAGE_PATH.exists():
        return photos
    
    for photo_dir in sorted(STORAGE_PATH.iterdir()):
        if photo_dir.is_dir() and not photo_dir.name.startswith("."):
            photo = parse_info_json(photo_dir)
            if photo:
                photos.append(photo)
    
    photos.sort(key=lambda p: p.t or 0)
    return photos


PHOTOS_CACHE: Optional[list[TimelinePhoto]] = None


def get_photos() -> list[TimelinePhoto]:
    global PHOTOS_CACHE
    if PHOTOS_CACHE is None:
        PHOTOS_CACHE = load_all_photos()
    return PHOTOS_CACHE


def build_response(photos: list[TimelinePhoto]) -> TimelineResponse:
    return TimelineResponse(
        schema="deeputin-api-stage1-inventory-v1.0",
        source_mode="research",
        not_a_verdict=True,
        note=f"Real data from {STORAGE_PATH}, {len(photos)} photos",
        photos=photos,
        era_meta=ERAS,
        chronology_anomalies={
            "change_points": {"years": []},
            "baseline_return": {"years": []},
            "irreversible_return": {"years": []},
            "chronology_rate": {"years": []},
            "biological_rate": {"years": []},
        },
        analysis_manifest={"change_points": {"years": []}},
        analysis_stage="stage1_inventory",
        stage1_manifest={
            "total_photos": len(photos),
            "processed_photos": len(photos),
        },
    )


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    limit: Optional[int] = Query(None, ge=1, le=10000),
    era: Optional[str] = Query(None),
    bucket: Optional[str] = Query(None),
):
    """Get full timeline data from real storage."""
    photos = get_photos()
    
    if era:
        photos = [p for p in photos if p.era == era]
    if bucket:
        photos = [p for p in photos if p.bucket == bucket]
    if limit:
        photos = photos[:limit]
    
    return build_response(photos)


@router.get("/timeline/stats")
async def get_timeline_stats():
    """Get timeline statistics."""
    photos = get_photos()
    
    return {
        "total_photos": len(photos),
        "by_era": {
            era: len([p for p in photos if p.era == era])
            for era in ERAS.keys()
        },
        "by_bucket": {
            bucket: len([p for p in photos if p.bucket == bucket])
            for bucket in ["left_profile", "left_deep", "left_mid", "left_light", "frontal", "right_light", "right_mid", "right_deep", "right_profile"]
        },
        "date_range": {
            "min": min((p.t for p in photos if p.t), default=0),
            "max": max((p.t for p in photos if p.t), default=0),
        },
    }