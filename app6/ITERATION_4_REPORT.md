# Итерация доработок 4 — transactional preflight и публичные статусы

Дата: 2026-07-24

## Границы

- `uv_module`, UV comparison, texture и skin implementation не изменялись.
- Итерация усиливает безопасность путей, overwrite-транзакции и публичную интерпретацию evidence.

## Реализовано

1. Stage 1 больше не создаёт output до проверки input, model assets, reconstruction dependencies и наличия поддерживаемых фотографий.
2. Stage 2 загружает и конструирует все read-only зависимости до destructive overwrite.
3. Ошибка Stage 2 preflight при `overwrite=True` сохраняет существующий output без изменений.
4. Stage 2 запрещает output, равный или вложенный в `stage1_root`/`calibration_root`.
5. Stage 2B запрещает output внутри Stage 2 и очищает старый output только после полной проверки manifest/evidence/prior inputs.
6. Stage 3 запрещает output внутри analysis root и очищает output только после полной проверки входных артефактов и change points.
7. Stage 2B проверяет `analysis_manifest.status`, тип packets и точную версию evidence schema.
8. Evidence schema повышена до `deeputin-stage2-evidence-v1.1` во всех canonical outputs.
9. Удалён риск расхождения дублированного `stage1/evidence.py`: он заменён compatibility shim на canonical `stage2.evidence`.
10. Stage 3 публично показывает итоговый `evidence_state` как `status`.
11. Внутренний геометрический статус сохраняется отдельно как `measurement_status`.
12. Change points также содержат публичный status и отдельный measurement status.
13. Контрольный аудит обновлён под более строгий path contract.

## Проверка

- Regression suite: 65/65 PASS.
- Exact implementation audit: 50/50 PASS.
- Python compileall: PASS.
- Устаревших evidence-v1.0 ссылок в активных Stage 1–3 модулях нет.
