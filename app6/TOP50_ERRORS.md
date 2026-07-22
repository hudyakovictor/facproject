# DEEPUTIN app6 — ТОП-50 КРИТИЧЕСКИХ ОШИБОК И ПРОБЛЕМ
# Дата: 2026-07-22
# Приоритет: ВЛИЯЕТ НА ДАННЫЕ (требует переизвлечения) → ВЛИЯЕТ НА АНАЛИЗ → ВЛИЯЕТ НА ОТЧЁТ

---

## КАТЕГОРИИ

- **[DATA]** — Ошибка в извлечении данных. Требует переизвлечения (~5 часов).
- **[ANALYSIS]** — Ошибка в анализе. Данные OK, но анализ неверен.
- **[MISSING]** — Отсутствующий функционал, критичный для расследования.
- **[ARCH]** — Архитектурная проблема, создаёт риски в будущем.
- **[PERF]** — Производительность (не критично, но важно).

---

## ТОП-50 (по приоритету)

### 1. [DATA] Stage2 использует НЕВЕРНЫЕ ландмарки для хронологии
**Файл**: app6/stage2/loaders.py → app6/stage2/core.py → compare_landmarks
**Проблема**: Stage2 читает ldm134_aligned.csv (только yaw коррекция) вместо ldm134_chronology.csv (полная pitch+yaw+roll коррекция).
**Влияние**: ВСЕ хронологические сравнения загрязнены pitch/roll шумами. Результаты stage2/stage3 недостоверны.
**Исправление**: Изменить loader для чтения chronology CSVs.

### 2. [DATA] Нет валидации что chronology alignment убрал pitch/roll
**Файл**: app6/stage1/engine.py
**Проблема**: После применения compute_chronology_alignment не проверяется что результат действительно имеет целевую позу.
**Влияние**: Если баг в формуле коррекции — мы этого не узнаем.
**Исправление**: Добавить assert: после коррекции углы должны быть ≈ (0, canonical_yaw, 0).

### 3. [DATA] full_pose_correction_matrix — возможная инверсия направления
**Файл**: app6/stage1/geometry.py
**Проблема**: Формула R_corr = (R_target @ R_actual^T).T может иметь инверсию знака для некоторых комбинаций углов.
**Влияние**: Ландмарки могут быть повёрнуты в НЕВЕРНОМ направлении.
**Исправление**: Добавить unit-тест с известными углами и проверить результат.

### 4. [DATA] Нет сохранения residual pose после коррекции
**Файл**: app6/stage1/engine.py
**Проблема**: Не сохраняется "сколько градусов было скорректировано" для каждого фото.
**Влияние**: Невозможно отфильтровать фото с чрезмерной коррекцией (>15°).
**Исправление**: Добавить correction_magnitude_deg в chronology секцию info.json.

### 5. [DATA] vertices_chronology_aligned использует identity-only без проверки
**Файл**: app6/stage1/reconstruction.py
**Проблема**: compute_chronology_alignment применяется к vertices_identity_only, но не проверяется что identity модель достаточно точна.
**Влияние**: Если identity reconstruction неточна — chronology данные неточны.
**Исправление**: Добавить сравнение с expression-included версией в метаданные.

### 6. [MISSING] Нет фильтрации пар по pose delta в stage2
**Файл**: app6/stage2/core.py
**Проблема**: MAX_YAW_DELTA_PRIMARY = 12.0 проверяется в pose_delta_gate, но НЕ проверяется residual после коррекции.
**Влияние**: Пары с большой разницей в pitch/roll внутри бина всё ещё сравниваются.
**Исправление**: Добавить проверку residual_pitch < 5° AND residual_roll < 5°.

### 7. [DATA] Нет сохранения visible_landmarks_mask для каждого фото
**Файл**: app6/stage1/engine.py
**Проблема**: combined_visible сохраняется в NPZ, но не в удобном формате для stage2.
**Влияние**: Stage2 не знает какие ландмарки видимы для конкретного ракурса.
**Исправление**: Сохранить visible_landmarks_134_mask в chronology секцию.

### 8. [ANALYSIS] compare_landmarks не учитывает canonical pose при сравнении
**Файл**: app6/stage2/core.py
**Проблема**: Функция сравнивает координаты напрямую, но не учитывает что разные позы имеют разную "видимую" форму.
**Влияние**: Сравнение фронтального и профильного фото (если они в одном бине) будет некорректным.
**Исправление**: Добавить проверку что оба фото в одном pose bin.

