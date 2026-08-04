"""📊 METRIC → Панель системного здоровья для `/api/v1/system/health`.

Отдаёт реальные показатели процесса и окружения: CPU/RAM (через `psutil`,
опционально), наличие весов 3DDFA_V3, наличие датасетов, версии
интерпретатора. Ничего не подделывает: если `psutil` не установлен —
поле явно помечается `unavailable`, а не нулём.
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any

SYSTEM_HEALTH_SCHEMA = "deeputin-api-system-health-v1.0"

REQUIRED_MODEL_ASSETS = (
    "face_model.npy", "net_recon.pth", "large_base_net.pth",
    "retinaface_resnet50_2020-07-20_old_torch.pth", "similarity_Lm3D_all.mat",
)


def _optional_dependency_status() -> dict[str, Any]:
    statuses = {}
    for module_name in ("torch", "cv2", "numpy", "psutil"):
        try:
            module = __import__(module_name)
            statuses[module_name] = {"available": True, "version": getattr(module, "__version__", "unknown")}
        except ImportError:
            statuses[module_name] = {"available": False, "version": None}
    return statuses


def _resource_usage() -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {"available": False, "reason": "psutil not installed"}
    process = psutil.Process(os.getpid())
    virtual_memory = psutil.virtual_memory()
    return {
        "available": True,
        "cpu_percent": psutil.cpu_percent(interval=0.05),
        "process_rss_mb": round(process.memory_info().rss / (1024 * 1024), 1),
        "system_memory_percent": virtual_memory.percent,
        "system_memory_total_gb": round(virtual_memory.total / (1024 ** 3), 2),
    }


def _gpu_status() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {"available": False, "reason": "torch not installed"}
    cuda_available = bool(torch.cuda.is_available())
    return {
        "available": True,
        "cuda_available": cuda_available,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
        "device_name": torch.cuda.get_device_name(0) if cuda_available else None,
    }


def build_system_health(project_root: Path) -> dict[str, Any]:
    assets_dir = project_root / "assets"
    missing_weights = [name for name in REQUIRED_MODEL_ASSETS if not (assets_dir / name).is_file()]
    from .bfm_topology import is_bfm_available
    from .runtime_config import load_runtime_paths, runtime_path_report

    paths = load_runtime_paths()
    path_report = runtime_path_report(paths)
    return {
        "schema": SYSTEM_HEALTH_SCHEMA,
        "not_a_verdict": True,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dependencies": _optional_dependency_status(),
        "resources": _resource_usage(),
        "gpu": _gpu_status(),
        "model_assets": {
            "required": list(REQUIRED_MODEL_ASSETS),
            "missing": missing_weights,
            "ready": not missing_weights,
        },
        "bfm_geometry_available": is_bfm_available(),
        "calibration_dataset_present": (paths.calibration_root / "all_calibration_index.csv").is_file()
        or (project_root / "calibration_dataset" / "all_calibration_index.csv").is_file(),
        "runtime_paths": path_report,
        "stage1_ready": path_report["status"]["stage1_ready"],
        "calibration_ready": path_report["status"]["calibration_ready"],
    }

