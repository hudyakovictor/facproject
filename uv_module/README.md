# uv_module v3 — high-detail forensic UV texture generation for 3DDFA_V3

Drop-in replacement for `uv_module` (same contract as v1/v2, used by
`app/stage1/assets.py`):

```python
from uv_module import HDUVConfig, HDUVTextureGenerator
cfg = HDUVConfig(uv_size=1000, super_sample=2)
analysis, beauty, observed, confidence, aux = HDUVTextureGenerator(cfg).generate(bgr, recon)
```

Two strictly separated products:

- **`analysis`** — evidence texture. Real photo pixels only, mathematically
  untouched (no CLAHE, no unsharp, no inpainting, no mirroring). Safe for
  LBP/GLCM/skan skin analytics. Hidden texels are black; `observed` is the
  provenance mask.
- **`beauty`** — morph texture. Contralateral (mirror) completion of the hidden
  half with LAB color matching + seam feather + TELEA for leftover holes.
  For 3D morph / visual geometry comparison ONLY. `aux["synthetic_mask"]`
  marks every synthetic texel.

## What changed vs v1/v2 (and why)

| # | Fix | Why |
|---|-----|-----|
| 1 | **UV v-orientation = v2 convention** (atlas row 0 = v=1) | Matches the OBJ convention and the flipped-y sampling in 3DDFA_V3 `get_colors_from_uv` / `process_uv`; v1 wrote the atlas upside down. |
| 2 | **No enhancement of the analysis texture** | v1/v2 ran CLAHE + unsharp on the *evidence* texture despite the docstring. This alters LBP/GLCM/Sato/skan statistics (forensic contamination) and is now morph-only. Optional enhanced copy for humans: `aux["analysis_view"]`. |
| 3 | **Mask-aware enhancement + BGR2LAB** | v1/v2 blurred black unobserved texels into the skin (measured ≈10-luma dark halo at the mask border) and converted BGR with `COLOR_RGB2LAB`. |
| 4 | **Per-pixel interpolated-depth occlusion test** | v1/v2 painted one constant depth per triangle (painter's algorithm); on steep geometry (nose flanks, brow ridge) this produced ragged false-occlusion holes. v3 paints triangle IDs and evaluates barycentric-interpolated depth at each vertex pixel. |
| 5 | **`cv2.remap` with `BORDER_REPLICATE`** | Lanczos against a constant black border rings and darkens frame-edge texels; out-of-frame texels are now removed by the `in_frame` mask instead. |
| 6 | **`observed_erode_px=2`** | INTER_AREA + Lanczos mix background/hair into boundary texels; erosion keeps them out of the evidence mask. |
| 7 | **Optional `recon["skin_mask"]`** | Pass the 3DDFA_V3 segmentation (or any skin matte) and background/hair/eyes/mouth-interior never enter the texture. Strongly recommended for the 9-pose-bin pipeline. |
| 8 | **LAB color match before mirror fill** | Side-lit poses no longer show a luminance step across the symmetry seam of the morph texture. |
| 9 | **Footprint Jacobian cleanup** | Sobel spikes at atlas borders removed (median filter + valid mask) → stabler confidence map. |

## Benchmark (synthetic ground truth, 800×800 photo, 28° yaw, nose occlusion)

| | observed | PSNR vs GT | analysis pure* | border halo | time (M1-class CPU) |
|---|---|---|---|---|---|
| v2 | 82.4 % | 29.77 dB | **no** | −10.15 luma | 6.1 s |
| v3 | 75.3 % | **38.97 dB** | **yes** | −2.32 luma | 5.3 s |

*pure = analysis output byte-identical with `detail_enhance` on/off.
v3 observes fewer texels **by design**: eroded borders + skin-mask gating keep
only clean evidence texels. Reproduce with `tests/test_synthetic_gt.py`.

## Practical settings for the 1999–2026 / 9-pose-bin dataset

- Photos ≤ 800×800 → `uv_size=1000`, `super_sample=2` (3 adds nothing but RAM/time).
- Keep `enable_delighting=False` for evidence textures; illumination must be
  handled downstream as a covariate, not edited into the pixels.
- Feed **only `analysis` + `observed` + `confidence`** to skin metrics;
  `beauty` is for the morph viewer. `aux["synthetic_mask"]` must be treated as
  a hard exclusion everywhere else.
- Confidence already encodes angle × occlusion × footprint: use it to weight
  chronological comparisons per pose bin instead of hard thresholds.
