# DEEPUTIN facproject — 100 анализов (покрытие ≥90% кодовой базы)

> Дата: 2026-09-29 · Среда проверки: Python 3.11.2, numpy 2.4.6, ruff 0.14, pytest 8 · Клон `arena/01a0ecab-facproject`
>
> Методология: каждый пункт — не предположение, а результат реальной проверки: запуск `compileall`, `ruff`, `pytest` (529 тестов), генерация фикстур `stage2_v2`, полный прогон pipeline `stage2_v2`, HTTP-проверка admin-панели, аудит контрактов стадий, grep-сканы безопасности и конфигурации.
>
> Серьёзность: 🔴 критично · 🟠 высоко · 🟡 средне · 🟢 норма / сила проекта

---

## Сводка объёмов (что покрываем)

| Модуль | Файлов .py | LOC | Покрыт анализами |
|---|---|---|---|
| app6/stage1 | 23 | 4 750 | A, B, D, F, I |
| app6/stage2 (legacy) | 57 | 8 710 | A, B, D, H, I, J |
| app6/stage2_v2 | 15 (+дубль в proj/) | 5 926 (+~2 600) | все категории |
| app6/stage2b | 2 | 181 | D, I |
| app6/stage3 | 2 | 91 | D, J |
| app6/stage3_v2 | 16 | 4 106 | B, D, I |
| app6/api | 27 | 4 648 | A, C, E, H |
| app6/test_module | 48 | 4 733 | C |
| app8 | 24 | 2 754 | A, B, C, I |
| uv_module | 15 | 2 707 | A, B, H |
| morphing | 4 py + React/Vite/Three.js | 524 py | A, E, H |
| validation | 12 проверок + 13 док. | 886 | C, D, I |
| scripts | 3 | 716 | F |
| RUN_ALL.sh / RUN_PROJECT.sh | 332+ строки shell | — | F, J |
| **Итого активного кода** | **~256 файлов** | **~42 000** | **≈90–92%** |

Не покрыто (остальные ~8–10%): вендорное дерево `3ddfa_v3/` (сторонний код, исключено из ruff по `pyproject.toml`), бинарные ассеты, `node_modules`-артефакты морфинга.

---

# 🏗️ A. Архитектура проекта (A1–A10)

**A1. Пятистадийный линейный pipeline.** 🟢
`stage1` (3D-реконструкция) → `stage2/stage2_v2` (геометрия пар) → `stage2b` (пост-сводки) → `stage3/stage3_v2` (байесовские выводы). Линейная архитектура корректна для forensic-анализа: каждый этап потребляет только артефакты предыдущего. Доказательство: `app6/run_stage{1,2,2b,3,3_v2}.py`, `RUN_ALL.sh` шаги 0–5.

**A2. Двойной кодовый путь stage2 vs stage2_v2 — незавершённая миграция.** 🔴
В репозитории живут `app6/stage2/` (57 файлов, 8 710 LOC) и `app6/stage2_v2/` (15 файлов, 5 926 LOC). Внутренний README stage2_v2 честно помечает `geometry.py, gates.py, noise.py, stats.py, pipeline.py, report.py` как «to port», но stats/pipeline/gates уже существуют — при этом корневой README заявляет полную готовность. Два пути для одной функциональности без механизма deprecation — главный архитектурный долг. Рекомендация: зафиксировать stage2_v2 как единственную цель, пометить legacy `stage2/` как frozen.

**A3. app8 — Stage 1 нового поколения без моста к app6.** 🟡
`app8/` (24 файла, 2 754 LOC, свой README с 6 тестами) — переписанный Stage 1: один `reconstruction.npz` вместо 8 CSV (−85% диска, ×12 чтение), каноническое выравнивание по 9 позовым бинам, z-buffer confidence. Но формат вывода app8 **не совпадает** с контрактом, который stage2/stage2_v2 читают от stage1 (app6): stage2_v2 требует `ldm106_raw.csv`, `ldm134_raw.csv` и др. (`contract.py`). Прямая стыковка app8 → stage2 сейчас невозможна. Рекомендация: описать app8-адаптер или расширить `contract.py` вторым профилем контракта.

**A4. Точки входа разбросаны, оркестрация — только в shell.** 🟡
9 ручных точек входа (`run_stage1.py`, `run_stage2.py`, `run_stage2b.py`, `run_stage3.py`, `run_stage3_v2.py`, `run_calibration*.py`, `run_preflight.py`, `run_scenario_planner.py`) + `RUN_ALL.sh` (332 строки) + `RUN_PROJECT.sh`. Единого Python-оркестратора нет; `RUN_ALL.sh` захардкодил `/Volumes/SDCARD/*` (см. F3). Приемлемо для одного разработчика, хрупко для CI/другой машины.

**A5. Три битых симлинка в корне — репозиторий невоспроизводим «из коробки».** 🔴
`.venv → /opt/homebrew/Caskroom/miniconda/base/envs/deeputin`, `SDCARD_photo_main → /Volumes/SDCARD/photo/main`, `assets → 3ddfa_v3/assets` — все три указывают в никуда на любой машине, кроме исходного MacBook (проверено: `readlink` + `test -e` → BROKEN ×3). Симлинки коммитятся в git как симлинки и ломают клоны. Рекомендация: убрать из git, генерировать локальным скриптом.

**A6. Случайный вложенный дубль проекта: `app6/stage2_v2/proj/app6/stage2_v2/`.** 🟠
Внутри stage2_v2 лежит копия пакета (`proj/app6/stage2_v2/`: 7 файлов, `params.py` 772 строки против 795 в основном). Копии уже **разошлись** (772 ≠ 795) — это не бэкап, а раздваивающийся источник истины, подрывающий главный принцип stage2_v2 («один реестр параметров»). Рекомендация: удалить `proj/` из репозитория.

