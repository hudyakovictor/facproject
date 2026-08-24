# DEEPUTIN Forensic Workstation — ТЗ для разработчика интерфейса

> **Важно:** этот документ написан простым языком. Если вы не эксперт по машинному зрению или судебной фотометрии — это нормально. Здесь нет сложных формул, только описание того, **что система уже умеет**, **какие данные она produces** и **что именно нужно показывать в интерфейсе**.

---

## 1. Что это за проект?

DEEPUTIN — это система для **анализа старых фотографий человека** с целью понять, какие изменения произошли с его внешностью во времени.

**Простой пример:**  
Представьте, что у вас есть 20 фотографий одного и того же человека, сделанных с 1998 по 2025 год. Система:

1. **На каждой фотографии** находит лицо, строит 3D-модель, определяет landmarks (ключевые точки: контур губ, брови, глаза и т.д.)
2. **Сравнивает пары фотографий** между собой, чтобы понять, какие зоны лица изменились сильнее всего
3. **Строит отчёт** с narrative-описанием, графиками и списком зон, где обнаружены изменения

**Ключевое ограничение:** система **не делает выводов о личности**. Она только измеряет геометрию и текстуру кожи. Никаких "это один человек / не один человек" — только объективные метрики.

---

## 2. Что уже работает (бэкенд)

Бэкенд полностью готов и запускается одной командой (см. `RUN_ALL.sh`):

```bash
bash RUN_ALL.sh --from-stage2
```

Он выполняет три этапа:

| Этап | Что делает | Результат |
|---|---|---|
| **Stage 1** | Извлекает 3D-модель из каждой фотографии | 1909 фотографий обработано, landmarks, маски, текстуры сохранены |
| **Stage 2** | Сравнивает все пары фотографий внутри одного ракурса | 5561 пара проанализирована, 348 change points обнаружено |
| **Stage 3** | Генерирует финальный HTML/JSON отчёт | Отчёт готов к просмотру |

Все результаты хранятся в `/Volumes/SDCARD/storage/` (это внешний диск, который вы подключили).

---

## 3. Что нужно сделать (интерфейс)

Задача дизайнера и фронтенд-разработчика — **сделать удобный способ смотреть на эти результаты**. Никакой новой логики, только визуализация уже готовых данных.

### 3.1. Главная страница — Хронология (Timeline)

**Что показывать:** список всех 1909 фотографий в хронологическом порядке.

**Какие данные у каждой фотографии:**
- Дата съёмки (из имени файла)
- Ракурс: frontal (анфас), left_light, left_mid, left_deep, left_profile, right_light, right_mid, right_deep, right_profile
- Углы наклона головы: pitch, yaw, roll
- Качество: geometry_status, segmentation_status, uv_status
- Показатель видимости лица: combined_visible_fraction (0..1)
- Охват кожи маской: skin_mask_coverage

**Откуда брать данные:**
- Файл `main_timeline.csv` (см. [SPEC.md, раздел 3.1](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/SPEC.md))
- Манифест `stage1_manifest.json` (общая статистика прогона)

**Что должно работать:**
- Фильтр по ракурсу (например, показать только frontal)
- Сортировка по дате, углам, качеству
- Клик по строке → открывается детальная карточка фото

### 3.2. Карточка фотографии (Photo Detail)

**Что показывать:** когда пользователь кликает на фото в timeline — открывается страница с полной информацией об этом кадре.

**Какие данные показывать:**
1. **Изображения:** оригинал, thumbnail, вырезка лица, UV-текстура, маска лица
2. **Углы и ракурс:** pitch/yaw/roll в градусах, ракурсная корзина
3. **Landmarks:** 106 точек и 134 точки в трёх пространствах:
   - `raw` — как вышло из нейросети
   - `aligned` — после выравнивания на канонический ракурс
   - `original` — спроецировано на исходное изображение в пикселях
4. **Качество 3D-реконструкции:** reprojection_rmse, alignment_quality
5. **Кожа:** authenticity_score, quality_score, texture_score
6. **Метаданные:** детекция улыбки, открытия рта, выражение лица

**Важно:** landmarks нельзя смешивать между пространствами. Если пользователь выбирает `raw` — показываем сырые координаты. Если `aligned` — выровненные. Это разные данные.

### 3.3. Сравнение двух фотографий (Compare)

**Что показывать:** side-by-side сравнение двух выбранных фотографий.

**Какие данные показывать:**
- Основные метрики: mesh_rmse, mesh_median, mesh_p95 (насколько различаются 3D-формы)
- Текстурные метрики: texture_score_0_1, texture_conclusions_allowed
- Landmark-метрики: ldm106_rmse, ldm134_rmse
- Expression gate: expression_gate_confidence, expression_gate_stratum
- Quality gate: quality_status_a/b, quality_limited
- Visibility gate: visibility_gate_accepted106, visibility_gate_accepted134
- Калибровка: calibration_limited, calibration_limitation_reason
- Multiple testing: mt_significant_fdr10, mt_q_value

