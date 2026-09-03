# Пакет передачи проекта: forensic facial comparison 1999–2026

## Назначение

Это каноническая точка входа для разработчика, аналитика и рецензента. Проект измеряет воспроизводимость и хронологическую устойчивость 3D-геометрии лица; он **не** выносит автоматический вывод о личности. Любой флаг — повод для ручной проверки источника, даты, качества и реконструкции.

## Порядок чтения

1. `01_FINAL_REMEDIATION_PLAN.md` — порядок применения патчей и критерии готовности.
2. `02_VALIDATED_METHOD.md` — метод, выбранный экспериментами.
3. `03_PROVENANCE_AND_DATING.md` — обязательный контракт P1-8.
4. `04_DATA_CONTRACTS.md` — входы, выходы и версии схем.
5. `05_CALIBRATION_PROTOCOL.md` — семь персон, девять ракурсов, защита от контаминации.
6. `06_STATISTICS_AND_THRESHOLDS.md` — пороги, FDR, ESS, LOPO.
7. `07_TESTING_AND_ACCEPTANCE.md` — тестовая пирамида и release gates.
8. `08_UI_AND_REPORTING.md` — API/UI/экспорт/публичная безопасность.
9. `09_RESULTS_REGISTER.md` — числа всех раундов.
10. `10_RISK_REGISTER.md` — известные ограничения и запреты.
11. `11_OPERATIONS_RUNBOOK.md` — команды воспроизводимого прогона.
12. `12_DECISION_LOG.md` — почему приняты ключевые решения.
13. `13_STATIC_REVIEW_BACKLOG.md` — идеи, не проверяемые симулятором.
14. `14_FORENSIC_REVIEW_PROTOCOL.md` — порядок экспертной интерпретации.

## Что входит в пакет патчей

- raw object-normalized координаты как primary geometry channel;
- axis-specific pose-gap gate: per-bin yaw из `pose_gate_v2.csv` (0–12°; profile — внутри 10° подбина ≤2°), pitch/roll производные через sensitivity;
- NaN-safe utility и детерминированный subset из ровно 91 точки;
- FDR 0.05 и передача фактического числа откалиброванных точек;
- абсолютный порог для A→B→A, устраняющий ложное срабатывание на NULL;
- contamination-hardened same-day baseline;
- полная датировочная запись: имя файла — authority, EXIF — corroboration;
- `input_provenance.csv`, dataset/code/model/config hashes;
- семь регрессионных тестов критических исправлений.

## Статус

Патчи компилируются Python 3.11+; новые регрессионные тесты проходят 7/7. Полный end-to-end прогон требует локальных весов 3DDFA и основного фотодатасета. UI-тесты в переданном архиве нельзя запустить без переустановки Linux optional dependency Rollup; это release blocker, а не основание считать UI проверенным.
