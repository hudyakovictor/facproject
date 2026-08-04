# Итерация 02 — Dataset Manager и полный timeline

## Статус

Завершено. Итерация расширяет подключение готового Stage 1 до validation workflow и гарантирует, что Stage 2 overlay не удаляет из интерфейса фотографии без пригодных пар.

## Реализовано

- полный paginated issue register для Stage 1;
- категории: missing photo ID, duplicate photo ID, unknown pose bin, date conflict, near duplicate, exact duplicate link, missing record directory, missing artifact;
- фильтрация issue register по категории;
- распределение Stage 1 по годам;
- отдельные счётчики provenance conflicts и duplicate links;
- UI validation report с пагинацией;
- пресеты timeline на 1, 3 и 9 ракурсов;
- сохранение выбранного пресета в localStorage;
- viewport virtualization миниатюр, anomaly markers и metric tracks;
- Stage 1 + Stage 2 merged timeline: все записи Stage 1 остаются видимыми;
- фотографии без Stage 2 pair получают явный статус `not_compared`;
- orphan Stage 2 IDs публикуются отдельно.

## API

- `GET /api/v1/datasets/issues?offset=0&limit=100&category=`
- `GET /api/v1/timeline` возвращает полный Stage 1 с Stage 2 overlay, если Stage 2 доступен.

## Проверка

```bash
cd backend
python3 -m compileall -q app6
python3 -m unittest \
  app6.test_module.test_iteration1_runtime_inventory \
  app6.test_module.test_iteration2_dataset_timeline -v
cd ..
npm run typecheck
```
