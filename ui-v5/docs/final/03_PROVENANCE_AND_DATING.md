# P1-8. Провенанс и датировка

## Политика

Дата из имени `YYYY_MM_DD[_N].ext` — единственный authority хронологии. EXIF и `claimed_date` из sidecar — только corroboration. Они никогда не заменяют filename date. Любое расхождение создаёт `status=conflict`, требует ручной проверки и исключает пару из chronology-rate/change evidence.

## Сквозной маршрут

Stage 1 `info.json` → `main_timeline.csv` → Stage 2 `Record` → `pair_metrics.csv` и evidence packet → API timeline → UI/JSON export → Stage 3 provenance summary. Сохраняются filename date, EXIF date, source-claimed date, delta days, conflict sources, status и limitation flag.

## Входной ledger

`input_provenance.csv` содержит относительный путь, SHA-256 исходных байтов, размер, byte-duplicate link, orientation-aware dHash, near-duplicate link/Hamming distance, sidecar status/path/SHA-256 и inclusion flag. Byte-identical файлы пропускаются. Perceptual near-duplicates при Hamming ≤4 сохраняются, но не считаются независимыми и исключаются из chronology/persistence evidence.

## Chain-of-custody sidecar

Допустимые имена: `<image>.provenance.json` или `<stem>.provenance.json`. Схема: `app6/schemas/provenance_sidecar_v1.json`. Разрешены только `source_url`, `archive_url`, `publisher`, `acquired_at`, `collector`, `claimed_date`, `notes`, `rights`. Требуется `source_url` или `archive_url`; URL — HTTP(S); даты — ISO-8601. Неизвестное поле или неверный тип fail closed.

```json
{
  "source_url": "https://example.org/article/123",
  "archive_url": "https://web.archive.org/example",
  "publisher": "Example News",
  "acquired_at": "2026-07-30T18:00:00+03:00",
  "collector": "reviewer-01",
  "claimed_date": "2018-05-07",
  "rights": "research copy",
  "notes": "frame extracted from official video"
}
```

## Хеши

Криптографические digests используют SHA-256. `dataset_hash` канонически строится по path + image SHA-256 + provenance-sidecar SHA-256 и не зависит от порядка строк или CRLF/LF. `code_hash`, `model_hash`, `config_hash` проверяются preflight. При наличии Stage 1 manifest его dataset hash является идентичностью run; calibration index hash публикуется отдельно.

## Release gates

- date conflict → `date_provenance_limited`;
- near duplicate → `near_duplicate_limited` для аномального результата;
- обе категории исключены из chronology rates;
- отсутствие source chain отражается в evidence alternatives и Stage 3 summary;
- Stage 2 contract fail closed проверяет обязательные provenance-поля;
- UI показывает filename, EXIF/source claim и delta; JSON exports сохраняют provenance.
