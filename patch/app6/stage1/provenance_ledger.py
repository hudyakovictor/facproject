"""Chain-of-custody sidecars and conservative perceptual duplicate clustering."""
from __future__ import annotations
import hashlib,json
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Any
import numpy as np
from PIL import Image,ImageOps
_ALLOWED={"source_url","archive_url","publisher","acquired_at","collector","claimed_date","notes","rights"}

def perceptual_dhash(path:str|Path)->str:
    with Image.open(path) as im:
        a=np.asarray(ImageOps.exif_transpose(im).convert("L").resize((9,8),Image.Resampling.LANCZOS),dtype=np.int16)
    bits=(a[:,1:]>a[:,:-1]).reshape(-1)
    return f"{sum(int(v)<<i for i,v in enumerate(bits.tolist())):016x}"

def hamming_distance(a:str,b:str)->int:return (int(a,16)^int(b,16)).bit_count()

def load_provenance_sidecar(path:str|Path)->dict[str,Any]:
    image=Path(path);candidates=(image.with_suffix(image.suffix+".provenance.json"),image.with_suffix(".provenance.json"))
    side=next((x for x in candidates if x.is_file()),None)
    if side is None:return {"status":"not_provided","sidecar_path":None,"sidecar_digest":None}
    raw=side.read_bytes()
    try:data=json.loads(raw.decode("utf-8"))
    except Exception as exc:raise ValueError(f"invalid provenance sidecar {side}: {exc}") from exc
    if not isinstance(data,dict):raise ValueError("provenance sidecar must be an object")
    unknown=sorted(set(data)-_ALLOWED)
    if unknown:raise ValueError(f"unknown provenance fields: {unknown}")
    if not data.get("source_url") and not data.get("archive_url"):raise ValueError("provenance sidecar requires source_url or archive_url")
    for key in ("source_url","archive_url"):
        value=data.get(key)
        if value is not None and (not isinstance(value,str) or urlparse(value).scheme not in {"http","https"}):raise ValueError(f"{key} must be an http(s) URL")
    for key in ("publisher","collector","notes","rights"):
        value=data.get(key)
        if value is not None and (not isinstance(value,str) or not value.strip()):raise ValueError(f"{key} must be a non-empty string")
    if data.get("claimed_date") is not None:
        try:date.fromisoformat(str(data["claimed_date"]))
        except ValueError as exc:raise ValueError("claimed_date must be YYYY-MM-DD") from exc
    if data.get("acquired_at") is not None:
        try:datetime.fromisoformat(str(data["acquired_at"]).replace("Z","+00:00"))
        except ValueError as exc:raise ValueError("acquired_at must be ISO-8601") from exc
    return {"status":"provided","sidecar_path":side.name,"sidecar_digest":hashlib.sha256(raw).hexdigest(),**data}