### 9. [DATA] normalize_mesh использует RMS scale по всему мешу
**Файл**: app6/stage1/geometry.py
**Проблема**: RMS scale чувствителен к выбросам и может искажать пропорции.
**Влияние**: Разные фото могут иметь разный scale, что влияет на сравнение.
**Исправление**: Использовать анатомический anchor (межглазное расстояние) для scale.

### 10. [MISSING] Нет проверки качества 3DDFA реконструкции
**Файл**: app6/stage1/reconstruction.py
**Проблема**: Нет проверки что reprojection error в допустимых пределах.
**Влияние**: Фото с плохой реконструкцией (blur, occlusion) портят хронологию.
**Исправление**: Добавить порог reprojection_rmse < 5px и флаг low_quality_reconstruction.

### 11. [DATA] Нет сохранения expression magnitude
**Файл**: app6/stage1/reconstruction.py
**Проблема**: alpha_exp сохраняется, но нет скалярной метрики "насколько открыт рот/улыбка".
**Влияние**: Невозможно отфильтровать фото с сильной мимикой.
**Исправление**: Добавить expression_magnitude и jaw_open_degree в info.json.

### 12. [ANALYSIS] aligned_point_motion не учитывает canonical pose
**Файл**: app6/stage2/motion.py
**Проблема**: Движение точек вычисляется между "aligned" ландмарками, но не учитывает что разные позы имеют разную геометрию.
**Влияние**: Ложные "движения" из-за разницы в позе, а не реальные изменения.
**Исправление**: Использовать chronology-aligned ландмарки.

### 13. [DATA] ldm134_aligned.csv содержит только yaw-коррекцию (устаревший формат)
**Файл**: app6/stage1/engine.py
**Проблема**: Файл ldm134_aligned.csv создан для обратной совместимости, но вводит в заблуждение.
**Влияние**: Если stage2 случайно прочитает этот файл — результаты будут неверны.
**Исправление**: Переименовать в ldm134_yaw_only.csv или удалить.

### 14. [MISSING] Нет проверки что оба фото в паре из одного pose bin
**Файл**: app6/stage2/engine.py
**Проблема**: Группировка по pose_bin есть, но нет явной проверки что пара внутри бина.
**Влияние**: Возможны "кросс-бин" сравнения с некорректными результатами.
**Исправление**: Добавить assert в начале compare_landmarks.

### 15. [DATA] Нет сохранения "confidence" для каждого ландмарка
**Файл**: app6/stage1/engine.py
**Проблема**: ldm134_visible — бинарный флаг, но нет confidence score.
**Влияние**: Невозможно взвесить ландмарки по уверенности в stage2.
**Исправление**: Добавить landmark_confidence на основе projection + visibility.

### 16. [ANALYSIS] calibrated_score использует только RMSE, не учитывает зоны
**Файл**: app6/stage2/core.py
**Проблема**: Score сравнивает глобальный RMSE, но не учитывает что разные зоны имеют разную важность.
**Влияние**: Костные зоны (высокий приоритет) и мягкие ткани (низкий) взвешены одинаково.
**Исправление**: Добавить zone-weighted score.

### 17. [DATA] Нет проверки что canonical_yaw соответствует реальной позе
**Файл**: app6/stage1/geometry.py
**Проблема**: Если yaw = -24° (bin left_light, canonical -17.5°), коррекция 4.5° нормальна. Но если yaw = -9° (почти фронтальный), canonical -17.5° — коррекция 8.5° избыточна.
**Влияние**: Фото на границе бинов получают чрезмерную коррекцию.
**Исправление**: Использовать nearest-bin canonical, не жёсткий bin center.

### 18. [MISSING] Нет метрики "alignment quality" для каждого фото
**Файл**: app6/stage1/engine.py
**Проблема**: Нет скалярной метрики насколько хорошо выравнивание сработало.
**Влияние**: Невозможно отфильтровать фото с плохим alignment.
**Исправление**: Добавить alignment_quality_score (0-1) в info.json.

### 19. [DATA] vertices_chronology_aligned не сохраняется для ldm индексов отдельно
**Файл**: app6/stage1/engine.py
**Проблема**: ldm134_chronology_aligned в NPZ, но нет отдельного компактного файла только для ландмарков.
**Влияние**: Stage2 должен читать весь NPZ (35709 вершин) вместо 134 ландмарков.
**Исправление**: Сохранить chronology_landmarks.npz только с ldm106 + ldm134.

