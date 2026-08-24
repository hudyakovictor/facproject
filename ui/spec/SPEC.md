# DEEPUTIN Forensic Workstation — UI Technical Specification

## 1. Purpose

This document defines **what data the interface must display**, not **how it should look**.  
Each section lists atomic UI elements with their exact data keys, types, and sources.  
Designers may propose any visual layout; developers must map real data to these elements without changing schemas.

---

## 2. Data Source Map

All real data lives under `/Volumes/SDCARD/storage/`.  
The interface must never invent values. If a source file is missing, show an explicit empty state with the reason.

| Layer | Path | Key files |
|---|---|---|
| Stage 1 | `/Volumes/SDCARD/storage/stage1/` | `main_timeline.csv`, `stage1_manifest.json`, `<photo_id>/info.json`, `<photo_id>/ldm106_*.csv`, `<photo_id>/ldm134_*.csv`, `<photo_id>/texture.json`, `<photo_id>/face_mask.png`, `<photo_id>/uv_texture.png` |
| Stage 2 | `/Volumes/SDCARD/storage/stage2/` | `analysis_manifest.json`, `pair_metrics.csv`, `pair_details.json`, `mesh_pair_metrics.csv`, `mesh_zone_metrics.csv`, `change_points.json`, `evidence_packets.json`, `artifact_index.json` |
| Stage 2B | `/Volumes/SDCARD/storage/stage2b/` | `stage2b_manifest.json`, `private_summary.json`, `corroboration_results.csv` |
| Stage 3 | `/Volumes/SDCARD/storage/stage3/` | `report_data.json`, `index.html` |
| API | FastAPI at `http://localhost:8000/api/v1/*` | See `API_CONTRACT.md` |

**Environment variables** (fallback chain in `app6/api/server.py:172`):
```
DEEPUTIN_STORAGE_ROOT → /Volumes/SDCARD/storage
DEEPUTIN_STAGE1_ROOT  → <storage>/stage1
DEEPUTIN_STAGE2_ROOT  → <storage>/stage2
DEEPUTIN_STAGE3_ROOT  → <storage>/stage3
DEEPUTIN_CALIBRATION_ROOT → /Volumes/SDCARD/photo/calibration_dataset/calibration_datasets
```

---

## 3. Pages / Views

### 3.1 Timeline (Home)

**Purpose:** chronological inventory of all photos with quality and pose metadata.

**Data source:** `stage1/main_timeline.csv` + `stage1/stage1_manifest.json`

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `schema_version` | `stage1_manifest.schema_version` | string | e.g. `deeputin-stage1-v2.4-chronology-alignment` |
| `status` | `stage1_manifest.status` | enum | `complete` / `partial` / `error` |
| `photo_count` | `stage1_manifest.success_count` | integer | Total successfully processed photos |
| `error_count` | `stage1_manifest.error_count` | integer | Photos that failed extraction |
| `elapsed_seconds` | `stage1_manifest.elapsed_seconds` | float | Total extraction time |
| `device` | `stage1_manifest.device` | string | `cpu` / `cuda` |
| `backbone` | `stage1_manifest.backbone` | string | `resnet50` / `mbnetv3` |
| `uv_size` | `stage1_manifest.uv_size` | integer | UV texture resolution |
| `created_at_utc` | `stage1_manifest.created_at_utc` | ISO8601 | When extraction finished |
| `input_dir` | `stage1_manifest.input_dir` | string | Source photos directory |
| `output_dir` | `stage1_manifest.output_dir` | string | Stage 1 output directory |
| `photo_list` | `main_timeline.csv` rows | array | One object per photo (see 3.1.1) |

**Empty state:** If `main_timeline.csv` is missing or empty, show:  
`"Stage 1 output not found. Run extraction first."` + button/link to trigger `POST /api/v1/jobs {"kind":"extract"}`.

---

### 3.1.1 Photo List Item (row/card in timeline)

**Data source:** one row from `stage1/main_timeline.csv`

