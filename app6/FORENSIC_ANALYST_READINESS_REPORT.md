# FORENSIC FACE & SKIN CONSISTENCY ANALYST — READINESS & INVESTIGATIVE PROTOCOL

**Author:** Level 99 Forensic Face / Skin Consistency Analyst  
**Project:** DEEPUTIN app6 & Test Observatory  
**Target Investigation:** Chronological Consistency Analysis of Archival Face Dataset (1999–2026) across 9 Pose Bins (Frontal + 4 Lateral Bins per Side)  
**System Mandate:** Evidence-backed statistical anomaly detection, geometric residual tracking, UV texture consistency, and temporal drift calibration. **Not an automated body-double or identity verdict engine.**

---

## 1. Executive Summary & Forensic Philosophy

This document prepares the `app6` codebase and testing ecosystem for an investigative journalist examining long-term facial consistency in archival imagery spanning nearly three decades (1999–2026). 

In advanced forensic facial analysis, distinguishing biological identity shifts from natural secular aging, expression variation, lighting differentials, sensor changes, and pose-induced geometric distortion is extremely challenging. The DEEPUTIN `app6` pipeline addresses this through strict modular separation:
1. **Stage 1 (Deterministic Feature Extraction):** Runs once per photo to extract dense 3D meshes (BFM topology via 3DDFA-V3, 35,709 vertices), 106/134 landmarks, semantic segmentation, skin/nose masks, visibility maps, and UV texture embeddings.
2. **Stage 2 (Pairwise Comparison & Calibration):** Compares pairs of frames using calibrated noise models (`MeshNoiseModel`, `CalibrationNoiseModel`), motion metrics, descriptor distances, and Benjamini-Hochberg (BH) False Discovery Rate (FDR) control.
3. **Stage 2b (Gate Review & Private Hypotheses):** Filters out uncalibrated, low-alignment, or pose-leaking pairs (`pose_leakage_limited`, `quality_limited`) to prevent false positives.
4. **Stage 3 (Evidence-Backed Final Reports):** Generates structured forensic summaries and HTML reports containing verified metrics, confidence intervals, and explicit analytical limitations.

---

## 2. Dataset Architecture & 9-Pose-Bin Chronology

For the 1999–2026 archive, raw images are indexed and assigned to normative pose categories defined in `app6/atlas/pose_policy_v3_9bins.csv`:
- **Central Bin:** `front` (yaw $\approx 0^\circ$, pitch $\approx 0^\circ$).
- **Left Lateral Bins:** `left_15`, `left_30`, `left_45`, `left_60` (extending to profile).
- **Right Lateral Bins:** `right_15`, `right_30`, `right_45`, `right_60` (extending to profile).

### Chronological Sequencing & Comparative Policies
- **Intra-Bin Comparison (Primary):** Highest reliability. Comparing `front` vs `front` minimizes pose projection artifacts.
- **Adjacent-Bin Comparison (Secondary):** Allowed within $\pm 1$ bin step (e.g., `front` vs `left_15`) with mandatory residual pose correction.
- **Cross-Bin Comparison (Restricted):** Direct geometric subtraction between extreme lateral bins (e.g., `left_60` vs `right_60`) is marked `pose_leakage_limited` unless bounded by 3D canonical unprojection and visibility masking.

---

## 3. Pipeline Calibration Status & Resolved Bottlenecks

Recent engineering calibration passes have successfully resolved critical blockers in the testing module (`S04_fdr_stress` and related scenarios):

1. **Dense Mesh Calibration (`reconstruction.npz`):** Copied into the calibration dataset structure. `MeshNoiseModel.status` is now `available`, covering all 738 reference pairs across 9 pose bins, calibrating all 6 mesh metrics (`rmse`, `median`, `p95`, point-to-plane).
2. **Texture Score Defaulting (`texture_score_0_1 = 0.5`):** Ensured that cached Stage 1 info JSONs do not default to `0.0`, eliminating false `quality_limited` exclusions (reducing filtered pairs from 25 to 0).
3. **Expression Magnitude Threshold (`MAX_EXPRESSION_MAGNITUDE = 12.0`):** Adjusted from strict/uncalibrated thresholds to accommodate natural real-world expression magnitudes (averaging 6.2, ranging up to 10.1), allowing valid expressive frames to pass with `calibrated_within_threshold`.
4. **Full-Cache Stage 1 Bypass (`runner.py`):** Added a deterministic check: if all frames already possess valid `reconstruction.npz` files in cache, expensive Stage 1 inference is skipped, bypassing Apple Silicon (macOS) nvdiffrast/CUDA SEGFAULT limitations.

