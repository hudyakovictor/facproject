# Итерация доработок 2 — fail-closed evidence hardening

Дата: 2026-07-24

## Границы

- Изменялся основной pipeline Stage 2, Stage 2B и Stage 3.
- `uv_module`, UV comparison, texture и skin-модули не изменялись.
- Новые ограничения меняют только applicability/evidence state; сырые измерения и научные пороги не переписываются.

## Реализовано

1. Mandatory QC теперь загружается без проходных значений по умолчанию.
2. Отсутствующий, повреждённый, нечисловой или неконечный QC переводит пару в `missing_mandatory_qc`.
3. Alignment/expression pair gates унифицированы в одну детерминированную функцию.
4. В manifest добавлены числа отсутствующих QC-записей и причины исключения пар.
5. Нестабильная или неполная calibration sensitivity по primary geometric metrics переводит ненулевой сигнал в `calibration_limited`.
6. Pose leakage по primary geometric metrics переводит ненулевой сигнал в `pose_leakage_limited`.
7. Raw status и измерения при этом сохраняются без изменения.
8. Evidence packets теперь содержат calibration/pose limitation flags и альтернативные объяснения.
9. Technical summary считает quality-, calibration- и pose-leakage-limited пары.
10. Stage 2B классифицирует новые evidence states и `inapplicable_pose`.
11. Добавлен реестр неклассифицированных Stage 2 evidence states; текущий результат пустой.
12. Stage 2B и Stage 3 валидируют Stage 2 до создания выходной директории.

## Проверка

- Regression suite: 47/47 PASS.
- Exact implementation audit: 50/50 PASS.
- Python compileall: PASS.
- Чистых `pass`/`NotImplementedError` заглушек в ядре нет.
