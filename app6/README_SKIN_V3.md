# app6 native skin pipeline — A20/S40/W14/Q v3

## Неподвижные правила

- Анализ выполняется по пикселям исходного EXIF-oriented фото.
- Каноническая маска — существующий `face_mask.npz:mask_original`, создаваемый вместе с `face_mask.png`. Preview 424×500 не используется как источник микротекстуры.
- Фон, глаза, брови и губы исключены mask policy до извлечения признаков.
- UV создаётся ровно один раз: `uv_texture.png` + `uv.npz:texture_bgr`. Это только 3D visualization/future morphing, не skin evidence.
- A20 — stable partition; S40 — nested partition; W14 — overlay; Q — core/boundary.

## Внешние веса

```bash
python3 app6/scripts/fetch_external_assets.py --output assets
python3 app6/scripts/preflight_skin_v3.py --project-root .
```

Отдельно положить FFHQ checkpoints в `FFHQ-detect-face-wrinkles/res/cp/`:

- `wrinkle_model.pth` или `best_checkpoint_iou032.pth`;
- `face_segmentation.pth`.

Без них classical wrinkle branch продолжает работать, а FFHQ/contamination имеют честный статус `weights_unavailable`.

## Stage 1 package

```text
skin/
  manifest.json + SUCCESS
  surface_observations.npz
  atlas_projection.npz
  quality_maps.npz / quality.json
  photometric_branches.npz
  patch_index.npz
  features/basic_macro.npz
  features/texture.npz
  features/local_candidates.npz
  wrinkles/classical.npz
  wrinkles/ffhq.npz          # только при наличии checkpoint
  wrinkles/summary.json
  material/evidence.json
  sensitivity/degradation.json
```

Реализованы native-mask LBP, masked GLCM, Gabor, spectrum, structure tensor, LoG/local variation, persistent candidates, classical wrinkle surface graph, optional FFHQ, quality decomposition, degradation sensitivity, common-surface pair comparison, geodesic wrinkle/local matching и chronology candidates.

## Запуск

```bash
python3 -m unittest discover -s app6/tests -v
python3 app6/scripts/release_gate_skin.py --phase engineering
python3 app6/run_stage1.py ...
python3 app6/run_skin_stage2.py --stage1 RESULTS --output SKIN_STAGE2
python3 app6/run_skin_stage3.py --stage2 SKIN_STAGE2 --output REPORT
```

Calibration/main gates требуют dataset metadata без capture-event/duplicate leakage и frozen calibration artifact. Material probability остаётся `null` до отдельной PAD/material calibration.