| Element | Data key | Type | Notes |
|---|---|---|---|
| `photo_id` | `photo_id` | string | Hash-based ID, e.g. `1998_01_01__9714228198ba` |
| `date` | `date` | ISO8601 date | `YYYY-MM-DD` from filename |
| `sequence` | `same_date_sequence` | integer | 1, 2, 3… for photos taken same day |
| `pose_bin` | `pose_bin` | enum | `frontal`, `left_light`, `left_mid`, `left_deep`, `left_profile`, `right_light`, `right_mid`, `right_deep`, `right_profile` |
| `pitch` | `pitch` | float degrees | Head pitch angle |
| `yaw` | `yaw` | float degrees | Head yaw angle |
| `roll` | `roll` | float degrees | Head roll angle |
| `source_filename` | `source_filename` | string | Original filename |
| `date_provenance_status` | `date_provenance_status` | string | `filename_only`, `exif`, `conflict`… |
| `perceptual_dhash` | `perceptual_dhash` | string | 64-bit perceptual hash |
| `near_duplicate_of` | `near_duplicate_of` | string / empty | photo_id of near-duplicate, if any |
| `geometry_status` | `geometry_status` | string | `valid` / `invalid` / `partial` |
| `segmentation_status` | `segmentation_status` | string | `valid` / `invalid` / `partial` |
| `uv_status` | `uv_status` | string | `valid` / `invalid` / `partial` |
| `combined_visible_fraction` | `combined_visible_fraction` | float 0..1 | Fraction of face visible in image |
| `skin_mask_coverage` | `skin_mask_coverage` | float 0..1 | Fraction of face covered by skin mask |
| `uv_observed_coverage` | `uv_observed_coverage` | float 0..1 | Fraction of UV map with observed pixels |
| `chronology_index_global` | `chronology_index_global` | integer | Global rank by date |
| `chronology_index_in_pose` | `chronology_index_in_pose` | integer | Rank within pose bin |

**Interactions:**
- Click row → open Photo Detail view (3.2)
- Filter by `pose_bin`
- Sort by `date`, `chronology_index_global`, `pitch`, `yaw`, `roll`

---

### 3.2 Photo Detail

**Purpose:** deep dive into a single photo’s extracted data.

**Data source:** `stage1/<photo_id>/info.json` + artifact files in same directory

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `photo_id` | `info.photo_id` | string | |
| `date` | `info.date` | ISO8601 | |
| `pose_bin` | `info.chronology.pose_bin` | enum | |
| `angles` | `info.chronology.actual_pose` | [pitch, yaw, roll] | degrees |
| `alignment_quality` | `info.chronology.alignment_quality` | float 0..1 | Quality of chronology alignment |
| `expression_magnitude` | `info.chronology.expression_magnitude` | float | Degrees of expression |
| `smile_detected` | `info.chronology.smile_detected` | boolean | |
| `jaw_open_detected` | `info.chronology.jaw_open_detected` | boolean | |
| `face_area_ratio` | `info.chronology.face_area_ratio` | float 0..1 | |
| `visible_landmarks_106` | `info.chronology.visible_landmarks_106` | integer | |
| `visible_landmarks_134` | `info.chronology.visible_landmarks_134` | integer | |
| `reprojection_rmse` | `info.chronology.reprojection_rmse` | float | 3DDFA reprojection error |
| `corner_lift_ioc` | `info.chronology.corner_lift_ioc` | float | Indicator of corner lift |
| `landmarks_106` | `info.landmark_contract.ldm106` | array of [x,y,z] | Raw object-normalized |
| `landmarks_134` | `info.landmark_contract.ldm134` | array of [x,y,z] | Raw object-normalized |
| `visible_106` | `info.landmark_contract.visible_106` | array of bool | |
| `visible_134` | `info.landmark_contract.visible_134` | array of bool | |
| `skin_authenticity_score` | `info.skin_authenticity_score` | float 0..1 | |
| `skin_quality_score` | `info.skin_quality_score` | float 0..1 | |
| `texture_score` | `info.skin.texture.score` | float 0..1 | From texture.json |
| `texture_status` | `info.skin.texture.status` | string | `high` / `medium` / `low` |
| `camera` | `info.camera` | object | `{focal, principal_point, projection, render_size}` |
| `normalization` | `info.normalization` | object | `{center: [x,y,z], scale: float}` |
| `crop` | `info.crop` | object | `{bbox_original: [x,y,w,h], bbox_crop: [x,y,w,h]}` |
| `source_provenance` | `info.source_provenance` | object | `{source_filename, source_relative_path, source_url, archive_url, provenance_status}` |
| `perceptual_dhash` | `info.perceptual_dhash` | string | |
| `near_duplicate_of` | `info.near_duplicate_of` | string / empty | |