**Важно:** если пара не прошла quality gate — нужно явно показать, что сравнение "limited" или "unavailable", а не показывать цифры без контекста.

### 3.4. Дашборд прогона (Run Summary)

**Что показывать:** общая статистика завершённого Stage 2.

**Какие данные показывать:**
- Всего пар: 5561
- Пар с mesh-метриками: 5561
- Change points: 348
- Рейвью для человека: 353 пары (manual_review_count)
- Public safety status: pass
- Распределение по ракурсам: frontal — 526 пар, left_light — 227 и т.д.
- Измерение по семьям метрик: mesh, texture, point_motion, descriptor и т.д. — сколько пар покрыто каждой метрикой

### 3.5. Отчёт (Report)

**Что показывать:** финальный отчёт Stage 3.

**Какие данные показывать:**
- narrative — текстовые разделы отчёта (summary, findings, methodology)
- timelines — графики по ракурсам
- change_points — список обнаруженных точек изменений с robust_z-score
- zones — детализация по зонам лица (4256 записей)
- motion_maps — карты движения (40 записей)

### 3.6. Загрузка новых фотографий (Upload)

**Что показывать:** форма загрузки фото.

**Ограничения:**
- Имя файла: `YYYY_MM_DD[_N].jpg|.jpeg|.png`
- Максимум 32 МБ
- Сигнатура файла должна совпадать с форматом (нельзя загрузить .exe с расширением .jpg)

---

## 4. Как работают мок-данные

**Проблема, которую это решает:**  
раньше дизайнеры делали макеты на выдуманных данных ("john doe, 35 лет"), а потом разработчики Hours переделывали всё под реальные ключи. Это тратило время и деньги.

**Решение:**  
в папке `ui/mock/` лежат **точные копии реальных данных** — те же ключи, тот же формат, та же вложенность папок.

```
ui/mock/
  stage1/
    main_timeline.csv          ← те же колонки, что в реальности
    stage1_manifest.json       ← те же ключи
    1998_01_01__9714228198ba/
      info.json                ← та же структура вложенности
      ldm106_raw.csv
      texture.json
      face_mask.png
  stage2/
    pair_metrics.csv           ← все 222 колонки
    analysis_manifest.json
  stage3/
    report_data.json
  api/
    photos.json                ← мок API-ответы
```

**Как включить мок-режим:**
```bash
export DEEPUTIN_MOCK_DATA_ROOT="/Users/victorkhudyakov/work/ui/mock"
```

Приложение должно проверять эту переменную при старте и подменять все запросы к данным на чтение из `ui/mock/`.

---

## 5. Ссылки на созданные файлы (GitHub)

Все ссылки ведут на ветку `main` репозитория https://github.com/hudyakovictor/facproject

### 5.1. Основное ТЗ (что показывать в интерфейсе)

