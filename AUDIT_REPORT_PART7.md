# AUDIT REPORT — Part 7: Deep Audit of 3ddfav3/face_box, renderers, and utilities

**Date:** 2026-07-19  
**Auditor:** Forensic Face & Skin Consistency Analyst  
**Scope:** 16 previously unchecked Python files in `3ddfav3/face_box/`, `3ddfav3/util/`, plus `3ddfav3/demo.py` and `3ddfav3/model/mb_v3_networks.py`

---

## Executive Summary

Deep audit of the **3DDFA_V3 face detection subsystem** and **CPU/GPU renderers** — the critical upstream pipeline that feeds the entire forensic analysis. Found **11 bugs** across 7 files, including a **CRITICAL integer division bug** in RetinaFace landmark encoding, **4 `exit()` calls** that crash the entire Python process, and **4 tensor mutation bugs** in renderers.

---

## Bugs Found & Fixed

### 1. CRITICAL: `3ddfav3/face_box/retinaface/box_utils.py:221` — Integer division in `encode_landm`

**Severity:** CRITICAL  
**Problem:** The landmark encoding function uses `g_cxcy // variances[0] * priors[:, :, 2:]` — **integer floor division** (`//`) instead of **true division** (`/`). This causes landmark coordinates to lose fractional precision during encoding, resulting in **quantized/pixelated landmark predictions**. The decode function uses `*` (multiplication by variance), which cannot recover the lost fractional bits. Every landmark prediction from RetinaFace was being truncated.

**Fix:** Changed `//` to `/` and restructured as `g_cxcy / (variances[0] * priors[:, :, 2:])` to match the decode formula in `decode_landm()`.

```python
# BEFORE (integer division — loses fractional precision):
g_cxcy = g_cxcy // variances[0] * priors[:, :, 2:]

# AFTER (correct float division matching decode_landm):
g_cxcy = g_cxcy / (variances[0] * priors[:, :, 2:])
```

### 2. HIGH: `3ddfav3/face_box/__init__.py` — 4× `exit()` kills entire process

**Severity:** HIGH  
**Problem:** Four locations use `exit()` instead of raising exceptions. In the facproject pipeline, `Stage1Engine.run()` has `continue_on_error=True` and catches exceptions per photo. But `exit()` bypasses all exception handling and **kills the entire Python process**, losing all progress on previously processed photos.

Locations:
- Line 14: `no_crop()` — image not 224×224
- Line 49: `retinaface.detector()` — no face detected, image not 224×224
- Line 84: `mtcnnface.detector()` — low confidence, image not 224×224
- Line 93: `mtcnnface.detector()` — no face detected, image not 224×224
- Line 108: `face_box.__init__()` — unknown detector name

**Fix:** All `exit()` replaced with `raise RuntimeError(...)` or `raise ValueError(...)`.

### 3. HIGH: `3ddfav3/util/nv_diffrast.py` — MeshRenderer mutates input tensor

**Severity:** HIGH  
**Locations:** Lines 51, 131 (both `MeshRenderer.forward()` and `MeshRenderer_UV.forward()`)  
**Problem:** `vertex[..., 1] = -vertex[..., 1]` modifies the caller's tensor in-place. In `face_model.forward()`, the `v3d` tensor is reused after the renderer call (for visible_idx computation and UV texture extraction). The Y-inversion leaks back to the caller, corrupting subsequent computations that depend on the original vertex coordinates.

**Fix:** Added `vertex = vertex.clone()` before the mutation in both `MeshRenderer` and `MeshRenderer_UV`.

### 4. HIGH: `3ddfav3/util/cpu_renderer.py` — MeshRenderer_cpu mutates input tensor

**Severity:** HIGH  
**Locations:** Lines 50, 128  
**Problem:** Same mutation bug as nv_diffrast.py — affects the CPU renderer path (used on MacBook M1).

**Fix:** Added `vertex = vertex.clone()` before Y-inversion in both `MeshRenderer_cpu` and `MeshRenderer_UV_cpu`.

### 5. MEDIUM: `3ddfav3/util/io.py:27` — Wrong color for 'b' in `plot_kpts()`

**Severity:** MEDIUM  
**Problem:** `color == 'b'` maps to `(255, 0, 0)` — which is **red**, not blue. This is a copy-paste error from the `color == 'r'` case above it.

**Fix:** Changed to `(0, 0, 255)` — correct BGR blue.

### 6. MEDIUM: `3ddfav3/demo.py:80` — `texture_size=1024` exceeds facproject limit

