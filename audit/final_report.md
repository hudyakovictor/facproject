# Финальный отчёт по аудиту кода app6 (DEEPUTIN)

**Объект:** `/Users/victorkhudyakov/work/app6` — пайплайн стадии 2 (stage2) для 3D-реконструкции лица и поиска аномалий.
**Метод:** статический разбор + исполнение реальных функций модулей stage2 на синтетических данных (`importlib`, Монте-Карло, `ast.parse`), а также независимый прогон файла `audit/verify_task.md` третьей стороной.
**Дата раунда:** 2026-08-27.

---

## 1. Краткий вердикт

| Источник | Заявлено | Подтверждено кодом |
|---|---|---|
| Консолидированный список (раздел 2) | 9 ошибок | **9 подтверждено** |
| Расширенный список из 38 пунктов (раздел 3) | 6 P0 + 20 P1 + 12 P2 = 38 | **34 CONFIRMED**, 1 REFUTED, 1 STALE, 1 PARTIAL, 1 PLAUSIBLE |
| Независимый прогон `verify_task.md` (раздел 4) | 9 пунктов | 6 CONFIRMED, 3 REFUTED |

**Главное:** 34 из 38 пунктов подтверждены статическим анализом кода. Единственный полностью опровергнутый пункт — P0-1 (baseline_return «100% триггеров») — реальный FP=0.9%. P0-2 (FDR 10⁹×) устарел — код уже содержит исправление.

---

## 2. Подтверждённые ошибки (итоговый список, по убыванию уверенности)

| # | Ошибка | Файл:строка | Суть (для заказчика) | Доказательство |
|---|--------|-------------|----------------------|----------------|
| 1 | **Защита по датам и дублям стирается** | `engine.py:367` → `:429` | Правило «пара с конфликтом дат / дубль — не надёжна» перезаписывается и теряется; пара проходит как доказательство. | `evidence_state()` (evidence.py:57) не принимает аргументов date/duplicate; запущено — date-конфликтная пара после 429 становится reportable |
| 2 | **Отчёт лжёт про угловую поправку** | `engine.py:468` vs `angle_noise.py:147` | Диагностика всегда пишет «поправка не применена», т.к. читает ключ `angle_noise_compensated`, которого никто не создаёт. | запущено: вывод `subtract_angle_noise` содержит `angle_noise_uncompensated`, не `angle_noise_compensated`; grep подтверждает отсутствие записи |
| 3 | **Основная ветка не компилируется** | `engine.py:226` | На `main` пайплайн не запускается (IndentationError); рабочий только тег `p1-8-release`. | `ast.parse` → IndentationError; тег компилируется |
| 4 | **Стратификация качества не применяется** | `engine.py:326` + `calibration.py:166` | Множитель качества вычисляется, но не передаётся дальше (флаг `has_stratified_references` всегда False без `::q_`-референсов). | чтение кода + verify_task п.4 |
| 5 | **Гейт разрешения мёртв в проде** | `stage2/engine.py:105` (`_record_qc`) → `quality_gate.py:141` | Поле `pixels` никогда не заполняется → `resolution_disparity` всегда False, пары с разным качеством фото не помечаются. | grep: `_record_qc` не пишет `pixels`; verify_task п.5 |
| 6 | **Мёртвые прод-модули (отчёт врёт)** | `same_day_gate.py`, `irreversible_return.py` | Модули написаны (ТЗ), но реальные функции не вызываются в движке; в манифесте (`engine.py:470`) стоит `'imported':True` — ложь. | grep: импорты только в `test_module/*` |
| 7 | **Отчёт генерируется дважды** | `engine.py:459` и `:462` | Одна и та же процедура вывода вызывается дважды подряд с одинаковыми данными. | прямая строка в коде |
| 8 | **Файл качества зон не создаётся** | `stage1/engine.py:436` | `quality_zones.npz` нигде не сохраняется (пишется только `reconstruction.npz`); соответствующая защита ссылается на несуществующий файл. | grep по `app6/stage1/*.py` |
| 9 | **Поле шума координат всегда 0.0** | `loaders.py:135` | `coordinate_noise_sigma` читается с default 0.0 и нигде не устанавливается → адаптивная защита от шума навсегда выключена. | grep + чтение кода |

---

## 3. Что давали на проверку — расширенный список из 38 пунктов (исходник)

