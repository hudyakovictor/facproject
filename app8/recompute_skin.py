"""🔁 Точечный пересчёт Skin Texture (mask + metrics) поверх готового Stage 1 (app8).

Назначение: обновить ТОЛЬКО текстурный контракт app6 (`face_mask.png`, `face_mask.npz`,
`texture.json`) в уже существующем каталоге результатов, НЕ перезапуская детекцию лица,
прогон `net_recon`, UV-развертку и экспорт mesh.

🧮 Почему это корректно без полного прогона: `app8.stage1`-эквивалент маски кожи
нуждается только в
1. `v3d` — позиционированной сетке в системе камеры; восстанавливается из npz точной
   операцией `to_camera(transform(vertices_object, rotation_matrix, translation))`
   (совпадает с `3ddfa_v3/model/recon.py`, инференс не участвует);
2. `visible_idx` — ровно `visible_mask` (renderer-visible минус нормали от камеры),
   распаковывается из `full_mesh_visible_packbits`;
3. `trans_params` и `ldm106_vertex_indices` — лежат в npz;
4. пикселей фотографии — читаются с носителя тем же декодом, что и в app6
   (`imaging.decode_oriented_bgr`).

Далее вызывается тот же код, что и в основном конвейере: `fm.segmentation_visible` →
`assets.build_skin_texture` (маска `app6.stage1.masks`, кроп `app6.stage1.assets`,
метрики `app6.stage1.authenticity`).

Пример:
    python3 -m app8.recompute_skin --results-dir /Volumes/SDCARD/storage2 \
        --photos-dir /Volumes/SDCARD/photo/main --limit 3 --verify-against-full 2
"""
from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

from .assets import build_skin_texture
from .config import IMAGE_EXTENSIONS, POSE_BINS
from .imaging import decode_oriented_bgr
from .visibility import unpack_mask

_BIN_NAMES = tuple(b[0] for b in POSE_BINS)
_NON_PHOTO_DIRS = frozenset({"packed_9bins", "packed"}) | {""}


def _is_photo_dir(path: Path) -> bool:
    """Каталог кадра: содержит reconstruction.npz (служебные ._*/архивы отбрасываются)."""
    return path.is_dir() and not path.name.startswith("._") and (path / "reconstruction.npz").is_file()


def iter_photo_dirs(results_dir: Path) -> Iterator[Path]:
    """Обходит кадры Stage 1: плоская раскладка и раскладка по бинам поз.

    Служебные каталоги (`._*`, `_*`, `packed_9bins`) пропускаются.
    """
    for entry in sorted(results_dir.iterdir()):
        if entry.name.startswith((".", "_")) or not entry.is_dir():
            continue
        if _is_photo_dir(entry):
            yield entry
            continue
        if entry.name in _NON_PHOTO_DIRS:
            continue
        for sub in sorted(entry.iterdir()):
            if sub.name in _BIN_NAMES or _is_photo_dir(sub):
                if _is_photo_dir(sub):
                    yield sub


