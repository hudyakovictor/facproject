# DEEPUTIN app6 — АУДИТ-2: 30 дополнительных анализов кода относительно патчей PR
Дата: 2026-07-22 · Ветка: `arena/019f89cd-facproject` · Методы: AST, symtable, контрактные diff, ручная верификация

Легенда: ✅ чисто · ⚠️ замечание/открытый пункт · 🐛 дефект (исправлен → ✅FIXED · не исправлен → 🐛)

---

## Блок A. Имена, импорты, логирование

### A1. Неиспользуемые импорты (AST-скан) — ⚠️
144 случая. Ядро — патч 25, добавивший `import log_status, log_blocker, log_warning` в ~57 файлов: `log_blocker` используется почти нигде, `log_warning` редко. Также `json`, `shutil` в stage1/engine.py, `ReconstructionBundle`, re-export в `__init__.py`. Влияния на рантайм нет — гигиенический долг.

### A2. Несвязанные свободные имена (symtable) — ✅ после ручной выверки
133 кандидата — все ложные (переменные comprehension/lambda-скоупов: `z`, `f`, `a`, `lab`...). Ручная проверка подозрительных (`log_status` в skin/projection.py — импортирован корректно) подтвердила отсутствие реальных несвязанных имён после фиксов сессии 1.

### A3. log_status до docstring — ⚠️ системный артефакт патчей 24/25
~43 функции: вызов `log_status(...)` вставлен ПЕРЕД docstring → docstring перестаёт быть `__doc__` (ломает help(), IDE-подсказки, sphinx). Файлы: geometry (7), engine, reconstruction, assets, storage, stage2 core/loaders/motion и др. Лечится перемещением вызова после docstring (не делалось — меняет появление логов; оставлено как дизайн-решение автора PR, но задокументировано).

### A4. Метка log_status vs имя функции — ✅ 0 расхождений
Во всех `log_status("label", ...)` метка совпадает с именем объемлющей функции.

### A5. in_progress без complete — ⚠️ 6 функций
`nearest_canonical_yaw`, `to_original_image`, `rasterize_surface`, `apply_chronology_rate_flags`, `texture_pair_deltas`, `uv_geometry_pair` логируют только `in_progress` (часто с пояснением «Not integrated») — по семантике STATUS_FLOW навсегда остаются «жёлтыми». Частично осознанно (need_testing).

### A6. Словарь статусов vs STATUS_FLOW — ⚠️ 1 отклонение
`quality_zones.py:185` использует статус `'deprecated'`, отсутствующий в `STATUS_FLOW`/`ALWAYS_SHOW` статус-системы.

### A7. Локальные импорты — 🐛→✅FIXED (2 бага), ⚠️ 62 всего
- `stage2/engine.py:137` и `stage2/texture_image.py:355`: локальный `from .status_logger import status_warning` → **app6.stage2.status_logger не существует → ImportError при вызове** (притом срабатывал ровно в warning-ветке). Удалены (module-level импорты уже добавлены в сессии 1). Также удалены redundant-локальные импорты в stage1 engine/reconstruction. Остальные 58 — осознанная ленивая загрузка (torch, nvdiffrast, skan, scipy).

### A8. Неиспользуемые локальные переменные — ⚠️ 28
Включая патч-резидуумы: `ldm134_original` (engine._one), `lo`/`hi` (nearest_canonical_yaw), `uv_beauty`/`confidence_u8` (assets.save_uv_and_mesh), `rng` (skin sensitivity), `aligned_fit` (mesh_dense), `pose_bin` (stage2.run), `rows` (package_calibration) и др.

---

## Блок B. Контракты данных

### B1. reconstruction.npz: записанные ключи vs NPZ_REQUIRED валидатора — ✅
Записывается 43 статических ключа + ldm/uv динамика; валидатор покрывает все, включая `vertices_chronology_aligned`, `chronology_correction_matrix`, `chronology_target_pose`, `vertex_visibility_confidence`.

### B2. info.json chronology-блок vs читатели stage2 — ✅
Пишется 28 ключей; stage2 читает `alignment_quality`, `expression_magnitude` (есть), также `jaw_open_degree`, `pose_confidence`, `detection_confidence` доступны. Подмножество ⊂ множества — дрейфа нет.

### B3. Потребители ldm*_chronology.csv — ⚠️
stage2/loaders читает chronology-массивы из **reconstruction.npz** (`ldm106/134_chronology_aligned`), а CSV-файлы — только внешний артефакт для ручного анализа. Осознанно, но стоит отметить: CSV и npz должны оставаться синхронными (валидатор B1 это гарантирует: сверяет CSV против npz ✓).

### B4. vertices_chronology_aligned — потребители — ⚠️
Меш-уровневый массив пишется и валидируется, но stage2 его не потребляет (только ландмарки). Либо задел на будущее, либо мёртвый объём (53268 float = ~213 КБ на фото).

### B5. files{} реестр vs фактические записи — ✅/⚠️
Все write_csv/atomic_json/np.savez отражены в `files`; `info.json` пишется через atomic_json, его собственный ключ в реестре отсутствует (нормально). Единственное замечание: `alignment_csv_106/134` — путь внутри chronology-блока, не верхнеуровневый files-ключ (форма API не описана в CONVENTIONS).

### B6. Схема CSV ландмарков (+`confidence` патча 05) vs читатели — ✅
Писатель добавил колонку `confidence`; все читатели используют `csv.DictReader`/pandas (доступ по имени) — обратная совместимость не сломана.

### B7. DEPRECATED ldm*_aligned.csv — ✅
stage2 не содержит читателей `ldm106/134_aligned.csv` (помечены DEPRECATED, yaw-only), только writer (engine), validator и тест-фикстура. Депрекация согласованная.

