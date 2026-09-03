# 🔍 15 АНАЛИЗОВ: ПРЕД-PULL REQUEST ПРОВЕРКА

**Дата:** 2026-08-27  
**Статус:** ✅ Завершён  
**Результат:** 2 критических бага найдены и исправлены, PR готов

---

## АНАЛИЗ 1: TODO/FIXME/HACK в коде

**Результат:** 6 TODO найдено

```
bayesian.py:393    # TODO: extract mesh_max_disp from pair
bayesian.py:401    # TODO: extract family_scores from pair  
engine.py:167      # TODO: measure memory_peak_mb
engine.py:248      # TODO: from calibration (noise_floor)
engine.py:283      # TODO: cross-pose analysis (уже реализовано отдельно)
engine.py:320-321  # TODO: mean_lr, top_points per zone
```

**Вердикт:** ✅ Не критично для PR. Это улучшения для будущих итераций.

---

## АНАЛИЗ 2: Bare except / Syntax errors

**Результат:** ✅ Проблем не найдено.

---

## АНАЛИЗ 3: Stage 2 CSV структура

**Результат:** pair_metrics.csv не существует в stage2/ (это нормально — это runtime output).  
Loader корректно обрабатывает ожидаемую структуру CSV.

**Вердикт:** ✅ OK

---

## АНАЛИЗ 4: Loader на реальных данных

**Результат:** ✅ Валидация проходит, 5 пар загружено, features извлечены корректно.

---

## АНАЛИЗ 5: Formatting edge cases

**Результат:** 11/13 тестов прошли.

**НАЙДЕН БАГ #1:**
```
fmt(0, "auto") → "0,00e+00" вместо "0,00"

Причина: _auto_precision(0) возвращал -1 (scientific notation)
Исправлено: добавлена проверка abs_val == 0 → return 2
```

**Вердикт:** ⚠️ БАГ НАЙДЕН И ИСПРАВЛЕН

---

## АНАЛИЗ 6: Export pipeline (full test)

**Результат:** ✅ Все файлы экспортируются корректно:
- report.json (13 ключей)
- narrative.txt (1342 chars)
- summary.json (8 ключей)

**НАЙДЕН БАГ #2 (критический):**
```
scipy.stats.gamma.pdf() вызывался с shape= вместо a=

mesh_likelihood:   stats.gamma.pdf(x, shape=2.0, scale=1.5)  → TypeError
descriptor_likelihood: stats.gamma.pdf(x, shape=2.5, scale=1.2) → TypeError

Это приводило к тому что ВСЕ пары падали в _analyze_pair() → pairs_analyzed=0

Исправлено: shape= → a= (правильный параметр scipy)
```

**Вердикт:** 🔴 КРИТИЧЕСКИЙ БАГ НАЙДЕН И ИСПРАВЛЕН

---

## АНАЛИЗ 7: Formatting fix verification

**Результат:** ✅ После исправления:
```
fmt(0, "auto") = "0,00" ✅
fmt(-2.5, "auto") = "-2,50" ✅
```

---

## АНАЛИЗ 8: private_hypothesis_seed

**Результат:** ✅ Файлы на месте:
- legacy_hypothesis_ledger.jsonl (37MB)
- hypothesis_retest_results.jsonl (2.5MB)
- QUARANTINE_POLICY.md
- README_PRIVATE.md

Legacy integrator корректно работает с этими данными.

---

## АНАЛИЗ 9: Stage3 v1 vs v2 совместимость

**Результат:** ✅ Оба существуют параллельно:
- app6/stage3/ — старый (рендеринг HTML)
- app6/stage3_v2/ — новый (LR + Effect Size + Narrative)

Нет конфликтов.

---

## АНАЛИЗ 10: Stage2 модули (зависимости)

**Результат:** ✅ 10/10 модулей импортируются:
```
✅ evidence, calibration, chronology, corroboration
✅ core, descriptors, motion, mesh_dense
✅ quality_gate, robustness
```

---

## АНАЛИЗ 11: API endpoints для stage3_v2

**Результат:** ⚠️ Нет API endpoints для stage3_v2.

**Вердикт:** Не критично для PR. CLI (`run_stage3_v2.py`) работает. API можно добавить позже.

---

## АНАЛИЗ 12: README

**Результат:** ⚠️ stage3_v2 не упомянут в README.

**Вердикт:** Не критично. Можно обновить в следующем PR.

---

## АНАЛИЗ 13: .gitignore

**Результат:** ✅ Корректно настроен:
```
__pycache__/
**/__pycache__/
storage/stage3/report_data.json
```

---

## АНАЛИЗ 14: pyproject.toml

**Результат:** ⚠️ stage3_v2 не в testpaths.

**Вердикт:** Не критично. Тесты запускаются явно.

---

## АНАЛИЗ 15: Финальная проверка импортов

**Результат:** ✅ 14/14 модулей импортируются корректно.

---

## 📊 ИТОГ

```
НАЙДЕНО ПРОБЛЕМ:
  🔴 Критических: 2 (оба исправлены)
     1. scipy.stats.gamma.pdf(shape=) → TypeError
     2. fmt(0) → scientific notation
  
  ⚠️ Не критичных: 3
     1. Нет API endpoints для stage3_v2
     2. README не обновлён
     3. pyproject.toml не обновлён
  
  ✅ OK: 10

ТЕСТЫ: 27/27 PASSED
PIPELINE: 5/5 pairs analyzed (после исправления бага #2)

PULL REQUEST: ГОТОВ ✅
```

---

## ИСПРАВЛЕНИЯ

```diff
# bayesian.py:274
-        p_h2 = stats.gamma.pdf(mesh_rmse * 1000, shape=2.0, scale=1.5)
+        p_h2 = stats.gamma.pdf(mesh_rmse * 1000, a=2.0, scale=1.5)

# bayesian.py:297
-        p_h2 = stats.gamma.pdf(descriptor_p95_z, shape=2.5, scale=1.2)
+        p_h2 = stats.gamma.pdf(descriptor_p95_z, a=2.5, scale=1.2)

# formatting.py:63
+    if abs_val == 0:
+        return 2
     elif abs_val >= 100:
```
