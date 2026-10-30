# ATLAS: 50-point audit after UV/morphing review

**Date:** 2026-10-20  
**Scope:** the current ATLAS implementation, specifically the linked `uv_module` and `morphing` projects, plus the previously reported texture/progress failures.  
**Important:** “99% of errors” is not a statistically testable guarantee; this is a structured code/test audit. Items marked GAP are known scope differences, not silently counted as passes.

## Findings fixed in this pass

1. **UV renderer hard limit:** one broad triangle generated a one-row `cv2.remap` map wider than OpenCV’s signed-short limit. The failure reproduced at 384×384 in a deterministic test. Sampling now occurs in chunks of at most 30,000 pixels.
2. **Unobserved UV fill:** the prior inpaint mask covered all unseen UV texels despite the comment saying “tiny cracks”. It now fills only one-pixel holes adjacent to observed texels; unobserved areas remain unclaimed/black rather than being represented as source evidence.
3. **Input validation:** malformed image shape, non-finite coordinates, invalid triangle indices, non-integer faces and invalid atlas sizes now fail clearly before OpenCV crashes or silently casts indices.
4. **Texture control misleading state:** the “photo” button highlighted the albedo flag rather than the actual photo-UV flag. It now highlights the correct mode.
5. **Overlay obscured the source:** heat colours were multiplying the texture too strongly. Blend strength is reduced when source texture is present, and the viewport now offers explicit **Карта / Фото UV / Фото + Δ / Сетка** modes.
6. **No recovery after early UV request:** a UV endpoint miss could leave the view untextured until a frame change. The loader retries while the atlas becomes available and shows loaded/loading/error state.
7. **Test-suite fixture assumption:** several tests selected only active synthetic demos and read the first raw database record, which may be trashed. This made tests fail on the user’s valid seven-photo library and risked testing a removed demo. Tests now use active, already-cached samples and skip model-dependent checks when model assets are absent.

## The 50 checks

### UV atlas and texture projection (1–16)

1. Template vertex UV coordinates remain the 3DDFA topology UVs — **PASS**.
2. Image-space source coordinates are baked into the canonical atlas rather than installed as mesh UVs — **PASS**.
3. Atlas endpoint returns a PNG for a processed photo — **PASS** (1,210,762 bytes in the live smoke test).
4. Atlas is cached by photo feature key and baker version — **PASS** (lazy cache path inspected and exercised).
5. EXIF orientation is applied to source pixels — **PASS** (same EXIF-transpose path as the image pipeline).
6. Source vertex projections outside the image remain out-of-bounds rather than clamped — **PASS** (clamping removed; regression test).
7. UV triangle degeneracy is skipped — **PASS**.
8. Source-image pixel bounds are enforced per texel — **PASS**.
9. Multi-triangle samples accumulate instead of replacing each other — **PASS** (accumulation/weight implementation inspected).
10. Standard UV V direction is compatible with Three.js `flipY` — **PASS** (canonical orientation used; rendered in Chromium).
11. Renderer loads the baked UV PNG — **PASS** (Chromium reports “UV · текстура загружена”).
12. Texture is visible on the 3D mesh with heat disabled — **PASS** (visual browser check).
13. Heatmap-only mode turns off the photo texture — **PASS** (mode switching check).
14. Photo-only mode turns off the heat map — **PASS** (mode switching check).
15. Combined photo + Δ mode keeps both layers active — **PASS** (mode switching check).
16. Atlas inpaint does not claim unseen texels as original photo — **PASS** (inpaint limited to adjacent raster cracks; mask remains separate).

### UV input and numerical stress checks (17–29)

