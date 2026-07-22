# AUDIT-6 — 50 финальных анализов (волна 2): ТОП-20 ошибок в диффах и незатронутом коде

Дата: 2026-07-22 · Ветка: `arena/019f89cd-facproject` · Новые углы сканирования, не повторяющие AUDIT-5: дубли ТЕЛ функций, арифметика return-кортежей, рассинхрон статус-реестра STATUS_AUDIT↔код, CLI-смоук, roundtrip-контракты, stage2→stage3 контракты.

Вердикты: **PASS** · **FIXED** · **NOTE** · **FAIL**.

---

## Блок A. Дубли тел и теневые реализации (A1–A10)

| # | Анализ | Вердикт | Детали |
|---|---|---|---|
| A1 | Дубли ТЕЛ функций (AST-нормализация, кросс-файлово) | **NOTE** | 1 группа: `sha256_file` (skin/serialization) ≡ `sha` (scripts/fetch_external_assets) — третья копия hash-хелпера. Тривиальный алгоритм в трёх местах; объединение отложено до packaging-задачи (D3 AUDIT-4). |
| A2 | Дубли тел с РАЗНЫМИ именами в одном модуле | **PASS** | 0. |
| A3 | Дубли тел >10 строк (существенные) | **PASS** | 0 — все найденные дубли ≤6 строк (тривиальные хелперы). |
| A4 | Классы-двойники loader.Record-like в skin/* | **PASS** | Разные доменные контракты — не дубли. |
| A5 | `load_records` в skin/calibration + skin/chronology | **PASS** | Паритет по домену калибровки/хронологии, сигнатуры разные. |
| A6 | `utc()`/`payload()` в stage2 и stage2b engines | **NOTE** | Копии 4-строчных хелперов; stage2b — отдельный этап с собственной версией SCHEMA. Оставлено. |
| A7 | `_utc` (quality_zones) vs `utc()` (stage2) | **PASS** | Разные области, обе используются локально. |
| A8 | `detect` (local_features) vs `detect` (wrinkles/classical) | **PASS** | Разные классы детекторов. |
| A9 | `predict` (contamination) vs `predict` (ffhq_adapter) | **PASS** | Одинаковое API-двух моделей — паттерн адаптера, не баг. |
| A10 | Реестр имён публичных функций на коллизию с builtins | **PASS** | Коллизий нет (проверено против dir(builtins)). |

## Блок B. Арифметика и форма возвратов (B1–B10)

| # | Анализ | Вердикт | Детали |
|---|---|---|---|
| B1 | Разные арности tuple-возвратов в одной функции | **PASS** | 0 функций (скан AST по Return/None/Tuple). |
| B2 | None-return на части путей при tuple-коллерах | **PASS** | 0. |
| B3 | Длина распаковки = длине возврата по всем callsite'ам | **PASS** | Спот-чек 12 горячих распаковок (engine 236/283/…) — совпадает. |
| B4 | Mutable дефолты | **PASS** | 0 (контроль с AUDIT-4). |
| B5 | `*args/**kwargs` с неоднозначной семантикой | **PASS** | Только renderer_forward — контракт проверен в AUDIT-5 C5. |
| B6 | Генераторы/контексты с забытым cleanup | **PASS** | atomic_photo_directory: temp всегда убирается (finally). |
| B7 | `return` внутри `finally` (глушение исключений) | **PASS** | 0. |
| B8 | Недостижимый код после return/raise | **PASS** | AST-скан: 0 стейтментов после терминальных в том же блоке. |
| B9 | Пустые тела (pass-only) публичных функций | **PASS** | 0 (все API имеют тело; заглушки отсутствуют). |
| B10 | Исключение в `__exit__`/contextmanager выходе | **PASS** | Пути согласованы с storage-тестами (78 passed). |

## Блок C. Статус-реестр STATUS_AUDIT ↔ код (C1–C10)

| # | Анализ | Вердикт | Детали |
|---|---|---|---|
| C1 | Расхождения статусов аудит↔код | **FIXED** | **34 расхождения устранены**: 14 покрытых тестами функций — аудит 🔴→✅ COMPLETE (код был прав); 18 без прямого покрытия — код ✅→🔴 need_testing (аудит был прав: patch-13 blanket ошибочно ставил complete); `to_original_image` → ⚠️ IN PROGRESS (обе стороны уточнены); `build` → 🔬 EXPERIMENTAL. |
| C2 | Функции со статусом в коде, отсутствующие в аудите | **FIXED** | `landmark_arrays` добавлен в STAGE1_STATUS (✅ COMPLETE, mirror of code). |
| C3 | Имена аудита, отсутствующие в коде | **PASS** | 0 (124/124 объявленных существуют). |
| C4 | need_testing-функции с прямым тест-покрытием | **PASS** | После C1 — согласовано (покрытые = ✅, непокрытые = 🔴). |
| C5 | Эмодзи-валидность статус-строк аудита | **PASS** | Все в словаре CONVENTIONS v2 (вкл. новый 🔬 EXPERIMENTAL). |
| C6 | print_audit_summary работоспособность | **PASS** | Исполняется, печатает по секциям (после фиксов glyph AUDIT-4). |
| C7 | close_function → авто-апдейт файла | **PASS** | `_update_audit_status` переписывает только статус-поле (regex-точность проверена на 6 пробах). |
| C8 | Двойной учёт классов и функций в аудите | **NOTE** | 12 классов ведутся наравне с функциями — осознанное расширение реестра. |
| C9 | FUNCTION_STATUS_LOG ↔ STATUS_AUDIT | **PASS** | Страница перегенерирована после правок; противоречий нет. |
| C10 | Регрессия B1(AUDIT-5): дубли log_status | **PASS** | 0 повторов (детектор пуст). |

## Блок D. CLI / entry-point смоук (D1–D10)

| # | Анализ | Вердикт | Детали |
|---|---|---|---|
| D1 | run_stage1 --help | **PASS** | argparse вывод ОК (device/detector/backbone/uv-size…). |
| D2 | run_stage2 --help | **PASS** | ОК. |
| D3 | run_stage3 --help | **PASS** | ОК. |
| D4 | run_stage2b --help | **PASS** | Импортируется, аргументы согласованы. |
| D5 | run_skin_* --help ×4 | **PASS** | manage/calibration/stage1-3 отзываются. |
| D6 | build_parser без import-time сайд-эффектов | **PASS** | Тяжёлые импорты — внутри main(). |
| D7 | Обязательные аргументы без дефолтов-ловушек | **PASS** | required=True только для путей. |
| D8 | Exit codes release-gate | **PASS** | Ненулевой по дизайну (AUDIT-4 J8). |
| D9 | sys.path bootstrap до импорта app6 | **PASS** | Вставка выполняется до app6-импортов во всех run_* (проверка порядка). |
| D10 | --overwrite семантика | **PASS** | rmtree только с флагом (stage3), атомарник в stage1. |

## Блок E. Контракты writer↔reader и roundtrip (E1–E10)

| # | Анализ | Вердикт | Детали |
|---|---|---|---|
| E1 | 40 обязательных файлов req-контракта stage2 | **PASS** | **40/40 имеют писателя** (29 в engine.py, 10 в postprocess_reports.py, evidence_packets.jsonl — engine.py:284). Валидация `analysis_validation.json` пустых ошибок не даст. |
| E2 | CSV landmark writer↔loader roundtrip | **PASS** | `_landmark_rows` (landmark_id=i, x,y,z,visible,vertex_index[,confidence]) ↔ `_read_landmark_csv` (by landmark_id) — поля согласованы; extra-колонки лоадером осознанно игнорируются. |
| E3 | pack_mask↔unpack_mask roundtrip | **PASS** | Побитово точно на 35709-маске, 8× компрессия. |
| E4 | analysis_manifest ↔ stage3 template keys | **PASS** | main_record_count/calibration_dataset_count/created_at_utc/schema_version — все пишутся (engine.py:292). |
| E5 | point_noise_model.npz ключи ↔ stage3 lookup | **PASS** | `{pose}__ldm134__template` формат идентичен на запись и чтение. |
| E6 | uv_geometry_zone_metrics.csv ↔ stage3 читатель | **PASS** | Имя файла совпадает; guard is_file присутствует; `uv_zone_rows` определён до записи (AUDIT-5 подозрение снято, лишняя копия списка помечена). |
| E7 | load_calibration_from_sidecar space-contract | **PASS** | object_normalized=(raw−center)/scale соблюдается; fallback NaN-alpha вместо фабрикованных нулей. |
| E8 | `visible` колонка CSV ↔ потребители | **PASS** | Лоадер использует NaN-пустоты из отсутствия, а не visible — семантически согласовано с combined_visible из stage1. |
| E9 | jsonl-формат evidence_packets | **PASS** | По одному json-пакету на строку, совместим с grep-стилем чтения. |
| E10 | stage3 fallback при отсутствии lead_registry/metric_catalog | **PASS** | Default-структуры + JS-guards (`||0`) — отчёт не падает. |

---

## ТОП-20 ошибок (итоговый рейтинг волны 2)

**FIXED (4 кластера):**
1. **C1** — 34 рассинхрона статуса STATUS_AUDIT↔код: патч-13 blanket проставлял `complete` без верификации (18 функций честно понижены до 🔴 need_testing), а аудит не догонял пройденные тесты (14 функций повышены до ✅ COMPLETE) — статус-система снова однозначна (0 mismatches).
2. **C2** — `landmark_arrays` без статуса в аудите (orphan) — добавлен.
3. **C1-вариант** — `to_original_image`: аудит/код спорили need_testing vs in_progress — уточнены к in_progress (конкретный недостаток «no bounds check» зафиксирован в обеих точках).
4. **C1-вариант** — `build` (material/evidence): зафиксирован как 🔬 EXPERIMENTAL и в аудите, и в коде.

**Документировано (16):**
5. A1 — три реализации sha256-хелпера (utils/serialization/fetch_assets) — технический дубль до packaging.
6. A6 — парные utc()/payload() хелперы stage2/stage2b.
7. E6-остаток — избыточная копия `uv_zone_rows=[z for z in uv_zone_list]...` (стиль патча).
8. D3(AUDIT-4) — 24 sys.path-хака (packaging-техдолг).
9. B7(AUDIT-4) — ~144 мёртвых логерных blanket-импорта (отдельная задача чистки).
10. E1(AUDIT-4) — 26 bare except в skin-слое (graceful degradation).
11. E9(AUDIT-4) — 10 функций >150 строк (декомпозиция позже).
12. F10(AUDIT-4) — `vertices_chronology_aligned` не потребляется stage2 (~213КБ/фото).
13. F7(AUDIT-4) — внешний ассет texture_zones npz (test_wrinkle_zones, out-of-scope).
14. L1(AUDIT-4) — uv_module single-render рефактор (вне app6).
15. D5(AUDIT-5) — отсутствие bounds-check в to_original_image (контракт координат; статус теперь честно in_progress).
16. C8 — классы в аудите без отдельного раздела (расширение реестра задокументировано).
17. A5-like — парные load_records доменов (калибровка/хронология).
18. H8(AUDIT-4) — отсутствие автотеста на STATUS_FLOW (предложение в бэклог).
19. M7(AUDIT-4) — часть порогов вшита в skin-функции (не в config).
20. D9-style — run_stage2b уровня «чернового» пост-отчёта (IN PROGRESS по замыслу).

**Проверки после исправлений:** компиляция 156/156; pytest **78 passed** (6+4 известных out-of-scope без изменений); CLI-смоук 3+4 входа ОК; статус-реестр 124 записи, 88 с код-статусом, **0 mismatches**; req-контракт 40/40; FUNCTION_STATUS_LOG перегенерирована.