**Artifact URLs (served by API):**
- `face_mask.png` → `GET /api/v1/photos/{photo_id}/artifacts/face_mask.png`
- `uv_texture.png` → `GET /api/v1/photos/{photo_id}/artifacts/uv_texture.png`
- `original.jpg` → `GET /api/v1/photos/{photo_id}/image?kind=original`
- `thumb.jpg` → `GET /api/v1/photos/{photo_id}/image?kind=thumbnail`
- `face_crop.jpg` → `GET /api/v1/photos/{photo_id}/image?kind=face_crop`

**Empty state:** If `<photo_id>` directory missing, show `"Photo not found in Stage 1 output."`

---

### 3.3 Pair Analysis (Compare)

**Purpose:** side-by-side comparison of two photos with pairwise metrics.

**Data source:** `stage2/pair_metrics.csv` + `stage2/pair_details.json` + `stage2/artifact_index.json`

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `pair_id` | `pair_metrics.pair_id` | string | Composite: `photo_a__photo_b` |
| `photo_a` | `pair_metrics.photo_a` | string | photo_id |
| `photo_b` | `pair_metrics.photo_b` | string | photo_id |
| `date_a` | `pair_metrics.date_a` | ISO8601 date | |
| `date_b` | `pair_metrics.date_b` | ISO8601 date | |
| `pose_bin` | `pair_metrics.pose_bin` | enum | Shared pose bin |
| `status` | `pair_metrics.status` | string | `measured` / `skipped` / `error` |
| `qc_skip_reason` | `pair_metrics.qc_skip_reason` | string / empty | Why pair was skipped |
| `alignment_quality_a` | `pair_metrics.alignment_quality_a` | float 0..1 | |
| `alignment_quality_b` | `pair_metrics.alignment_quality_b` | float 0..1 | |
| `expression_gate_confidence` | `pair_metrics.expression_gate_confidence` | float | 0..1 confidence |
| `expression_gate_stratum` | `pair_metrics.expression_gate_stratum` | string | Stratum label |
| `quality_status_a` | `pair_metrics.quality_status_a` | string | `pass` / `limited` / `fail` |
| `quality_status_b` | `pair_metrics.quality_status_b` | string | `pass` / `limited` / `fail` |
| `quality_limited` | `pair_metrics.quality_limited` | boolean | |
| `visibility_gate_accepted106` | `pair_metrics.visibility_gate_accepted106` | boolean | |
| `visibility_gate_accepted134` | `pair_metrics.visibility_gate_accepted134` | boolean | |
| `pose_distance` | `pair_metrics.pose_distance` | float | Angular distance between poses |
| `pitch_gap_deg` | `pair_metrics.pitch_gap_deg` | float | |
| `yaw_gap_deg` | `pair_metrics.yaw_gap_deg` | float | |
| `roll_gap_deg` | `pair_metrics.roll_gap_deg` | float | |
| `primary_robust_z` | `pair_metrics.primary_robust_z` | float | Primary calibrated z-score |
| `primary_calibration_p95` | `pair_metrics.primary_calibration_p95` | float | P95 of calibration noise |
| `evidence_state` | `pair_metrics.evidence_state` | string | `measured` / `limited` / `unavailable` |
| `primary_zone_status` | `pair_metrics.primary_zone_status` | string | Zone-level status |
| `primary_zone_rmse` | `pair_metrics.primary_zone_rmse` | float | |
| `primary_zone_names` | `pair_metrics.primary_zone_names` | string (pipe-separated) | Zone names |
| `mesh_status` | `pair_metrics.mesh_status` | string | `complete` / `partial` / `unavailable` |
| `mesh_rmse` | `pair_metrics.mesh_rmse` | float | |
| `mesh_median` | `pair_metrics.mesh_median` | float | |
| `mesh_p95` | `pair_metrics.mesh_p95` | float | |
| `mesh_point_to_plane_rmse` | `pair_metrics.mesh_point_to_plane_rmse` | float | |
| `mesh_calibrated_metric_count` | `pair_metrics.mesh_calibrated_metric_count` | integer | |
| `mesh_calibrated_summary` | `pair_metrics.mesh_calibrated_summary` | string | Summary text |
| `texture_score_0_1` | `pair_metrics.texture_score_0_1` | float 0..1 | |
| `texture_conclusions_allowed` | `pair_metrics.texture_conclusions_allowed` | boolean | |
| `ldm106_rmse` | `pair_metrics.ldm106_rmse` | float | Landmark RMSE (106 points) |
| `ldm106_median` | `pair_metrics.ldm106_median` | float | |
| `ldm106_p95` | `pair_metrics.ldm106_p95` | float | |
| `ldm134_rmse` | `pair_metrics.ldm134_rmse` | float | Landmark RMSE (134 points) |
| `ldm134_median` | `pair_metrics.ldm134_median` | float | |
| `ldm134_p95` | `pair_metrics.ldm134_p95` | float | |
| `descriptor_significant_fraction` | `pair_metrics.descriptor_significant_fraction` | float 0..1 | |
| `descriptor_p95_z` | `pair_metrics.descriptor_p95_z` | float | |
| `cross_bin_corroboration_status` | `pair_metrics.cross_bin_corroboration_status` | string | `supported` / `limited` / `none` |
| `calibration_limited` | `pair_metrics.calibration_limited` | boolean | |
| `calibration_limitation_reason` | `pair_metrics.calibration_limitation_reason` | string / empty | |
| `pose_leakage_limited` | `pair_metrics.pose_leakage_limited` | boolean | |
| `coherent_motion_fraction` | `pair_metrics.coherent_motion_fraction` | float 0..1 | |
| `identity_only_motion_rmse` | `pair_metrics.identity_only_motion_rmse` | float | |
| `expression_influence` | `pair_metrics.expression_influence` | float | |
| `lead_overlap` | `pair_metrics.lead_overlap` | integer | Number of overlapping lead events |
| `lead_priority` | `pair_metrics.lead_priority` | string | `primary` / `secondary` / `none` |
| `lead_events` | `pair_metrics.lead_events` | string | Pipe-separated event IDs |
| `mt_significant_fdr10` | `pair_metrics.mt_significant_fdr10` | boolean | Multiple testing significant at FDR 10% |
| `mt_q_value` | `pair_metrics.mt_q_value` | float | Q-value |

