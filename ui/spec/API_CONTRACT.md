# DEEPUTIN Forensic Workstation — API Contract

## Base URL

```
http://localhost:8000/api/v1
```

All responses include:
```json
{
  "schema": "deeputin-api-v1.0",
  "source_mode": "research",
  "not_a_verdict": true
}
```

---

## Endpoints

### Health

**GET** `/health`

Response:
```json
{
  "status": "ok",
  "stage1_ready": true,
  "stage2_ready": true,
  "stage3_ready": true,
  "storage_root": "/Volumes/SDCARD/storage",
  "stage1_root": "/Volumes/SDCARD/storage/stage1",
  "stage2_root": "/Volumes/SDCARD/storage/stage2",
  "stage3_root": "/Volumes/SDCARD/storage/stage3",
  "photo_count": 1909,
  "pair_count": 5561
}
```

### Photos

**GET** `/photos?offset=0&limit=200&pose_bin=frontal`

Response:
```json
{
  "count": 1909,
  "offset": 0,
  "limit": 200,
  "photos": [
    {
      "id": "1998_01_01__9714228198ba",
      "date": "1998-01-01",
      "bucket": "left_light"
    }
  ]
}
```

**GET** `/photos/{photo_id}`

Response:
```json
{
  "id": "1998_01_01__9714228198ba",
  "date": "1998-01-01",
  "bucket": "left_light",
  "angles": {
    "pitch": 16.62,
    "yaw": -13.42,
    "roll": -6.57
  },
  "landmarks_106": [[x,y,z], ...],
  "landmarks_134": [[x,y,z], ...],
  "visible_134": [bool, ...],
  "full_mesh_available": true
}
```

**GET** `/photos/{photo_id}/artifacts/{name}`

Allowed names: `face_mask.png`, `texture.json`, `info.json`  
Returns binary (PNG) or JSON.

**GET** `/photos/{photo_id}/image?kind=original`

Allowed kinds: `original`, `thumbnail`, `face_crop`, `uv_texture`, `zones_overlay`  
Returns image binary.

**GET** `/photos/{photo_id}/landmarks/{count}/{space}`

- `count`: `106` or `134`
- `space`: `raw`, `aligned`, `original`

Response:
```json
{
  "schema": "deeputin-api-v1.0",
  "photo_id": "1998_01_01__9714228198ba",
  "count": 106,
  "space": "raw",
  "coordinate_space": "raw_object_normalized",
  "points": [[x,y,z], ...],
  "source_file": "ldm106_raw.csv"
}
```

### Compare

**POST** `/compare`

Request:
```json
{
  "photo_a": "1998_01_01__9714228198ba",
  "photo_b": "1999_01_11__db32bc4a4ce9"
}
```

Response: see `pair_metrics.csv` columns (186 active metrics).

**POST** `/compare/upload`

Upload photo for inline comparison (returns 501 without Stage 1).

**POST** `/compare/full_mesh`

Full BFM mesh comparison (35,709 vertices). Returns mesh deltas.

### Pair Metrics

**GET** `/pairs/{photo_a}/{photo_b}/metrics`

Returns all 222 columns from `pair_metrics.csv` for the pair.

### Run Summary

**GET** `/run/summary`

Returns `analysis_manifest.json` top-level keys.

**GET** `/run/artifacts/{name}`

Returns artifact from `artifact_index.json` allowlist.

**GET** `/run/keys/{name}`

Backward-compatible alias for `/run/artifacts/{name}`.

### Report (Stage 3)

**GET** `/report/summary`

Returns Stage 3 report summary (counters, narrative, sections).

**GET** `/report/sections/{name}?offset=0&limit=100`

Returns one paginated section from `report_data.json`.

### Calibration

**GET** `/calibration/health`

Returns calibration dataset health.

**GET** `/calibration/match?photo_id=...&yaw=...&pitch=...&roll=...&pose_bin=...&limit=5`

Returns matching calibration frames.

**POST** `/calibration/subtract_noise`

Request:
```json
{
  "photo_a": "...",
  "photo_b": "...",
  "tolerance": {"yaw": 5.0, "pitch": 5.0, "roll": 5.0}
}
```

Returns compensated vs uncompensated metrics.

**GET** `/calibration/noise_model?yaw=...&pitch=...&roll=...&sample=40`

Returns noise model state and coverage.

### Upload

**POST** `/photos/upload`

Request: `multipart/form-data` with image file.  
Filename must match `YYYY_MM_DD[_N].ext`.  
Max size: 32 MiB.

Response:
```json
{
  "schema": "deeputin-api-v1.0",
  "photo_id": "1998_01_01__9714228198ba",
  "date": "1998-01-01",
  "stored": true,
  "message": "saved to /path/to/file.jpg"
}
```

### Jobs

**POST** `/jobs`

Request:
```json
{
  "kind": "extract",
  "input_dir": "/path/to/photos",
  "output_dir": "/path/to/output",
  "device": "cpu",
  "limit": 0
}
```

Supported kinds: `extract`, `recompute_metrics`

**GET** `/jobs`

**GET** `/jobs/{job_id}`

**POST** `/jobs/{job_id}/cancel`

### System

**GET** `/system/health`

Returns system health info.

**GET** `/settings`

**POST** `/settings`

### Review

**POST** `/reviews`

Request: payload dict. Appends review record.

---

## Error Format

All errors return:
```json
{
  "detail": "Human-readable error message"
}
```

Status codes:
- `400` — bad request (invalid filename, unknown kind)
- `401` — unauthorized (not used currently)
- `403` — forbidden
- `404` — not found (photo, artifact, stage output)
- `409` — conflict (stage not ready, storage misconfigured)
- `413` — payload too large (upload exceeds limit)
- `422` — validation error (invalid data format)
- `500` — internal server error
- `501` — not implemented (inline extraction from upload)
- `503` — service unavailable (BFM geometry missing)

---

## Pagination

- `offset` / `limit` query params for list endpoints.
- Default `limit`: 200, max: 1000.
- Use `limit=0` for unlimited (backend only, never expose in UI).
