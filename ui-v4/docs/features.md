# UI v4.1 — added workflows

## Data Manager

- Clear extracted Stage 1/2/3 outputs through `POST /api/v1/data/clear`.
- Default source: `/Volumes/SDCARD/photo/main`.
- Limited extraction: user-selected `limit`.
- Full extraction: all supported files.
- Deterministic test extraction: five photos per year.
- Device selector, live job queue, progress, logs and cancellation.
- Destructive clear requires typing `ОЧИСТИТЬ`.

## Analysis settings

Typed controls for quality, confidence, smile, jaw-open, geometry and texture thresholds, heatmap stops and residual reference. Values are loaded and saved through `/api/v1/settings`; arbitrary JSON editing is not used.

The Settings page also uploads a real test photograph through `/api/v1/photos/upload` and opens its photo workbench by returned `photo_id`.

## Photo workbench

- Original image and face crop.
- `face_mask.png`.
- UV texture and zones overlay.
- `texture.json` tree.
- `info.json` tree.
- Full photo API payload.
- Interactive 3D BFM mesh using the real vertices and triangles from `/api/v1/photos/{id}/mesh`. Rotation and wheel zoom run without a third-party 3D dependency.

## Backend additions

The app6 API directly supports jobs, clearing, settings, upload, mesh, UV texture, standard photo images, and the following integrated routes:

1. an allowlisted route for `face_mask.png`, `texture.json`, and `info.json`;
2. deterministic per-year sampling for the five-photos-per-year test mode;
3. exact integration instructions.

No mock data or fallback measurements were introduced.
