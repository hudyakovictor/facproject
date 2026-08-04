# Iterations 05–11 — implementation status (2026-08-04)

This document describes what was implemented on top of ui-v4 (Iterations 01–04)
and what remains to reach 100% readiness for the main 1999–2026 dataset.

All new code was developed and tested against a **synthetic Stage 1 fixture**
that reproduces the exact artifact contracts of the real extraction
(`main_timeline.csv`, per-photo `info.json` / `reconstruction.npz` /
`ldm106_chronology.csv` / `uv_texture.png` / …). The fixture generator:
`backend/app6/scripts/make_synthetic_stage1.py`.

---

## Iteration 05 — Stage 2 Run Manager ✅ (done)

Backend: `backend/app6/api/run_manager.py` + endpoints in `server.py`.

- `GET /api/v1/runs` — list of runs; the legacy `<storage>/stage2` output is
  registered as a read-only `legacy` run and is never overwritten.
- `POST /api/v1/runs/preflight` — validates Stage 1 + calibration + profile,
  estimates adjacent/baseline pair counts per pose bin **before** starting.
- `POST /api/v1/runs/stage2` — creates `stage2/runs/run_YYYYMMDD_HHMMSS/`,
  freezes the profile selection (`selection_manifest.json`), runs
  `Stage2Engine` in a background thread with live `status.json` + logs,
  progress callback every 10 pairs.
- `POST /api/v1/runs/{id}/cancel` — cooperative cancellation via
  `threading.Event` checked in the engine pair loop.
- `POST /api/v1/runs/{id}/stage2b` — Stage 2B post-processing; output lives in
  `<storage>/stage2b/<run_id>/` (Stage2BConfig forbids output inside
  stage2_root). Refuses regeneration (no overwrite).
- `POST /api/v1/runs/{id}/archive` — moves finished runs to `stage2/archive/`.

Engine changes (minimal, backwards compatible):
- `Stage2Config` gains `selection_ids`, `cancel_event`, `progress_callback`.
- `load_main(stage1_root, selection_ids=None)` — selection-aware loading.
- Robustness fixes discovered while running the engine end-to-end:
  - `calibrated_score`: a metric with **no calibration reference and no
    matched-null values** used to crash the whole run with
    `ValueError: base_threshold must be positive`; now it returns an honest
    `insufficient_calibration` status (missing data is not shown as zero).
  - engine row: `primary_calibration_p95` / `primary_robust_z` tolerate `None`.
  - `model_hash` is `"missing"` when the BFM weights file is absent (CI-safe).

## Iteration 06 — Stage 3 Report Manager ✅ (done)

Backend: `backend/app6/api/report_manager.py` + endpoints in `server.py`.

- `GET /api/v1/reports` — list of reports (`stage3/reports/report_*/`), legacy
  Stage 3 output registered read-only.
- `POST /api/v1/reports` — generate a report from a **specific completed run**
  in modes `technical` / `internal` / `public`; writes `report_config.json`,
  engine outputs, and `exports/` (pairs.csv, exclusions.csv, provenance.csv,
  report.json, summary.json).
- Public mode runs a **public-safety lint** over every string in the report
  payload (affirmative uses of forbidden identity terms fail generation;
  negation/disclaimer contexts like «не доказывает маску» are allowed).
- `POST /api/v1/reports/{id}/regenerate` — re-renders from the linked run
  without re-running Stage 2.
- `GET /api/v1/reports/{id}/file/{name}` — HTML/JSON/CSV downloads
  (path-traversal safe). One run supports multiple reports.

## Iteration 07 — Timeline & LDM tracks ✅ (mostly done)

Frontend (`src/features/timeline/TimelineView.tsx`):

- **A/B selection mode** on the timeline (button or keys `A` / `B`): first
  click sets A, second sets B; then «⌖ Точки» opens the Landmark Comparison
  popup and «◈ Morphing» opens the Morphing popup for the pair.
- **Keyboard navigation**: ← / → move through photos, `Enter` opens landmark
  comparison for the selected pair, `Esc` clears A/B.
- **Jump-to-date** input in the header.
- **Batch pair endpoint** `POST /api/v1/pairs/batch` with a module-level cache
  replaced the per-pair `pair()` calls in the LDM shift track; the track now
  shows LDM106 and LDM134 displacement separately and uses **calibrated
  p95-based thresholds** from the active Stage 2 run when available
  (falls back to diagnostic thresholds).

Remaining (small): bookmarks, year/quarter/month/day zoom presets, q-value
tracks — all feasible on top of the current structure.

## Iteration 08 — Landmark Comparison widget ✅ (done)

`src/features/landmarks/LandmarkCompareWorkspace.tsx` — big modal popup:

- LDM 106 / LDM 134 models in **chronology-aligned** space (raw optional).
- Big 3D render (`src/shared/landmarkRenderer.ts`, orbit camera, wheel zoom).
- **Mini timeline strip** inside the widget: click = photo A, right-click =
  photo B, ‹A / B› step buttons.
- **Settings widget applies live** (no Save button): general displacement
  thresholds per model («LDM106 допустимо/подозрительно», «LDM134 …») — the
  two general values requested in the brief; calibrated p95 highlight;
  overlay / side-by-side / blink modes; displacement vectors; point labels;
  region filters (contour, brows, eyes, nose, mouth, cheeks, inner contour).
- Exceedance list: every point above tolerance with magnitude + calibrated p95.
- Backend: `GET /api/v1/landmarks/compare/{a}/{b}` returns per-point
  displacement + calibration reference from the active run's
  `point_noise_model.npz`.

## Iteration 09 — Morphing workspace ✅ (done)

