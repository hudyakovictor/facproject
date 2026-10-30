# ATLAS · узловая лаборатория изменений

**Рабочее приложение:** 3DDFA_V3 на CPU, фото-текстура из реальных пикселей, тепловая карта, морфинг, отдельная панель метрик, α_id-кластеры и измерения глаз на MediaPipe 478-landmark CPU. FAN и AdaFace не подключены. Синтетические demo-карточки можно удалить; рабочий набор по умолчанию не включает demo.

## Открыть

В Arena откройте live preview **«ATLAS — узловая лаборатория»**. Приложение обслуживается на порту 5173. Все запросы из браузера — относительные `/api/...`; отдельный localhost пользователю не нужен.

Восстановление окружения после снапшота (выполняет ИИ-разработчик в среде):

```bash
cd /home/user/atlas
bash scripts/setup.sh
```

Запускать как **долгоживущий процесс**, например через Arena `start_process`:

```bash
cd /home/user/atlas
bash scripts/start.sh
```

Для разработки отдельно: FastAPI на 8000 и Vite на 5173. Production запускается одним `scripts/start.sh` на 5173. После изменений фронтенда `cd web && npm run build` и обновите preview; после Python-изменений перезапустите API. В среде с 2 GB RAM не запускайте сборку одновременно с новым инференсом/UMAP.

## Работа с приложением

### Две рабочие панели

- **«3D · морфинг · фотографии»**: большая сцена с моделью, оригинальной фототекстурой, теплокартой, тремя независимыми наборами landmarks, миниатюрами и общим управлением морфингом.
- **«Таймлайн · измерения»** — отдельная панель дат и метрических дорожек. Курсор связан с 3D-сценой. Ноды можно двигать/менять размер.
- Навигационная полоса: 3D / Метрики / Глаза / Кластеры / Фото и переключатель «рука». Колесо перемещает поле, Ctrl/⌘+колесо масштабирует, Space временно включает перенос; `1–5` переходят к панели, `F` показывает всё поле.

### Фото и demo

1. В источнике выберите группу или загрузите изображения/ZIP. В ZIP пути папок становятся группами; даты распознаются из имён `2002_12_02`, `2009_12_10_2`, `2003_10_16__hash`.
2. Клик по кадру выбирает реконструкцию; переход между миниатюрами задаёт морфинг пары; Ctrl/⌘ — маршрут из 2–10 кадров. Play/общая перемотка синхронизируют обе панели.
3. Синтетические demo-портреты не выбираются в рабочую группу по умолчанию. «Убрать все демо» перемещает их в корзину; «Удалить навсегда» с явным подтверждением физически удаляет **только** помеченные приложением synthetic files и их cache. Обычные пользовательские снимки удаляются в восстанавливаемую корзину.
4. Двойной клик по фото задаёт дату/углы головы; ручные углы не запускают новый inference.

### Фототекстура и тепловая карта

- Переключатель **«Фото»** использует пиксели исходного снимка и UV, рассчитанные по проекции реконструированного 3DDFA mesh для каждого vertex. Это не альбедо 3DMM и не синтетическая заливка. Источник полноразмерный; топология по-прежнему ограничена 35 709 вершинами.
- Карта включена по умолчанию: расстояние, α_id shape или normal displacement относительно первого, предыдущего или указанного кадра. Перцентиль, пороги, палитры, гамма, прозрачность, сглаживание.
- `ldm68/106/134` — независимые слои **одного 3DDFA_V3**, не три разных модели.
- Без WebGL включается CPU PNG-рендер с geometry, теплокартой, статистикой, landmarks, орбитой и масштабом; до 6 кадров/с. **Этот fallback пока не переносит оригинальную фототекстуру на поверхность**; текстура доступна в WebGL-сцене. 3D-cluster без WebGL помечается как XY.

### Таймлайн, кластеры и ракурсы

- Метрики находятся в самостоятельной таймлайн-ноде с датами, дорожками, значениями/robust MAD z/Δ предыдущему и одной синхронной линией кадра.
- PCA, UMAP, t-SNE используют кэшированные параметры **α_id**; seed, расстояние, K-means, 2D/3D. Вычисление/интерполяция явно помечаются.
- 5 профилей yaw/pitch/roll редактируются по отдельности. Ручные углы у фото имеют приоритет над автоматическими.

### «Глаза»: измерение и качество, а не аутентификация

