# 35 Дополнительных Анализов + Исправления (Раунд 2)

**Дата:** 2026-08-27
**Цель:** выявить все оставшиеся ошибки, недоработки и исправить что можно

---

## ИСПРАВЛЕНО В РАУНДЕ 2 (6 ошибок)

### Fix #9: gate_report — `ready` без проверки error_rate (P1-12)
**Файл:** `app6/stage2/postprocess_reports.py`
**Проблема:** `_write_gate_report()` ставил `ready_for_full_run_if_error_rate_ok` при `pair_count >= 100`, но НЕ проверял реальный error_rate. Система могла рекомендовать "ready" при 80% calibration_limited.
**Исправление:** Добавлена проверка `limited_fraction > 0.5 → blocked_high_limited_fraction`, `error_count > 0 → blocked_errors_present`. В отчёт добавлены `calibration_limited_fraction`, `error_count`, `limited_fraction`.

### Fix #10: public_safety — str(pkt) поверхностная проверка (P1-13)
**Файл:** `app6/stage2/postprocess_reports.py`
**Проблема:** `_write_public_safety()` проверял `str(pkt).lower()` — это включало имена полей (например `"mask"` в поле `"face_mask"`) и давало ложные срабатывания.
**Исправление:** Проверяются конкретные текстовые поля: `evidence_state`, `status`, `primary_zone_or_family`, `alternative_explanations`.

### Fix #11: chronology — exclusion reason не проверяет pose_leakage_limited
**Файл:** `app6/stage2/chronology.py`
**Проблема:** `_quality_exclusion_reason()` проверял `date_provenance_limited`, `near_duplicate_pair`, `quality_limited`, но НЕ проверял `pose_leakage_limited` и `residual_tilt_limited`. Пары с pose-dependent metrics попадали в chronology rate analysis.
**Исправление:** Добавлены проверки `pose_leakage_limited` и `residual_tilt_limited`.

### Fix #12: _persistence — 2 смежных кандидата = persistent (P2-11)
**Файл:** `app6/stage2/engine.py`
**Проблема:** Любая следующая пара со статусом кандидата превращала текущую в `persistent_geometric_change`. Два шумовых кандидата подряд давали "persistent".
**Исправление:** Successor должен иметь `p95_point_z >= 3.0` И быть кандидатом. Шумовой successor с p95=1.2 больше не создаёт "persistent".

### Fix #13: chronology rate — self-calibrating baseline (P0-3)
**Файл:** `app6/stage2/chronology.py`
**Проблема:** Rate thresholds калибруются из самих анализируемых данных. Это круговая логика, но код не предупреждал об этом.
**Исправление:** Добавлены поля `baseline_source: 'self_calibrating_from_analyzed_pairs'` и `baseline_warning` в output refs.

### Fix #14: consistency_check не вызывается (P2-9)
**Файл:** `app6/stage2/engine.py`
**Проблема:** `CalibrationModel.consistency_check()` написан, протестирован, но нигде не вызывался в production.
**Исправление:** Добавлен вызов `model.consistency_check()` после создания CalibrationModel. Результат записывается в `calibration_consistency.json` и добавляется в manifest.

---

## 35 АНАЛИЗОВ (что ещё найдено)

### БЛОК A: СТАТИСТИКА И FDR (8 анализов)

**A1.** `_p_from_p95_z` — биномиальная формула для зависимых точек.
*Статус:* Фундаментальная проблема. Замена требует permutation null на калибровке. НЕ исправляется одним патчем.
*Влияние:* p-value занижен на 5–9 порядков для коррелированных точек.

**A2.** Single-z fallback для <20 точек — 81% пар.
*Статус:* Антиконсервативен в 10–30×. Требует redesign: либо запретить статус для <20 точек, либо использовать эмпирический null.

**A3.** `apply_zone_fdr` — n_eff = все зоны всех пар.
*Статус:* Подтверждено. Должно быть per-pose-bin. Не исправлено (требует реструктуризацию).

**A4.** `dependence_inflation = m / n_eff` — эвристика, не теорема.
*Статус:* `n_eff = photo_count // 2`. Не имеет строгого обоснования.