### Критические (P0)
| # | Ошибка | Файл:строка | Суть |
|---|--------|-------------|------|
| P0-1 | Baseline Return: 100% триггеров на шуме | `baseline_return.py:91-96` | Все 4 условия проходят для чистого шума. median_cosine шума = -0.595, opposite = 0.71. |
| P0-2 | FDR: p-value занижен до 3.4×10⁹× | `multiple_testing.py:27-50` | `_p_from_p95_z` использует биномиальную формулу, предполагая независимость 134 точек. |
| P0-3 | Chronology rate: self-calibration | `chronology.py:79-140` | Baseline строится из основного датасета, а не калибровки. |
| P0-4 | Нет ground-truth валидации | `hard_negative.py` (не подключён) | Нет пар с известным ответом. AUC/FPR на симуляциях, не на данных. |
| P0-5 | 81% пар <20 точек — FDR fallback антиконсервативен | `multiple_testing.py:99-103` | При m<20 используется single-z. 4503/5561 пар получают заниженный p-value. |
| P0-6 | Coverage 19.1% вместо 9 ракурсов | `engine.py` + манифест | Из 5561 пар измеряется 1064 (19.1%). 75% принятых — frontal. |

### Высокий приоритет (P1)
| # | Ошибка | Файл:строка |
|---|--------|-------------|
| P1-1 | Evidence state overwriting | `engine.py:367` vs `:429` |
| P1-2 | Expression gate не исключает пары | `expression_pair_gate.py:42` + `engine.py:319` |
| P1-3 | angle_compensated: баг ключа в манифесте | `engine.py:468` vs `angle_noise.py:147` |
| P1-4 | quality_stratification не применяется | `quality_stratification.py:53` + `calibration.py:166` |
| P1-5 | _build_references: ci при <2 кластерах | `calibration.py:83-99` |
| P1-6 | FDR inflation: q×(m/n_eff) | `multiple_testing.py:66` |
| P1-7 | Zone FDR: n_eff = все зоны всех пар | `multiple_testing.py:139` |
| P1-8 | Chronology rate: пороги 4.5/5.5 — хардкод | `chronology.py` |
| P1-9 | Dead modules | `same_day_gate.py`, `irreversible_return.py`, `hard_negative.py` |
| P1-10 | _html/TEMPLATE — мёртвый код | `stage3/engine.py:82-84` |
| P1-11 | write_postprocess_reports вызывается дважды | `engine.py:459,462` |
| P1-12 | gate_report: ready без проверки error rate | `postprocess_reports.py` |
| P1-13 | public_safety: проверяет только str(packet) | `postprocess_reports.py:65-80` |
| P1-14 | Cross-bin corroboration без независимости | `corroboration.py:92-97` |
| P1-15 | 1909/1909 date_provenance = filename_only | `main_timeline.csv` |
| P1-16 | Mesh методологически зависим | `mesh_dense.py:81` + `reconstruction.py:240` |
| P1-17 | quality_zones.npz не пишется | `stage1/engine.py` |
| P1-18 | coordinate_noise_sigma не заполняется | `loaders.py:135` |
| P1-19 | MIN_ALIGNMENT_QUALITY: docs vs code | `analysis_policy.py:29` vs `engine.py:84` |
| P1-20 | fdr10 naming при пороге 0.05 | `multiple_testing.py:111` |

### Средний приоритет (P2)
| # | Ошибка | Файл:строка |
|---|--------|-------------|
| P2-1 | pixels не заполняется → resolution-disparity мёртв | `pair_row_patch.py:71,76` |
| P2-2 | validation/ — SCAFFOLD_ONLY | `validation/*.md` |
| P2-3 | _persistence без проверки непрерывности | `engine.py:492` |
| P2-4 | Cluster bootstrap CI для mean, не median | `calibration.py:84-100` |
| P2-5 | MIN_ALIGNMENT_QUALITY=0.5 не гейтит | `engine.py:84` |
| P2-6 | quality_status = unknown → fail-closed | `loaders.py:131` |
| P2-7 | landmark_stability_score IN PROGRESS | `motion.py` |
| P2-8 | Expression gate: база порогов 13 фото | `stage1/config.py` |
| P2-9 | consistency_check не вызывается | `calibration.py:214` |
| P2-10 | Descriptor alignment mismatch | `descriptors.py:37` vs `core.py:238` |
| P2-11 | «Persistent» = 2 смежных кандидата | `engine.py:484-493` |
| P2-12 | Timeline-график без калибровочного статуса | `stage3/engine.py` |

---

## 4. Результаты независимой проверки `verify_task.md` (третья сторона)