### 20. [ANALYSIS] expression_influence вычисляется неверно
**Файл**: app6/stage2/engine.py
**Проблема**: expression_influence = 1 - identity_rmse / full_rmse — но если full_rmse ≈ 0, деление на ноль.
**Влияние**: NaN в результатах, которые могут быть проигнорированы.
**Исправление**: Добавить epsilon к denominator.

### 21. [DATA] Нет сохранения "residual pose" после коррекции
**Файл**: app6/stage1/engine.py
**Проблема**: После compute_chronology_alignment не сохраняется какой остаточный pitch/roll остался.
**Влияние**: Невозможно верить что коррекция 完美.
**Исправление**: Вычислить и сохранить residual angles.

### 22. [MISSING] Нет проверки что фото не дублируется по содержимому
**Файл**: app6/stage1/engine.py
**Проблема**: Два фото с одинаковым содержимым (но разными именами) создадут разные папки.
**Влияние**: Дубликаты в хронологии могут создать ложные "stable" результаты.
**Исправление**: Добавить perceptual hash проверку.

### 23. [DATA] face_mask.npz содержит mask_original в original resolution
**Файл**: app6/stage1/assets.py
**Проблема**: mask_original может быть очень большим (например, 4000x3000).
**Влияние**: Размер файлов, медленное чтение.
**Исправление**: Сохранить в сжатом виде или только crop.

### 24. [ANALYSIS] texture_pair_deltas не учитывает pose difference
**Файл**: app6/stage2/texture_pair.py
**Проблема**: Текстурные сравнения чувствительны к ракурсу, но нет нормализации.
**Влияние**: Разные ракурсы → разные текстуры, даже для одного человека.
**Исправление**: Добавить pose-normalized texture comparison.

### 25. [DATA] Нет сохранения "pose confidence" от 3DDFA
**Файл**: app6/stage1/reconstruction.py
**Проблема**: 3DDFA может давать неточные углы для extreme poses.
**Влияние**: Фото с >50° yaw могут иметь неточный canonical_yaw.
**Исправление**: Добавить pose_confidence на основе yaw magnitude.

### 26. [MISSING] Нет проверки что фото в правильном бине
**Файл**: app6/stage1/geometry.py
**Проблема**: Если yaw = 9.9° (frontal bin), canonical = 0°. Но если yaw = -10.1° (left_light), canonical = -17.5°. Разница 20° для соседних фото.
**Влияние**: Резкий скачок alignment на границе бинов.
**Исправление**: Использовать soft bin assignment или nearest canonical.

### 27. [DATA] vertices_chronology_aligned не проверяется на выбросы
**Файл**: app6/stage1/reconstruction.py
**Проблема**: Если 3DDFA дала плохую реконструкцию, aligned вершины могут быть некорректны.
**Влияние**: Выбросы в хронологии.
**Исправление**: Добавить outlier detection на основе vertex displacement.

### 28. [ANALYSIS] apply_chronology_rate_flags не учитывает качество alignment
**Файл**: app6/stage2/chronology.py
**Проблема**: Rate flags применяются ко всем парам, даже с плохим alignment.
**Влияние**: Ложные "rapid change" флаги из-за плохого alignment.
**Исправление**: Фильтровать по alignment_quality > threshold.

### 29. [DATA] Нет сохранения "landmark stability score"
**Файл**: app6/stage1/engine.py
**Проблема**: Нет метрики насколько ландмарки стабильны между соседними кадрами.
**Влияние**: Невозможно отличить "реальное изменение" от "шум реконструкции".
**Исправление**: Добавить temporal consistency check.

### 30. [MISSING] Нет проверки что калибровочные фото одного человека
**Файл**: app6/stage2/calibration.py
**Проблема**: Calibration model предполагает что все калибровочные фото одного человека, но нет проверки.
**Влияние**: Если в калибровку попадёт другой человек — модель будет неверна.
**Исправление**: Добавить consistency check для калибровочного датасета.