### B8. POSE_BINS: config vs geometry vs golden-тест — ✅
9 бинов, canonical yaw [0, ±17.5, ±32.5, ±45, ±70] совпадают в `config.POSE_BINS`, `classify_pose`, `nearest_canonical_yaw`, `test_alignment_golden` (включая исправленное `(40, 45.0)`).

### B9. Динамические shape-проверки landmark/uv массивов — ✅
Валидатор динамически масштабирует `(MESH_COUNT,3)` под реальный mesh_count фото — расхождений с writer нет.

### B10. Контракт STATUS_AUDIT vs фактические log_status-метки — ✅
Все уникальные метки из кода покрываются реестром аудита (проверка совпадения множеств имён).

---

## Блок C. Поведенческая проводка исправлений TOP50

### C1. NaN/Inf валидация chronology (обещание патча 01/CONVENTIONS) — ✅
Валидатор гоняет `np.isfinite()` по **всем** числовым массивам npz, включая chronology; loaders дополнительно проверяют конечность chronology-массивов с fallback.

### C2. MAX_REPROJECTION_P95 (#10) — ✅
`reconstruction.py:284` = 5.0 px, raise RuntimeError с диагностикой. Не отключаем.

### C3. Фильтр expression (#11) — ✅/⚠️
`MAX_EXPRESSION_MAGNITUDE = 1.5` и пропуск пар `skipped_expression` — проведено. Константы определены как локальные внутри `run()` (не в config) — стиль.
`expression_magnitude`/`jaw_open_degree` пишутся в info.json ✓.

### C4. Фильтр alignment quality < 0.5 (#20 из патча 02) — ✅/⚠️
`MIN_ALIGNMENT_QUALITY = 0.5` применён и для соседних, и для несоседних пар. Тоже локальная константа.

### C5. SHA256-дедапликация (#22) — ✅ после фикса C10
В `Stage1Engine.run()` дубликаты по контент-хешу пропускаются ✓. Калибровка ранее шла отдельным сломанным путём — унифицирована (см. C10), дедупликацию наследует от движка.

### C6. Outlier detection (#27) — ✅
`reconstruction.py:267-279`: displacement > percentile(99)*3 → при >100 выбросах RuntimeError. Проведено в процесс, не мёртвый код.

### C7. nearest_canonical_yaw (#17) — ⚠️ не интегрирован
Функция добавлена и залогирована, но вызывается только сама из себя; в пайплайне не используется («Not integrated into main pipeline yet» — сама себя и маркирует in_progress). Открытый пункт.

### C8. residual_* (#21) — ✅
`residual_pitch/yaw/roll` вычисляются и уходят в info.json (`residual_*_deg`). Не мёртвые.

### C9. Broad-except, подавляющий новые валидации (#25) — ✅
engine.py:193 `raise RuntimeError(cannot decode)` — узкий try по decode_oriented (не глушит); batch.py:36 RuntimeError ловится per-photo с записью в errors — осознанная семантика resume, валидации не теряются.

### C10. Калибровочный паритет (аудит A2) — 🐛→✅FIXED
`run_calibration.py` вызывал **несуществующие** `engine._decode_oriented()` / `engine._save_output()` → AttributeError при первом фото (аудиторская рассинхронизация A2 воплотилась в лом). Переписан на `engine._one(path)` — единый исправленный пайплайн (chronology alignment, NaN-валидация, skin без второго inference). Компилируется.

---

## Блок D. Гигиена

### D1. ≥3 подряд пустых строк (резидуум ручных правок) — ✅FIXED
8 мест (geometry, reconstruction, status_logger ×4, stage2/engine, stage2/motion) нормализованы до ≤2. py_compile чист.

### D2. Мутабельные дефолты в сигнатурах — ✅ 0

### D3. Дубликаты dict-ключей / переопределения функций — ✅ 0 / ✅ 0

### D4. Секреты/токены — ✅ чисто
Регекс по api_key/secret/password/token/bearer — 0 совпадений (кроме плейсхолдеров).

### D5. TODO/FIXME — ⚠️ 9 (все осмысленные)
stage2/engine ×2 (cross-validation, residual gate), chronology ×2, texture_image, core, reconstruction, engine, CONVENTIONS — соответствуют открытым пунктам самого PR (документируют намеренно отложенное).

### D6. Emoji вне словаря CONVENTIONS — ⚠️ 2–3
`📝`, `🏭` используются в коде, но не описаны в CONVENTIONS; `🗑` без VS16 встречается наряду с `🗑️` — мелкая нескомфность словаря.

### D7. Тест-фикстура валидатора vs патч 01 — 🐛→✅FIXED
Validator после патча 01 требует `ldm*_chronology.csv`, фикстура их не писала → `test_valid_fixture` падал с 'invalid'. Фикстура дополнена chronology-CSV и keys в info.files → **2/2 passed**.

### D8. Слепые зоны импорта статус-системы — ✅ после сессий 1–2
`log_status`/`status_warning` связаны во всех 5 проблемных файлах; повторный AST-скан — 0 несвязанных логгер-вызовов.

---

## Итоговый счёт
- 🐛→✅ FIXED в этом аудите: **4** (2× broken relative status_logger import, run_calibration parity, validator fixture)
- ✅ проверено чистых: **19**
- ⚠️ открытые/косметические: **7** (unused imports ×144, displaced docstrings ×43, in_progress ×6, статус 'deprecated', unused locals ×28, vertices_chronology_aligned waste, C7 not integrated, emoji/TODO)

Тест-дельта после аудита: `76 passed → 78 passed`, `8 failed → 6 failed` (оставшиеся 6 failed + 4 errors — вне скоупа: корневой `uv_module` и отсутствующие atlas-ассеты; на базовом коммите те же тесты не собирались вовсе).
