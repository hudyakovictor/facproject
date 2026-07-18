# Production specification: pose-aware skin-line chronology v2

## Scope

The subsystem measures the consistency of visible skin-line/ridge structure over time. It is not an identity classifier. It never measures synthetic UV pixels.

## Pose targeting matrix

| Pose | Primary targets | Down-weighted/disabled |
|---|---|---|
| frontal | horizontal forehead, glabella, both under-eye zones, both crow's-feet, both upper cheeks, both nasolabial folds, chin | none; quality gates still apply |
| left/right light | near-side targets plus central forehead/glabella | far side weight 0.65 |
| left/right mid | near-side forehead, under-eye, crow's-feet, cheek, nasolabial | far side disabled; center weight 0.72 |
| left/right deep | near-side eye/crow's-feet/cheek/nasolabial/forehead | opposite and most center zones disabled |
| left/right profile | near-side crow's-feet, cheek, nasolabial and lateral forehead | all other zones disabled |

Visibility is not inferred from the label alone. A zone must also pass the observed-source mask, triangle visibility, source-pixel span, coverage, noise and detector-consensus gates.

## Resolution policy

The zone is measured in original source-image pixels using its reconstructed mesh vertices. Upscaling the UV never increases this evidence count.

- below 12 px minimum span: reject;
- 12–19 px: coarse lines only, confidence ceiling 0.38;
- 20–35 px: limited analysis, confidence ceiling 0.62;
- 36 px and above: standard multiscale analysis.

Thus low-resolution material is retained when it supports coarse stable furrows, but the system refuses claims about fine wrinkles that the source could not resolve.

## Grain/noise policy

1. Estimate local noise independently for every anatomical zone.
2. Preserve the original analytical UV unchanged.
3. Build a raw Retinex-normalized descriptor branch.
4. Build a conservative noise-adaptive non-local-means descriptor branch.
5. Run an anatomically oriented Hessian bank over several scales in both branches.
6. Keep a candidate only when it persists across scales and both branches.
7. Set the threshold from robust local statistics and cap graph density.
8. Remove components shorter than a source-resolution-proportional minimum.

This prevents a denoiser from becoming evidence and reduces the chance that film grain/JPEG noise becomes a wrinkle graph.

## Anatomical orientation priors

- forehead/chin/under-eye: predominantly horizontal;
- glabella: predominantly vertical;
- crow's-feet: radial family around −45°, 0°, +45°;
- nasolabial: oblique-to-vertical family;
- cheek: broad shallow orientation family.

The priors are soft Gaussian weights, not hard line deletion.

## Skan graph contract

Each accepted branch stores normalized UV centroid, geodesic pixel length, median tangent orientation, mean ridge strength and Skan branch type. Skan branch IDs are local and never treated as persistent identifiers.

Consecutive dates are matched only within the same `pose_bin × anatomical_zone` using constrained centroid/orientation/length assignment. Chronology uses branch persistence plus aggregate ridge density and total length. A candidate must pass quality and, for a persistent label, remain supported by the following comparison.

## Outputs

Per photo:

- `wrinkle_zones.json`: quality, metrics and branch descriptors;
- `wrinkle_zones.npz`: zone masks, valid masks, ridge probabilities, binaries and skeletons;
- `uv_wrinkle_skeletons.png`: QA preview;
- `uv_analysis.png`: immutable observed-only evidence;
- `uv_synthetic.png`: visual/morphing product, prohibited from metrics.

Across dates:

```bash
python scripts/run_wrinkle_chronology.py --stage1 results/stage1 --output results/wrinkle_chronology.json
```

## Required calibration before evidentiary use

Run the supplied 10-photo and 100-photo gates with representative frontal/profile, low-resolution, high-grain, compressed and retouched samples. Manually inspect zone overlays and false branch rate. Thresholds must be frozen and recorded with the config/code hash before the full 1999–2026 batch. Absence of this calibration means results are exploratory, not publication-grade evidence.