**Artifact URLs (from `artifact_index.json` + API):**
- `mesh_file` → `GET /api/v1/run/artifacts/{name}`
- `motion_file` → `GET /api/v1/run/artifacts/{name}`

**Empty state:** If no pairs exist for selected photos, show `"No pairwise analysis available. Run Stage 2 first."`

---

### 3.4 Run Summary (Stage 2 Dashboard)

**Purpose:** aggregated statistics of the completed Stage 2 run.

**Data source:** `stage2/analysis_manifest.json` + `stage2/metric_catalog.json`

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `schema_version` | `analysis_manifest.schema_version` | string | |
| `status` | `analysis_manifest.status` | enum | `complete` / `partial` / `error` |
| `main_record_count` | `analysis_manifest.main_record_count` | integer | Photos in Stage 1 |
| `calibration_record_count` | `analysis_manifest.calibration_record_count` | integer | Calibration frames loaded |
| `pair_count` | `analysis_manifest.pair_count` | integer | Total pairs analyzed |
| `mesh_pair_count` | `analysis_manifest.mesh_pair_count` | integer | Pairs with mesh metrics |
| `point_motion_pair_count` | `analysis_manifest.point_motion_pair_count` | integer | Pairs with motion metrics |
| `texture_pair_count` | `analysis_manifest.texture_pair_count` | integer | Pairs with texture metrics |
| `quality_zone_pair_count` | `analysis_manifest.quality_zone_pair_count` | integer | Pairs with zone quality |
| `mesh_zone_count` | `analysis_manifest.mesh_zone_count` | integer | Total mesh zones measured |
| `texture_zone_metric_count` | `analysis_manifest.texture_zone_metric_count` | integer | Total texture zone metrics |
| `zone_measurement_count` | `analysis_manifest.zone_measurement_count` | integer | Total zone measurements |
| `expression_gate_summary` | `analysis_manifest.expression_gate_summary` | object | `{accepted, pairs}` |
| `pose_bins` | `analysis_manifest.pose_bins` | object | Bin → pair count |
| `anchor_policy_by_bin` | `analysis_manifest.anchor_policy_by_bin` | object | Per-bin alignment policy |
| `limitations` | `analysis_manifest.limitations` | array of strings | Known limitations |
| `elapsed_seconds` | `analysis_manifest.elapsed_seconds` | float | |
| `change_point_count` | `analysis_manifest.change_point_count` | integer | Detected change points |
| `manual_review_count` | `analysis_manifest.postprocess_summary.manual_review_count` | integer | Pairs flagged for review |
| `public_safety_status` | `analysis_manifest.postprocess_summary.public_safety_status` | string | `pass` / `review` / `fail` |
| `mesh_calibration_status` | `analysis_manifest.mesh_calibration_status` | string | |
| `calibration_sensitivity_status` | `analysis_manifest.calibration_sensitivity_status` | string | |
| `pose_leakage_status` | `analysis_manifest.pose_leakage_status` | string | |
| `lead_registry_status` | `analysis_manifest.lead_registry_status` | string | |
| `degraded_counts` | `analysis_manifest.postprocess_summary.degraded_counts` | object | Counts of degraded modules |

