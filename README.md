# DEEPUTIN facproject — Stage 2 Rebuild (stage2_v2)
/Users/victorkhudyakov/work/.venv/bin/python
## Обзор

**stage2_v2** — это переосмысленная реализация этапа 2 анализа facial geometry. Это Complete rewrite (полная переработка) legacy Stage 2 из `app6/stage2/`, который был ненадежным и непротестируемым без Model Weights и SD-CARD.

## ✅ Что такое stage2_v2

stage2_v2 — это модуль из ~20 файлов (вместо ~98 у legacy), который:

- ✅ **Работает с фикстурами** (синтетические Stage 1 data, только numpy) — тестируется на любом ноуте
- ✅ **Имеет единый реестр параметров** (83 параметра в `params.py`) — один источник истины
- ✅ **Имеет admin-панель** на `127.0.0.1:8770` — генерация UI из registry
- ✅ **Имеет built-in профили** (default, strict_evidence, exploratory, fast_smoke)
- ✅ **Имеет dry-run планирование** — "что если tightening yaw gate?"
- ✅ **Имеет HTTP API** (validate, dry-run, profiles)
- ✅ **Имеет hash/reproduce** (content hash в manifest)
- ✅ **Исправляет 7 критических багов** из аудита (см. ниже)

## 📊 Ключевые отличия: Legacy vs stage2_v2

| Характеристика | **Legacy (app6/stage2/)** | **New stage2_v2** |
|----------------|---------------------------|-------------------|
| **Файлов кода** | ~98 файлов | ~20 файлов |
| **Пороговые значения** | Разбросаны в 50+ файлах, дублирование констант | Единый реестр `params.py` (83 параметра) |
| **Тестирование** | Нельзя без весов + SD_CARD | **Можно** с фикстурами (только numpy) |
| **Admin панель** | Нет | **Есть** (на порту 8770, генерация из registry) |
| **Built-in профили** | Нет | ✅ 4: default, strict_evidence, exploratory, fast_smoke |
| **Dry-run планирование** | Нет | **Есть** ("что если tightening yaw gate?") |
| **HTTP API** | Нет | **Есть** (validate, dry-run, profiles) |
| **Hash/reproduce** | Нет | ✅ Content hash + resume hash |
| **7 audit fixes** | 7 критических багов | **Все исправлены** |
| **Quality fix** | Все пары `quality_limited` (баг) | ✅ Исправлено: correct texture quality path |
| **Evidence limits** | Перезапись вместо накопления | ✅ Накапливаются (set, а не overwrite) |

### 7 AUDIT FIXES (исправленные баги):

1. **Texture quality path** — больше не все пары `quality_limited` (was reading non-existent key `info.json → quality_summary.global_texture_quality` → 0.0)
2. **Evidence limits accumulation** — limits растут как множество, а не перезаписываются
3. **Единный parameter registry** — нет дублирования `MIN_ALIGNMENT_QUALITY` в 3+ файлах
4. **Registry-based thresholds** — pose_leakage_distance_threshold из registry, а жестко закодированный внутри цикла
5. **Zone weights consistency** — устранено дублирование ZONE_WEIGHTS
6. **Гейты принимают Params object** — все пороговые значения через params["key"], а не default values
7. **Нет silent except blocks** — все ошибки собираются в failures, а не заглушаются

### downstream совместимость:

- ✅ **stage2b** — работает с обеими версиями (читает те же 33 артефакта)
- ✅ **stage3** — работает с обеими версиями
- ✅ **stage3_v2** — работает с обеими версиями (я проверял тестами)

### Команды запуска:

**Legacy stage2:**
```bash
/Users/victorkhudyakov/work/.venv/bin/python app6/run_stage2.py \
    --stage1 results/stage1_v2 --output results/stage2 --profile default
```

**New stage2_v2:**
```bash
python -m stage2_v2.cli run \
    --stage1 results/stage1_v2 \
    --output results/stage2_v2 \
    --profile default
```

## 🚀 Запуск

### С фикстурами (test mode, без весов):
```bash
# Генерация синтетических Stage 1 data
python -m app6.stage2_v2.fixtures /tmp/test_s1 --per-day 2 --change 0.01

# Запуск pipeline
python -m stage2_v2.cli run \
    --stage1 /tmp/test_s1 \
    --output /tmp/stage2_out \
    --profile default
```

### С real данными:
```bash
python -m stage2_v2.cli run \
    --stage1 /Volumes/SDCARD/storage/stage1 \
    --output results/stage2_v2 \
    --profile default
```

## 🏁 Мой вердикт

**Начинай с stage2_v2** (новой версии), если:
1. Хочешь тестировать pipeline без загрузки весов и реальных данных
2. Хочешь иметь админ-панель для настройки параметров
3. Хочешь использовать профили (default, strict_evidence, exploratory, fast_smoke)
4. Хочешь dry-run планировку передmulti-hour job
5. Важен hash/reproduce для reproducibility

**Оставайся на Legacy stage2**, если:
- У тебя уже есть готовые результаты отlegacy-версии
- Нужен полный гарантированный результат (официальная версия)
- Не нужны новые фичи (admin panel, profiles, dry-run)

**Важно:** stage2_v2 **полностью совместим** с legacy Stage 1 output и downstream стадиями (stage2b, stage3, stage3_v2). Ты не теряешь ни одной функциональности, переходя на новую версию — ты только получаешь новые возможности.

---
*Документация на основе audit stage2: 7 критических багов, отраженных в коде stage2_v2*