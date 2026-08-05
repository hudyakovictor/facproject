# Итерация 04 — Analysis Profiles + manual curation

## Статус

Завершено на 100% в рамках утверждённого плана.

## Цель

Сделать выборку воспроизводимой: у каждой фотографии однозначный статус, каждый ручной override журналируется, формируется immutable `selection_manifest.json`.

## Реализовано

### Photo statuses
- `primary`
- `diagnostic_only`
- `automatic_exclusion`
- `manual_exclusion`
- `manual_include`
- `manual_review`
- `invalid`

### Curation
- set status for one/many photos
- reason codes + comments
- bulk actions
- restore automatic decision
- append-only journal (`journal.jsonl`)

### Analysis Profiles (`storage/profiles/<id>/`)
- create / rename / clone
- lock / unlock
- update filter_state
- freeze selection_manifest
- diff two profiles
- export / import JSON

### API
- `GET/POST /api/v1/profiles`
- `GET /api/v1/profiles/{id}`
- `POST .../rename|clone|lock|freeze`
- `PUT .../filters`
- `POST .../curation` + `.../curation/restore`
- `GET .../statuses`
- `GET .../export` + `POST /profiles/import`
- `GET /profiles/diff/{a}/{b}`

### UI
- Nav item **Profiles**
- profile list + create
- status counts
- curation table with multi-select
- journal tail
- diff + import/export

## Gates

- [x] каждая фотография имеет однозначный статус
- [x] каждый manual override журналируется
- [x] freeze пишет immutable selection_manifest вне Stage 1
- [x] locked profile нельзя редактировать
- [x] Stage 1 evidence не мутируется

## Проверка

```bash
cd backend
PYTHONPATH=. python3 -m unittest \\
  app6.test_module.test_iteration4_analysis_profiles -v
cd .. && npm run typecheck
```