MediaPipe Face Landmarker на CPU даёт 478 landmarks, включая 10 iris points. Приближённый отбор ранжирует по head yaw/pitch/roll, gaze offsets, размеру щели и пикселям; на исходном фото видны и редактируются все ключевые точки. Для каждой записи можно задать обезличенный comparative cohort `A/B/C`, ввести углы из пользовательской таблицы, явно проверить gaze и отметить ручную разметку. 20 формул доступны в панели/CSV с причинами исключения: iris/width и iris/aperture, раскрытие/форма/наклон/асимметрия глаз, межуголковое расстояние/IPD, нос/переносица, средняя зона, голова/челюсть/подбородок.

Это **видимые двумерные проекции мягких тканей**, не измерение костей. Значение iris diameter / aperture height >1 само по себе обычно: веки закрывают часть радужки. Ошибка точки и ракурс существенно влияют на узкие щели. Метрики, группы и α_id не доказывают личность, наличие накладки/маски или естественность. Отбор требует сопоставимых углов, прямого взгляда, выражения, разрешения и ручной проверки landmarks.

## Метрики и расширение

### Один новый Python-файл

Скопируйте `docs/examples/mesh_height.py` в `metrics/tddfa_v3/mesh_height.py` и нажмите «Обновить» в реестре. Метрика появляется в списке и, при стандартном выборе дорожек, на графике без правки React.

```python
from server.registry import metric
import numpy as np

@metric('my_height', 'Высота реконструкции', model='3ddfa_v3', unit='IOD₀', inputs=('vertices',))
def compute(ctx):
    return np.ptp(ctx['vertices'][:, 1])
```

В контексте 3DDFA: `vertices` (ID+exp), `identity` (без exp), `albedo`, `alpha`, `ldm68`, `ldm106`, `ldm134`. Геометрия — в общей канонической системе, в масштабе среднего шаблона IOD₀. Все значения на исходных кадрах считаются Python-функциями, не нарисованы в браузере.

В декораторе можно указать `poses=('frontal', 'three_quarter_left')`. YAML переопределяет включение, заголовок/единицы и warn/alert отдельно для каждого профиля:

```
configs/metrics/3ddfa_v3/frontal.yaml
configs/metrics/3ddfa_v3/three_quarter_left.yaml
configs/metrics/3ddfa_v3/three_quarter_right.yaml
configs/metrics/3ddfa_v3/profile_left.yaml
configs/metrics/3ddfa_v3/profile_right.yaml
```

Для `mediapipe`, `fan`, `adaface` существуют pose-specific YAML по пяти профилям. MediaPipe реально выдаёт точки; 20 геометрических глазных показателей описаны отдельно в `server/ocular.py`. Только две из них подключены к метрическому timeline, где остаются `null` до прохождения quality-filter и ручной проверки. FAN/AdaFace не вычисляются.

Робастный z: `(x−median)/(1.4826·MAD)`, отдельно по группе и ракурсу. При n<3/нулевом MAD недостоверная оценка не выдумывается. Метрика вне разрешённого ракурса даёт пустое значение с объяснением.

### Профиль ракурса

Диапазоны пяти текущих профилей редактируются в ноде и в `configs/pose_profiles.yaml`. Добавление шестого пока намеренно запрещено валидатором (требование — ровно пять); для расширения количества меняется эта проверка и список метрик нового профиля. Основные списки строятся по данным.

### Следующая модель

Граница адаптера описана в `server/models/base.py`; план моделей и ожидаемые ключи — `configs/models.yaml`. Реализуйте адаптер с версией/хэшами весов и явными координатами; добавьте его в последовательный pipeline `server/storage.py`, расширьте создание metric context в `server/analysis.py` и доступность `/api/models`. Признаки модели храните независимо, не инвалидируя 3DDFA. Для новых оверлеев понадобится вернуть настоящие точки в общей системе и добавить управление ими. 2D-точки нельзя выдавать за измеренные 3D. Автоматическое появление **метрик** уже реализовано; автоматическое подключение произвольной новой **модели** — отдельная интеграция.

## Данные, кэш и воспроизводимость