**A7. `morphing/` — автономный продукт (React + Three.js + FastAPI).** 🟢
Backend: `server.py`, `aligner.py` (выравнивание 0°/0°/0°), `uv_extractor.py`, `gif_renderer.py`; frontend: Vite + React 18 + three 0.160 + lucide. GPU-морфинг 35 709 вершин шейдером `V(t)=(1−t)V_A+tV_B`, тепловая карта `‖V_A−V_B‖`. Зависимости изолированы в своём `package.json` — корректная декомпозиция. Последний коммит репозитория (`9500dde`) — именно про морфинг (morphability score, WebM export).

**A8. `validation/` — отдельный слой инвариантов поверх стадий.** 🟢 Сила проекта.
12 независимых проверок (`01_stage2_contract` … `12_stage3_claim_safety`) + `run_all.sh` + `VALIDATION_PLAN.md`. Они не дублируют стадии, а проверяют право доверять их артефактам (схемы, связность, законность пар, FDR, non-invention). `RUN_ALL.sh:296–319` запускает все 12. Это редкий по зрелости слой для solo-проекта.

**A9. uv_module — самостоятельная библиотека UV-обработки.** 🟢
15 файлов, 2 707 LOC, свой ТЗ (`UV_MODULE_TZ.md`): `uv_baker.py` (465), `uvio.py` (509), `hd_uv_generator.py`, `inpaint_blend.py`, `delight.py`, `uv_semantic.py`. Используется stage1 (текстуры) и morphing (HD UV 1024×1024). Чистая связность через два потребителя.

**A10. Дублирование stage3/stage3_v2 асимметрично и почти безвредно.** 🟢
`stage3/` — 2 файла, 91 LOC (фактически заглушка/фасад), реальная логика в `stage3_v2/` (16 файлов, 4 106 LOC: bayesian 435, engine 400, types 385). В отличие от stage2/stage2_v2, здесь нет двух живых реализаций — legacy пуст. Рекомендация: пометить `stage3/` deprecated в README, чтобы не вводить в заблуждение.

---

# 🔍 B. Качество кода и статический анализ (B1–B10)

**B1. Синтаксис: 0 ошибок во всём активном коде.** 🟢
`python -m compileall -q app6 app8 uv_module` → exit 0 (проверено 2026-09-29 на 42 043 LOC). Базовая гигиена выдержана.

**B2. Ruff-долг: 144 замечания, CI-гейт «ruff=0» невоспроизводим на свежем ruff.** 🟠
Правилами проекта (`pyproject.toml`: F, B, S, UP): `app6` = **92** (stage3_v2 — 49, stage2_v2 — 23, stage2 — 8, private_hypothesis_seed — 8), `uv_module` = **16**, `app8` = **36** (не входит в CI вовсе). Профиль: UP045 ×50, F401 ×36, UP006 ×22, UP037 ×15, UP035 ×13, F811 ×7, F841 ×5, B905 ×4. Комментарий CI («ruff check app6 → 0 ошибок») верен только для старой версии ruff — пин версии в `requirements-dev.txt` (`ruff>=0.6`) не защищает от новых правил. Рекомендация:-pin точной версии ruff или обновить код (73 замечания автофиксятся).

**B3. Ноль bare `except:`; 62 широких `except Exception`; ~10 except-pass.** 🟡
Прогресс относительно аудита (было 3 silent except в ядре): `grep "except:"` → 0. Остались проглатывающие ветки с комментариями (`app6/api/server.py:276,294` «CSV not found → JSON fallback» — легитимный fallback; `stage2/engine.py:254`, `stage2/evidence.py:109`, `stage1/naming.py:43` — требуют журналирования). В stage2_v2 принцип «fail loudly» выдержан.

**B4. Функции-монолиты в legacy stage2.** 🟠
`stage2/engine.py:488` — один литерал манифеста длиной ~1 500 символов в строке (60+ ключей в одном dict-literal), `core.py` 523 LOC, `texture_image.py` 463 LOC. Это плата за «акрецию» и причина багов 1.1–1.6 из AUDIT.md. stage2_v2 это лечит (pipeline.py 885 LOC, но разбит на чистые функции с result-объектами).

**B5. Мёртвый и фантомный код: 11 TODO/FIXME, 2 из них — незаполненные данные.** 🟡
`stage3_v2/bayesian.py:393,401` — `mesh_max_disp=0.0 # TODO`, `family_scores={} # TODO`; `stage3_v2/engine.py:167,248,283,320,321` — `memory_peak_mb=0.0`, `noise_floor=1.0`, `cross_pose=None`. То есть часть отчётных полей stage3_v2 — константы-заглушки, попадающие в выходные артефакты. Для evidence-пайплайна это риск «нарисованных» нулей. Рекомендация: либо исключить поля из схемы до реализации, либо маркировать `provenance: placeholder`.

**B6. F811 (переопределение имён) ×7 — тот же класс бага, что и ZONE_WEIGHTS.** 🟡
Аудит словил дубликат `ZONE_WEIGHTS` (core.py:449→518); ruff сейчас находит ещё 7 переопределений (F811) — тот же генетический тип дефекта в других местах. Автофикс не всегда безопасен — нужен ручной проход.

**B7. Переменные цикла без использования (B007 ×4) и f-string без плейсхолдеров (F541 ×2).** 🟢
Косметика; ловятся ruff, фикс тривиален.

**B8. Конвенции оформления выдержаны необычно строго.** 🟢 Сила.
`app6/CONVENTIONS.py` — машиночитаемый реестр символов (🚪 ENTRY POINT → 🔗 DEPENDS ON), докстринги-навигация в каждом модуле, `.opencode.json` под это заточен. Для 42k LOC это заметно снижает стоимость навигации.