**A5.** `fdr10` naming при пороге 0.05 — legacy alias вводит в заблуждение.
*Статус:* Подтверждено (P1-20). Поле `mt_significant_fdr10` на самом деле использует FDR 0.05.

**A6.** Zone FDR: `n_visible = n_eff` — одна переменная для двух разных целей.
*Статус:* `n_visible` в zone FDR = общее число измеренных зон, а не per-pair visible zones.

**A7.** BH коррекция: m = 5561 при 1058 реально проверяемых.
*Статус:* 4503 пары с p95=0.0 → p=1.0 попадают в знаменатель. Инфлирует q-values.

**A8.** `mt_role = "diagnostic_only"` — все FDR результаты diagnostic.
*Статус:* Correct by design. FDR не управляет evidence_state.

### БЛОК B: КАЛИБРОВКА (7 анализов)

**B9.** `CalibrationModel._use_count` — глобальный, порядок обработки влияет на matched-null.
*Статус:* При resume модель создаётся заново → продолженный прогон может отличаться.

**B10.** `_nearest` — MAX_REUSE=3, но при исчерпании fresh fallback на все candidates.
*Статус:* Когда "свежих" кадров нет, код снова выбирает из исчерпанных.

**B11.** `_pose_distance` нормализует на [15, 20, 15] — разные масштабы для pitch/yaw/roll.
*Статус:* Обосновано sensitivity ratios, но не документировано почему именно эти числа.

**B12.** Calibration null pairs: `pose_distance ≤ 2.5` vs production `pose_gap`.
*Статус:* Null шире production → завышение шума → консервативнее (меньше FP).

