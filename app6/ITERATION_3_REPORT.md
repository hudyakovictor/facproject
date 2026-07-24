# Итерация доработок 3 — public evidence boundary

Дата: 2026-07-24

## Границы

- `uv_module`, `stage2/uv_comparison.py`, texture и skin implementation не изменялись.
- Texture/UV окончательно закреплены как visualization/morphing only.
- Raw технические артефакты сохраняются, но не могут попасть в forensic evidence channel или публичный Stage 3 payload.

## Реализовано

1. Добавлен централизованный `is_reportable_change()`.
2. `change_points.json` теперь формируется по итоговому evidence state, а не по raw status.
3. `quality_limited`, `calibration_limited`, `pose_leakage_limited`, expression-dominated и uncertain пары не попадают в публичные change points.
4. Публичным change point может быть только adjacent-пара.
5. Добавлен `evidence_metric_channel()` без texture/UV метрик.
6. Texture/UV вынесены из evidence measurements в явный блок `visualization_only`.
7. Metric catalog маркирует texture family как `visualization_only`.
8. Stage 3 удаляет texture/UV поля из публичной проекции pair data.
9. Stage 3 повторно проверяет, что каждый change point прошёл evidence gate.
10. Добавлена семантическая Stage 2 validation v1.1:
   - соответствие числа packets и pair rows;
   - уникальность pair IDs;
   - равенство packet/pair ID sets;
   - запрет non-reportable change points;
   - обязательный public-safety pass;
   - запрет texture/UV leakage в evidence metric channel.
11. Degraded report и manual review queue учитывают calibration/pose limitations.
12. `STATUS_AUDIT.py` дополнен новыми закрытыми функциями.

## Проверка

- Regression suite: 56/56 PASS.
- Exact implementation audit: 50/50 PASS.
- Python compileall: PASS.
- Чистых `pass`/`NotImplementedError` заглушек в ядре нет.
