# Итоговый стек Surface Evidence Lab

Да, целевой стек именно такой:

```text
3DDFA_V3
    mesh + camera + pose

uv_module rasterizer
    source ↔ triangle ↔ barycentric mapping

potpourri3d
    canonical geodesic patches
    physical surface distances
    future graph transport

OpenCV
    remap / masks / visual overlays

FFHQ-Wrinkle U-Net
    wrinkle probability по оригинальному фото

scikit-image
    LBP / GLCM / Gabor / morphology / skeletonize

Skan
    skeleton graph

NumPy / SciPy
    matching, statistics, chronology
```

Важное разделение:

- RGB UV texture — только визуализация и morph.
- Морщины/кожа считаются по оригинальному фото или image-space patch.
- Результат переносится на mesh/UV через triangle ID + barycentric coordinates.
- Сравнение двух фото с разным yaw идёт по common observed surface patches.

`best_checkpoint_iou032.pth` — вероятный FFHQ-Wrinkle U-Net checkpoint.

`79999_iter.pth` — BiSeNet face parsing checkpoint; сейчас не обязателен, потому что Stage 1 уже даёт `face_mask.npz`.
