# DEEPUTIN app7 — Stage 1 Справочник

## Запуск

```bash
# Базовый запуск (все фото из папки)
python app7/run_stage1.py --input /path/to/photos --output /path/to/results

# Только 1 фото (тест)
python app7/run_stage1.py --input /path/to/photos --output /path/to/results --limit 1

# Без превью (быстрее, меньше файлов)
python app7/run_stage1.py --input /path/to/photos --output /path/to/results --preview-level none

# Полные превью (для отладки)
python app7/run_stage1.py --input /path/to/photos --output /path/to/results --preview-level full

# Перезаписать уже обработанные фото
python app7/run_stage1.py --input /path/to/photos --output /path/to/results --overwrite
```

## Структура проекта

```
app7/
  run_stage1.py              ← Единый entry point
  stage1/
    config.py                ← Pose bins, настройки, preview_level
    naming.py                ← Парсинг YYYY_MM_DD, photo_id (БЕЗ SHA-256)
    geometry.py              ← Классификация позы, нормализация, трансформы
    reconstruction.py        ← 3DDFA_V3 обёртка (один вызов на фото)
    masks.py                 ← Skin mask из семантических каналов
    assets.py                ← Сохранение crop, UV, mesh, face_mask
    engine.py                ← Главный движок (оркестратор)
    input_provenance.py      ← Декодирование + EXIF ориентация
    storage.py               ← Атомарное создание директорий
    utils.py                 ← atomic_json, write_csv, хеши
    validator.py             ← Проверка полноты выходных данных
    skin/
      pipeline.py            ← Главный пайплайн кожи (всё в одном месте)
      atlas_registry.py      ← Загрузка BFM зон
      projection.py          ← Z-buffer растеризация + проекция атласа
      quality.py             ← Карты качества + применимость
      contamination.py       ← BiSeNet face parsing (волосы/очки)
      pose_policy.py         ← CSV-backed pose weights + soft evidence
      surface_geometry.py    ← Геодезические расстояния, tangent frames
      photometric.py         ← Фотометрическая нормализация
      patch_sampler.py       ← Сэмплирование патчей из зон
      contracts.py           ← Схемы, EvidenceState, PairStatus
      serialization.py       ← Atomic JSON/NPZ
      manifest.py            ← Создание/финализация манифеста
      previews.py            ← Превью (none|minimal|full)
      texture/
        basic.py             ← Макро-люминантность (3 метрики)
        features.py          ← 24 текстурных признака (LBP, GLCM, Gabor, FFT, Lab)
      wrinkles/
        classical.py         ← Frangi + Meijering + blackhat + Skan
        ffhq_adapter.py      ← FFHQ UNet (ПРИНИМАЕТ ОРИГИНАЛ, не маску!)
      local_features/
        detector.py          ← Noise-anchored локальные аномалии
      material/
        evidence.py          ← Экспериментальные индикаторы (не вердикт!)
      sensitivity/
        degradation.py       ← Бенчмарк чувствительности
```

## Ключевые исправления vs app6

| Проблема | app6 | app7 |
|----------|------|------|
| FFHQ вход | `np.where(seg, crop, 0)` — маскированное | `crop` — оригинальное |
| photo_id | `name__sha256[:12]` | `YYYY_MM_DD_suffix` |
| SHA-256 фото | Вычисляется для каждого файла | Убрано |
| Копия оригинала | `original.jpg` в output | Нет, путь в info.json |
| Превью | 9 файлов безусловно | 2 (minimal) / 7 (full) / 0 (none) |
| Skin скрипты | 5 отдельных run_skin_*.py | Интегрировано в stage1 |
| Фотометрия | Вычислялась, не использовалась | Применяется перед texture extraction |
| Backup файлы | 20 .backup_* в репо | Нет |
| Код | 12K строк | 3.5K строк |

## Выходные данные на одно фото

### Обязательные файлы (~15):
```
{photo_id}/
  info.json                 ← Все метаданные
  reconstruction.npz        ← 3D данные (вершины, нормали, α)
  ldm106_raw.csv            ← 106 точек: объектные координаты
  ldm106_aligned.csv        ← 106 точек: канонические координаты
  ldm134_raw.csv            ← 134 точки: объектные координаты
  ldm134_aligned.csv        ← 134 точки: канонические координаты
  face_crop.jpg             ← Кроп лица 424×500
  thumb.jpg                 ← Миниатюра 128×128
  face_mask.png             ← Визуальная маска (RGBA)
  face_mask.npz             ← Числовая маска
  uv_texture.png            ← UV текстура
  uv.npz                    ← UV данные + confidence
  mesh.obj + mesh.mtl       ← 3D модель
  validation.json           ← Результат валидации
  skin/                     ← Пакет кожных данных
    manifest.json           ← Манифест + SUCCESS
    surface_observations.npz
    atlas_projection.npz
    quality_maps.npz
    photometric_branches.npz
    analysis_mask.png
    quality.json
    features/basic_macro.npz
    features/texture.npz
    features/local_candidates.npz
    wrinkles/classical.npz
    wrinkles/ffhq.npz       ← Если веса доступны
    wrinkles/summary.json
    material/evidence.json
    sensitivity/degradation.json
    previews/               ← 0, 2 или 7 файлов в зависимости от --preview-level
```

## Требования к весам

На машине должны быть доступны:
- `assets/face_model.npy` — BFM модель
- `assets/net_recon.pth` — 3DDFA resnet50 веса
- `assets/large_base_net.pth` — детектор лиц
- `app7/atlas/texture_zones_bfm35709_v3.npz` — атлас зон
- `FFHQ-detect-face-wrinkles/res/cp/wrinkle_model.pth` — FFHQ морщины (опционально)
- `FFHQ-detect-face-wrinkles/res/cp/face_segmentation.pth` — BiSeNet (опционально)

Если FFHQ веса отсутствуют — skin-пакет создаётся, но wrinkle_ffhq.npz не генерируется.