**B13.** `consistency_check` — простой heuristic, без ground truth.
*Статус:* Теперь вызывается (Fix #14). `consistency_flag = "ok"` при max_distance < 0.1.

**B14.** `references_excluding_dataset` (LOPO) — пересобирает из кэша, не пересчитывает.
*Статус:* Correct by design. Быстрее чем полный пересчёт.

**B15.** `balanced_reference` — person-level equal weight.
*Статус:* Правильное решение. 7 человек получают равный вес независимо от числа кадров.

### БЛОК C: КОД И ЛОГИКА (8 анализов)

**C16.** `expression_gate()` всегда возвращает `accepted=True`.
*Статус:* Подтверждено. Expression gate фактически не гейтит. Документация говорит "Expression больше не исключает пары".

**C17.** `_record_qc` — `pixels` теперь читается (Fix #6 round 1), но `quality_gate.py:resolution_ratio` не вызывается в engine.
*Статус:* Gate написан, но не подключён в production path.

**C18.** `quality_stratification.py` — множители (1.0/1.45/2.05) не применяются.
*Статус:** `quality_threshold_multiplier` пишется в row, но нигде не читается.

**C19.** `same_day_gate.py` и `irreversible_return.py` — написаны, не подключены.
*Статус:* Модули существуют, тесты проходят, но engine.py не вызывает их.

**C20.** `corroboration.py:independent_source_count` — вычисляется, не используется как условие.
*Статус:* Все 1909 кадров `source_provenance_status = not_provided`.

**C21.** `engine.py:_modules` — `angle_noise` теперь корректно (Fix #4). `chronology_rate` `'applied': bool(chronology_refs)` — всегда True если есть adjacent pairs.
*Статус:* Некорректная метрика "applied" — refs всегда непусты.

**C22.** `mesh_dense.py` — `vertices_identity_only` из того же latent space что `alpha_id`.
*Статус:* Mesh канал не независимый. Подтверждено.

**C23.** `landmark_stability_score` — помечен IN PROGRESS. Простая heuristic.
*Статус:* Не вызывается в production. Написан для будущего использования.

### БЛОК D: ОТЧЁТ И ИНТЕРПРЕТАЦИЯ (7 анализов)

**D24.** Stage 3 narrative — 6 фиксированных параграфов о методе.
*Статус:* Нет per-pair, per-photo, per-epoch narrative. Подтверждено.

**D25.** Stage 3 HTML template — `_html()`/TEMPLATE мёртвый код (P1-10).
*Статус:** HTML генерируется через embedded JS в sections, не через `_html()`.

**D26.** Stage 3 не публикует: lower CI bound, holdout FPR, effective units, excluded pairs.
*Статус:** Подтверждено (P1-12). Отчёт показывает статусы, но не границы применимости.

**D27.** Timeline SVG — `p95_point_z` без пометки калибровочного статуса.
*Статус:** Визуально может преувеличивать значимость (P2-13).

**D28.** `public_pair_projection` — статус = evidence_state, raw = metadata.
*Статус:** Correct by design. Неопределённость не теряется.

**D29.** `is_reportable_change` — adjacent + reportable evidence_state.
*Статус:** Correct. Change points фильтруются через evidence gate.

**D30.** FORBIDDEN_PUBLIC_TERMS — 10 терминов.
*Статус:** Correct. Теперь проверяет конкретные поля (Fix #10).

### БЛОК E: МЕТОДОЛОГИЯ (5 анализов)

**E31.** Rate = p95_z × coherent_fraction / sqrt(days) — физика броуновского движения.
*Статус:* Для малых days → rate взлетает. Partially mitigated: `eff = max(1, days)`, но `sqrt(1)=1` всё равно даёт высокие rate для same-day.

**E32.** `cumulative_drift_flags` — CUSUM с `point_z_floor = 2.5`.
*Статус:* Floor hardcoded. Не калибруется из данных.

**E33.** `alpha_chronology` — drift detection на alpha_id coefficients.
*Статус:* Diagnostic only. alpha_id — слабейший канал (ci_lo 0.6768).

**E34.** `baseline_return` — FP = 0.9% на null (аудит подтвердил OK).
*Статус:** Работает корректно после предыдущего фикса с абсолютным порогом.

**E35.** `pose_leakage_diagnostic` — считается после отсечения 81% пар.
*Статус:** На усечённой выборке корреляция занижена по построению (P1-9).

---

## СВОДКА ИСПРАВЛЕНИЙ (РАУНД 1 + РАУНД 2)

| # | Ошибка | Раунд | Файл | Статус |
|---|--------|-------|------|--------|
| 1 | IndentationError (4 места) | R1 | engine.py | ✅ |
| 2 | Evidence state перезапись | R1 | engine.py | ✅ |
| 3 | Двойной write_postprocess_reports | R1 | engine.py | ✅ |
| 4 | Ключ angle_noise_compensated | R1 | engine.py | ✅ |
| 5 | coordinate_noise_sigma = 0.0 | R1 | loaders.py | ✅ |
| 6 | Поле pixels не заполняется | R1 | engine.py | ✅ |
| 7 | Ложный imported:True | R1 | engine.py | ✅ |
| 8 | Отступы в engine.py | R1 | engine.py | ✅ |
| 9 | gate_report без error_rate | R2 | postprocess_reports.py | ✅ |
| 10 | public_safety str(pkt) | R2 | postprocess_reports.py | ✅ |
| 11 | chronology: pose_leakage_limited | R2 | chronology.py | ✅ |
| 12 | persistence = 2 пары | R2 | engine.py | ✅ |
| 13 | chronology self-calibrating | R2 | chronology.py | ✅ |
| 14 | consistency_check не вызывается | R2 | engine.py | ✅ |

**Итого: 14 исправленных ошибок за 2 раунда.**

---

## ЧТО НЕ ИСПРАВЛЕНО (требует больших изменений)

| # | Проблема | Почему не исправлено |
|---|----------|---------------------|
| FDR на зависимых данных | Требует permutation null на калибровке (~1 неделя) |
| Single-z fallback <20 точек | Требует redesign policy |
| Expression gate dead | Архитектурное решение команды |
| same_day_gate/irreversible_return | Требует интеграции + тестов |
| Quality stratification dead | Требует пересборки калибровки |
| Domain shift 6.3× | Требует новой калибровки на целевом домене |
| Мини-флаги (0/10) | Новая функциональность (~2 недели) |
| Хронологический каркас | Новая функциональность (~3 недели) |
| Сквозные наблюдения | Новая функциональность (~1 неделя) |