`src/features/morphing/MorphingWorkspace.tsx` — big modal popup:

- Textured 3D morphing between **any two photos of the same pose bin** in the
  bin's canonical chronology pose (`vertices_chronology_aligned` from
  `reconstruction.npz`, shared BFM topology ⇒ interpolation is well-defined).
- Custom WebGL renderer (`src/shared/morphRenderer.ts`): two textures blended
  in the fragment shader, CPU-interpolated vertex positions, wireframe,
  landmark overlay, orbit camera with per-bin default viewing angle.
- **Settings widget applies live**: 9-pose selector, chronology / manual A–B
  mode, photo selects with dates, morph slider, wireframe/landmarks/spin
  toggles, camera reset.
- **Chronological sequence playback** (▶ Запуск): walks through all photos of
  the bin at adjustable speed with loop — lowest priority per the brief, but
  implemented.
- Explicit `visualization-only` notice; interpolated frames never reach Stage 2.
- Backend: `GET /api/v1/morphing/bins` (9 bins, chronology order, camera),
  `GET /api/v1/morphing/photo/{id}` (mesh+UV+texture URL, flat arrays).

## Iteration 10 — Calibration workspace ✅ (done)

`src/features/calibration/CalibrationPage.tsx` + backend
`calibration_workspace.py`:

- 7 persons × 9 bins coverage matrix, frame counts, same-person pair
  estimates, completeness.
- Calibrated thresholds per (pose bin, LDM count): median / MAD / p95 scalar +
  per-point arrays from the active Stage 2 run; LOPO sensitivity summary.
- Explicit **diagnostic vs calibrated** distinction (manual sliders are never
  labelled calibrated).

## Iteration 11 — Validation & tests ✅ (mostly done)

- Backend tests: `backend/app6/test_module/test_iteration5_11.py` — 14 tests:
  morphing contract (topology shared, chronology order), landmark compare
  (106/134, batch cap), calibration workspace, preflight, full run lifecycle
  (start → complete → stage2b → no-overwrite → calibrated thresholds →
  technical/public/internal reports → file downloads → regenerate), cancel,
  selection-aware preflight.
- Full suite: **117 passed**; 2 pre-existing failures unrelated to this work
  (`test_skin_zones.py` — the `skin_zone_atlas.json` asset was not shipped in
  this partial copy; the atlas is normative data that must not be invented).
- Frontend: `tsc --noEmit` clean, `vite build` clean.

---

## What remains for 100% readiness (real dataset)

1. **Run the full stack against `/Volumes/SDCARD/storage` + `/Volumes/SDCARD/calibration`**
   (macOS, with the 3DDFA weights and the real extraction):
   - `DEEPUTIN_STORAGE_ROOT=/Volumes/SDCARD/storage DEEPUTIN_CALIBRATION_ROOT=/Volumes/SDCARD/calibration`
   - First Stage 2 run on the real selection; then generate technical +
     public reports; check the report HTML visually.
2. **Register the existing `stage2_before_…` / legacy outputs** via the Run
   Manager (they are listed as read-only `legacy` runs automatically; archive
   them explicitly when ready).
3. **Perf check on full BFM meshes** (35 709 vertices): the morphing payload
   is ~3–4 MB JSON per photo (gzip-compressed by the middleware); if the
   workstation is slow, add a `?lod=` decimation option to the morphing
   endpoint.
4. **Frontend E2E / visual regression** (Playwright) and keyboard/a11y pass on
   the new modals; screenshots for the two workspaces.
5. **Restore the missing `skin_zone_atlas.json`** asset (out of scope of this
   session; the two failing tests will pass once it is present).
6. Optional: bookmarks and zoom presets on the timeline (Iteration 07 tail),
   q-value / pose-gap tracks, PDF export for reports.

## Iteration 12 — Event log panel ✅ (done)

Глобальная панель логирования: вкладки «Клиент» (живой журнал браузера) и
«Сервер» (append-only журнал API).

Backend (`app6/api/event_log.py`):
- `GET /api/v1/logs` — журнал (новые сверху), фильтры level/source/origin/since.
- `GET /api/v1/logs/summary` — счётчики по уровням/источникам.
- `POST /api/v1/logs/client` — приём событий из браузера (кап 100/запрос).
- `GET /api/v1/logs/export` — скачивание полного журнала `.jsonl`.
- Middleware пишет каждый HTTP-ответ ≥400 (warn), ≥500 (error); обработчик
  исключений пишет error со стеком; хуки в run_manager (старт/завершение/
  отмена/архив), report_manager (генерация, lint-fail), jobs (статусы).
- Журнал хранится в `<storage>/registry/logs/events.jsonl`, append-only,
  зеркалится в кольцевой буфер (2000) и переживает перезапуск сервера.

Frontend:
- `src/shared/logger.ts` — кольцевой буфер (1000), подписка, глобальный
  перехват `window.onerror` / `unhandledrejection`, debounced-отправка
  клиентских событий на сервер (без зацикливания при сбое отправки).
- `api.ts` — каждая неудачная API-выборка логируется автоматически
  (путь + статус + деталь).
- `src/features/logs/LogPanel.tsx` — slide-out панель: табы Клиент/Сервер,
  фильтры по уровню/источнику, поиск, раскрытие деталей и стеков, экспорт
  JSON, очистка локальных, скачивание серверного журнала, индикатор LIVE.
- Кнопка «⌑ Logs» в навигации с бейджем непрочитанных warn/error, хоткей
  Ctrl+Shift+L.

Тесты: 5 новых (журнал+middleware, client ingest+фильтры, summary, export,
капы/валидация) — всего 25 в test_iteration5_11.py.
