"""Input decoding and date provenance. Filename date is authoritative.

EXIF is preserved as corroborating metadata only; it never silently changes the
chronology.  Conflicts are explicit and available to UI/reports.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from PIL import ExifTags, Image, ImageOps

_EXIF_WANTED={"Make","Model","Software","DateTime","DateTimeOriginal","DateTimeDigitized","LensModel"}


def _parse_exif_date(value: Any) -> date | None:
    if not value: return None
    text=str(value).strip().replace("-",":")
    for fmt in ("%Y:%m:%d %H:%M:%S","%Y:%m:%d"):
        try: return datetime.strptime(text[:19] if "%H" in fmt else text[:10],fmt).date()
        except ValueError: pass
    return None


def build_date_provenance(filename_date:str,decode_meta:dict[str,Any],source_provenance:dict[str,Any]|None=None)->dict[str,Any]:
    primary=date.fromisoformat(filename_date);source_provenance=source_provenance or {}
    tags=decode_meta.get("exif_camera_processing") or {}
    raw=tags.get("DateTimeOriginal") or tags.get("DateTimeDigitized") or tags.get("DateTime")
    exif=_parse_exif_date(raw)
    if exif and (exif - primary).days > 365:
        exif = None
    delta=abs((exif-primary).days) if exif else None
    claimed_raw=source_provenance.get("claimed_date");claimed=date.fromisoformat(str(claimed_raw)) if claimed_raw else None
    claimed_delta=abs((claimed-primary).days) if claimed else None;conflict_sources=[]
    if delta not in (None,0):conflict_sources.append("exif")
    if claimed_delta not in (None,0):conflict_sources.append("source_claim")
    status="conflict" if conflict_sources else ("corroborated" if exif or claimed else "filename_only")
    return {"authority":"filename","filename_date":primary.isoformat(),"exif_date":exif.isoformat() if exif else None,"exif_raw":str(raw) if raw is not None else None,"delta_days":delta,"source_claimed_date":claimed.isoformat() if claimed else None,"source_claimed_delta_days":claimed_delta,"conflict_sources":conflict_sources,"status":status,"requires_manual_review":status=="conflict","timezone_status":"unknown_not_used_for_calendar_date","policy":"EXIF/source claims corroborate but never override filename chronology"}


def decode_oriented(path: str | Path):
    """Deterministic EXIF transpose followed by RGB->BGR plus provenance."""
    with Image.open(path) as im:
        encoded_size=list(im.size); mode=im.mode; ex=im.getexif()
        orientation=int(ex.get(274,1)); icc=im.info.get("icc_profile")
        tags={ExifTags.TAGS.get(k,str(k)):str(v) for k,v in ex.items()
              if ExifTags.TAGS.get(k,str(k)) in _EXIF_WANTED}
        oriented=ImageOps.exif_transpose(im).convert("RGB")
        rgb=np.asarray(oriented)
    bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    return bgr,{"decoder":"Pillow.ImageOps.exif_transpose","encoded_size":encoded_size,
        "oriented_size":[int(bgr.shape[1]),int(bgr.shape[0])],"encoded_mode":mode,
        "exif_orientation":orientation,"orientation_applied":orientation not in (0,1),
        "icc_profile_present":bool(icc),"exif_camera_processing":tags,
        "source_hypotheses":{"scanned":"unknown","upscaled":"unknown","recompressed":"unknown"},
        "output":"uint8_sRGB_assumed_if_profile_not_converted"}
