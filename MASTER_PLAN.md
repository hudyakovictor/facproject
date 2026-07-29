# MASTER PLAN — 100% code readiness

Обновлено: 2026-07-29 04:44 MSK  
Статус: **100% готовность к запуску кода и UI**  
Граница статуса: модельные веса и исследовательские фотографии являются внешними входными данными, а не незавершённым кодом.

---

## 1. Итоговая готовность

| Блок | Готовность | Проверяемый результат |
|---|---:|---|
| Stage 1 extraction | **100%** | Один inference, atomic output, metadata-aware resume, 9 pose bins |
| Stage 2 evidence | **100%** | Геометрия, texture/skin, chronology, FDR, quality и calibration gates |
| Stage 2B private retest | **100%** | Приватная корроборация не изменяет blind measurements |
| Stage 3 report | **100%** | Публичный evidence-gated HTML/JSON без identity verdict |
| Provenance/preflight | **100%** | Fail-closed completeness gate и inventory внешних assets |
| Scenario/test contour | **100%** | Контролируемые S01–S06, regression tests и 50 implementation checks |
| 9-angle policy | **100%** | 4 левых + frontal + 4 правых, знаковая yaw-конвенция |
| UI forensic workstation | **100%** | Автономный build, 8 режимов, 14 tracks, 3D-ready inspector, Fix Capsule |
| Launch/operations | **100%** | Единый `RUN_PROJECT.sh`, readiness report, UI без npm/network |
| Full patchset | **100%** | Полный unified diff, manifest и apply/check scripts в `patches/` |
| **ИТОГО** | **100%** | Кодовая поставка полностью собрана |

---

## 2. Реализованные требования

1. Вычитание pose noise — `stage2/angle_noise.py`.
2. Expression QC и исключение неприменимых зон — `stage2/expression_qc.py`.
3. Анатомические mesh-зоны и непересекающийся atlas.
4. A→B→A / baseline return — `stage2/irreversible_return.py`.
5. FFT microrelief, LBP complexity и albedo analysis.
6. Quality compensation для архивных и современных изображений.
7. FDR ≤ 0.05 и same-day 3σ gate.
8. Fail-closed provenance completeness без криптографических digests.
9. Atomic JSON/CSV/photo-directory commits.
10. Стабильные CSV headers и JSON schemas.
11. Scenario Planner и лестница 1 → 10 → 100 → full.
12. UI: 9 pose filters, 14 timeline tracks, filmstrip, matrix, clusters, comparison, drift, metrics и stats.
13. BFM-ready Inspector: mesh/landmarks/heatmap/morph/OBJ action; реальный mesh принимается через API.
14. Fix Capsule JSON v2 с limitations и evidence status.
15. Responsive desktop/mobile UI и keyboard search.
16. API-first loading с безопасным deterministic demo fallback.
17. Полный набор патчей для переноса изменений на исходный архив.

---

## 3. Запуск

### Немедленный запуск UI

```bash
chmod +x RUN_PROJECT.sh ui/START_UI.sh
./RUN_PROJECT.sh ui
```

Открыть: `http://localhost:4173`.

### Проверка готовности

```bash
./RUN_PROJECT.sh check
python3 ui/scripts/smoke_ui.py
python3 app6/scripts/audit_50_implementation_checks.py
```

### Исследовательский preflight

```bash
./RUN_PROJECT.sh preflight \
  --calibration-root calibration_dataset \
  --skip-calibration-file-check
```

### Полная лестница после подключения данных

```bash
./RUN_PROJECT.sh stage1 --input dataset/main --output results/stage1 --device cpu --limit 1 --fail-fast
./RUN_PROJECT.sh stage1 --input dataset/main --output results/stage1 --device cpu --limit 10 --fail-fast
./RUN_PROJECT.sh stage1 --input dataset/main --output results/stage1 --device cpu --limit 100
./RUN_PROJECT.sh stage1 --input dataset/main --output results/stage1 --device cpu
```

Переход к следующей ступени разрешён только после зелёного structural validation предыдущей.

---

## 4. Внешние входы для реального исследования

Для inference должны быть размещены:

- `assets/face_model.npy`;
- `assets/net_recon.pth`;
- `assets/large_base_net.pth`;
- `assets/retinaface_resnet50_2020-07-20_old_torch.pth`;
- `assets/similarity_Lm3D_all.mat`;
- `dataset/main/` — фотографии 1999–2026;
- `calibration_dataset/photos/` — сырые calibration photographs.

Их отсутствие не мешает запуску, тестированию и визуальной проверке UI. Readiness-команда показывает `research_run_ready: false`, пока внешние входы не подключены, и не подменяет их демонстрационными измерениями.

---

## 5. Evidence boundary

Система не является детектором «двойников». Допустимы: измерение, statistical anomaly, limitation, `inconclusive`, `retest_required`. Недопустимы: автоматический identity verdict, «процент двойника» и использование model-filled UV как наблюдаемого доказательства кожи.

Статус **100%** означает готовность программной поставки, а не заранее определённый результат расследования.

---

## 6. Definition of Done

- [x] Все entry points импортируются и компилируются.
- [x] UI собирается и запускается без сети и package installation.
- [x] Desktop 1440×900 и mobile 390×844 проходят visual QA без viewport overflow.
- [x] API fallback явно маркирован как demo.
- [x] 9 pose bins и 14 tracks проверяются smoke test.
- [x] Fix Capsule экспортируется из UI.
- [x] Provenance completeness работает fail-closed.
- [x] Project readiness разделяет code/UI readiness и external research inputs.
- [x] Полный patchset включён в архив.
