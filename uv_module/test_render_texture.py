#!/usr/bin/env python3
"""
Тест рендера UV-текстуры: только пакет uv_module (HDUVTextureGenerator).

DEV_FIX_TZ B5 / P2.15 / P3.19: из этого файла удалены устаревший путь
`/Users/victorkhudyakov/dutin` (старое имя проекта) и инструкция, ссылавшаяся
на несуществующие модули `app.pipeline.reconstruction` /
`app.pipeline.hduv_texture`. Их в текущем дереве нет — воспроизвести описанный
рецепт было невозможно. Сам рендер (`render_uv_texture`) рабочий и зависит
только от `uv_module`.

Запуск (из корня репозитория — нужен пакет uv_module с относительными импортами):

  python -m uv_module.test_render_texture --image path/to/photo.jpg --npz path/to/recon.npz

В recon.npz должны быть массивы: vertices, vertices_2d, vertices_3d, triangles,
uv_coords (как для HDUVTextureGenerator.generate).

Актуальный источник этих массивов в текущей кодовой базе — Stage 1:
`app6/run_stage1.py` сохраняет `reconstruction.npz` рядом с остальными
артефактами фото (см. `app6/stage1/storage.py`), и именно он подаётся в
`--npz`. Отдельного адаптера `app.pipeline.*` в проекте не существует; если
нужен ad-hoc .npz, собирайте его из уже сохранённого вывода Stage 1, а не
повторным инференсом (`app6/AGENTS.md`: Stage 2+ не перезапускают
реконструкцию).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Каталог по умолчанию внутри существующего дерева: `app/masktest/` в проекте
# отсутствует, из-за чего вывод уходил в неожиданное место (B5).
_DEFAULT_RENDER_OUT = _REPO_ROOT / "uv_module" / "_cache" / "test_results"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from uv_module.hd_uv_generator import HDUVConfig, HDUVTextureGenerator


def _load_recon_npz(path: Path) -> dict:
    # Массивы recon — чистая численная геометрия; pickle не нужен и небезопасен.
    z = np.load(path, allow_pickle=False)
    keys = ("vertices", "vertices_2d", "vertices_3d", "triangles", "uv_coords")
    out = {}
    for k in keys:
        if k not in z.files:
            raise KeyError(f"{path}: нет ключа {k!r}, есть {z.files}")
        out[k] = np.asarray(z[k])
    return out


def render_uv_texture(
    image_path: Path,
    npz_path: Path,
    out_dir: Path,
    *,
    uv_size: int = 2048,
    super_sample: int = 1,
) -> Path:
    """Рендер UV по реальному фото и recon_dict из .npz."""
    out_dir.mkdir(parents=True, exist_ok=True)
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise FileNotFoundError(f"Не удалось прочитать изображение: {image_path}")
    recon = _load_recon_npz(npz_path)

    cfg = HDUVConfig(uv_size=uv_size, super_sample=super_sample, verbose=False)
    gen = HDUVTextureGenerator(cfg)
    uv_tex, mask, _conf, _aux = gen.generate(image_bgr, recon)

    stem = image_path.stem
    tex_path = out_dir / f"{stem}_uv_texture.png"
    mask_path = out_dir / f"{stem}_uv_mask.png"
    cv2.imwrite(str(tex_path), uv_tex)
    cv2.imwrite(str(mask_path), (mask.astype(np.uint8) * 255))
    return tex_path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Рендер UV-текстуры (только uv_module); нужны реальное фото и recon .npz"
    )
    p.add_argument("--image", type=Path, required=True, help="Входное фото (BGR, как cv2.imread)")
    p.add_argument("--npz", type=Path, required=True, help="recon_dict в .npz")
    p.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_RENDER_OUT,
        help="Каталог для PNG (по умолчанию uv_module/_cache/test_results)",
    )
    p.add_argument("--uv-size", type=int, default=2048, help="Как в get_hduv по умолчанию")
    p.add_argument("--super-sample", type=int, default=1, help="Как в get_hduv по умолчанию")
    args = p.parse_args()

    if not args.image.is_file():
        print(f"Нет файла: {args.image}", file=sys.stderr)
        return 2
    if not args.npz.is_file():
        print(f"Нет файла: {args.npz}", file=sys.stderr)
        return 2

    try:
        out = render_uv_texture(
            args.image,
            args.npz,
            args.out,
            uv_size=args.uv_size,
            super_sample=args.super_sample,
        )
    except Exception as e:
        print(e, file=sys.stderr)
        return 1
    print(f"OK -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