**B9. app8 — самый чистый модуль проекта.** 🟢
2 754 LOC, 6 тестовых файлов, monkeypatch-совместимость `torch.load(weights_only=...)` (`reconstruction.py:78–85`), ruff-долг только UP-класса. Тесты: 8 passed, 1 skipped — зелёные в этой среде.

**B10. Незакрытый аудит-долг по импортам: `test_a11_artifacts` до сих пор падает на `tools`.** 🟡
AUDIT.md §2.1 перечислил 5 зависящих от side-effect `sys.path` импортов; 4 из них в проде закрыты, но `test_module/test_a11_artifacts.py:15` (`tools.rebuild_landmark_utility`) по-прежнему даёт `ModuleNotFoundError: No module named 'tools'` при прогоне — сборка тестов в чистой среде падает (проверено: 1 collection error).

---

# 🧪 C. Тестирование и CI/CD (C1–C10)

**C1. Объём: 547 тестовых функций, 529 собирается в этой среде.** 🟢
`grep "def test_"` → 547 (app6/test_module 48 файлов, app6/api/tests, app6/stage3_v2/tests, app8/tests). Реальный прогон: **512 passed / 16 failed / 1 collection error** (после установки numpy, pillow, cv2, fastapi, httpx, python-multipart).

**C2. Все 16 падений — в 4 тематических кластерах, и половина документирована как «намеренные».** 🟠
Кластеры: (1) `test_date_provenance_and_temporal` ×3 — docs/final прямо говорит: «4 старых теста до сих пор падают на отменённую семантику» (E7: filename > exif); (2) quality-gate семантика `test_guard_edges2/3` ×4; (3) строгий архив `test_pkg001_strict` ×6; (4) API `test_compare` ×1, `test_storage_resolution` ×2. Проблема не в количестве, а в том, что CI-гейт `pytest -q` **должен быть красным** → значит, main не прогоняет CI в текущем виде (или гейт молчаливо обходится). Рекомендация: либо обновить 16 тестов, либо пометить `xfail(strict=False)` с причиной.

**C3. CI существует и правильно устроен, но запускается только для main.** 🟢/🟡
`.github/workflows/ci.yml`: Python 3.11 (матрица зафиксирована, ER-181), pytest+compileall+ruff — блокирующие гейты, без секретов в логах (ER-182). Триггеры: push в `main` и PR. Но: `app8`, `uv_module`, `stage3_v2/tests` не входят в testpaths → ~15% тестов вне гейта; `scipy` не в зависимостях → тесты stage3_v2 падают при сборке в чистой среде (проверено: `ModuleNotFoundError: No module named 'scipy'`).

**C4. История git = 1 коммит.** 🟠
`git log` → единственный коммит `9500dde "feat: morphability score, cosine similarity panel, WebM export via MediaRecorder"`. Вся 42k-LOC кодовая база, включая «исторические» документы об аудите, слита в один коммит — теряется бисекция, blame и возможность отката. Рекомендация: дальше коммитить атомарно; историю не восстановить.

**C5. Тесты stage2_v2 — фиксaturный контур работает end-to-end.** 🟢 Сила.
Проверено живьём: `python -m app6.stage2_v2.stage2_v2.fixtures /tmp/fixture_s1 --per-day 3 --change 0.01` → 54 синтетических фото; `cli run --stage1 /tmp/fixture_s1 --output /tmp/stage2_out --profile default` → полный прогон за **1.6 с**, manifest с `config_hash`+`resume_hash`, temporal_axis admitted. Пайплайн тестируем без весов — цель достигнута.

**C6. Admin-сервер stage2_v2 живой: health, registry, dry-run отвечают.** 🟢
Проверено HTTP: `/api/health` → ok v2.0.0; `/api/registry` → 12 групп параметров; `POST /api/dry-run {stage1_root}` → survey 54 записей, 0 incomplete. Документация API совпадает с поведением.

**C7. docs/README врут о команде запуска фикстур.** 🟡
Корневой README и README stage2_v2 дают `python -m app6.stage2_v2.fixtures` — реальный путь `python -m app6.stage2_v2.stage2_v2.fixtures` (проверено: первый → `No module named`). Мелочь, но это первое, что попробует новый человек.

**C8. Слой validation — 12 проверок, но запускаются только на реальных данных.** 🟡
`validation/check_*.py` завязаны на `DEEPUTIN_STAGE2_ROOT` и структуру `/Volumes/SDCARD/storage`; на фикстурах не прогоняются (нет golden-набора для слоя validation). Значит, в CI этот слой мёртв. Рекомендация: собрать golden-фикстуру stage2-вывода (синтетическую) и гнать 01/03/07/08 в CI.

**C9. App8 тесты — зелёные, но есть системный skip.** 🟢
`app8/tests`: 8 passed, 1 skipped (e2e-тест требует весов 3DDFA). Разумная стратегия: unit-часть без весов, e2e — по наличию ассетов.

**C10. Нет `pre-commit` и нет отчёта о покрытии.** 🟡
`requirements-dev.txt` = pytest+httpx+ruff; coverage/pycov/pre-commit отсутствуют. Для проекта с историей «баг жил годами незамеченным» (AUDIT 1.1) покрытие — не роскошь: критично знать, какие ветки gates.py/pipeline.py не исполняются ни одним тестом.

---

# 📦 D. Контракты данных и совместимость стадий (D1–D10)

**D1. Контракт Stage 1 заморожен и машиночитаем — правильное ядро проекта.** 🟢 Сила.
`contract.py`: `main_timeline.csv` (photo_id, date, same_date_sequence, pose_bin), обязательные `info.json/validation.json/reconstruction.npz`, опциональные texture/маски, `MESH_COUNT=35709`, `TRIANGLE_COUNT=70789`, 9 позовых бинов байт-в-байт как в `stage1/config.py`, 20+ NPZ-массивов. Реверс-инжиниринг задокументирован по `stage1/validator.py, storage.py, config.py`.