**Metric catalog (`metric_catalog.json`):**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `metric_name` | `metric_catalog.metrics[i].name` | string | |
| `family` | `metric_catalog.metrics[i].family` | string | `pair`, `mesh`, `texture`, `point_motion`, `zone`, `descriptor` |
| `status` | `metric_catalog.metrics[i].status` | string | `active`, `disabled_missing_data`, `degraded` |
| `pair_coverage_fraction` | `metric_catalog.metrics[i].pair_coverage_fraction` | float 0..1 | |
| `pair_value_count` | `metric_catalog.metrics[i].pair_value_count` | integer | |

---

### 3.5 Report (Stage 3)

**Purpose:** final forensic report with narrative, timelines, and change points.

**Data source:** `stage3/report_data.json`

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `schema_version` | `report_data.schema_version` | string | e.g. `deeputin-report-v1.0` |
| `summary` | `report_data.summary` | object | `{run_id, photo_count, pair_count, generated_at, status}` |
| `narrative` | `report_data.narrative` | array | List of narrative sections (text + metadata) |
| `timelines` | `report_data.timelines` | object | Per-bin timeline data |
| `change_points` | `report_data.change_points` | array | Detected change points with evidence |
| `lead_pairs` | `report_data.lead_pairs` | array | Lead pairs (currently empty if no prior) |
| `lead_registry` | `report_data.lead_registry` | object | Registry of lead events |
| `zones` | `report_data.zones` | array | Zone-level measurements (4256 entries) |
| `motion_maps` | `report_data.motion_maps` | array | Motion map data |
| `methodology` | `report_data.methodology` | object | Methodology description |
| `metric_catalog` | `report_data.metric_catalog` | object | Same structure as stage2 metric_catalog |
| `analysis_manifest` | `report_data.analysis_manifest` | object | Mirrors stage2 manifest |

**Empty state:** If `report_data.json` missing, show `"Stage 3 report not generated."` + link to trigger `POST /api/v1/jobs` or run `run_stage3.py`.

---

### 3.6 Upload / Ingestion

**Purpose:** upload new photos for future extraction runs.

**Data source:** API endpoint `POST /api/v1/photos/upload`

**Elements:**

| Element | Data key | Type | Notes |
|---|---|---|---|
| `photo_id` | response.photo_id | string | Generated hash-based ID |
| `date` | response.date | ISO8601 date / null | Parsed from filename |
| `stored` | response.stored | boolean | `true` if new file, `false` if duplicate |
| `message` | response.message | string | Human-readable status |

**Constraints:**
- Filename must match `YYYY_MM_DD[_N].jpg|.jpeg|.png`
- Max file size: 32 MiB (configurable via `DEEPUTIN_MAX_UPLOAD_MB`)
- Content must match image signature
- Image must decode successfully

---

## 4. Mock Data Requirements

All mock data MUST follow these rules:

1. **Exact schema match:** Every mock JSON/CSV must have the same keys and value types as real data.
2. **Same directory structure:** Mock `stage1/` must contain `<photo_id>/info.json` exactly like real output.
3. **Swappable via config:** The app must read `DEEPUTIN_MOCK_DATA_ROOT` env var. If set, load from mock; otherwise load from real paths.
4. **No hardcoded values:** Mock files must be loaded dynamically, not inlined in component code.
5. **Coverage:** Mock data must include at least:
   - 3 photos in `stage1/` with complete `info.json`, `main_timeline.csv`, `stage1_manifest.json`
   - 2 pairs in `stage2/pair_metrics.csv` with all 222 columns populated
   - 1 entry in `stage2/analysis_manifest.json`
   - 1 entry in `stage3/report_data.json`

