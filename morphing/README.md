# 🎭 3D Face Morphing Studio

Веб-инструмент для канонического 3D-морфинга лица на базе `app8`, Three.js и
`uv_module`. Текущая версия поддерживает не только A → B, но и timeline на
2–4 keyframe, одновременный barycentric blend, количественные метрики,
зональный forensic-разбор, UV Diff и запись видео из WebGL canvas.

> **Ограничение интерпретации.** `Morphability`, forensic score, симметрия и
> temporal drift — описательные геометрические индикаторы. Это не
> калиброванная вероятность личности, медицинское заключение или доказательство
> идентичности. Для forensic-вывода нужен отдельный валидированный reference
> dataset и контроль качества входных снимков.

## Что добавлено

### Smooth deformation

- `POST /api/morph-pair` принимает optional `deformation=linear|tps`.
- `tps` строит 3D polyharmonic thin-plate displacement field по 106
  canonical landmarks, применяет его chunked к dense mesh и возвращает
  `metadata.deformation` с landmark RMSE и displacement diagnostics.
- Linear correspondence остаётся default. TPS — диагностический smooth режим;
  полноценный ARAP solver намеренно не имитируется без mesh optimizer.

### Multi-face timeline и blend

- `POST /api/morph-sequence` принимает 2–4 файла в поле `photos` и optional
  JSON `metadata` с `label`/`year`.
- Вектор формы интерполируется Catmull–Rom spline, проходящей через каждый
  keyframe. Boundary control points дублируются, поэтому A и D не
  overshoot-ятся.
- На фронтенде режим **Barycentric blend** даёт 3 слайдера для треугольника и
  4 для тетраэдра. Веса нормализуются к `Σw = 1` и применяются GPU-шэйдером.
- При наличии годов API дополнительно отдаёт `metadata.temporal_drift`: скорость
  dense-shape drift, скорость по зонам и отклонения от линейной траектории.
  Годы также становятся неравномерными `timeline.keyframe_times`, поэтому 10-летний
  интервал получает больше времени spline, чем 1-летний.
- В Timeline можно указать будущий год. API выполнит bounded polynomial
  extrapolation по dense mesh (максимальный горизонт — 50 лет) и вернёт
  `extrapolation.vertices`; UI позволяет переключиться на режим
  `Last observed → Forecast`. Это what-if projection, а не валидированное
  предсказание внешности.

### Экспорт и диагностические слои

- Кнопка **MP4 / WebM** записывает ровно 60 кадров через
  `canvas.captureStream(60)` + `MediaRecorder`. Браузер выбирает MP4, если его
  кодек доступен, иначе безопасно скачивается VP9/VP8 WebM.
- Live metrics пересчитываются на каждом tick: mean/max delta, p95,
  `% vertices > threshold`, cosine similarity и distance до финального
  keyframe.
- `POST /api/similarity` возвращает полный Euclidean L2, mean/max/p95,
  cosine similarity, Morphability и top-5 зон расхождения.
- `POST /api/forensic-score` возвращает взвешенный зональный score и объяснение
  (какие зоны поддерживают/снижают сходство). Используются явные веса зон,
  результат помечен как geometric similarity proxy; совместимое поле
  `probability_same_person` намеренно возвращает `null`, score не калиброван как вероятность.
- `POST /api/uv-diff` и слой **UV Diff** показывают нормализованную разницу
  двух UV-текстур независимо от геометрии.
- `GET /api/parameter-registry` отдаёт реестр Stage 2 v2; в ответе pair также
  есть групповой heatmap 83 параметров с provenance-меткой
  `dense-mesh mean delta proxy`. Это намеренно не выдаётся за измерение
  порогов Stage 2.
- `POST /api/symmetry` оценивает bilateral symmetry canonical mesh с разбором по
  зонам.
- Quality gates оценивают resolution, sharpness, contrast, exposure, clipping,
  entropy, mesh finite vertices, invalid/degenerate faces и topology edge counts.
  Замечания показываются в UI; эти heuristic checks не оценивают качество
  реконструкции как ground-truth.
