# Runbook воспроизводимого прогона

## 1. Чистая среда

Зафиксировать Python/Node/OS, установить зависимости из lock files, проверить веса и SHA-256. Не использовать вложенный `node_modules` из чужой ОС.

## 2. Preflight

```bash
python app6/run_preflight.py \
  --calibration-root /data/calibration \
  --stage1-root /data/stage1 \
  --expected-dataset-hash "$DATASET_HASH" \
  --expected-code-hash "$CODE_HASH" \
  --expected-model-hash "$MODEL_HASH" \
  --expected-config-hash "$CONFIG_HASH" \
  --output preflight.json
```

## 3. Tests

```bash
python -m compileall -q app6
python -m unittest app6.test_module.test_round5_patches -v
pytest --branch
cd ui && npm ci && npm test -- --run && npm run build
```

## 4. Stage 1

Полностью переизвлечь данные после coordinate-policy patch. Проверить `input_provenance.csv`, date conflicts, duplicate count, 9-bin counts, stage1 manifest и validation files.

## 5. Calibration release

Построить null, LOPO, contamination, noise и negative-control reports. Зафиксировать utility/subset artifact hash. Только approved calibration получает version/tag.

## 6. Stage 2/3

Запускать на immutable Stage 1 root. После Stage 2 проверить validation, FDR, exclusions, safety report, artifact index/hash. После Stage 3 прогнать lint финального HTML/export.

## 7. Архивация

Сохранить source ledger, manifests, configs, logs, package versions, reports, reviewer decisions и patch version. Не удалять failed rows.