| Файл | Что там |
|---|---|
| [ui/spec/SPEC.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/SPEC.md) | Полный список элементов интерфейса: каждый элемент, его ключ в данных, тип, источник. Это главный документ для дизайнера. |
| [ui/spec/API_CONTRACT.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/API_CONTRACT.md) | Все API-эндпоинты, которые должен использовать интерфейс: GET/POST, параметры, форматы ответов, ошибки. |
| [ui/spec/DATA_SOURCES.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/DATA_SOURCES.md) | Карта: каждый UI-элемент → точный файл на диске и путь к ключу. |
| [ui/README.md](https://github.com/hudyakovictor/facproject/blob/main/ui/README.md) | Краткая инструкция: как работает папка ui/, что делать дизайнерам и разработчикам. |

### 5.2. Мок-данные (для дизайна и разработки)

| Файл | Что там |
|---|---|
| [ui/mock/stage1/main_timeline.csv](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage1/main_timeline.csv) | Пример timeline с 3 фото — точно такая же структура, как в реальности |
| [ui/mock/stage1/stage1_manifest.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage1/stage1_manifest.json) | Манифест Stage 1 с ключами: status, success_count, elapsed_seconds, device, backbone |
| [ui/mock/stage1/1998_01_01__9714228198ba/info.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage1/1998_01_01__9714228198ba/info.json) | Полная карточка одной фотографии — все ключи, которые есть в реальном info.json |
| [ui/mock/stage2/analysis_manifest.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage2/analysis_manifest.json) | Манифест Stage 2 с pair_count, pose_bins, limitations, elapsed_seconds |
| [ui/mock/stage2/pair_metrics.csv](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage2/pair_metrics.csv) | Все 222 колонки метрик пары — дизайнер может взять любые ключи из [SPEC.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/SPEC.md) и найти их здесь |
| [ui/mock/stage2/pair_details.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage2/pair_details.json) | Детали по парам: zones, calibrated_metrics |
| [ui/mock/stage3/report_data.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/stage3/report_data.json) | Финальный отчёт: narrative, timelines, change_points, zones, motion_maps |
| [ui/mock/api/photos.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/api/photos.json) | Мок ответа API `/api/v1/photos` |
| [ui/mock/api/health.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/api/health.json) | Мок ответа API `/api/v1/health` |
| [ui/mock/api/pairs.json](https://github.com/hudyakovictor/facproject/blob/main/ui/mock/api/pairs.json) | Мок ответа API `/api/v1/compare` |

### 5.2. Реальные примеры данных (production)

| Файл | Что там |
|---|---|
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/info.json](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/info.json) | **Реальная** карточка фронтального фото из вашего набора |
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/ldm106_raw.csv](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/ldm106_raw.csv) | Реальные 106 landmarks в сыром пространстве |
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/ldm134_chronology.csv](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/ldm134_chronology.csv) | Реальные 134 landmarks после выравнивания |
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/texture.json](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/texture.json) | Реальная текстура кожи с метриками |
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/face_mask.png](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/face_mask.png) | Реальная маска лица |
| [ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/mesh.obj](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage1/1999_09_01__fdfba9d7bcd5/mesh.obj) | Реальный 3D-меш лица (7 MB, 35k вершин) |
| [ui/real_examples/stage2/pair_metrics_sample.csv](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage2/pair_metrics_sample.csv) | Реальная строка из pair_metrics.csv — одна пара с 222 колонками |
| [ui/real_examples/stage2/analysis_manifest.json](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage2/analysis_manifest.json) | Реальный манифест Stage 2 |
| [ui/real_examples/stage2/pair_details_sample.json](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage2/pair_details_sample.json) | Реальные детали пары: zones, calibrated_metrics |
| [ui/real_examples/stage3/report_data.json](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples/stage3/report_data.json) | Реальный финальный отчёт Stage 3 |

### 5.3. Запускальщик пайплайна

| Файл | Что там |
|---|---|
| [RUN_ALL.sh](https://github.com/hudyakovictor/facproject/blob/main/RUN_ALL.sh) | Скрипт, который запускает все этапы последовательно. Использует пути `/Volumes/SDCARD/...` которые вы указали. |

---

## 6. Правила, которые нельзя нарушать

Эти правила зашиты в бэкенд и должны соблюдаться в интерфейсе:

1. **`not_a_verdict: true`** — во всех ответах API и во всех элементах UI это поле должно присутствовать. Система показывает измерения, а не выводы о личности.
2. **`source_mode: research`** — все данные являются исследовательскими, не forensic-вердиктами.
3. **Пустые состояния** — никогда не показывайте пустой экран. Если данных нет, покажите сообщение: "Данные Stage 1 не найдены. Запустите извлечение." + кнопку действия.
4. **Пространства координат** — никогда не смешивайте `raw`, `aligned` и `original`. Это разные данные для разных целей.
5. **Большие объёмы данных** — `pair_metrics.csv` weighs 15 MB, `pair_details.json` weighs 58 MB. Интерфейс должен подгружать данные постранично, не загружая всё в браузер сразу.

---

## 7. Что дальше

1. **Дизайнер** читает [SPEC.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/SPEC.md), открывает [mock/](https://github.com/hudyakovictor/facproject/blob/main/ui/mock) для схемы данных и [real_examples/](https://github.com/hudyakovictor/facproject/blob/main/ui/real_examples) для реальных примеров, и делает макеты, привязываясь к ключам из SPEC.md.
2. **Разработчик** берёт макеты и подключает их к API (см. [API_CONTRACT.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/API_CONTRACT.md)) или прямым файлам (см. [DATA_SOURCES.md](https://github.com/hudyakovictor/facproject/blob/main/ui/spec/DATA_SOURCES.md)).
3. **Мок-данные заменяются на реальные** одной переменной окружения `DEEPUTIN_MOCK_DATA_ROOT`. Никакого переписывания кода не требуется.

---

## 8. Быстрый старт для разработчика

```bash
# 1. Клонировать репозиторий
git clone https://github.com/hudyakovictor/facproject.git
cd facproject

# 2. Включить мок-режим
export DEEPUTIN_MOCK_DATA_ROOT="$(pwd)/ui/mock"

# 3. Запустить бэкенд (если нужен)
bash RUN_ALL.sh --skip-ui --skip-api --stage1-only

# 4. Запустить фронтенд (когда он будет готов)
cd ui
npm install
npm run dev
```

---

*Документ создан: 2026-08-24*  
*Репозиторий: https://github.com/hudyakovictor/facproject*  
*Коммит: fef1b65b3*
