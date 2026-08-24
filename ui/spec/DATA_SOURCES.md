# DEEPUTIN UI — Data Sources Reference

This file maps every UI element to its exact source file and key path.

## Stage 1 Sources

| UI Element | Source File | Key Path | Format |
|---|---|---|---|
| `photo_id` | `stage1/main_timeline.csv` | `photo_id` | CSV column |
| `date` | `stage1/main_timeline.csv` | `date` | CSV column |
| `pose_bin` | `stage1/main_timeline.csv` | `pose_bin` | CSV column |
| `pitch/yaw/roll` | `stage1/main_timeline.csv` | `pitch`, `yaw`, `roll` | CSV columns |
| `geometry_status` | `stage1/main_timeline.csv` | `geometry_status` | CSV column |
| `alignment_quality` | `stage1/<photo_id>/info.json` | `chronology.alignment_quality` | JSON float |
| `expression_magnitude` | `stage1/<photo_id>/info.json` | `chronology.expression_magnitude` | JSON float |
| `smile_detected` | `stage1/<photo_id>/info.json` | `chronology.smile_detected` | JSON bool |
| `landmarks_106` | `stage1/<photo_id>/info.json` | `landmark_contract.ldm106` | JSON array |
| `landmarks_134` | `stage1/<photo_id>/info.json` | `landmark_contract.ldm134` | JSON array |
| `visible_106` | `stage1/<photo_id>/info.json` | `landmark_contract.visible_106` | JSON array |
| `visible_134` | `stage1/<photo_id>/info.json` | `landmark_contract.visible_134` | JSON array |
| `texture_score` | `stage1/<photo_id>/texture.json` | `quality.score` | JSON float |
| `skin_authenticity_score` | `stage1/<photo_id>/info.json` | `skin_authenticity_score` | JSON float |
| `face_mask.png` | `stage1/<photo_id>/face_mask.png` | file | PNG binary |
| `uv_texture.png` | `stage1/<photo_id>/uv_texture.png` | file | PNG binary |
| `original.jpg` | `stage1/<photo_id>/original.jpg` | file | JPEG binary |
| `manifest.status` | `stage1/stage1_manifest.json` | `status` | JSON string |
| `manifest.photo_count` | `stage1/stage1_manifest.json` | `success_count` | JSON int |
| `manifest.elapsed` | `stage1/stage1_manifest.json` | `elapsed_seconds` | JSON float |

## Stage 2 Sources

| UI Element | Source File | Key Path | Format |
|---|---|---|---|
| `pair_id` | `stage2/pair_metrics.csv` | `pair_id` | CSV column |
| `photo_a/b` | `stage2/pair_metrics.csv` | `photo_a`, `photo_b` | CSV columns |
| `status` | `stage2/pair_metrics.csv` | `status` | CSV column |
| `mesh_rmse` | `stage2/pair_metrics.csv` | `mesh_rmse` | CSV column |
| `mesh_median` | `stage2/pair_metrics.csv` | `mesh_median` | CSV column |
| `texture_score_0_1` | `stage2/pair_metrics.csv` | `texture_score_0_1` | CSV column |
| `primary_robust_z` | `stage2/pair_metrics.csv` | `primary_robust_z` | CSV column |
| `ldm106_rmse` | `stage2/pair_metrics.csv` | `ldm106_rmse` | CSV column |
| `ldm134_rmse` | `stage2/pair_metrics.csv` | `ldm134_rmse` | CSV column |
| `pair_count` | `stage2/analysis_manifest.json` | `pair_count` | JSON int |
| `pose_bins` | `stage2/analysis_manifest.json` | `pose_bins` | JSON object |
| `limitations` | `stage2/analysis_manifest.json` | `limitations` | JSON array |
| `change_points` | `stage2/change_points.json` | array | JSON array |
| `zones` | `stage2/pair_details.json` | `pairs[*].zones[*]` | JSON array |

## Stage 3 Sources

| UI Element | Source File | Key Path | Format |
|---|---|---|---|
| `summary.run_id` | `stage3/report_data.json` | `summary.run_id` | JSON string |
| `summary.status` | `stage3/report_data.json` | `summary.status` | JSON string |
| `narrative` | `stage3/report_data.json` | `narrative` | JSON array |
| `change_points` | `stage3/report_data.json` | `change_points` | JSON array |
| `timelines` | `stage3/report_data.json` | `timelines` | JSON object |
| `zones` | `stage3/report_data.json` | `zones` | JSON array |

## API Equivalents

Every file above is also accessible via API endpoints listed in `API_CONTRACT.md`.  
Prefer API reads over direct filesystem access in the UI. Direct filesystem access is only needed for binary artifacts (images, OBJ).

## Mock Data

Mock data lives in `ui/mock/` and mirrors the exact directory structure and file formats of real outputs.  
To enable mock mode, set:

```bash
export DEEPUTIN_MOCK_DATA_ROOT="/Users/victorkhudyakov/work/ui/mock"
```

The app should check this variable at startup and redirect all data reads to the mock tree.