- `POST /api/similarity-matrix` принимает 2–16 лиц и строит парные distance,
  cosine и zonal matrices с геометрическим outlier ranking.
- Batch diagnostics включают deterministic bootstrap intervals по зонам и
  real-year displacement rates. Интервалы descriptive: vertex resampling не
  моделирует spatial dependence и не является population confidence interval.
- `GET /api/quality-schema` публикует quality gates.
- `POST /api/report-pair?format=json|html` собирает reproducible report packet
  с metrics, image/mesh quality, symmetry, input SHA-256 hashes, provenance и
  limitations. UI умеет скачать оба формата; HTML экранирует untrusted labels.

## Структура

```text
morphing/
├── backend/
│   ├── server.py       # FastAPI: pair, sequence, similarity, forensic, UV, symmetry
│   ├── analysis.py     # детерминированные метрики и diagnostic helpers
│   ├── timeline.py     # Catmull–Rom / normalized multi-face blend
│   ├── deformation.py  # optional smooth TPS deformation
│   ├── extrapolation.py # dated polynomial shape projection
│   ├── regions.py      # anatomical region registry and aggregation
│   ├── quality.py      # image/mesh quality gates
│   ├── reporting.py    # JSON/HTML evidence packet
│   ├── batch.py        # pair matrices, peer ranking, descriptive bootstrap
│   ├── tests/          # unittest coverage for math, quality, batch and reports
│   ├── aligner.py      # каноническое выравнивание
│   └── uv_extractor.py # HD UV через uv_module
├── frontend/
│   ├── src/App.jsx
│   ├── src/components/FaceSpacePlot.jsx
│   ├── src/components/TimelineUploader.jsx
│   ├── src/components/Canvas3D.jsx
│   ├── src/components/Controls.jsx
│   └── src/utils/timeline.js
└── run.sh
```

## Запуск

```bash
cd facproject/morphing
./run.sh
```

Или вручную:

```bash
cd facproject
python3 -m uvicorn morphing.backend.server:app --host 0.0.0.0 --port 8000
cd morphing/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

Vite проксирует `/api` на backend, поэтому браузер не обращается к
`localhost` напрямую. Для preview-сред Arena оба сервера слушают
`0.0.0.0`.

## API-контракт

| Endpoint | Назначение |
|---|---|
| `GET /api/health` | health/version |
| `GET /api/parameter-registry` | Stage 2 v2 registry |
| `POST /api/morph-pair` | A/B mesh, UV, metrics, forensic sidecar; optional `deformation=linear|tps` |
| `POST /api/morph-sequence` | 2–4 keyframe Catmull–Rom timeline; optional `future_year` forecast |
| `POST /api/morph-multi` | alias for multi-face timeline |
| `POST /api/morph-blend` | normalized barycentric mesh blend |
| `POST /api/face-space` | PCA 3D scatter coordinates and ordered path |
| `POST /api/similarity` | dense quantitative similarity |
| `POST /api/similarity-matrix` | 2–16 face distance/cosine/regional matrix |
| `POST /api/forensic-score` | weighted zone similarity proxy |
| `POST /api/uv-diff` | normalized UV difference texture |
| `POST /api/symmetry` | bilateral symmetry diagnostic |
| `GET /api/quality-schema` | quality-gate registry |
| `POST /api/report-pair?format=json|html` | reproducible analysis report |
| `POST /api/export-gif` | legacy HD GIF export |

Backend unit tests (не загружают реконструкционную GPU-модель) запускаются из корня:

```bash
python3 -m unittest discover -s morphing/backend/tests -v
```

`morph-pair` сохраняет старые поля `vertices_a`, `vertices_b`,
`landmarks_106_a/b`, `texture_a_base64`, `texture_b_base64`, поэтому старые
клиенты остаются совместимыми. Новые клиенты могут использовать
`sequence_vertices`, `sequence_landmarks` и `sequence_textures` для 2–4 точек.