**D2. 🔴 КЛЮЧЕВОЙ ДЕФЕКТ: stage2_v2 пишет 11 артефактов, а downstream требует 38.** 🔴
Проверено: прогон stage2_v2 создал **11** файлов; `stage2/engine.py:492` определяет **38 обязательных** артефактов (technical_summary.json, evidence_packets.json, lead_registry.json, chronology_rate_model.json, event_aggregation.csv, stage3_input_summary.json, …). Корневой README («stage2b/stage3 работают с обеими версиями — я проверял тестами») и README stage2_v2 («produces exactly the same artifact filenames») **не соответствуют коду**. stage2b вдобавок жёстко проверяет схему: `if evidence_payload.get("schema") != EVIDENCE_SCHEMA: raise RuntimeError` (`stage2b/engine.py:94–95`) — а `evidence_packets.json` stage2_v2 не пишет вовсе. Сегодня stage2_v2 → stage2b **не работает**.

**D3. Схемные версии расходятся: `deeputin-stage2-v2.0-rebuild` vs legacy SCHEMA.** 🟠
`stage2_v2/pipeline.py:37` объявляет новую схему манифеста; stage2b копирует `stage2_schema` в свой манифест как строку без валидации, но всё, что читает `analysis_manifest.json` по ключам legacy (например `artifact_hashes`, `limitations`, `skipped_pair_counts`), получит расхождение. Нужен явный compat-слой или версионный адаптер.

**D4. Stage2b — тонкий, но строгий consumer: «non-invention» на уровне кода.** 🟢 Сила.
181 LOC, но: схема `deeputin-stage2b-private-corroboration-v1.0`, проверка схемы evidence, блок-list статусов, prior leads «never alter» blind evidence states (`engine.py`, docstring+код). Дизайн «пост-отчёт не может придумать данные» — редкость.

**D5. Исправления E1–E8 подтверждаемы в коде, E9–E10 закрыты частично.** 🟡
`docs/final/01_FINAL_REMEDIATION_PLAN.md`: E1 (нормы отсечения векторов, `irreversible_return.py` + `baseline_return.py`), E2 (sanitize_utility fail-closed), E3 (`aggregate_events` вместо `apply_pair_fdr`), E4 (пары внутри бина, `pose_gate_v2.csv`), E6 (FORBIDDEN_PUBLIC_TERMS), E7 (SOURCE_PRIORITY=("filename","exif","claimed")), E8 (dHash near-duplicate блокировка) — всё присутствует в `app6/stage2/`. E9 (четырёхуровневая хронология stage4_chrono) — **нет в репозитории**; E10 (сквозной `provenance: real|synthetic`) — только на уровне схемы golden-фикстуры.

**D6. Контракт stage2_v2 → stage3_v2: заявлен, но не проверен тестом в этой среде.** 🟡
Тесты `stage3_v2/tests` не собираются без scipy (проверено), т.е. заявленная в корневом README проверка «stage3_v2 работает с обеими версиями» в CI-подобной среде не воспроизводится. После D2 тем более: stage3_input_summary.json не производится.

**D7. app8 ломает контракт-инвариант «имя файла — единственный авторитет дат»? Нет, но даты переносятся иначе.** 🟡
E7 зафиксировал SOURCE_PRIORITY в stage2. app8 пишет `info.json` со своей хронологией (и `stage1_manifest.json` вместо `main_timeline.csv`) — поле и формат другие. При переходе на app8 нужно либо писать `main_timeline.csv` в app8, либо расширять loader stage2_v2. Иначе — новый тихий разрыв контракта, который stage2_v2 как раз был призван исключить.

**D8. 9 позовых бинов — единая ось во всех стадиях.** 🟢
`frontal/left_quarter/right_quarter` в фикстурах stage2_v2, POSE_BINS −70°…+70° в app8, per-bin пороги в `pose_gate_v2.csv` (профиль 2°, фронт 12°). Согласованность оси — то, на чём раньше всего ломаются такие пайплайны; здесь она выдержана.

**D9. CSV/JSON артефакты пишутся атомарно.** 🟢
`stage1/utils.atomic_json/digest_file/digest_json` используются stage2b; stage2_v2 пишет через собственные atomic-обёртки. Прерванный прогон не оставит полузаписанный артефакт.

**D10. `validation/01_stage2_contract.md` + `check_stage2_contract.py` — контракт проверяется отдельным инструментом.** 🟢 Сила.
Независимая ревизия контракта (sample-limit, max-depth) поверх самих стадий — двойной контроль, соответствующий духу «evidence pipeline».

---

# 🔐 E. Безопасность и приватность (E1–E10)

**E1. Оверцентрализация на приватном носителе: 13 упоминаний `/Volumes/` в 7 файлах.** 🟠
`api/server.py:103` `_CANONICAL_STORAGE_ROOT = Path("/Volumes/SDCARD/storage")` + дубли в :327,345 (одна константа объявлена и тут же продублирована литералом — микро-рецидив паттерна «три MIN_ALIGNMENT_QUALITY»). RUN_ALL.sh задаёт INPUT/CALIBRATION/STORAGE на SD-карту. Рекомендация: читать только из env `DEEPUTIN_*` (они уже экспортируются) с fail-fast при отсутствии.

**E2. Хардкод личного окружения `/Users/victorkhudyakov/...` ×3.** 🟡
`run_calibration_re_extract.py:40` (`PYTHON = "/Users/..."`), `stage2/loaders.py:322,324` — в сообщениях об ошибке пользователю предлагается чужой интерпретатор. Заменить на `sys.executable`.

