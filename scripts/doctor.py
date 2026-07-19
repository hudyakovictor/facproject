#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, platform, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
modules = {name: importlib.util.find_spec(name) is not None for name in (
    "cv2", "numpy", "scipy", "skimage", "skan", "torch", "torchvision"
)}
assets_dir = ROOT / "3ddfav3" / "assets"
assets = {
    "face_model.npy": (assets_dir / "face_model.npy").is_file(),
    "net_recon": any((assets_dir / n).is_file() for n in ("net_recon.pth", "net_recon_mbnet.pth")),
    "large_base_net.pth": (assets_dir / "large_base_net.pth").is_file(),
}
renderer = list((ROOT / "3ddfav3" / "util" / "cython_renderer").glob("mesh_core_cython*.so"))
payload = {
    "platform": platform.platform(), "machine": platform.machine(),
    "python": sys.version.split()[0], "python_bits": struct.calcsize("P") * 8,
    "modules": modules, "assets": assets, "cpu_renderer_compiled": bool(renderer),
    "scientific_stack_ready": all(modules.values()),
    "stage1_ready": all(modules.values()) and all(assets.values()) and bool(renderer),
}
print(json.dumps(payload, indent=2))
raise SystemExit(0 if payload["stage1_ready"] else 1)
