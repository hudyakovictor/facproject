# Архитектура UI: Calibration Studio + Comparison/Morph Lab

## 1. Scope

React-приложение обслуживает только:

- конфигурирование и same-day калибровку;
- тестовое сравнение фотографий любых людей;
- 3D/UV morphing;
- jobs/logs/settings.

Основной датасет обрабатывается headless и не открывается в UI.

## 2. Стек

Frontend:

- React + TypeScript + Vite;
- React Router;
- TanStack Query;
- Zustand;
- Three.js + React Three Fiber;
- WebGL/Canvas overlays;
- Vitest/Testing Library/Playwright.

Local backend:

- FastAPI/uvicorn;
- SQLite для sessions, draft configs, jobs и UI decisions;
- существующие `app6` и `uv_module` как Python services;
- SSE для progress/logs;
- localhost only и session token.

## 3. Routes

```text
/doctor
/calibration
/calibration/:id/coverage
/calibration/:id/workbench/:pose/:zone
/calibration/:id/report
/compare
/compare/:sessionId
/morph/:sessionId
/runs
/settings
```

Нет routes для main dataset timeline/reports.

## 4. Frontend modules

```text
src/features/
  system-doctor/
  calibration-import/
  pose-coverage/
  zone-calibration/
  config-editor/
  split-inspector/
  calibration-validation/
  comparison-session/
  pair-selector/
  geometry-compare/
  skin-compare/
  skan-compare/
  morph-studio/
  three-viewer/
  jobs/
  settings/
```

## 5. Backend services

- `SystemDoctorService`;
- `CalibrationRunService`;
- `DraftConfigService`;
- `PhotoProcessingService`;
- `PairSelectionService`;
- `GeometryComparisonService`;
- `SkinComparisonService`;
- `MorphPreparationService`;
- `JobManager`;
- `PreviewService`.

## 6. API

System:

- `GET /api/system/doctor`
- `POST /api/system/recheck`

Calibration:

- `POST /api/calibrations/scan`
- `GET /api/calibrations/{id}/coverage`
- `POST /api/calibrations/{id}/run`
- `GET /api/calibrations/{id}/zones/{pose}/{zone}`
- `PATCH /api/calibrations/{id}/draft-config`
- `POST /api/calibrations/{id}/preview`
- `GET /api/calibrations/{id}/config-diff`
- `POST /api/calibrations/{id}/validate`
- `POST /api/calibrations/{id}/freeze`
- `GET /api/calibrations/{id}/export`

Comparison:

- `POST /api/comparisons`
- `POST /api/comparisons/{id}/photos/a`
- `POST /api/comparisons/{id}/photos/b`
- `POST /api/comparisons/{id}/process`
- `GET /api/comparisons/{id}/pair-matrix`
- `GET /api/comparisons/{id}/pairs/{a}/{b}/geometry`
- `GET /api/comparisons/{id}/pairs/{a}/{b}/skin`
- `GET /api/comparisons/{id}/pairs/{a}/{b}/skan`

Morph:

- `POST /api/comparisons/{id}/morph/prepare`
- `GET /api/comparisons/{id}/morph/assets`
- `GET /api/comparisons/{id}/morph/mesh?t=...&mode=...`
- `GET /api/comparisons/{id}/morph/texture?t=...&mode=...`
- `POST /api/comparisons/{id}/morph/export`

Jobs:

- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/events`
- `POST /api/jobs/{id}/cancel|retry|resume`

## 7. Morph data contract

`MorphPair`:

```text
pair_id
photo_a_id / photo_b_id
topology_hash
vertex_count / triangle_count / uv_count
alignment_rotation / alignment_translation
mesh_a_identity / mesh_b_identity_aligned
mesh_a_expression / mesh_b_expression_aligned
uv_analytical_a / uv_analytical_b
uv_synthetic_a / uv_synthetic_b
observed_overlap_mask
region_vertex_weights
source hashes / model hash / config hash
```

Frontend получает базовые meshes A/B один раз и интерполирует vertices/normals в WebGL для real-time slider. Backend создаёт export artifacts и проверяет hashes.

Texture crossfade выполняется shader uniform. Analytical overlap использует mask и не заполняет дыры. Synthetic texture mode получает постоянный visual-only badge.

## 8. Geometry comparison

Backend:

1. загружает fixed-topology BFM meshes;
2. выбирает identity-only либо expression mesh;
3. Kabsch-aligns B→A без scale;
4. вычисляет per-vertex displacement;
5. агрегирует региональные показатели;
6. отдаёт typed arrays/GLB-friendly buffers.

Frontend только визуализирует, но не пересчитывает научные метрики.

## 9. Skin comparison

Backend сравнивает только common observed mask и одинаковые/сопоставимые pose-zones. Возвращает raw metrics, calibration-normalized metrics, quality limits, branch correspondences и layer previews.

## 10. Draft config preview

Изменение UI-параметра создаёт versioned draft config и запускает preview только на выбранной зоне/подмножестве. Ответ содержит:

- changed photos;
- status flips;
- metric deltas;
- false-anomaly impact;
- cache reuse;
- warnings/blockers;
- exact config diff.

Frozen profile не используется как mutable draft.

## 11. Storage

```text
ui_workspace/
  ui.sqlite
  calibrations/<id>/
  comparisons/<id>/
    source_links/
    stage1/
    pair_cache/
    morph_cache/
  jobs/<id>/
  exports/
```

Оригиналы не копируются без необходимости и не удаляются. Derived cleanup ограничен зарегистрированными workspace paths.

## 12. Производительность M1

- один 3DDFA worker по умолчанию;
- hash-aware resume;
- thumbnail/UV/mesh cache;
- pair metrics lazy on selection;
- morph slider полностью GPU-side после загрузки buffers;
- normals пересчитываются shader/worker path;
- LOD для mesh preview;
- не более двух активных 3D canvas;
- export animation выполняется отдельным cancellable job.

## 13. Тесты

Unit:

- config macros/diffs;
- synthetic analytical guard;
- morph interpolation;
- topology mismatch rejection;
- pair ranking;
- frozen profile immutability.

Component:

- pose board;
- zone workbench;
- pair matrix;
- geometry/skin panels;
- morph controls;
- visual-only badges.

E2E:

1. doctor;
2. calibration import;
3. edit draft config;
4. validate and freeze;
5. create comparison session;
6. upload two people;
7. process and select pair;
8. inspect geometry/skin/Skan;
9. morph identity-only geometry;
10. independently crossfade synthetic texture;
11. export morph frame.
