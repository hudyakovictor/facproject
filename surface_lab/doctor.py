from pathlib import Path
import importlib.util, platform, sys
SURFACE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SURFACE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
mods = ["cv2", "numpy", "scipy", "skimage", "skan", "torch", "potpourri3d"]
print("platform:", platform.platform())
print("python:", sys.version.split()[0])
print("project_root:", PROJECT_ROOT)
print("surface_lab_dir:", SURFACE_DIR)
for m in mods:
    print(f"{m}:", bool(importlib.util.find_spec(m)))
try:
    import uv_module
    print("uv_module:", uv_module.__file__)
except Exception as exc:
    print("uv_module: ERROR", repr(exc))
repo = SURFACE_DIR / "third_party" / "FFHQ-detect-face-wrinkles"
print("ffhq_repo:", repo.exists())