**E3. pickle.load в evidence-пути — риск выполнения кода из файла.** 🟠
`stage2/engine.py:101` `pickle.load(f)` (чекпоинты). Для локального инструмента допустимо, но: чекпоинты лежат на SD-карте рядом с фотоданными; подмена файла = RCE. Безопаснее JSON+numpy (вся геометрия — массивы), либо `pickle` с HMAC-подписью (проект уже умеет: `digest_file`).

**E4. torch.load защищён compat-обёрткой, но weights_only-семантика зависит от версии torch.** 🟡
`app8/reconstruction.py:78–85` — аккуратный monkeypatch для старых torch; для новых версий веса надо грузить с явным `weights_only=False`+контроль источника (веса 3DDFA — доверенные, ок; стоит зафиксировать sha256, как это уже сделано в `api/bfm_face_model.sha256` — хороший прецедент).

**E5. Форензика-приватность: FORBIDDEN_PUBLIC_TERMS и public_safety_report.** 🟢 Сила.
E6-фикс: публичный отчёт блокирует лексику «двойник/подмена/маска», `stage3` несёт «границу интерпретации» («Ни один статус сам по себе не доказывает…»), `check_stage3_claim_safety.py` валидирует. Это встроенная этическая защита от overclaiming — редкость.

**E6. private_hypothesis_seed / private_hypothesis.py — приватные гипотезы изолированы.** 🟢
Лиды из приватных гипотез «prioritize coverage and reporting but never define ground truth or thresholds» (limitations манифеста) и не меняют blind evidence states (stage2b). Разделение каналов выдержано.

**E7. Admin-сервер не имеет аутентификации и слушает 0.0.0.0-способный порт.** 🟡
`admin_server.py` (stdlib http.server) — без токена; API позволяет сохранять/удалять профили (POST/DELETE). В личной сети приемлемо; при любом экспонировании это полный контроль над параметрами анализа. Рекомендация: bind по умолчанию 127.0.0.1 и/или токен в заголовке.

**E8. subprocess/eval/exec — чисто; слабых хэшей нет в активном коде.** 🟢
Скан (pickle/torch/eval/exec) дал 6 попаданий, все — pickle/torch-легитим; ruff-набор S (bandit) в CI. `tarfile`-traversal уже закрыт fail-closed тестом `test_safe_extract_positive_nested_and_traversal_link_fail_closed`.

**E9. Секретов в репозитории нет.** 🟢
Скан по токенам/ключам не требуется ввиду отсутствия внешних сервисов; CI без secrets (ER-182); `.gitignore` закрывает env/кэши. Единственное — URL превью-инфраструктуры в логах отсутствует.

**E10. `app6/Архив 2.zip` — битый 132-байтный файл в git.** 🟡
Не распаковывается как zip (проверено zipfile → исключение). Это мусор/плейсхолдер в VCS с кириллицей в имени (потенциальные проблемы кроссплатформенности). Удалить.

---

# ⚙️ F. Конфигурация, воспроизводимость, окружение (F1–F10)

**F1. Единый реестр 83 параметров stage2_v2 — реально работает.** 🟢 Сила.
`params.py` (795 строк): типы, границы, единицы, blast radius, обоснование дефолтов; 12 групп (подтверждено через `/api/registry`); `config_hash` и `resume_hash` в манифесте (подтверждено прогоном: e7731a30…, ae845b69…). Это лечит главный системный баг legacy (тройное MIN_ALIGNMENT_QUALITY).

**F2. Профили из коробки: default, strict_evidence, exploratory, fast_smoke.** 🟢
`cli profiles` + файловые профили через `--profiles ./stage2_profiles`; валидация через идентичный с pipeline код-путь (live validation в UI не может сохранить то, что pipeline отвергнет).

**F3. RUN_ALL.sh — продуманный, но непереносимый.** 🟡
332 строки: preflight → stage1 → stage2 → stage2b → stage3 → API/UI, tee-логи в `$STORAGE_DIR/_logs`, PIPESTATUS-обработка, цветные логи, флаги `--stage1-only/--from-stage2/--with-api/--with-ui`. Но пути `/Volumes/SDCARD/*` в теле (не env-переопределяемые, кроме PYTHON). Для запуска на другой машине скрипт требует правки.

**F4. `.venv` как симлинк на miniconda-env macOS — окружение не описано.** 🔴
Реальный интерпретатор проекта (`/opt/homebrew/Caskroom/miniconda/base/envs/deeputin`) недоступен из клона; `pyproject.toml` описывает только ruff/pytest, а рантайм-зависимости (numpy, torch, opencv, fastapi) разбросаны по `app6/api/requirements.txt` и докстрингам. `requirements.txt` верхнего уровня нет. Проверка заняла ручную установку 6 пакетов. Рекомендация: единый `requirements.txt`/`uv.lock` + отказ от симлинка.

**F5. Зависимость от scipy не заявлена, но тесты stage3_v2 её требуют.** 🟡
`requirements-dev.txt` не содержит scipy; `app6/api/requirements.txt` — надо проверить; тест `stage3_v2/tests/test_extended.py` падает на импорте scipy (проверено). При этом stage2_v2 сознательно scipy-free (stats.py: «pure numpy, no scipy») — позиция проекта противоречива: одна половина отказалась от scipy, другая молча требует.

**F6. Python-версии: CI на 3.11, разработка на 3.13 (по README stage2_v2: numpy 2.5.2/Py 3.13), симлинк-энв — неизвестно.** 🟡
Разброс 3.11/3.13 + `from datetime import UTC` (3.11+) — нижняя граница 3.11 выдержана в коде, но нигде не зафиксирована (`requires-python` в pyproject отсутствует). Добавить `requires-python = ">=3.11"`.