- `data/groups/` — файлы; `data/library.json` — исходные имена, даты, группы, ручные углы.
- `cache/{photo_id}/features-{key}.npz`, `meta.json` — реальные результаты, SHA исходника, seed, версия/веса/выравнивание/runtime.
- `cache/{photo_id}/metrics.json` — независимые ключи метрик; `ocular-detection.json`, `ocular-manual.json`, `ocular.json` — версия landmarks и ручные исправления; `cache/projections/` — проекции с параметрами/seed.
- `exports/*.mp4` и соседний JSON — параметры, источники и конфиги. `data/jobs.json` — история задач; незавершённые при рестарте помечаются отменёнными.
- Крупные веса: `.cache/models/3ddfa_v3/` (не сохраняются снапшотом Arena, восстанавливаются скриптом). Установленные библиотеки и web/dist тоже требуют восстановления.
- Приватные фото не отправляются во внешние inference API. Они хранятся в этой среде; HTTP-доступ к приложению не имеет собственной авторизации. Не публикуйте preview как защищённый многопользовательский сервис без аутентификации.

## Проверки

```bash
python -m pip install pytest
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 NUMBA_NUM_THREADS=2 python -m pytest tests -q
(cd web && npm run build)
# Production должен уже работать на 5173. Нужны Playwright Chromium + install-deps.
(cd web && node acceptance-production.mjs)
# Дополнительная dev-проверка (включая 90 дорожек) требует Vite, а не production:
(cd web && node acceptance-browser.mjs)
# Из корня atlas: фоновые задачи, 3D-проекции и MP4:
OPENBLAS_NUM_THREADS=2 python scripts/acceptance_jobs.py
```

**Финальная приёмка:** 37 backend/API-тестов, 21 production/WebGL/CPU UI-проверка, 15 фоновых/job-проверок; browser errors отсутствуют. Ранее dev-приёмка: 15 проверок, включая виртуализацию 90 дорожек. Три новых MP4 (distance / identity / normal, внешний эталон, custom-палитра, сглаживание) декодированы как H264, 256×256, 8 FPS, по 5 кадров. Настоящий UMAP проверен на 10 реконструкциях, не на малом PCA-fallback.

Отчёты: `ENV_REPORT.md`, `DECISIONS.md`, `reports/verification-summary.json`, `reports/pytest-v2.log`, `reports/production-acceptance.json`, `reports/browser-acceptance.json`, `reports/jobs-acceptance.json`, `reports/ocular-sample.json`, `reports/ocular-local-sample.md`. В доступной локальной библиотеке: пять пользовательских фото в одной общей группе и пять synthetic demo; стартовый выбор группы автоматически исключает демо. Ocular sweep обработал 5/5, ни одно фото не проходит строгие yaw/pitch ±8°; три раздельные сравнительные группы пока не размечены. Google Drive search не обнаружил shared `groups` папку или угол-таблицу; они не были импортированы.

## Границы первого этапа

Пока нет Drive API/rclone, AdaFace/FAN-инференса, межмодельных соответствий, texture in CPU fallback, 2D-морфинга, CUSUM/PELT. Есть настоящий 3D-морфинг, CPU MP4, MAD-порог, реальные α_id и три геометрические метрики. Тепловая карта показывает разницу оценок модели, не медицинское заключение и не проверку личности.

Официальный код 3DDFA-V3 и его лицензия находятся в `vendor/3DDFA-V3`. Отдельно проверяйте условия использования весов и BFM-ассетов, особенно перед коммерческим использованием.

### Quick start on the canvas
The dismissible **Быстрый старт** card links directly to the photo source, 3D scene, and metrics timeline. It reports the current photo/cache counts and can be dismissed without changing the saved workspace. Reopen onboarding by clearing the browser's `atlas-guide-dismissed` localStorage key.

### Canonical UV photo texture
The WebGL viewer now bakes the source photo into the original 3DDFA template UV atlas triangle by triangle and retains the model's canonical UV coordinates. Per-photo atlases are lazy and cached in `cache/{photo_id}/`; source pixels outside the projected face remain unobserved rather than being clamped to image borders. This adapts the affine UV-baking approach in the linked `uv_module` project. Beauty-fill and synthetic symmetry content are not used for analysis.

### Optional mesh-noise calibration
In 3D heat-map settings, open **Калибровка шума меша** and assign 2–3 ready non-demo views to each of seven participants. A per-vertex within-participant repeatability threshold is computed and can be subtracted from geometric distance heat values (values floor at zero). It does not affect α_id or normal displacement. This is an empirical repeatability baseline, not pure model error; pose, expression, image quality, and real variation may contribute. Raw uncorrected heat remains available. The current local library does not contain the required seven-person sample, so calibration must wait until those photos are imported.
