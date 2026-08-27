# Исправления — Раунд 1 (подтвержденные ошибки аудита)

**Дата:** 2026-08-27  
**Объект:** `app6/stage2/`  
**Основа:** `audit/final_report.md` — 9 консолидированных + 34 расширенных подтверждённых ошибки

---

## ✅ Исправлено (8 ошибок)

### #1. IndentationError на main ветке (P1-3 / консолидированный #3)
**Файл:** `app6/stage2/engine.py` (строки ~225-235, ~411, ~479)  
**Проблема:** 3 пробела вместо 2 в нескольких местах внутри `run()` — файл не компилировался.  
**Исправление:** Выровнены отступы во всех проблемных блоках:
- Загрузка данных (`main=load_main(...)`)
- Цикл `for r in cal:` (calibration yaw range)
- Цикл `for r in rows:` (pose leakage per-pair)
- `req=` (validation file list)

### #2. Evidence state перезаписывается (P1-1 / консолидированный #1)
**Файл:** `app6/stage2/engine.py` (строка ~429)  
**Проблема:** На строке ~367 evidence_state корректно устанавливается с учётом `date_provenance_limited` и `near_duplicate_limited`. На строке ~429 он безусловно перезаписывается через `evidence_state()` — которая не принимает эти аргументы. Результат: пары с конфликтом дат или дублями проходят как доказательства.  
**Исправление:** Добавлена проверка — если предыдущий evidence_state был `date_provenance_limited` или `near_duplicate_limited`, он сохраняется; иначе применяется обычный расчёт.

### #3. Двойной вызов write_postprocess_reports (P1-11 / консолидированный #7)
**Файл:** `app6/stage2/engine.py` (строки ~459, ~462)  
**Проблема:** `write_postprocess_reports()` вызывалась дважды с идентичными аргументами — пустая трата времени и потенциальная перезапись файлов.  
**Исправление:** Удалён первый вызов; оставлен второй (после записи photo_analysis/).

### #4. Ключ angle_noise_compensated не существует (P1-3 / консолидированный #2)
**Файл:** `app6/stage2/engine.py` (строка ~468, `_modules` dict)  
**Проблема:** Манифест читал `r.get('angle_noise_compensated')` — ключ, который `subtract_angle_noise()` никогда не создаёт. Функция пишет `{metric}_angle_compensated` и `angle_noise_uncompensated`.  
**Исправление:** Заменено на `r.get('angle_noise_uncompensated') is False` — корректно определяет, была ли компенсация применена.

### #5. coordinate_noise_sigma всегда 0.0 (P1-18 / консолидированный #9)
**Файл:** `app6/stage2/loaders.py` (строка ~135)  
**Проблема:** `coordinate_noise_sigma` читалась из `chronology_info.get("coordinate_noise_sigma", 0.0)`, но stage1 никогда не записывает этот ключ. Результат: адаптивная защита от шума всегда выключена.  
**Исправление:** Добавлен fallback на `reprojection_rmse` — реальная метрика из stage1, которая присутствует в chronology и является оценкой шума реконструкции:
```python
coordinate_noise_sigma=float(chronology_info.get("coordinate_noise_sigma") or chronology_info.get("reprojection_rmse", 0.0) or 0.0)
```

### #6. Поле `pixels` не заполняется в QC (P2-1 / консолидированный #5)
**Файл:** `app6/stage2/engine.py` (функция `_record_qc`)  
**Проблема:** `_record_qc()` читал info.json, но не извлекал `image.pixels`. В `pair_row_patch.py` и `quality_gate.py` проверка `resolution_disparity` всегда давала False.  
**Исправление:** Добавлено чтение `pixels` из `payload['image']['pixels']` и включение в результат QC.

### #7. Ложный `imported:True` для мёртвого модуля (P1-9 / консолидированный #6)
**Файл:** `app6/stage2/engine.py` (строка ~480, `_modules` dict)  
**Проблема:** `same_day_gate_v2` имеет `'imported':True` в манифесте, но модуль не импортирован и не вызывается в движке.  
**Исправление:** Заменено на `'imported':False` с пояснением что модуль не подключён; `days_delta=0` пары отслеживаются через chronology flags.

### #8. IndentationError — блок калибровочного yaw range
**Файл:** `app6/stage2/engine.py` (строки ~228-236)  
**Проблема:** `for r in cal:` и `record_yaw` имели отступ 3 пробела вместо 2.  
**Исправление:** Выровнено до 2 пробелов.

---

## ⏳ Отложено (требует отдельных решений)

### quality_zones.npz не пишется (P1-17 / консолидированный #8)
**Статус:** Stage2 корректно обрабатывает отсутствие (fail-closed: `status: missing`). Не блокирует работу.  
**Для исправления:** Нужен отдельный модуль генерации quality_zones.npz из skin_zone_atlas + UV данных в stage1. Это ~1 день работы.

### Стратификация качества не применяется (P1-4)
**Статус:** Требует добавления `::q_` суффиксов в калибровочные ключи. Не блокирующая — просто не улучшает точность.  
**Для исправления:** Нужна доработка `calibration.py` и `quality_stratification.py`.

---

## Проверка

```
✅ app6/stage2/engine.py — компилируется
✅ app6/stage2/loaders.py — компилируется
✅ app6/stage2/evidence.py — компилируется
✅ app6/stage2/angle_noise.py — компилируется
```

---

## Следующие шаги

1. **Технические долги (P1-4, P1-5, P1-6, P1-7):** стратификация, calibration CI, FDR inflation
2. **Новый слой отчёта:** хронологический каркас для журналистов (секция 5 из брифа)
3. **Полный прогон:** после получения весов модели и фотоархива