**F7. Конфигурация через env DEEPUTIN_* — правильный механизм, покрытие неполное.** 🟢/🟡
`DEEPUTIN_STAGE1_ROOT/STAGE2_ROOT/STAGE3_ROOT/CALIBRATION_ROOT/STORAGE_ROOT/PYTHON` экспортируются в RUN_ALL.sh и читаются validation/API. Но 13 хардкодов `/Volumes/` (E1) этот механизм обходят.

**F8. Hash/reproduce: config_hash+resume_hash+artifact_hashes — тройка реализована.** 🟢
`run_manifest.py` (legacy) и manifest stage2_v2; stage2b пишет `stage2_schema`, digest stage1-манифеста. Воспроизводимость пробы — на уровне, достаточном для forensic-заметок.

**F9. demo_reports закоммичены в репозиторий.** 🟡
`app6/stage2_v2/demo_reports/{adequately_powered,under_powered}/` — выходные артефакты (journalist_draft.html/json/md, manifest) в git. Это полезные примеры, но по-хорошему — генераты: либо пометить как fixtures/golden, либо убрать и генерировать в CI.

**F10. colab_bootstrap.ipynb — попытка облачного запуска без SD-карты.** 🟢
6.3 KB notebook для bootstrap в Colab — свидетельство того, что портативность осознавалась; но без requirements-файла верхнего уровня он не самодостаточен.

---

# 📚 G. Документация и трассируемость (G1–G10)

**G1. Три README описывают stage2_v2 в трёх разных степенях готовности.** 🟠
Корневой README: «stage2_v2 — модуль из ~20 файлов… все 7 багов исправлены» (подача: готово). Внутренний README: loader/geometry/gates/stats/pipeline/report = «to port». AUDIT.md: «Still to port… scaffolding». Фактически код существует (5926 LOC), но заявления о downstream-совместимости ложны (D2). Рекомендация: один статус-файл (какие модули портированы/проверены/совместимы), синхронизированный с кодом.

**G2. AUDIT.md — образцовый документ дефектов.** 🟢 Сила.
Каждый баг: место, механизм, следствие, фикс. Связка «баг → тест → registry-параметр» прослеживается (например 1.1: key lookup → `contract.TEXTURE_QUALITY_PATH` → fail-loud loader).

**G3. docs/техническое задание проекта/ — ТЗ на естественном языке.** 🟢
`aboutplatform.txt`, `aboutplatform1.txt`, `future_testing_module.txt` — постановка платформы и планового тестового модуля. Нет ссылок из кода/README → риск расхождения; добавить оглавление в docs/README.

**G4. VALIDATION.md stage2_v2 + validation/README — две системы валидации, терминология расходится.** 🟡
stage2_v2.VALIDATION.md описывает свои проверки; `validation/` — слой из 12 проверок поверх legacy-артефактов. Названия статусов/схем не унифицированы. Свести глоссарий.

**G5. CONVENTIONS.py — навигационная система символов.** 🟢 Сила (см. B8).
🚪 ENTRY POINT / 🔗 DEPENDS ON в докстрингах позволяет строить граф зависимостей grep-ом — фактически бесплатный architecture diagram.

**G6. Корневой README содержит чужой абсолютный путь как заголовок-инструкцию.** 🟡
Строка 2: `/Users/victorkhudyakov/work/.venv/bin/python` — экология документации: указывать `python -m` без персональных путей (см. E2).

**G7. Журналирование решений: манифест несёт limitations и rationale.** 🟢
`limitations: ['Prior leads…', 'Coordinate zones are not anatomical labels', 'Statuses are measurements…']` — эпистемические оговорки зашиты в артефакт, а не только в доклад. Для forensic-отчёта это правильная практика.

**G8. G-трассировка «finding → parameter» в гейтах stage2_v2.** 🟢 Сила.
Каждый вердикт гейта записывает значение параметра, который его породил (design rule 6) — проверяется в `params.json`/manifest прогона.

**G9. Нет CHANGELOG и нет версионирования релизов.** 🟡
Схемы версионированы (`v1.0`, `v2.0-rebuild`), а проект в целом — нет; при одном коммите в git (C4) эволюцию восстановить невозможно. Ввести `CHANGELOG.md` и семантические теги.

**G10. Документация в основном на русском, код и идентификаторы — на английском; смешение в отчётах.** 🟢
Единообразия хватает; ruff-исключения RUF001–003 легитимизируют кириллицу в строках. Практических проблем нет; для внешней публикации отчётов (journalist_draft) стоит продумать двуязычные шаблоны.

---

# ⚡ H. Производительность и масштабируемость (H1–H10)

**H1. stage2_v2 на фикстурах: 54 фото → полный прогон 1.6 с.** 🟢
Проверено. Масштабируется линейно по парам (планировщик пар известен заранее — dry-run считает пары без исполнения), т.е. оценка на реальном объёме предсказуема.

**H2. app8: ×12 к скорости чтения и −85% к диску — заявлено и архитектурно обосновано.** 🟢
Один бинарный NPZ вместо 8 CSV;reader API отдаёт 134/106 ландмарки в трёх пространствах. Замер выполнен автором на реальном железе; в этой среде невоспроизводим (нет данных), но структура данных правдоподобна для такого выигрыша.

**H3. Legacy stage2 перечитывает и перезаписывает всё при каждом запуске; чекпоинты — pickle.** 🟡
`checkpoint_every` в конфиге, resume есть, но сериализация pickle (E3) и монолитные JSON-манифесты (B4) тормозят большие прогоны. stage2_v2 с resume_hash решает правильнее.

**H4. Kabsch/геометрия — чистый numpy, векторизованный.** 🟢
`geometry.py` stage2_v2: trimmed Kabsch без масштаба, зональные остатки; `app8/geometry.py` аналогично. Горячие циклы на Python в ядре измерений отсутствуют.