### 31. [DATA] skin_zone_atlas_final.py — 40-зонный атлас НЕ ИНТЕГРИРОВАН
**Файл**: app6/stage1/skin_zone_atlas_final.py
**Проблема**: Есть продвинутый 40-зонный атлас, но он не используется в основном пайплайне.
**Влияние**: Дублирование функционала, путаница какой атлас "основной".
**Исправление**: Интегрировать или явно пометить как experimental.

### 32. [ANALYSIS] dense_mesh_pair не учитывает canonical pose
**Файл**: app6/stage2/mesh_dense.py
**Проблема**: Dense mesh comparison сравнивает вершины напрямую, без pose normalization.
**Влияние**: Некорректные mesh deltas для разных ракурсов.
**Исправление**: Использовать chronology-aligned вершины.

### 33. [DATA] Нет сохранения "per-vertex visibility" для хронологии
**Файл**: app6/stage1/engine.py
**Проблема**: combined_visible сохраняется, но нет per-vertex confidence.
**Влияние**: Stage2 не может взвесить вершины по видимости.
**Исправление**: Добавить vertex_visibility_confidence в chronology файл.

### 34. [MISSING] Нет проверки что фото не перевёрнуто (upside-down)
**Файл**: app6/stage1/engine.py
**Проблема**: Если фото случайно перевёрнутое, 3DDFA может дать некорректную реконструкцию.
**Влияние**: Неверная pose, неверный alignment.
**Исправление**: Добавить sanity check на основе face orientation.

### 35. [DATA] canonical_rotation сохраняется, но chronology_correction_matrix — нет
**Файл**: app6/stage1/engine.py
**Проблема**: В NPZ сохраняется canonical_rotation_row_matrix, но не chronology_correction_matrix.
**Влияние**: Невозможно воспроизвести alignment из сохранённых данных.
**Исправление**: Сохранять оба матрицы.

### 36. [ANALYSIS] apply_alpha_chronology не учитывает качество реконструкции
**Файл**: app6/stage2/alpha_chronology.py
**Проблема**: Alpha (shape) comparison чувствителен к качеству 3DDFA.
**Влияние**: Ложные alpha jumps из-за плохой реконструкции.
**Исправление**: Фильтровать по reprojection quality.

### 37. [DATA] Нет сохранения "face detection confidence"
**Файл**: app6/stage1/reconstruction.py
**Проблема**: RetinaFace может дать low-confidence detection, но это не сохраняется.
**Влияние**: Фото с плохим detection портят хронологию.
**Исправление**: Сохранить face_detection_score в info.json.

### 38. [MISSING] Нет проверки что все ландмарки в пределах изображения
**Файл**: app6/stage1/engine.py
**Проблема**: После to_original_image, ландмарки могут быть за пределами изображения.
**Влияние**: Некорректные координаты в CSV.
**Исправление**: Добавить clamp + flag для out-of-bounds landmarks.

### 39. [DATA] ldm134_chronology.csv не содержит confidence column
**Файл**: app6/stage1/engine.py
**Проблема**: CSV содержит только x, y, z, visible, vertex_index — но нет confidence.
**Влияние**: Stage2 не может взвесить ландмарки.
**Исправление**: Добавить confidence column.

### 40. [ANALYSIS] pose_leakage_diagnostic не учитывает новый alignment
**Файл**: app6/stage2/pose_leakage.py
**Проблема**: Диагностика pose leakage использует старый alignment.
**Влияние**: Неверная диагностика.
**Исправление**: Обновить для chronology alignment.

### 41. [DATA] Нет сохранения "image quality metrics" для хронологии
**Файл**: app6/stage1/assets.py
**Проблема**: technical_quality сохраняется, но не агрегируется в скаляр.
**Влияние**: Невозможно быстро отфильтровать низкокачественные фото.
**Исправление**: Добавить image_quality_score в info.json.

### 42. [MISSING] Нет проверки что фото не дублируется по SHA256
**Файл**: app6/stage1/engine.py
**Проблема**: Два одинаковых файла с разными именами создадут разные папки.
**Влияние**: Дубликаты в данных.
**Исправление**: Проверять SHA256 перед обработкой.

### 43. [DATA] vertices_chronology_aligned не проверяется на NaN/Inf
**Файл**: app6/stage1/reconstruction.py
**Проблема**: Если 3DDFA дала NaN, aligned вершины тоже будут NaN.
**Влияние**: NaN распространяется в stage2.
**Исправление**: Добавить assert np.isfinite(vertices_chronology_aligned).all().

