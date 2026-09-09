# Stage 2 v2 — Переосмысленная реализация этапа 2

**Stage 2 v2** — это переработанная версия этапа 2 анализа facial geometry, которая устраняет все критические ошибки legacy-версии и предоставляет современные инструменты для работы.

## 📊 Сравнение версий: Legacy vs New

### Old Stage 2 (legacy, `app6/stage2/`)

| Характеристика | Старая версия |
|----------------|---------------|
| **Файлов кода** | ~98 файлов |
| **Пороговые значения** | Разбросаны в 50+ файлах, дублирование констант |
| **Тестирование** | Нельзя (требуются веса + SD_CARD) |
| **Admin панель** | Нет |
| **Профили** | Нет |
| **Dry-run планирование** | Нет |
| **HTTP API** | Нет |
| **Hash/reproduce** | Нет |
| **Quality fix** | Баг: все пары маркируются `quality_limited` |
| **Evidence limits** | Баг:limits перезаписывались вместо накопления |
| **Parameter registry** | Нет единого источника истины |

### New Stage 2 v2 (перестроенная, `stage2_v2/`)

| Характеристика | Новая версия |
|----------------|--------------|
| **Файлов кода** | ~20 файлов |
| **Пороговые значения** | Единый реестр в `params.py` (83 параметра) |
| **Тестирование** | Можно с фикстурами (только numpy) |
| **Admin панель** | Есть (генерируется из registry) |
| **Профили** | ✅ 4 built-in: default, strict_evidence, exploratory, fast_smoke |
| **Dry-run планирование** | ✅ Можно ответить "что если tightening yaw gate?" |
| **HTTP API** | ✅ Полный API (validate, dry-run, profiles) |
| **Hash/reproduce** | ✅ Content hash + resume hash в манифесте |
| **Quality fix** | ✅ Исправлен: correct texture quality path |
| **Evidence limits** | ✅ Накапливаются (set, а не overwrite) |
| **Architecture** | ✅ Registry-driven, testable, maintainable |

---

## 🚀 Что нового в stage2_v2?

### 1. **Единый реестр параметров** (`params.py`)
- Все 83+ параметров объявлены один раз
- Есть валидация, границы, единицы измерения
- Есть 4 built-in профиля: `default`, `strict_evidence`, `exploratory`, `fast_smoke`

### 2. **Admin панель**
- Открывается на `127.0.0.1:8770`
- Показывает все параметры с bounds и defaults
- Dry-run planner: "если tightening yaw gate, потеряю N пар"
- Экспорт/импорт конфигураций

### 3. **Fixtures для тестирования**
- `fixtures.py` генерирует синтетические Stage 1 data
- Тестирование Stage 2 можно сделать на любом ноуте с Python + numpy
- Можно инъектировать известное изменение и проверить, его находят ли gates

### 4. **Исправленные баги (Audit fixes)**
1. ✅ **Texture quality path** — больше не все пары `quality_limited`
2. ✅ **Evidence limits accumulation** — limits растут, не перезаписываются
3. ✅ **Single parameter registry** — нет дублирования в 3+ файлах
4. ✅ **Registry-based thresholds** — pose_leakage_distance_threshold и др.
5. ✅ **Zone weights consistency** — устранено дублирование
6. ✅ **Гейты принимают Params object** — никакого дрейфа default'ов
7. ✅ **Нет silent except blocks** — ошибки логируются

### 5. **Production-ready возможности**
- ✅ Hash-based reproducibility (content hash в manifest)
- ✅ Resume hash (для чекпоинтов)
- ✅ Profile diffing (что изменилось vs default)
- ✅ Валидация config перед запуском multi-hour job

---

## 🔄 Совместимость с downstream стадиями

### stage2b (пост-обработка)
- ✅ **Обе версии** читают одни и те же 33 артефакта
- `python app6/run_stage2b.py --stage2 results/stage2` (legacy)
- `python app6/run_stage2b.py --stage2 results/stage2_v2` (new) — **работает**

### stage3 (финальный отчёт)
- ✅ **Обе версии** читают одни и те же 33 артефакта
- `python app6/run_stage3.py --analysis results/stage2b` (legacy)
- `python app6/run_stage3.py --analysis results/stage2_v2` (new) — **работает**

### stage3_v2 (новый аналитический отчёт)
- ✅ **Работает с обеими версиями stage2**
- `python -m stage2_v2.cli run ... --stage2 results/stage2_v2`
- `python app6/run_stage3_v2.py --stage2 results/stage2_v2`

---

## 🏁 Что выбрать?

### Выбирай **Legacy stage2** (`app6/stage2/`), если:
- ✅ Нужна **гарантированная стабильность** (официальная версия)
- ✅ Есть **веса модели** + `SD_CARD` с данными
- ✅ Команда привыкла к старому workflow
- ✅ Нужна **минимальная смена процесса**

**Команда запуска:**
```bash
/Users/victorkhudyakov/work/.venv/bin/python app6/run_stage2.py \
    --stage1 results/stage1_v2 \
    --output results/stage2 \
    --profile default
```

### Выбирай **Stage 2 v2** (новая версия), если:
- ✅ Хочется **тестировать** без реальных данных (fixtures)
- ✅ Нужна **admin панель** для настройки параметров
- ✅ Нужны **profiles** (default, strict_evidence, exploratory, fast_smoke)
- ✅ Нужна **dry-run планировка** перед multi-hour job
- ✅ Хочется **Hash/reproduce** результаты
- ✅ Важен **modern workflow** с validation и错误 handling

**Команда запуска:**
```bash
python -m stage2_v2.cli run \
    --stage1 results/stage1_v2 \
    --output results/stage2_v2 \
    --profile default
```

---

## 🎯 Мой рекомендация

**Начинай с stage2_v2** (новой версии), если:
1. Ты хочешь **тестировать pipeline** без загрузки весов и реальных данных
2. Хочешь иметь **панель контроля** над параметрами
3. Хочешь использовать **profiles** для разных сценариев
4. Хочешь **dry-run** перед запуском дорогих вычислений

**Оставайся на Legacy stage2**, если:
- ✅ У тебя уже есть готовые результаты отlegacy-версии
- ✅ Нужна **полная гарантированная совместимость** со старыми скриптами
- ✅ Не нужны новые фичи (admin panel, profiles, dry-run)

**Важно:** stage2_v2 **полностью совместим** с legacy stage1 output и downstream стадиями (stage2b, stage3, stage3_v2). Ты не теряешь ни одной функциональности, переходя на новую версию — ты только получаешь новые возможности.

---
*Эта документация сгенерирована на основе audit stage2 и сравнения старых и новых архитектур.*