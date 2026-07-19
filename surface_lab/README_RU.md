# surface_lab

Эта папка должна лежать в корне проекта рядом с `uv_module`:

```text
/Users/victorkhudyakov/work/
├── uv_module/      # отдельный texture/UV module, НЕ входит в этот архив
└── surface_lab/    # все файлы Surface Evidence Lab
```

Внутри `surface_lab/` лежит всё, что относится к новому pipeline:

```text
surface_lab/
├── run_lab.py
├── doctor.py
├── setup_macos_m1.sh
├── requirements-macos-m1.txt
├── requirements-geometry-extra.txt
├── backends.py
├── config.py
├── graphs.py
├── identity.py
├── mesh_patches.py
├── pipeline.py
├── records.py
├── tests/
└── third_party/
```

`uv_module` остаётся отдельной соседней папкой и импортируется из корня проекта.

## Установка

```bash
cd /Users/victorkhudyakov/work
rm -rf surface_lab
unzip -q ~/Downloads/surface_lab.zip

cd surface_lab
source /Users/victorkhudyakov/work/.venv/bin/activate
chmod +x setup_macos_m1.sh
./setup_macos_m1.sh
python doctor.py
```

В `doctor.py` должно быть:

```text
uv_module: /Users/victorkhudyakov/work/uv_module/__init__.py
```

## Важно про глаза и губы

По умолчанию `surface_lab` теперь запускает FFHQ по **всему изображению/видимому лицу**:

```text
--analysis-region full_face
```

UV overlay тоже строится по `observed_face_mask`, поэтому глаза/губы больше не вырезаются из визуализации. Skin-only режим оставлен только для будущих texture metrics:

```text
--analysis-region skin_only
```

Дополнительно сохраняются:

```text
image_wrinkle_overlay.png
uv_observed_face_preview.png
uv_observed_skin_preview.png
```

## Технический тест без FFHQ-весов

```bash
python run_lab.py \
  --records /Users/victorkhudyakov/work/runs/uv_test_2_replacement \
  --output /Users/victorkhudyakov/work/runs/surface_lab_classical \
  --backend classical \
  --limit 2 \
  --all-pairs
```

## Запуск с FFHQ-Wrinkle

```bash
python run_lab.py \
  --records /Users/victorkhudyakov/work/runs/uv_test_2_replacement \
  --output /Users/victorkhudyakov/work/runs/surface_lab_ffhq \
  --backend ffhq \
  --checkpoint /Users/victorkhudyakov/Downloads/best_checkpoint_iou032.pth \
  --device cpu \
  --limit 2
```
