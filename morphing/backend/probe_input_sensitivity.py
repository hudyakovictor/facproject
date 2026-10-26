"""🧪 Чувствительность конвейера к входу при неизменной геометрии (morphing).

Зачем. `calibrate_pose_noise.py` измеряет повторяемость на видеокадрах одной
съёмочной сессии: в парной разности сокращается общее смещение сессии (камера,
свет, обработка), и это данным материалом не измеряется в принципе. Здесь берётся
**один и тот же кадр**, геометрия которого по построению не меняется, и к нему
применяются деградации входа (свет, gamma, contrast, размытие, перемасштабирование,
сдвиг окна, JPEG). Вопрос, на который отвечает прогон: «0.003 — это шум конвейера
или его устойчивость?». Если сдвиг формы на джиттере одного кадра сопоставим с
полосой видеокадров, полоса измеряет чувствительность сети, а не «шум», которого
нет.

По каждой версии пишется:
— `mean_delta`/`p95_delta`/`max_delta` против контроль-версии того же кадра
  (те же единицы, что и в калибровке — доли краниометрического радиуса);
— `dyaw`/`dpitch` — уехала ли оценка позы вместе с формой;
— `alpha_id_rel` — относительный сдвиг коэффициентов формы, независимо от сетки;
— `radius_ratio` — как изменился нормировочный радиус (т.е. знаменатель метрики);
— справочная полоса бина контроль-кадра и вердикт по ней (`pose_noise_model`).

Важно: версии с малым `dyaw` не отбираются — отбор по выходу реконструктора
скрыл бы именно те его ошибки, которые измеряются. И `blur`/`downscale` меняют
информативность кадра (пропадают детали), поэтому они прокси к реальной пересъёмке
с другим фокусом/разрешением, а не доказательство того, что метрика «должна» быть
нулевой. Чистая устойчивость конвейера к идентичным пикселям — это `control`.

Запуск (офлайн, CPU):
    cd /Users/victorkhudyakov/work
    OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m morphing.backend.probe_input_sensitivity \\
        --photos /Volumes/SDCARD/calibration_rakurs/person_02/frontal/frame_000222.jpg \\
        --workers 1
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK_DIR = ROOT / ".runtime" / "sens_probe"

# (имя, параметр) в том порядке, в котором версии пишутся в отчёт.
VARIANTS: tuple[tuple[str, float], ...] = (
    ("control", 0.0),
    ("brightness+10", 0.10),
    ("brightness-10", -0.10),
    ("brightness+5", 0.05),
    ("gamma_up", 1.10),
    ("gamma_down", 0.90),
    ("contrast_up", 1.10),
    ("contrast_down", 0.90),
    ("blur_sigma1", 1.0),
    ("downscale_0.7", 0.70),
    ("crop_shift_3pct", 0.03),
    ("jpeg_q70", 70.0),
    ("jpeg_q40", 40.0),
)


def _degrade(rgb: np.ndarray, kind: str, value: float) -> np.ndarray:
    """Возвращает RGB (uint8) того же кадра при неизменной геометрии морфинга пикселей."""
    from PIL import Image, ImageFilter

    img = Image.fromarray(np.clip(np.asarray(rgb, dtype=np.float32), 0, 255).astype(np.uint8))
    if kind == "control":
        return np.asarray(img)
    if kind.startswith("brightness"):
        return np.clip(np.asarray(img, dtype=np.float32) + 255.0 * value, 0, 255).astype(np.uint8)
    if kind.startswith("gamma"):
        arr = np.asarray(img, dtype=np.float32) / 255.0
        return np.clip(arr ** (1.0 / value) * 255.0, 0, 255).astype(np.uint8)
    if kind.startswith("contrast"):
        arr = np.asarray(img, dtype=np.float32)
        mean = float(arr.mean())
        return np.clip((arr - mean) * value + mean, 0, 255).astype(np.uint8)
    if kind.startswith("blur"):
        return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=value)))
    if kind.startswith("downscale"):
        width, height = img.size
        small = img.resize((max(1, int(width * value)), max(1, int(height * value))))
        return np.asarray(small.resize((width, height)))
    if kind.startswith("crop_shift"):
        # Сдвиг окна на % ширины с заворотом края: лицо то же, рамка детектора другая.
        shift = max(1, int(round(img.size[0] * value)))
        return np.roll(np.asarray(img), shift, axis=1)
    if kind.startswith("jpeg"):
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=int(value))
        buffer.seek(0)
        return np.asarray(Image.open(buffer).convert("RGB"))
    raise ValueError(f"неизвестный вариант: {kind}")


def _mesh_and_heads(recon: dict[str, Any]) -> tuple[np.ndarray, float, float, np.ndarray, float]:
    """(сетка в нормированном объектном пространстве, yaw, pitch, alpha_id, радиус)."""
    from morphing.backend.aligner import align_identity_mesh

    vertices, _, radius = align_identity_mesh(recon)
    angles = np.asarray(recon["angles_deg"], dtype=np.float64)
    alpha = np.asarray(recon["alpha_id"], dtype=np.float64)
    return vertices, float(angles[1]), float(angles[0]), alpha, float(radius)


def _render(work: Path, stem: str, kind: str, value: float, pixels: np.ndarray) -> Path:
    from PIL import Image

    out = work / f"{stem}__{kind}.png"
    Image.fromarray(_degrade(pixels, kind, value)).save(out, format="PNG")
    return out


def _probe_photo(job: tuple[str, int]) -> dict[str, Any]:
    from app8.imaging import decode_oriented_bgr
    from app8.reconstruction import reconstruct_image

    photo, worker_index = job
    source = Path(photo)
    work = WORK_DIR / f"w{worker_index}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        pixels = decode_oriented_bgr(source)[:, :, ::-1]  # BGR -> RGB
        control = reconstruct_image(_render(work, source.stem, "control", 0.0, pixels), device="cpu")
        if not control:
            return {"photo": str(source), "error": "контрольный кадр не реконструировался"}
        mesh_c, yaw_c, pitch_c, alpha_c, radius_c = _mesh_and_heads(control)

        rows: list[dict[str, Any]] = []
        for kind, value in VARIANTS:
            if kind == "control":
                continue
            recon = reconstruct_image(_render(work, source.stem, kind, value, pixels), device="cpu")
            if not recon:
                rows.append({"variant": kind, "failed": True})
                continue
            mesh, yaw, pitch, alpha, radius = _mesh_and_heads(recon)
            dist = np.linalg.norm(mesh - mesh_c, axis=1)
            rows.append({
                "variant": kind,
                "mean_delta": round(float(dist.mean()), 8),
                "p95_vertex": round(float(np.percentile(dist, 95)), 8),
                "max_delta": round(float(dist.max()), 8),
                "dyaw": round(yaw - yaw_c, 3),
                "dpitch": round(pitch - pitch_c, 3),
                "alpha_id_rel": round(
                    float(np.linalg.norm(alpha - alpha_c) / max(float(np.linalg.norm(alpha_c)), 1e-9)), 5
                ),
                "radius_ratio": round(radius / max(radius_c, 1e-9), 5),
            })
        return {"photo": str(source), "bin": control.get("pose_bin"), "yaw": round(yaw_c, 3), "rows": rows}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _annotate(payload: dict[str, Any]) -> None:
    """Ставит каждую версию рядом с замороженной полосой бина контроль-кадра."""
    from morphing.backend.pose_noise_model import noise_reference

    pose_bin = payload.get("bin")
    if not pose_bin:
        return
    for row in payload.get("rows", []):
        if row.get("failed"):
            continue
        ref = noise_reference(pose_bin, row["mean_delta"], yaw_spread_deg=abs(row["dyaw"]))
        row["band_source"] = ref.get("band_source")
        row["band_p50"] = ref.get("expected_p50")
        row["band_p95"] = ref.get("expected_p95")
        row["verdict"] = ref.get("verdict")
        row["verdict_label"] = ref.get("verdict_label")


def main() -> int:
    parser = argparse.ArgumentParser(description="Чувствительность реконструкции к джиттеру входа")
    parser.add_argument("--photos", required=True, nargs="+", type=Path)
    parser.add_argument("--workers", default=1, type=int)
    parser.add_argument("--out", default=str(WORK_DIR / "sensitivity.json"), type=Path)
    args = parser.parse_args()

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [(str(path.resolve()), index) for index, path in enumerate(args.photos)]
    results: list[dict[str, Any]] = []
    if args.workers <= 1:
        results = [_probe_photo(job) for job in jobs]
    else:
        # imap_unordered, а не map: прогон на десятки минут, и без строк прогресса
        # он выглядит зависшим.
        done = 0
        with Pool(processes=min(args.workers, len(jobs)), maxtasksperchild=1) as pool:
            for payload in pool.imap_unordered(_probe_photo, jobs):
                done += 1
                print(f"[{done}/{len(jobs)}] {payload['photo'] if payload else 'сбой'}", flush=True)
                results.append(payload)
    results = [payload for payload in results if payload]
    for payload in results:
        _annotate(payload)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"photos": results}, ensure_ascii=False, indent=2))
    for payload in results:
        print(f"\n{payload['photo']}  bin={payload.get('bin')} yaw={payload.get('yaw')}")
        for row in payload.get("rows", []):
            if row.get("failed"):
                print(f"  {row['variant']:18s} не реконструировался")
                continue
            print(f"  {row['variant']:18s} d={row['mean_delta']:.5f} p95верш={row['p95_vertex']:.5f} "
                  f"Δyaw={row['dyaw']:+.2f}° α'={row['alpha_id_rel']:.4f} r×={row['radius_ratio']:.4f} "
                  f"→ {row.get('verdict_label', '?')} (полоса {row.get('band_p50')}–{row.get('band_p95')})")
    print(f"\nСохранено: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