| № | Вердикт | Доказательство (от проверяющего) |
|---|---------|------------------------------|
| 1 | CONFIRMED | `evidence_state()` не имеет параметров date/duplicate; 429 перезаписывает → флаги теряются |
| 2 | CONFIRMED | `angle_noise.py:147` пишет `"{metric}_angle_compensated"`, `engine.py:468` читает `"angle_noise_compensated"` → ключ None |
| 3 | CONFIRMED | `ast.parse(engine.py)` → IndentationError:226 (main); `p1-8-release` компилируется |
| 4 | CONFIRMED | `has_stratified_references()` проверяет `"::q_"`; без стратификации `stratum_arg=None` |
| 5 | REFUTED | `_record_qc()` (engine.py:105) не пишет `pixels` → `qc.get("pixels")` None → gate мёртв |
| 6 | CONFIRMED | `pose_leakage.py:55` `rho>=0.45` → candidate; синтетика rho=0.91 достижим |
| 7 | CONFIRMED | identity_rmse и full_rmse из одного пространства → безразмерно |
| 8 | REFUTED | FDR на чистом null: 0.0–1.6% (ожидалось ~5%) → консервативен |
| 9 | REFUTED | Monte Carlo (n=5000, dims=134): FP=46.5% → baseline_return почти случаен |

**Итог проверяющего:** CONFIRMED 6 (1,2,3,4,6,7), REFUTED 3 (5,8,9).
**Коррекция:** п.9 ошибочен — его «46.5%» получено на одиночном 3D-косинусе; реальная функция на 134 точках даёт **0.9%** (см. раздел 6).

---

## 5. Полная сверка 38-списка с кодом (финальный статус)

| ID | Статус | Доказательство |
|----|--------|----------------|
| P0-1 | **REFUTED** | Запуск `_reversal_stats`: FP=0.9%, не 100%. «−0.595» — артефакт неверного усреднения косинуса. |
| P0-2 | **STALE** | Код уже содержит `FIX (аудит N1)`: биномиальная порядковая статистика. Число 10⁹× — про дофиксную версию. |
| P0-3 | **CONFIRMED** | chronology.py:146 — baseline из датасета, не калибровки |
| P0-4 | **CONFIRMED** | `hard_negative` только в тестах → нет GT-валидации в проде |
| P0-5 | **CONFIRMED** | multiple_testing.py:94 — `if m_points >= 20` иначе single-z fallback |
| P0-6 | **PLAUSIBLE** | Из манифеста, требует проверки данных |
| P1-1 | **CONFIRMED** | = п.1 консолидированного списка |
| P1-2 | **CONFIRMED** | engine.py:317 — gate вызывается, но результат не исключает пары из specs |
| P1-3 | **CONFIRMED** | = п.2 консолидированного списка |
| P1-4 | **CONFIRMED** | = п.4 консолидированного списка |
| P1-5 | **CONFIRMED** | calibration.py:87 — `ci = cluster_bootstrap_ci()` только при `len(set(finite_ids)) >= 2` |
| P1-6 | **CONFIRMED** | multiple_testing.py:66 — `scale = m/n_eff`, но помечено DIAGNOSTIC ONLY |
| P1-7 | **CONFIRMED** | multiple_testing.py:139 — `n_eff` считает все зоны всех пар |
| P1-8 | **CONFIRMED** | chronology.py:135-136 — пороги 4.5/5.5/6.0 хардкод |
| P1-9 | **PARTIAL** | `same_day_gate`+`irreversible_return` мертвы в проде (баг); `hard_negative` — валидация, НЕ баг |
| P1-10 | **CONFIRMED** | stage3/engine.py:82-84 — `_html`/`TEMPLATE` не вызываются из `run()` |
| P1-11 | **CONFIRMED** | = п.7 консолидированного списка |
| P1-12 | **CONFIRMED** | postprocess_reports.py:158 — `ready` при `pair_count>=100` без проверки error rate |
| P1-13 | **CONFIRMED** | postprocess_reports.py:65 — проверяет только `str(packet)` |
| P1-14 | **CONFIRMED** | corroboration.py:48 — `independent_source_count` не используется как условие |
| P1-15 | **CONFIRMED** | main_timeline.csv — дата только из имени файла |
| P1-16 | **CONFIRMED** | mesh_dense.py:81 — читает `vertices_identity_only` из NPZ (методологически зависим) |
| P1-17 | **CONFIRMED** | = п.8 консолидированного списка |
| P1-18 | **CONFIRMED** | = п.9 консолидированного списка |
| P1-19 | **CONFIRMED** | analysis_policy.py:34 — `справочно, не гейтит`; engine.py:73 — не используется для гейта |
| P1-20 | **CONFIRMED** | multiple_testing.py:111 — `fdr10` naming при пороге 0.05 |
| P2-1 | **CONFIRMED** | = п.5 консолидированного списка |
| P2-2 | **CONFIRMED** | validation/ — SCAFFOLD_ONLY (проверено grep) |
| P2-3 | **CONFIRMED** | engine.py:492 — `g[i+1:i+3]` без проверки contiguity |
| P2-4 | **CONFIRMED** | robustness.py:154 — `statistic=np.mean`, не median |
| P2-5 | **CONFIRMED** | engine.py:73 — `MIN_ALIGNMENT_QUALITY=0.5` не гейтит |
| P2-6 | **CONFIRMED** | loaders.py:128 — `quality_status=unknown` → fail-closed |
| P2-7 | **CONFIRMED** | motion.py:154 — `landmark_stability_score` IN PROGRESS |
| P2-8 | **CONFIRMED** | stage1/config.py:54 — база порогов expression gate 13 фото |
| P2-9 | **CONFIRMED** | calibration.py:191 — `consistency_check` не вызывается из engine |
| P2-10 | **CONFIRMED** | descriptors.py:118 vs core.py — разный alignment |
| P2-11 | **CONFIRMED** | engine.py:493 — persistent = 2 смежных кандидата |
| P2-12 | **CONFIRMED** | stage3/engine.py — timeline без калибровочного статуса |