### 44. [ANALYSIS] multiple_testing не учитывает качество пар
**Файл**: app6/stage2/multiple_testing.py
**Проблема**: FDR correction применяется ко всем парам одинаково.
**Влияние**: Пары с плохим alignment "разбавляют" значимые результаты.
**Исправление**: Weighted FDR by alignment quality.

### 45. [DATA] Нет сохранения "temporal context" (соседние фото)
**Файл**: app6/stage1/engine.py
**Проблема**: Stage1 обрабатывает фото изолированно, не зная о соседях.
**Влияние**: Невозможно сделать temporal smoothing на этапе извлечения.
**Исправление**: Добавить temporal_context в stage2.

### 46. [MISSING] Нет проверки что калибровочная модель стабильна
**Файл**: app6/stage2/calibration.py
**Проблема**: Нет cross-validation калибровочной модели.
**Влияние**: Overfitting на калибровочные данные.
**Исправление**: Добавить leave-one-out validation.

### 47. [DATA] face_mask может быть None при projection failure
**Файл**: app6/stage1/masks.py
**Проблема**: Если projection упал, mask = None, но это не всегда логируется.
**Влияние**: Фото без mask всё же сохраняется, но skin analysis не работает.
**Исправление**: Добавить explicit error handling.

### 48. [ANALYSIS] evidence_state не учитывает alignment quality
**Файл**: app6/stage2/evidence.py
**Проблема**: Evidence state основан на status, но не на качестве alignment.
**Влияние**: "Persistent geometric change" может быть артефактом alignment.
**Исправление**: Добавить alignment quality gate.

### 49. [DATA] Нет сохранения "processing timestamp" для каждого этапа
**Файл**: app6/stage1/engine.py
**Проблема**: Только один timestamp для всего фото.
**Влияние**: Невозможно профилировать узкие места.
**Исправление**: Добавить per-stage timing.

### 50. [MISSING] Нет "golden test" для проверки alignment
**Файл**: app6/stage1/tests/
**Проблема**: Нет unit-теста который проверяет что alignment работает корректно.
**Влияние**: Регрессии могут остаться незамеченными.
**Исправление**: Создать golden test с известными углами.

---

## СВОДКА ПО ПРИОРИТЕТАМ

### КРИТИЧНО (требует переизвлечения — ~5 часов):
1. Stage2 использует неверные ландмарки (#1)
2. Нет валидации alignment (#2)
3. Возможная инверсия направления (#3)
4. Нет фильтрации по pose delta (#6)
5. Нет проверки качества реконструкции (#10)
6. Нет сохранения expression magnitude (#11)
7. aligned_point_motion не учитывает canonical pose (#12)
8. Нет метрики alignment quality (#18)
9. Нет per-landmark confidence (#15)
10. Нет проверки на NaN/Inf (#43)

### ВАЖНО (влияет на анализ, но не на данные):
11. Нет zone-weighted score (#16)
12. Нет проверки что пара в одном бине (#14)
13. Нет pose-normalized texture comparison (#24)
14. Нет фильтрации по alignment quality (#28)
15. Нет consistency check для калибровки (#30)

### ЖЕЛАТЕЛЬНО (улучшения):
16. Интеграция 40-зонного атласа (#31)
17. Удаление дублирующего кода (#13)
18. Оптимизация размера файлов (#23)
19. Golden test для alignment (#50)
20. Per-stage timing (#49)

---

## РЕКОМЕНДАЦИИ

### Перед переизвлечением:
1. Исправить #1 (stage2 loader) — критично
2. Добавить #2 (валидация alignment) — критично
3. Протестировать #3 (unit-test для формулы) — критично
4. Добавить #10 (проверка качества) — критично
5. Добавить #43 (NaN check) — критично

### После переизвлечения:
6. Добавить #18 (alignment quality metric)
7. Добавить #15 (per-landmark confidence)
8. Исправить #16 (zone-weighted score)
9. Исправить #28 (фильтрация по quality)
10. Интегрировать #31 (40-зонный атлас)

---

## МЕТРИКИ ДЛЯ ВАЛИДАЦИИ

После переизвлечения проверить:
- Средний residual pitch/roll после коррекции < 2°
- Нет NaN/Inf в chronology файлах
- Все пары в одном pose bin
- Alignment quality > 0.8 для 95% фото
- Expression magnitude < 0.3 для фото используемых в хронологии