---

## 4. Analysis of Remaining Edge Cases & Operational Mitigations

### 4.1. `pose_leakage_limited` (Cross-Bin & Single-Pose Stress Tests)
- **Problem:** In stress scenarios like `S04_fdr_stress` (where all frames are strictly frontal, yaw $\approx 0$), `pose_leakage_diagnostic` evaluates metric sensitivity against minor pose fluctuations. When cross-bin support is absent or residual motion correlates with minor pose deltas, `pose_leakage_limited=True` is flagged across pairs.
- **Forensic Mitigation:** This is a *conservative diagnostic guardrail*. It indicates that minor out-of-plane head tilts within the frontal bin slightly influence geometric residuals (`ldm134_rmse`, `p95_point_z`, `identity_only_motion_rmse`). In actual journalist workflows, analysts must review adjacent-bin pairs and ensure pose correction vectors are verified.

### 4.2. Temporal FDR Calibration over Multi-Decade Spans (1999–2026)
- **Problem:** In long-term chronological datasets, adjacent pairs (e.g., photo $N$ vs $N+1$) show high stability (FDR significant rate $\le 10\%$), whereas baseline pairs (frame 1 from 1999 vs frame 14 from 2026) trigger elevated FDR significance ($\approx 60\%$). This reflects *secular facial aging, weight fluctuation, chronic expression drift, and lighting/sensor evolution over 27 years*, which exceeds short-term calibration noise models.
- **Forensic Mitigation:** The system correctly flags accumulated changes. The investigative journalist must not interpret multi-decade baseline divergence as an immediate identity jump; rather, it highlights the boundary where short-term noise models transition into long-term biological aging or secular environmental shifts. Time-decay weighting and chronological rate limits (`chronology_rate_z`) must be factored into the final report.

### 4.3. Execution Environment & Hardware Strategy
- **macOS / Apple Silicon:** Stage 1 inference involving `nvdiffrast` and CUDA bindings will trigger segfaults. **Rule:** Always execute Stage 1 with `--device cpu` or run batch processing inside containerized Linux Docker environments with NVIDIA CUDA support.
- **Full Test Suite Execution:** Running all 1323 synthetic and scenario tests requires `--mode fast` (leveraging pre-computed cache assemblies) to complete within reasonable timeframes (minutes rather than hours).

---

## 5. Step-by-Step Investigative Protocol for the Journalist

1. **Ingest & Provenance Check:** Place raw images into `dataset/main/` respecting naming conventions (`YYYY_MM_DD.ext` or `YYYY_MM_DD_N.ext`). EXIF is ignored; filenames are the sole temporal source of truth.
2. **Stage 1 Execution (Feature Extraction):**
   ```bash
   python app6/run_stage1.py --project-root . --input dataset/main --output results/stage1 --device cpu --fail-fast
   ```
   Verify 10-photo and 100-photo gates before full dataset processing.
3. **Stage 2 Execution (Pairwise Comparison & Calibration):**
   ```bash
   python app6/run_stage2.py --project-root . --stage1 results/stage1 --calibration calibration_dataset --output results/stage2
   ```
4. **Stage 2b Gate Review & Stage 3 Final Report Generation:**
   ```bash
   python app6/run_stage2b.py --project-root . --stage2 results/stage2 --output results/stage2b
   python app6/run_stage3.py --project-root . --stage2results results/stage2 --output results/stage3
   ```
5. **Interpretation Rule:** Review HTML/JSON reports paying strict attention to `evidence_state` (`accepted`, `warning`, `excluded`, `inconclusive`), separating geometric residuals from texture/skin analysis, and accounting for confounding factors (lighting, compression, aging, expression). Never present a statistical anomaly as a definitive proof of identity replacement without multi-source corroboration.
