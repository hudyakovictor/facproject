# UI, API и отчёты

## Обязательные поля интерфейса

Для каждой пары: даты и provenance statuses, pose bin, axis gaps, quality, common/calibrated points, coordinate space, calibration coverage, measurement status, evidence state, FDR q, exclusions, alternative explanations. Для всего run: hash quartet, schema/config version, counts по bins и degraded modules.

## Отчёты

JSON/CSV — source of truth; HTML/print — представление. Export schema должен быть versioned. Любое отсутствующее значение показывается как `нет данных/исключено`, не как 0. UI не должен превращать `candidate` в утвердительную формулировку.

## Public safety

`FORBIDDEN_PUBLIC_TERMS` проверяется в evidence packets и дополнительно в финальном HTML, print report и export JSON. Проверка блокирует publication build. Внутренние исследовательские гипотезы отделены от публичного отчёта.

## Многоаудиторные публикационные черновики

После Stage 2 создаётся структурированный `journalist_handoff.json`, а Stage 3 формирует синхронизированный draft package для четырёх аудиторий:

1. понятное объяснение метода для широкой аудитории;
2. техническое приложение с точными contracts и reproducibility;
3. skeptic Q&A с альтернативами и falsification tests;
4. machine-review packet с claims ledger и evidence pointers.

Каждая числовая публичная формулировка сохраняет знаменатель, applicability, calibration/uncertainty и ссылку на artifact. `candidate` нельзя усиливать редакционной правкой без нового review/evidence state. Method series не зависит от результатов основного расследования. Полный контракт: `docs/PUBLICATION_PIPELINE.md`.

## Golden end-to-end fixture

Минимальный synthetic artifact должен содержать 9 bins, quality-limited pair, date conflict, same-day conflict, NULL sequence, true step и true return. Snapshot покрывает API response, timeline, anomaly counts, report sections, publication drafts/claims ledger, print/export и mobile rendering.