17. Atlas sizes 16 and 24 — **PASS**.
18. Atlas sizes 32 and 48 — **PASS**.
19. Atlas sizes 64 and 96 — **PASS**.
20. Atlas sizes 128 and 192 — **PASS**.
21. Atlas sizes 256 and 384 — **PASS**; 384 exposed the OpenCV remap-size bug, then passed after chunking.
22. Grayscale source image is rejected with a clear `ValueError` — **PASS**.
23. Images smaller than 2×2 are rejected — **PASS**.
24. Atlas sizes below 2 are rejected — **PASS**.
25. Source/template vertex count mismatch is rejected — **PASS**.
26. NaN UV coordinates are rejected — **PASS**.
27. Out-of-range triangle indices are rejected — **PASS**.
28. Fractional triangle indices are rejected rather than silently truncated — **PASS**.
29. Fully out-of-frame source triangles produce no visible mask and no fabricated pixels — **PASS** (five offset cases).

### Morphing behavior compared with the linked morphing project (30–39)

30. Two-photo interpolation reaches the first endpoint — **PASS** (existing test).
31. Two-photo interpolation reaches the last endpoint — **PASS** (existing test).
32. Intermediate linear interpolation is finite — **PASS**.
33. Current timeline can select/scrub a transition and synchronizes the displayed frame — **PASS** (previous production browser acceptance; linear pairwise route).
34. MP4 export validates input count/parameters — **PASS** (existing API suite).
35. MP4 export uses the cached topology if available — **PASS** (existing job acceptance).
36. Job cancellation and partial-file cleanup — **PASS** (previous 15/15 jobs acceptance).
37. Linked repo’s 2–4 keyframe Catmull–Rom timeline is present in ATLAS — **GAP**. ATLAS currently does pairwise linear/eased interpolation across its selected route; it does not claim age-aware Catmull–Rom.
38. Linked repo’s normalized barycentric 3–4-face blend is present in ATLAS — **GAP**. Not implemented in this audit.
39. Linked repo’s image/mesh quality-report packet and UV-difference analysis are present in ATLAS — **GAP**. These are additions in the reference project, not current ATLAS capabilities.

### Processing and degraded-mode behavior (40–44)

40. Processing endpoint accepts selected photo IDs and returns a job — **PASS** (observed job `0abeb91af4fd`).
41. Seven pending non-demo photos completed with no inference errors — **PASS** (`7 photos`, `0 errors`).
42. Newly processed records are ready and have usable cached meshes — **PASS** (all seven status checks returned ready).
43. Original-pixel UV atlas can be built from the processed photo — **PASS** (HTTP 200 PNG smoke test).
44. CPU/no-WebGL preview retains the original-photo texture — **GAP/KNOWN LIMIT**. The texture path is WebGL only; CPU fallback and current MP4 export do not use this original-photo atlas.

### Build, tests and browser checks (45–50)

45. TypeScript type-check — **PASS**.
46. Production Vite build — **PASS** (2,306 modules; existing large-chunk advisory remains).
47. Python backend modules compile — **PASS**.
48. New UV/calibration tests — **PASS**, 24 cases.
49. Full backend/API suite after making fixture selection safe — **PASS**, 61 passed, 1 harmless Starlette/httpx deprecation warning.
50. Chromium texture smoke test — **PASS**: texture status loaded; all three surface modes switched; no page or console errors.

## Remaining work / limits

- I cannot truthfully certify “99% of all possible errors”; this report covers 50 specific checks, not every browser/GPU, image, pose, and export combination.
- The linked morphing repo has additional features (multi-keyframe Catmull–Rom, barycentric blend, UV difference, quality gates/report packets) that remain **gaps** in ATLAS. I did not silently import those algorithms during this bug-fix audit.
- The original photo texture is verified in the WebGL scene only. CPU preview and MP4 still use their existing render path.
- The full test suite now avoids reading trashed demo IDs or processing uncached user uploads; it does not restore or mutate trashed demo/user data.

## Source review

- UV reference: https://github.com/hudyakovictor/facproject/tree/main/uv_module — affine per-triangle image→canonical-UV baking and visibility-aware handling.
- Morphing reference: https://github.com/hudyakovictor/facproject/tree/main/morphing — 2–4 keyframe Catmull–Rom, normalized barycentric blend, quality gates, UV diagnostics, and provenance-aware reports.