def build_photo_index(photos_dir: Path) -> dict[str, Path]:
    """Соответствие `stem -> путь к фото` (имя каталога кадра = stem исходника)."""
    index: dict[str, Path] = {}
    for p in sorted(photos_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("._") or p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        index.setdefault(p.stem, p)
    return index


def _recon_payload_from_npz(arrays: dict[str, np.ndarray],
                            seg_channels: np.ndarray,
                            v2d_orig: np.ndarray,
                            visible_mask: np.ndarray) -> dict[str, Any]:
    """Собирает из прочитанного npz словарь в формате выхода `reconstruct_image`.

    Ровно тот набор ключей, который читают `assets.semantic_skin_mask` /
    `assets.build_skin_texture` (основной путь + fallback на проекции сетки).
    """
    return {
        "semantic_channels_224": np.asarray(seg_channels, np.float32),
        "trans_params": np.asarray(arrays["trans_params"], np.float32),
        "ldm106_indices": np.asarray(arrays["ldm106_vertex_indices"], np.int64),
        "vertices_2d_orig": np.asarray(v2d_orig, np.float32),
        "triangles": np.asarray(arrays["triangles"], np.int64),
        "visible_mask": np.asarray(visible_mask, bool),
    }


def rebuild_geometry(recon_data_npz: dict[str, np.ndarray], fm: Any):
    """Восстанавливает v3d и 2D-проекцию из npz без инференса реконструктора.

    Возвращает `(v3d, vis_idx, visible_mask, vertices_2d_orig)`.
    """
    import torch

    from .geometry import to_original_image

    device = fm.device
    shape = torch.as_tensor(np.asarray(recon_data_npz["vertices_object"], np.float32), device=device)
    shape = shape.reshape(1, *shape.shape)
    rot = torch.as_tensor(np.asarray(recon_data_npz["rotation_matrix"], np.float32), device=device).reshape(1, 3, 3)
    trans = torch.as_tensor(np.asarray(recon_data_npz["translation"], np.float32), device=device).reshape(1, 3)

    v3d = fm.to_camera(fm.transform(shape, rot, trans))

    n_vert = int(shape.shape[1])
    visible_mask = unpack_mask(np.asarray(recon_data_npz["full_mesh_visible_packbits"]), n_vert)
    front_facing = np.asarray(recon_data_npz["normals_object"], np.float32)[:, 2] > 0
    # В основном проходе visible_mask уже равен front_facing & renderer_visible;
    # пересечение вторично — страховка от смешанных версий npz.
    vis_idx = torch.as_tensor((visible_mask & front_facing).astype(np.int64), dtype=torch.int64, device=device)

    v2d_224 = fm.to_image(v3d)[0].detach().cpu().numpy()
    v2d_orig = to_original_image(v2d_224[:, :2], np.asarray(recon_data_npz["trans_params"], np.float32))
    return v3d, vis_idx, visible_mask, v2d_orig


def _verify_against_full_pipeline(stem: str, photo: Path, fast_payload: dict[str, Any]) -> dict[str, Any]:
    """Контроль точности: сравнивает быстрое восстановление с полноценным прогоном Stage 1."""
    from .reconstruction import reconstruct_image

    res = reconstruct_image(photo, device="cpu")
    if res is None:
        return {"stem": stem, "ok": False, "reason": "reconstruct_image вернул None (лицо не найдено)"}

    seg_fast = np.asarray(fast_payload["semantic_channels_224"], np.float32)
    seg_full = np.asarray(res["semantic_channels_224"], np.float32)
    v2d_fast = np.asarray(fast_payload["vertices_2d_orig"], np.float32)
    v2d_full = np.asarray(res["vertices_2d_orig"], np.float32)
    vis_fast = np.asarray(fast_payload["visible_mask"], bool)
    vis_full = np.asarray(res["visible_mask"], bool)
    return {
        "stem": stem,
        "ok": True,
        "seg_max_abs_diff": float(np.abs(seg_fast - seg_full).max()),
        "seg_flipped_pixels": int(np.count_nonzero((seg_fast >= 0.5) != (seg_full >= 0.5))),
        "v2d_max_abs_diff_px": float(np.abs(v2d_fast - v2d_full).max()),
        "visible_mask_diff_vertices": int(np.count_nonzero(vis_fast != vis_full)),
    }


def recompute_skin(
    results_dir: Path,
    photos_dir: Path,
    *,
    device: str = "cpu",
    limit: int = 0,
    only_stems: tuple[str, ...] = (),
    skip_existing: bool = False,
    verify_against_full: int = 0,
    report_path: Path | None = None,
    quiet_every: int = 50,
) -> dict[str, Any]:
    """Пересчитывает маску кожи и `texture.json` для всех кадров Stage 1 на месте."""
    results_dir = Path(results_dir).resolve()
    photos_dir = Path(photos_dir).resolve()
    if not results_dir.is_dir():
        raise FileNotFoundError(f"results dir not found: {results_dir}")
    if not photos_dir.is_dir():
        raise FileNotFoundError(f"photos dir not found: {photos_dir}")

    from .reconstruction import get_models

    import torch

    fm, _det, _basis = get_models(device)
    photo_index = build_photo_index(photos_dir)

    dirs = [d for d in iter_photo_dirs(results_dir)
            if (not only_stems or d.name in only_stems)
            and not (skip_existing and (d / "texture.json").is_file() and (d / "face_mask.png").is_file())]
    if limit > 0:
        dirs = dirs[:limit]

    print(f"[app8 recompute-skin] кадров к пересчёту: {len(dirs)} (фото-индекс: {len(photo_index)})")
    t0 = time.time()
    done = 0
    failures: list[dict[str, str]] = []
    origins: dict[str, int] = {}
    verify: list[dict[str, Any]] = []

    for idx, photo_dir in enumerate(dirs, start=1):
        stem = photo_dir.name
        photo = photo_index.get(stem)
        if photo is None:
            failures.append({"photo_id": stem, "error": "source photo not found"})
            continue
        try:
            with np.load(photo_dir / "reconstruction.npz", allow_pickle=True) as z:
                arrays = {k: z[k] for k in z.files}
            v3d, vis_idx, visible_mask, v2d_orig = rebuild_geometry(arrays, fm)
            with torch.no_grad():
                seg = np.asarray(fm.segmentation_visible(v3d.clone(), vis_idx), np.float32)
            if seg.shape != (224, 224, 8):
                raise ValueError(f"unexpected seg_visible shape {seg.shape}")

            payload = _recon_payload_from_npz(arrays, seg, v2d_orig, visible_mask)
            bgr = decode_oriented_bgr(photo)
            build_skin_texture(bgr, payload, photo_dir, photo_id=stem)

            origin = str(json.loads((photo_dir / "texture.json").read_text(encoding="utf-8"))
                         .get("source", {}).get("mask_origin", "unknown"))
            origins[origin] = origins.get(origin, 0) + 1
            done += 1
            if idx <= verify_against_full:
                verify.append(_verify_against_full_pipeline(stem, photo, payload))
            if quiet_every and idx % quiet_every == 0:
                el = time.time() - t0
                print(f"  {idx}/{len(dirs)} ок={done} {el:.0f}s ({idx / max(el, 1e-3):.2f} кад/с)")
        except Exception as exc:
            failures.append({"photo_id": stem, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    SKINFAIL: {stem} — {exc}")

    elapsed = time.time() - t0
    report = {
        "schema": "deeputin-app8-recompute-skin-v1",
        "results_dir": str(results_dir),
        "photos_dir": str(photos_dir),
        "device": device,
        "requested": len(dirs),
        "recomputed": done,
        "failed": len(failures),
        "elapsed_seconds": round(elapsed, 2),
        "photos_per_second": round(done / max(elapsed, 1e-3), 3),
        "mask_origin_distribution": origins,
        "failures": failures,
        "verify_against_full": verify,
    }
    if report_path is not None:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[app8 recompute-skin] готово: {done}/{len(dirs)} за {elapsed:.1f}с; "
          f"ошибок {len(failures)}; origins={origins}")
    for v in verify:
        print(f"  VERIFY {v}")
    return report


def main() -> int:
    p = argparse.ArgumentParser(
        description="app8: пересчёт маски кожи и texture.json поверх готового Stage 1 (без детекции/реконструкции/UV)")
    p.add_argument("--results-dir", type=Path, required=True, help="Каталог результатов Stage 1")
    p.add_argument("--photos-dir", type=Path, required=True, help="Каталог исходных фотографий")
    p.add_argument("--device", default="cpu", help="Устройство инференса сегментации (cpu)")
    p.add_argument("--limit", type=int, default=0, help="Максимум кадров (0 = все)")
    p.add_argument("--only", action="append", default=[], help="Пересчитать только указанные photo_id (можно повторно)")
    p.add_argument("--skip-existing", action="store_true",
                   help="Пропускать кадры, где уже есть face_mask.png (режим resume)")
    p.add_argument("--verify-against-full", type=int, default=0,
                   help="Для первых N кадров дополнительно прогнать полный Stage 1 и сверить маски/проекцию")
    p.add_argument("--report", type=Path, default=None, help="Куда записать JSON-отчёт о пересчёте")
    args = p.parse_args()

    rep = recompute_skin(
        args.results_dir,
        args.photos_dir,
        device=args.device,
        limit=args.limit,
        only_stems=tuple(args.only),
        skip_existing=args.skip_existing,
        verify_against_full=args.verify_against_full,
        report_path=args.report,
    )
    return 0 if rep["recomputed"] > 0 and rep["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