**Severity:** MEDIUM  
**Problem:** Default `--texture_size` is 1024, exceeding the 1000px UV atlas cap established for facproject (source photos ≤800x800px).

**Fix:** Changed default to 1000.

### 7. MEDIUM: `3ddfav3/face_box/retinaface/network.py:23` — Deprecated `pretrained=` parameter

**Severity:** MEDIUM  
**Problem:** `models.resnet50(pretrained=pretrained)` uses the deprecated `pretrained` parameter. In newer torchvision versions this produces a `FutureWarning` and may be removed.

**Fix:** Changed to `models.resnet50(weights=models.ResNet50_Weights.DEFAULT if pretrained else None)`.

### 8. LOW: `3ddfav3/face_box/retinaface/predict_single.py:66` — `np.array` type hint

**Severity:** LOW  
**Problem:** Type annotation uses `np.array` (a function) instead of `np.ndarray` (the type). This confuses static type checkers.

**Fix:** Changed to `np.ndarray`.

### 9. LOW: `3ddfav3/face_box/retinaface/utils.py` — Multiple `np.array` type hints

**Severity:** LOW  
**Problem:** Same as above — `np.array` used instead of `np.ndarray` in 2 type annotations.

**Fix:** Changed all occurrences to `np.ndarray`.

### 10. LOW: `3ddfav3/face_box/facelandmark/large_model_infer.py:90` — `torch.load` without `weights_only`

**Severity:** LOW  
**Problem:** `torch.load(path, map_location="cpu")` without `weights_only=False` will trigger a `FutureWarning` in PyTorch 2.6+ and may default to `True` in future versions, causing loading failures.

**Fix:** Added `weights_only=False`.

### 11. INFO: `3ddfav3/model/mb_v3_networks.py` — Audited, no bugs

**Finding:** Standard MobileNetV3 architecture with `recon_MobileNetV3` variant (no classifier head, outputs features directly). Clean code, proper initialization. No issues found.

---

## Files Audited Without Changes

| File | Lines | Status |
|------|-------|--------|
| `3ddfav3/model/mb_v3_networks.py` | 308 | ✅ Clean — standard MobileNetV3 |
| `3ddfav3/face_box/retinaface/prior_box.py` | 28 | ✅ Clean — anchor box generation |
| `3ddfav3/face_box/retinaface/net.py` | 124 | ✅ Clean — SSH + FPN modules |
| `3ddfav3/face_box/facelandmark/nets/large_base_lmks_net.py` | 189 | ✅ Clean — SoftArgmax + landmark network |
| `3ddfav3/util/cython_renderer/setup.py` | 20 | ✅ Clean — build script |

---

## Architectural Observations

### 1. Face detection pipeline flow
```
face_box/__init__.py → LargeModelInfer → RetinaFace → detect boxes
                                              ↓
                            LargeBaseLmkInfer → 106 landmarks
                                              ↓
                            preprocess.align_img → 224×224 aligned face
```

The `face_box.retinaface` detector extracts bounding boxes, then `LargeModelInfer` does a **two-pass landmark detection** (coarse → refined crop → fine) which is a good approach for accuracy.

### 2. Landmark index selection in `face_box/__init__.py:37`
```python
for idx in [74, 83, 54, 84, 90]:
```
These 5 indices map 106-point landmarks to the 5 canonical points (left eye, right eye, nose, left mouth, right mouth) used for affine alignment. This mapping is correct for the 3DDFA_V3 106-point model.

### 3. CPU vs GPU renderer code duplication
`cpu_renderer.py` and `nv_diffrast.py` share nearly identical logic (~80% code duplication) for vertex transformation and rendering. The CPU version uses a Cython mesh core (`mesh_core_cython.MeshRenderer_cpu_core`), while the GPU version uses `nvdiffrast`. This is a maintenance burden but functionally correct.

### 4. `large_model_infer.py:fat_face()` calls undefined functions
The `fat_face()` method calls `spread_flow()` and `image_warp_grid1()` which are **not imported and not defined** in the module. These appear to be from a removed utility module. This method is dead code — it's never called from the facproject pipeline.

---

## Test Results

```
55 passed, 2 warnings, 3 subtests passed in 11.50s
```

All tests pass after all changes.

---

## Cumulative Fix Count

| Audit Round | Bugs Fixed |
|-------------|-----------|
| Part 1 | 10 |
| Part 2 | 3 |
| Part 3 | 3 |
| Part 4 | 11 |
| Part 5 | 1 |
| Part 6 | 7 |
| **Part 7** | **11** |
| **Total** | **46** |
