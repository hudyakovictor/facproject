from __future__ import annotations
import importlib, json, platform, sys
from pathlib import Path
mods = ["cv2", "numpy", "torch", "skimage", "skan", "scipy"]
report = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(), "modules": {}}
for name in mods:
    try:
        m = importlib.import_module(name)
        report["modules"][name] = {"ok": True, "version": getattr(m, "__version__", "unknown")}
    except Exception as exc:
        report["modules"][name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
try:
    import torch
    report["torch"] = {"mps_built": torch.backends.mps.is_built(), "mps_available": torch.backends.mps.is_available(), "stage1_device": "cpu"}
except Exception:
    pass
assets = Path("3ddfav3/assets")
report["assets"] = {n: (assets/n).is_file() for n in ["face_model.npy", "net_recon.pth", "net_recon_mbnet.pth", "large_base_net.pth"]}
print(json.dumps(report, ensure_ascii=False, indent=2))
if not all(v["ok"] for v in report["modules"].values()):
    raise SystemExit(1)
