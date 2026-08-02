# UI, API и отчёты

## Обязательные поля интерфейса

Для каждой пары: даты и provenance statuses, pose bin, axis gaps, quality, common/calibrated points, coordinate space, calibration coverage, measurement status, evidence state, FDR q, exclusions, alternative explanations. Для всего run: hash quartet, schema/config version, counts по bins и degraded modules.

## Отчёты

JSON/CSV — source of truth; HTML/print — представление. Export schema должен быть versioned. Любое отсутствующее значение показывается как `нет данных/исключено`, не как 0. UI не должен превращать `candidate` в утвердительную формулировку.

## Public safety

`FORBIDDEN_PUBLIC_TERMS` проверяется в evidence packets и дополнительно в финальном HTML, print report и export JSON. Проверка блокирует publication build. Внутренние исследовательские гипотезы отделены от публичного отчёта.

## Golden end-to-end fixture

Минимальный synthetic artifact должен содержать 9 bins, quality-limited pair, date conflict, same-day conflict, NULL sequence, true step и true return. Snapshot покрывает API response, timeline, anomaly counts, report sections, print/export и mobile rendering.