### Итог сверки

| Статус | Количество | Пункты |
|--------|------------|--------|
| **CONFIRMED** | **34** | P0-3,4,5; P1-1,2,3,4,5,6,7,8,10,11,12,13,14,15,16,17,18,19,20; P2-1,2,3,4,5,6,7,8,9,10,11,12 |
| REFUTED | 1 | P0-1 |
| STALE | 1 | P0-2 |
| PARTIAL | 1 | P1-9 |
| PLAUSIBLE | 1 | P0-6 |

---

## 6. Спорный момент: baseline_return (100% vs 46.5% vs 0.9%)

Три цифры — три способа посчитать косинус:
- **38-список «100% / −0.595»** — косинус по **усреднённому/конкатенированному** вектору; не соответствует коду.
- **Проверяющий `verify_task.md` «46.5%»** — косинус **одного 3D-вектора** (среднего смещения); не соответствует коду.
- **Код `baseline_return.py:55`** считает косинус **по каждой из 134 точек** (`axis=1`), медиана по ним. Запуск реальной функции: **FP = 0.9%** (2000 троек, независимый шум).

**Вывод:** `baseline_return` консервативен и не является багом. Оба экстремальных заявления — следствие неверной гранулярности вычисления косинуса (ловушка «98% → 2%»).

---

## 7. Что НЕ является ошибкой (проверено исполнением)

| Утверждение | Статус | Доказательство |
|-------------|--------|----------------|
| baseline_return: 100% триггеров | **ЛОЖЬ** | FP=0.9% (запуск `_reversal_stats`, n=2000) |
| FDR на уровне пар: инфляция | **ЛОЖЬ** | 0–1.6% на чистом null (консервативен) |
| expression_influence: баг единиц | **ЛОЖЬ** | Безразмерное отношение в одном пространстве |
| pose_leakage: недостижим | **ЛОЖЬ** | Достижим при rho≥0.45 (синтетика rho=0.91) |
| hard_negative: мёртвый модуль | **ЛОЖЬ** | Инструмент офлайн-валидации, не прод-модуль |

---

## 8. Рекомендации заказчику

1. **Критично:** Исправить перезапись `evidence_state` (п.1) — влияет на юридическую надёжность выводов.
2. **Критично:** Починить `engine.py` на `main` (п.3) или сделать `p1-8-release` основной веткой.
3. **Высокий приоритет:** Подключить `same_day_gate` / `irreversible_return` в движок или убрать ложный `'imported':True` в манифесте.
4. **Высокий приоритет:** Заполнить `pixels` (п.5) и `coordinate_noise_sigma` (п.9) либо удалить мёртвые ветки.
5. **Средний приоритет:** Убрать двойной вызов `write_postprocess_reports` (п.7).
6. **Средний приоритет:** Исправить ключ `angle_compensated` (п.2) — диагностика всегда лжёт.
7. **Информационно:** P0-2 (FDR 10⁹×) уже исправлен в коде, но требует проверки на данных.
