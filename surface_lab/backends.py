from __future__ import annotations
from pathlib import Path
import importlib, sys
import cv2
import numpy as np


def enhance_for_wrinkle_inference(bgr: np.ndarray, mode: str = "none") -> np.ndarray:
    """Return a model-input copy with optional local detail enhancement.

    This is for detector sensitivity testing only.  It must not replace the
    original image in evidence/visual outputs.
    """
    mode = (mode or "none").lower()
    if mode == "none":
        return np.asarray(bgr, np.uint8).copy()
    img = np.asarray(bgr, np.uint8)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    if mode == "clahe":
        l2 = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(l)
        return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    if mode == "gentle":
        clahe_clip, amount, sigma = 1.25, 0.35, 1.2
    elif mode == "strong":
        clahe_clip, amount, sigma = 1.8, 0.75, 1.0
    else:
        raise ValueError(f"unsupported detail mode: {mode}")
    l2 = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8)).apply(l)
    base = cv2.GaussianBlur(l2, (0, 0), sigma)
    sharp = cv2.addWeighted(l2, 1.0 + amount, base, -amount, 0)
    sharp = np.clip(sharp, 0, 255).astype(np.uint8)
    return cv2.cvtColor(cv2.merge([sharp, a, b]), cv2.COLOR_LAB2BGR)

class ClassicalRidgeBackend:
    """Dependency-light geometry test backend; not forensic classification."""
    name = "classical-ridge-fallback"
    def __init__(self, detail_mode: str = "none"):
        self.detail_mode = detail_mode
        self.last_input_bgr = None

    def predict(self, bgr: np.ndarray, valid_mask: np.ndarray | None = None) -> np.ndarray:
        inp = enhance_for_wrinkle_inference(bgr, self.detail_mode)
        self.last_input_bgr = inp
        gray = cv2.cvtColor(inp, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        local = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply((gray*255).astype(np.uint8)).astype(np.float32)/255.0
        try:
            from skimage.filters import frangi
            response = frangi(1.0-local, sigmas=(1, 2, 3), black_ridges=False)
        except Exception:
            # Structural smoke-test fallback when scikit-image is not yet
            # installed. Official experiments should use the FFHQ backend.
            u8=np.round(local*255).astype(np.uint8)
            maps=[]
            for k in (5,9,13):
                maps.append(cv2.morphologyEx(u8,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))).astype(np.float32)/255.0)
            response=np.maximum.reduce(maps)
        response = np.nan_to_num(response.astype(np.float32))
        if valid_mask is None:
            valid_mask = np.ones(response.shape, bool)
        valid_mask = np.asarray(valid_mask, bool)
        vals = response[valid_mask]
        if vals.size:
            lo, hi = np.percentile(vals, [70, 99.5])
            response = np.clip((response-lo)/(hi-lo+1e-6), 0, 1)
        response[~valid_mask] = 0
        return response

class FFHQWrinkleBackend:
    """Adapter for the official rmsandu repository and a user-supplied checkpoint."""
    name = "ffhq-wrinkle-unet"
    def __init__(self, repo: str | Path, checkpoint: str | Path, device: str = "cpu", input_size: int = 512, detail_mode: str = "none"):
        import torch
        self.torch, self.device, self.input_size = torch, torch.device(device), int(input_size)
        self.detail_mode = detail_mode
        self.last_input_bgr = None
        repo = Path(repo).resolve(); checkpoint = Path(checkpoint).resolve()
        if not repo.exists(): raise FileNotFoundError(repo)
        if not checkpoint.exists(): raise FileNotFoundError(checkpoint)
        sys.path.insert(0, str(repo))
        try:
            mod = importlib.import_module("unet")
            UNet = getattr(mod, "UNet")
        except Exception:
            mod = importlib.import_module("unet.unet_model")
            UNet = getattr(mod, "UNet")
        model = UNet(n_channels=3, n_classes=1, bilinear=False)
        raw = torch.load(checkpoint, map_location=self.device)
        state = raw.get("model_state_dict", raw.get("state_dict", raw)) if isinstance(raw, dict) else raw
        state = {str(k).removeprefix("module."): v for k,v in state.items()}
        model.load_state_dict(state, strict=True)
        self.model = model.to(self.device).eval()

    def predict(self, bgr: np.ndarray, valid_mask: np.ndarray | None = None) -> np.ndarray:
        torch = self.torch; h,w=bgr.shape[:2]
        inp = enhance_for_wrinkle_inference(bgr, self.detail_mode)
        self.last_input_bgr = inp
        rgb=cv2.cvtColor(inp,cv2.COLOR_BGR2RGB)
        x=cv2.resize(rgb,(self.input_size,self.input_size),interpolation=cv2.INTER_AREA).astype(np.float32)/255.0
        x=torch.from_numpy(x.transpose(2,0,1))[None].to(self.device)
        with torch.inference_mode():
            logits=self.model(x)
            if isinstance(logits,dict): logits=logits.get("out",next(iter(logits.values())))
            prob=torch.sigmoid(logits)[0,0].detach().cpu().numpy()
        prob=cv2.resize(prob,(w,h),interpolation=cv2.INTER_LINEAR).astype(np.float32)
        if valid_mask is not None:
            prob[~np.asarray(valid_mask, bool)] = 0
        return np.clip(prob,0,1)
