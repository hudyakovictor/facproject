# Оценка проекта app7 и дизайн скрипта проверки

## Оценка по 10 категориям: 37/100

| # | Категория | Балл | Что есть | Чего нет |
|---|-----------|------|----------|----------|
| 1 | **Геометрия (3D)** | **82** | 3DDFA, 6 вариантов меша, vertices_identity_only, 106+134 ландмарки, visibility, canonical rotation | Зонная карта vertex→zone (костные/кожные зоны), детекция мимики |
| 2 | **Текстура кожи** | **78** | 24 признака × 60 зон, фотометрическая нормализация, GLCM/LBP/Gabor/FFT/Lab, между зональная вариативность | Сравнение между фото, адаптация под качество, возрастная нормализация |
| 3 | **Морщины** | **75** | Classical (Frangi+Meijering+Skan) + FFHQ (оригинал!), 14 зон W14 | Сравнение/матчинг паттернов, wrinkle signature |
| 4 | **Детекция синтетики** | **40** | 5 семей индикаторов (microtexture, homogeneity, spectral, specular, processing) | PAD-классификатор, пороги, LBP для силикона, specular analysis, albedo color |
| 5 | **Калибровка** | **15** | Pose-policy CSV, calibration photos через тот же пайплайн | CalibrationModel, PointNoiseModel, вычитание шума ракурса, baseline return |
| 6 | **Хронология** | **5** | Хронологический индекс в main_index.csv | Rate-of-change, alpha_chronology, детекция аномалий, возраст, baseline return |
| 7 | **Pose-forensics** | **55** | 9 бинов, canonical yaw, soft weights | Cross-bin corroboration, pose leakage diagnostic |
| 8 | **Мимика-робастность** | **20** | vertices_identity_only, alpha_id/exp | Детекция мимики, динамическое исключение зон, bone/skin взвешивание |
| 9 | **Сравнение пар** | **0** | — | Всё: landmark/mesh/texture comparison, SNR, z-scores, FDR, байесовский вывод |
| 10 | **Отчётность** | **0** | — | HTML, временная линия, тезисы, русский язык |

**Итого: 37/100** — Stage 1 крепкая основа, но без Stage 2/3 это склад данных без аналитика.

---

## Скрипт verify_same_person.py — что делает

**Цель:** проверить, достаточно ли данных Stage 1 для различения одного человека vs разных — **до написания Stage 2**.

### Запуск

```bash
# После Stage 1 на своих фото:
python app7/verify_same_person.py --output ./test_output
```

### Логика (только внутри бина ракурса, геометрия ≠ кожа)

**ГЕОМЕТРИЯ:**
1. `vertices_identity_only` (меш БЕЗ мимики) → Procrustes-выравнивание → per-vertex distance
2. Per-zone разложение: bone зоны (переносица, глазницы, скулы, подбородок, челюсть) vs skin зоны (щёки, губы)
3. `alpha_id` cosine similarity — вектор идентичности 3DDFA
4. Ландмарки (106 + 134) после canonical-yaw выравнивания

**КОЖА (уникальные особенности):**
1. 24 текстурных признака × 60 зон → cosine similarity по каждой зоне + по 5 группам:
   - **microtexture** (LBP, LoG, MAD) — поры, микрорельеф
   - **mesotexture** (GLCM) — паттерн текстуры
   - **orientation** (Gabor, coherence) — направленность складок
   - **spectral** (FFT) — частотный профиль кожи
   - **pigmentation** (Lab, chroma) — пигментация
2. Морщины: classical ridge correlation + FFHQ correlation + Bhattacharyya histogram
3. Локальные особенности (поры/шрамы): пространственное распределение + эксцентриситет

**ВЕРДИКТ** (отдельно геометрия, отдельно кожа):
- `SAME` / `LIKELY_SAME` / `BORDERLINE` / `LIKELY_DIFFERENT` / `DIFFERENT`

**ВЫВОД:**
- Per-pair детализация (ключевые метрики + per-zone breakdown)
- Distance matrix для каждого бина (для визуальной проверки кластеризации)
- JSON файл с полными результатами

### Что ожидать

**Тест 1 — один человек (твои фото):**
- bone_rms ≈ 0.010-0.025, alpha_id cosine > 0.90
- texture cosine > 0.80, microtexture/spectral > 0.70
- Все пары → SAME во всех бинах
- Distance matrix: однородная (один кластер)

**Тест 2 — + другой человек:**
- Межличностные пары: bone_rms > 0.04, alpha_id cosine < 0.80
- texture cosine < 0.60, microtexture/spectral < 0.45
- Distance matrix: видны 2 кластера
- Скрипт → CONTAINS DIFFERENT PEOPLE