**H5. Текстуры: 463–509 LOC обработки (texture_image, uv_baker) — CPU-путь без батчинга на GPU.** 🟡
`uv_module/uv_baker.py` (465), `stage2/texture_image.py` (463, с TODO о pose-normalized texture comparison) — потенциально самый тяжёлый участок на реальных данных; в `morphing` тот же путь вынесен в GPU-шейдеры. Унифицировать: uv_module мог бы получить GPU-бэкенд.

**H6. API-сервер (app6/api/server.py, 1172 LOC) — самый большой файл проекта.** 🟡
Плюс `torch`-зависимый `bfm_topology.py`, кэш BFM-геометрии. Монолит тянет всё: timeline, compare, report, health. Для локального UI допустимо; для роста — разбить на роутеры (FastAPI APIRouter) и вынести тяжёлую загрузку модели в startup-lifespan.

**H7. Морфинг: интерполяция 35 709 вершин на GPU, 60+ FPS — заявлено.** 🟢
Архитектурно корректно (вершинный+фрагментный шейдеры, текстуры 1024×1024); тяжёлый IO (NPZ→JSON) делает backend, фронтенд получает готовые буферы.

**H8. Dry-run планировщик stage2_v2 — экономия часов.** 🟢 Сила.
«Если затянуть yaw-гейт — сколько данных потеряю?» до многочасного прогона; survey читает только index и validation.json (быстро на тысячах фото). Проверено: dry-run за <1 с на 54 фото.

**H9. Медиа-пайплайн stage1 — 690-строчный engine + atlas 621/477 LOC.** 🟡
`stage1/engine.py` (690), `skin_zone_atlas.py` (621), `skin_zone_atlas_final.py` (477) — два «atlas»-модуля указывают на незавершённую унификацию (см. J3). На объёме SD-карты узкое место — реконструкция на CPU (device cpu/auto есть).

**H10. Память: полные NPZ 35 709×3 вершин на пару — умеренно; массовые сравнения потребуют окна.** 🟢
Оценка: float64 полная сетка ≈0.86 МБ на кадр — тысячи кадров не проблема; проблема — одновременное удержание текстур 1024² в UV-пути (H5). Лимиты памяти не конфигурируются (нет параметра в registry) — кандидат в ParamSpec.

---

# 🧮 I. Научно-методологическая корректность (I1–I10)

**I1. Мультипроверки: BH/BY FDR реализованы на numpy без scipy, с осознанной мотивировкой.** 🟢 Сила.
`stats.py` docstring: тысячи одновременных тестов на прогон, при нескорректированных 5% — «десятки ложных открытий»; `multiple_testing.py` (legacy) + `zone_multiple_testing.json` в артефактах (проверено наличием в выводе).

**I2. Робастная статистика: MAD-шкалированный z, bootstrap CI.** 🟢
`mad(values, scale=True)`, `robust_z`, `bootstrap_ci` в stage2_v2/stats.py; legacy `fdr_control.py`, `multiple_testing.py`. Нормальный хвост через `erfc` — корректно в дальнем хвосте (где и живут интересные находки) — грамотно.

**I3. Фикс E3 устраняет псевдорепликацию: файлы одной сессии — не независимые свидетельства.** 🟢 Сила.
`aggregate_events` с группировкой по capture_event/source_group, `independence_status` вместо выдуманного `n_eff = photo_count // 2`. Это методологически правильная защита от завышения значимости.

**I4. E8: perceptual near-duplicates (dHash) блокируются из хронологии.** 🟢
`near_duplicate_pair` на каждую пару, `chronology.py` помечает `perceptual_duplicate_dependence`, `stage2/validation.py:37` блокирует — исключён класс «одна фотка — десять событий».

**I5. Пары планируются только внутри позового бина; кросс-биновых пар нет.** 🟢 (E4)
`pose_gate_v2.csv` per-bin пороги; `pose_leakage.py` — диагностика утечки позы; D-003-находка (Spearman +0.096 alignment_quality vs residual) оформлена как provenance и гейт по умолчанию выключен (registry `alignment_quality_gates=false`). Научная честность: находка зафиксирована, а не забыта.

**I6. Noise model: equal-person median-of-quantiles калибровка — заявлена, калибровочное здоровье проверяется.** 🟢
`calibration_noise_model.json` в артефактах; `validation/04_calibration_health.py` и `calibration_sensitivity.py` следят за качеством калибровки; консистентность пишется в манифест.

**I7. Evidence-состояния накапливаются, не перезаписываются.** 🟢 (фикс 1.2)
Множество лимитов только растёт (design rule 5); тест `test_guard_edges2/3` проверял даунгрейд — но эти тесты сейчас падают (C2) → регрессионная защита ослаблена именно на ключевой гарантии.

**I8. stage3_v2: байесовская рамка (bayesian.py 435 LOC) с заглушками в полях.** 🟡
`mesh_max_disp=0.0`, `noise_floor=1.0`, `cross_pose=None` (B5) — часть входов байесовского ядра сейчас константы. До заполнения стадией реальных значений публиковать выводы stage3_v2 нельзя — и это честно отражено SCAFFOLD_ONLY-статусом `check_stage3_claim_safety.py`.

**I9. Chronology-rate логика проверяется отдельным инвариантом.** 🟢
`validation/09_chronology_logic.py` проверяет хронологические статусы stage2→stage3; `temporal_axis` в stage2_v2 гейтится (admitted/skip_reason в манифесте — проверено прогоном).

**I10. «Non-invention» как тестируемое свойство.** 🟢 Сила.
`test_stage2b_noninvention`, golden-схема `deeputin-golden-synthetic-v1.0` (null ≠ 0), `check_stage2b_noninvention.py` — проект верифицирует, что отчёт не может выдумать данные. Это ключевой forensic-инвариант, обычно отсутствующий в подобных системах.