**Directory layout for mock data:**
```
ui/mock/
  stage1/
    main_timeline.csv          # same columns as real
    stage1_manifest.json       # same keys as real
    <photo_id>/
      info.json                # same nested structure as real
      ldm106_raw.csv           # same format as real
      ldm134_raw.csv
      texture.json
      face_mask.png            # placeholder image
      uv_texture.png
  stage2/
    analysis_manifest.json     # same keys as real
    pair_metrics.csv           # same 222 columns as real
    pair_details.json          # same nested structure as real
    metric_catalog.json        # same structure as real
  stage3/
    report_data.json           # same nested structure as real
  api/
    photos.json                # mock API responses
    pairs.json
    health.json
```

---

## 5. API Contract Summary

Full contract in `API_CONTRACT.md`. Key endpoints:

| Method | Path | Returns | Data source |
|---|---|---|---|
| GET | `/api/v1/health` | `{status, stage1_ready, stage2_ready, stage3_ready, ...}` | Live status check |
| GET | `/api/v1/photos` | `{count, photos: [{id, date, bucket}]}` | `stage1/main_timeline.csv` |
| GET | `/api/v1/photos/{photo_id}` | Full photo record | `stage1/<photo_id>/info.json` |
| GET | `/api/v1/photos/{photo_id}/artifacts/{name}` | Binary / JSON | Artifact files in stage1 |
| GET | `/api/v1/photos/{photo_id}/image?kind=` | Image binary | Stage 1 saved images |
| POST | `/api/v1/photos/upload` | `{photo_id, date, stored, message}` | Upload handler |
| POST | `/api/v1/compare` | Pair metrics JSON | `stage2/pair_metrics.csv` |
| GET | `/api/v1/pairs/{a}/{b}/metrics` | Full 186+ column metrics | `stage2/pair_metrics.csv` |
| GET | `/api/v1/run/summary` | Stage 2 summary | `stage2/analysis_manifest.json` |
| GET | `/api/v1/report/summary` | Stage 3 summary | `stage3/report_data.json` |

---

## 6. Validation Rules

All data displayed in the UI must respect these rules:

1. **not_a_verdict:** Every API response and UI element must display `not_a_verdict: true`. The system provides measurements, not identity conclusions.
2. **source_mode:** Display `source_mode: research` for all real data.
3. **Empty states:** Never show blank screens. Always show explicit message + remediation action.
4. **Coordinate spaces:** Distinguish `raw_object_normalized`, `chronology_aligned`, `original_image_px`. Never mix them.
5. **Missing artifacts:** If `face_mask.png` missing, show placeholder with label `"Face mask not extracted"`. Same for all artifacts.
6. **Large datasets:** `pair_metrics.csv` has 222 columns and 5561 rows. UI must paginate / virtualize. Do not load entire file into browser memory at once.
7. **Dates:** All dates from filenames only (EXIF not read). Display provenance status explicitly.

---

## 7. Implementation Notes for Developers

1. **Data fetching:** Prefer API endpoints over direct filesystem reads. Direct filesystem access only for artifacts (images, OBJ).
2. **Caching:** Cache `main_timeline.csv` and `analysis_manifest.json` in memory; invalidate on mtime change.
3. **Mock mode:** Check `DEEPUTIN_MOCK_DATA_ROOT` at app startup. If set, intercept API calls and serve from mock directory.
4. **Type safety:** Use TypeScript interfaces derived from this spec. Every interface must match a real JSON schema.
5. **Error boundaries:** Wrap every data-dependent component in error boundary with explicit fallback UI.
6. **Performance:** `pair_metrics.csv` is 15 MB. Use streaming/parsing for table views. `pair_details.json` is 58 MB — load only requested pair.

---

## 8. Out of Scope (Explicitly Excluded)

- Identity verdicts or match percentages
- Medical diagnoses
- Automated decision-making
- Editing or modifying source data
- Real-time 3DDFA inference in browser
- User authentication / multi-user accounts
