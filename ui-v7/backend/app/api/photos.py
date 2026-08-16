from fastapi import APIRouter, Path as ApiPath, HTTPException
from typing import Optional
from app.api.timeline import get_photos, parse_info_json
from pathlib import Path
import json


router = APIRouter()

STORAGE_PATH = Path("/Volumes/SDCARD/storage/stage1")


def find_photo_dir(photo_id: str) -> Optional[Path]:
    """Resolve the API id to the real hashed directory on the storage volume."""
    direct = STORAGE_PATH / photo_id
    if direct.is_dir():
        return direct
    for photo_dir in STORAGE_PATH.iterdir():
        if not photo_dir.is_dir() or photo_dir.name.startswith('.'):
            continue
        info_path = photo_dir / "info.json"
        try:
            with info_path.open() as info_file:
                if json.load(info_file).get("photo_id") == photo_id:
                    return photo_dir
        except (OSError, ValueError, TypeError):
            continue
    return None


@router.get("/photos/{photo_id}/info")
async def get_photo_info(
    photo_id: str = ApiPath(..., description="Photo ID"),
):
    """Get detailed photo information."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    # Load full info.json for more details
    photo_dir = find_photo_dir(photo_id)
    if photo_dir is None:
        raise HTTPException(status_code=404, detail="Photo directory not found")
    info_path = photo_dir / "info.json"
    if info_path.exists():
        with open(info_path) as f:
            full_info = json.load(f)
        return {**photo.model_dump(), "full_info": full_info}
    
    return photo.model_dump()


@router.get("/photos/{photo_id}/landmarks/{count}/{space}")
async def get_landmarks(
    photo_id: str = ApiPath(..., description="Photo ID"),
    count: int = ApiPath(..., description="Number of landmarks"),
    space: str = ApiPath(..., description="Coordinate space (raw/aligned/chronology)"),
):
    """Get facial landmarks for a photo."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        return {"points": [], "columns": []}
    
    photo_dir = find_photo_dir(photo_id)
    if photo_dir is None:
        return {"points": [], "columns": []}
    csv_name = f"ldm{count}_{space}.csv"
    csv_path = photo_dir / csv_name
    
    if not csv_path.exists():
        return {"points": [], "columns": []}
    
    import csv
    points = []
    columns = []
    try:
        with open(csv_path) as f:
            reader = csv.reader(f)
            rows = list(reader)
            if rows:
                columns = rows[0]
                for row in rows[1:]:
                    if len(row) >= 3:
                        points.append([float(row[0]), float(row[1]), float(row[2])])
                    elif len(row) >= 2:
                        points.append([float(row[0]), float(row[1]), 0.0])
    except Exception:
        pass
    
    return {"points": points, "columns": columns or ["x", "y", "z"]}


@router.get("/photos/{photo_id}/mesh")
async def get_mesh(
    photo_id: str = ApiPath(..., description="Photo ID"),
):
    """Get 3D mesh for a photo."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    photo_dir = find_photo_dir(photo_id)
    if photo_dir is None:
        raise HTTPException(status_code=404, detail="Photo directory not found")
    obj_path = photo_dir / "mesh.obj"
    
    if not obj_path.exists():
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    # Read OBJ file
    vertices = []
    faces = []
    try:
        with open(obj_path) as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.split()
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif line.startswith("f "):
                    parts = line.split()
                    face = [int(p.split("/")[0]) - 1 for p in parts[1:]]
                    faces.append(face)
    except Exception:
        pass
    
    return {"vertices": vertices, "faces": faces}


@router.get("/photos/{photo_id}/thumbnail")
async def get_thumbnail(
    photo_id: str = ApiPath(..., description="Photo ID"),
):
    """Get thumbnail image path."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    photo_dir = find_photo_dir(photo_id)
    if photo_dir is None:
        raise HTTPException(status_code=404, detail="Photo directory not found")
    thumb_path = photo_dir / "thumb.jpg"
    
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(thumb_path)


@router.get("/photos/{photo_id}/face_crop")
async def get_face_crop(
    photo_id: str = ApiPath(..., description="Photo ID"),
):
    """Get face crop image."""
    photos = get_photos()
    photo = next((p for p in photos if p.id == photo_id), None)
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    photo_dir = find_photo_dir(photo_id)
    if photo_dir is None:
        raise HTTPException(status_code=404, detail="Photo directory not found")
    crop_path = photo_dir / "face_crop.jpg"
    
    if not crop_path.exists():
        raise HTTPException(status_code=404, detail="Face crop not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(crop_path)
