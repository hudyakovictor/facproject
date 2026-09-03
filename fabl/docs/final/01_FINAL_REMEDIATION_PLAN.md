# Итоговый план исправлений и применения патчей

## Принцип

Порядок обязателен: сначала провенанс и контракты, затем геометрия и калибровка, после — статистика, отчёты и UI. Нельзя калибровать пороги на старых координатах, а затем переключать пространство.

## Серия патчей

| № | Содержание | Основные файлы | Приоритет | Проверка |
|---|---|---|---|---|
| 0001 | P1-8: датировка, EXIF, входной ledger, 4 хеша | `stage1/input_provenance.py`, `stage1/engine.py`, `run_preflight.py` | P0 | unit + повторный hash |
| 0002 | Геометрическая политика raw + axis pose gap | `stage2/analysis_policy.py`, `core.py`, `motion.py`, `calibration.py`, `loaders.py` | P0 | synthetic + 943-frame calibration |
| 0003 | NaN-safe utility/subset91 | `stage2/landmark_policy.py` | P0 | NaN profile fixtures |
| 0004 | Статистика: FDR, calibrated count, return, contamination | `multiple_testing.py`, `engine.py`, `irreversible_return.py`, `same_day_gate.py` | P0 | NULL/AABBAA/contamination |
| 0005 | Регрессионные тесты | `app6/test_module/test_round5_patches.py` | P0 | 7/7 |
| 0006 | Документация передачи | `docs/final/*` | P1 | link/lint review |

## Порядок внедрения

1. Создать ветку и чистый baseline tag.
2. Применить патчи по номеру: `git apply --check patches/0001-*.patch`, затем `git apply ...`.
3. Запустить `python -m compileall -q app6` и unit tests.
4. Зафиксировать эталонные `dataset_hash`, `code_hash`, `model_hash`, `config_hash` из первого одобренного прогона.
5. Полностью переизвлечь Stage 1. Старые `chronology`-артефакты нельзя смешивать с новым raw primary channel.
6. Пересобрать калибровочные null-модели на семи персонах.
7. Выполнить LOPO, negative control, contamination test и scenario truth tests.
8. Только после статистического gate запустить Stage 2/3 и UI snapshot tests.
9. Сравнить manifest/artifact hashes при повторном прогоне.
10. Выпустить immutable release bundle: код, конфиг, манифесты, отчёты и журналы.

## P0 — обязательно до основного датасета

- [x] Имя файла `YYYY_MM_DD[_N]` является единственным authority даты.
- [x] EXIF сохраняется, сравнивается и никогда молча не заменяет дату.
- [x] Входной ledger включает каждый файл, размер, SHA-256 и duplicate link.
- [x] Dataset hash не зависит от абсолютного пути и порядка файловой системы.
- [x] Preflight умеет сверять dataset/code/model/config hashes.
- [x] Primary geometry = object-normalized raw + robust Kabsch.
- [x] Внутрибиновый pose gate axis-specific; границы девяти бинов не меняются.
- [x] Utility обрабатывает NaN, subset всегда содержит ровно 91 индекс.
- [x] FDR = 0.05; p95 order-statistic получает реальное число точек.
- [x] NULL не активирует irreversible return.
- [x] Same-day threshold защищён от ≤20% contamination.
- [ ] Выполнить полное переизвлечение с реальными весами и фото.
- [ ] Зафиксировать новый golden calibration bundle.

## P1 — до публикационного анализа

- End-to-end synthetic Stage 3 fixtures и golden JSON/CSV/HTML snapshots.
- Runtime API tests всех endpoints `server.py`.
- UI tests и screenshots после чистого `npm ci` на Linux.
- Public-term lint не только evidence packets, но и финального HTML/print export.
- Cluster bootstrap/ESS в confidence intervals; единица независимости — person-pair/event, не кадр-пара.
- Report должен показывать space, pose gate, calibration coverage, excluded pairs и hash quartet.

## P2 — до внешней рецензии

- Два независимых экспертных review на слепой выборке.
- Межэкспертное согласие и журнал adjudication.
- Calibration transfer test на новом человеке/источнике.
- JPEG/downscale/source-domain stress tests.
- Версионированные ENFSI-style формулировки без identity verdict.

## Критерий 100% технической готовности

Готовность означает не «нет идей для улучшения», а одновременное выполнение проверяемых условий: 0 critical test failures; negative-control AUC 0.45–0.55; все четыре хеша совпали; 9/9 bins представлены; 7/7 calibration persons проходят LOPO; schema/UI/report snapshots совпали; public-safety lint = pass; все exclusions отражены в отчёте; повторный прогон детерминирован.
