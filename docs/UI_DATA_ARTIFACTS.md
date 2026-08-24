# DEEPUTIN UI — Data Artifacts Guide

## Problem

Stage 3 produces heavy files unsuitable for direct UI consumption:
- `report_data.json` — 57 MB
- `pair_details.json` — 58 MB  
- `pair_metrics.csv` — 15 MB

Loading these into browser memory is impossible. UI needs lightweight, purpose-built artifacts.

## Solution

Script `scripts/prepare_ui_data.py` generates UI-ready artifacts from Stage 1/2/3 outputs.

Run after each pipeline execution:
```bash
python3 scripts/prepare_ui_data.py
```

Output: `/Volumes/SDCARD/storage/ui_artifacts/`

## Generated Artifacts

| File | Size | Purpose | Source |
|------|------|---------|--------|
| `timeline_matrix.json` | 5.5 KB | Year × pose_bin matrix for Timeline Map | `stage1/main_timeline.csv` |
| `zone_summary.csv` | 896 KB | Pair-level zone aggregates (avg_rmse, max_rmse, zone_count) | `stage2/pair_details.json` |
| `pair_metrics_preview.csv` | 104 KB | First 500 pairs with key metrics only | `stage2/pair_metrics.csv` |
| `report_meta.json` | 1.3 KB | Report structure: sections, counters, limitations | `stage2/analysis_manifest.json` |
| `report_sections/summary.json` | 0.7 KB | Report summary section | `stage3/report_data.json` |
| `report_sections/narrative.json` | 1.9 KB | Narrative sections | `stage3/report_data.json` |
| `report_sections/timelines.json` | 549 KB | Timeline data per pose bin | `stage3/report_data.json` |
| `report_sections/change_points.json` | 259 KB | Detected change points | `stage3/report_data.json` |
| `report_sections/zones.json` | 3.7 MB | Zone-level measurements | `stage3/report_data.json` |
| `report_sections/motion_maps.json` | 1.4 MB | Motion map data | `stage3/report_data.json` |

## Stage 3 Actual Data Structure

`stage3/report_data.json` top-level keys:
```
analysis_manifest, change_points, lead_pairs, lead_registry, methodology,
metric_catalog, motion_maps, narrative, pairs, schema_version,
summary, timelines, zones
```

Each section in `report_sections/` contains only that section's data.

## Usage Pattern

1. **App startup** — load `report_meta.json` (1.3 KB) to build navigation
2. **Timeline page** — load `timeline_matrix.json` (5.5 KB) for heatmap
3. **Pair list** — load `pair_metrics_preview.csv` (104 KB) for table
4. **Pair detail** — load `zone_summary.csv` (896 KB) for aggregates, then fetch specific `pair_details.json` entry on demand
5. **Report** — load `report_meta.json`, then fetch only needed section from `report_sections/`

## Stage 3 Output Files

| File | Size | Description |
|------|------|-------------|
| `stage3/index.html` | 48.8 MB | Static HTML report (not for UI consumption) |
| `stage3/report_data.json` | 57 MB | Full report data (source for artifacts) |
| `stage3/report_validation.json` | 450 B | Validation status |

## Regeneration

After any pipeline re-run, execute:
```bash
python3 scripts/prepare_ui_data.py
```

This keeps UI artifacts in sync with backend results.