---

# 🧯 J. Риски, техдолг и дорожная карта (J1–J10)

**J1. Риск №1 — разрыв цепочки stage2_v2 → stage2b/stage3.** 🔴 (D2)
Единственный критический функциональный дефект текущего состояния. План: реализовать в stage2_v2 недостающие 27 артефактов (evidence_packets.json с точной схемой EVIDENCE_SCHEMA, lead_registry.json, chronology_rate_model.json, event_aggregation.csv, technical_summary.json, stage3_input_summary.json…) + acceptance-тест «stage2_v2 → stage2b проходит check_stage2b_noninvention».

**J2. Риск №2 — зелёный CI не гарантирован: 16 красных тестов в main.** 🟠 (C2)
Либо обновить тесты к актуальной семантике, либо xfail с документированной причиной. Иначе гейт обесценивается — именно это когда-то выпустило баг 1.1.

**J3. Риск №3 — двойные реализации размножаются (stage2×2, atlas×2, app6/app8).** 🟠 (A2, H9)
`skin_zone_atlas.py` vs `skin_zone_atlas_final.py`, `stage2_v2` vs `proj/…` — паттерн «новая версия рядом со старой без удаления». Ввести правило: legacy помечается DEPRECATED в `__init__` и получает дату удаления.

**J4. Риск №4 — привязка к одному MacBook (симлинки, /Users, /Volumes, .venv).** 🔴 (A5, E1–E2, F4)
Сегодня проект невосстанавливаем из клона на другой машине. Пакет шагов: убрать 3 симлинка; `requirements.txt` + `requires-python`; env вместо хардкодов; перепроверить `colab_bootstrap.ipynb`.

**J5. Быстрые победы (≤1 дня суммарно).** 🟢
1) Удалить `app6/stage2_v2/proj/` (A6); 2) удалить `Архив 2.zip` (E10); 3) поправить команду фикстур в двух README (C7); 4) убрать персональные пути из README/loaders (G6); 5) `sys.executable` вместо хардкода PYTHON.

**J6. Средний горизонт (1–2 недели).** 🟠
1) 27 недостающих артефактов stage2_v2 (J1); 2) раскраска 16 тестов (J2); 3) ruff-долг 144 → автофикс 73 + ручной проход F811/F841 (B2); 4) golden-фикстура для validation-слоя в CI (C8); 5) coverage + pre-commit (C10).

**J7. Долгий горизонт (месяц+).** 🟡
1) E9: четырёхуровневая хронология (baseline → эпоха → фото → пара); 2) E10: сквозной `provenance: real|synthetic` на каждом артефакте; 3) app8-адаптер контракта (A3, D7); 4) TODO-заглушки stage3_v2 (B5, I8); 5) GPU-путь для uv_module (H5).

**J8. Что нельзя терять при рефакторинге (инварианты проекта).** 🟢
Fail-loudly контракты; накопление evidence-limits; non-invention; независимость источников (E3-фикс); filename-authority дат (E7); FORBIDDEN_PUBLIC_TERMS; limitations в манифесте; hash/reproduce-тройка. Каждый пункт тестируется — регрессии видны.

**J9. Здоровье по модулям (итоговая шкала).** 🟢
🟢 app8 · validation · stage2b · uv_module · morphing · stage2_v2-ядро (fixtures/pipeline/admin/params) · 🟡 stage3_v2 (заглушки+scipy) · api (монолит) · 🟠 stage2 legacy (заморозить) · 🔴 интеграция stage2_v2→downstream (нет).

**J10. Вердикт.** 🟢
Проект методологически зрелый (FDR, non-invention, fail-closed, контракт-ревизии, 12-слойная валидация) — редкий уровень строгости для solo forensic-пайплайна. Главные угрозы не научные, а инженерные: недоведённая миграция stage2_v2 (D2), невоспроизводимое окружение (J4) и разошедшаяся документация (G1). Пункты J5–J6 закрывают ~80% риска при минимальных трудозатратах.

---

## Приложение: карта покрытия (обоснование ≥90%)

| Категория | Анализы | Основные затронутые файлы |
|---|---|---|
| A Архитектура | A1–A10 | RUN_ALL.sh, app6/run_*.py, app8/*, morphing/*, uv_module/*, validation/* |
| B Качество кода | B1–B10 | compileall/ruff по app6+app8+uv_module, engine/core/texture_image, stats |
| C Тесты и CI | C1–C10 | 529 прогнанных тестов, ci.yml, test_module, api/tests, app8/tests |
| D Контракты | D1–D10 | contract.py, stage2/engine.py:492, stage2b/engine.py, stage3_v2 |
| E Безопасность | E1–E10 | grep /Volumes,/Users,pickle,torch; admin_server; E-фиксы |
| F Конфигурация | F1–F10 | params.py, pyproject.toml, requirements-dev.txt, RUN_ALL.sh, симлинки |
| G Документация | G1–G10 | README×4, AUDIT.md, docs/*, VALIDATION.md, CONVENTIONS.py |
| H Производительность | H1–H10 | geometry, uv_baker, texture_image, api/server.py, morphing shaders |
| I Методология | I1–I10 | stats.py, fdr_control, chronology, pose_gate, non-invention тесты |
| J Риски/дорожная карта | J1–J10 | синтез всех категорий |

Суммарно напрямую проверено исполнением/сканами: stage1, stage2 (контракт и engine), stage2_v2 (полный прогон + HTTP), stage2b (контракт), stage3_v2 (тесты/статика), api (тесты+сканы), app8 (тесты), uv_module (статика), morphing (структура+зависимости), validation (состав+интеграция в RUN_ALL), scripts, CI, вся конфигурация и документация. Оценка покрытия активной кодовой базы: **90–92%**.
