# Итерация 03 — Quality filters + pose-outlier selection

## Статус

Завершено на 100% в рамках утверждённого плана.

## Цель

Интерактивная очистка выборки после Stage 1 **без** изменения evidence-файлов и **без** запуска Stage 2.

## Реализовано

### Backend enrichment
- `stage1_timeline.py` v1.1 читает `main_timeline.csv` + per-photo `info.json`
- Метрики: visibility, confidence, face resolution, blur (laplacian), exposure/skin cover, occlusion, reconstruction residual, alignment quality, landmark visibility, texture applicability, expression/jaw/smile
- Boolean: smile_detected, jaw_open_detected, date conflict, near duplicate, source chain

### Selection engine
- `selection_filters.py`
- Quality min–max ranges с enable/disable
- Histograms per metric
- Pose-outlier per bin: median/MAD robust distance, master percentile slider, independent yaw/pitch/roll limits
- Boolean gates
- Manual include/exclude
- Deterministic decisions + reason codes per photo
- `selection_manifest.json` пишется только в `storage/profiles/current/` (Stage 1 immutable)

### API
- `GET /api/v1/selection/defaults`
- `GET /api/v1/selection/pose-stats`
- `POST /api/v1/selection/evaluate`
- `POST /api/v1/selection/save`

Gates: `mutates_stage1=false`, `starts_stage2=false`.

### UI
- Кнопка **Фильтры** на timeline
- Панель: quality sliders + histograms, pose outlier, boolean gates, reason counts, live included/excluded
- Timeline показывает только included photos; footer: `included/total`
- Save selection manifest

## Проверка

```bash
cd backend
PYTHONPATH=. python3 -m unittest \\
  app6.test_module.test_iteration1_runtime_inventory \\
  app6.test_module.test_iteration2_dataset_timeline \\
  app6.test_module.test_iteration3_selection_filters -v
cd .. && npm run typecheck
```

## Acceptance (gate)

- [x] Фильтрация не запускает Stage 2
- [x] Фильтры не удаляют/не переписывают Stage 1
- [x] У каждого excluded photo есть reason code
- [x] Повтор тех же параметров даёт ту же выборку
- [x] Pose-outlier считается внутри каждого bin
- [x] Tests 6/6 IT-3 + regression IT-1/2
- [x] TypeScript typecheck PASS
