"""Хронологический морфинг-ролик из уже извлечённых 106 ориентиров.

Источник: facresults/facresults_v27.npz (L106_identity_normalized, 1909 датированных кадров).
Идея: кадры сортируются по дате (из имени файла), координаты сглаживаются по
времени, между соседними кейфреймами вставляется N промежуточных, каждый кадр
рендерится как 3D-облако 106 ориентиров, затем ffmpeg склеивает в MP4.

Видео принадлежит основному пайплайну (это офлайн-джоба), а не 4-слотовый
GPU-шейдер morphing-веба. Никакой реконструкции не выполняется — только чтение npz.

Примеры:
    # быстрое превью (мало кейфреймов, короткий mp4 + пара PNG)
    python scripts/chronology_morph_video.py --preview

    # длинный ролик: по одному реперу в месяц, фронтальные кадры, 8 вставок между
    python scripts/chronology_morph_video.py --per-month --frontal --interp 8 --fps 30
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NPZ_PATH = ROOT / "facresults" / "facresults_v27.npz"

# Индексы столбцов meta (см. meta_cols в npz)
COL_YAW, COL_PITCH, COL_ROLL, COL_SMILE = 8, 9, 10, 7


def parse_date(pid: str) -> dt.date | None:
    """Из имени вида '1999_08_12_2__hash' / '1998_01_01__hash' берёт дату."""
    head = pid.split("__")[0].split("_")
    try:
        return dt.date(int(head[0]), int(head[1]), int(head[2]))
    except (ValueError, IndexError):
        return None


def load_timeline(npz_path: Path, frontal_deg: float | None, drop_smiles: bool):
    # только числовые/строковые массивы — pickle не нужен (hardening)
    data = np.load(npz_path, allow_pickle=False)
    pids = [str(x) for x in data["pids"]]
    landmarks = data["L106_identity_normalized"].astype(np.float64)  # (N,106,3)
    meta = data["meta"].astype(np.float64)

    dates = [parse_date(p) for p in pids]
    keep = np.array([d is not None for d in dates])
    if frontal_deg is not None:
        yaw = np.abs(meta[:, COL_YAW])
        keep &= np.isfinite(yaw) & (yaw <= float(frontal_deg))
    if drop_smiles:
        keep &= np.nan_to_num(meta[:, COL_SMILE]) < 0.5

    idx = np.where(keep)[0]
    recs = [(dates[i], i) for i in idx]
    recs.sort(key=lambda r: r[0])  # хронологический порядок
    order = [i for _, i in recs]
    sorted_dates = [dates[i] for i in order]
    return landmarks[order], sorted_dates, [pids[i] for i in order]


def select_keyframes(landmarks, dates, per_month: bool, stride: int, per_year: int = 0):
    """Прореживает хронологию до кейфреймов (по году / по месяцу / с шагом).

    per_year>0: до N кейфреймов на каждый год, равномерно по дате внутри года.
    """
    if per_year and per_year > 0:
        by_year: dict[int, list[int]] = {}
        for k, d in enumerate(dates):  # dates уже хронологически отсортированы
            by_year.setdefault(d.year, []).append(k)
        out = []
        for year in sorted(by_year):
            idxs = by_year[year]
            take = min(per_year, len(idxs))
            picks = sorted(set(np.linspace(0, len(idxs) - 1, take).round().astype(int).tolist()))
            out.extend(idxs[p] for p in picks)
        return np.array(sorted(out))
    if per_month:
        seen, out = set(), []
        for k, d in enumerate(dates):
            key = (d.year, d.month)
            if key not in seen:
                seen.add(key)
                out.append(k)
        return np.array(out)
    return np.arange(0, len(dates), max(1, stride))


def smooth(series: np.ndarray, window: int) -> np.ndarray:
    """Скользящее среднее по оси времени для подавления шума реконструкции."""
    if window <= 1:
        return series
    n = series.shape[0]
    pad = window // 2
    ext = np.concatenate([np.repeat(series[:1], pad, 0), series, np.repeat(series[-1:], pad, 0)], axis=0)
    kernel = np.ones(window) / window
    flat = series.reshape(n, -1)
    ext_flat = ext.reshape(ext.shape[0], -1)
    out = np.empty_like(flat)
    for i in range(n):
        seg = ext_flat[i:i + window]
        out[i] = seg.mean(axis=0)
    _ = kernel  # равномерное окно; оставлено для читаемости
    return out.reshape(series.shape)


def build_frames(key_lm: np.ndarray, interp: int) -> tuple[np.ndarray, list[float]]:
    """Линейная интерполяция между соседними кейфреймами; возвращает кадры и позиции t."""
    frames = []
    for a, b in zip(key_lm[:-1], key_lm[1:]):
        for s in range(interp):
            u = s / interp
            frames.append(a + (b - a) * u)
    frames.append(key_lm[-1])
    return np.stack(frames), list(range(len(frames)))


def render_frame(ax_manager, lm, year_label, diag_color):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = ax_manager["fig"]
    ax = ax_manager["ax"]
    if ax is not None:
        ax.cla()
        fig.canvas.draw()
    fig.clf()
    ax = fig.add_subplot(111, projection="3d")
    # конвенция 3DDFA: axis0=ширина, axis1=верх(вертикаль), axis2=глубина.
    # matplotlib делает z вертикалью -> подаём x=ширина, y=глубина, z=верх.
    x, y, z = lm[:, 0], lm[:, 2], lm[:, 1]
    ax.scatter(x, y, z, c=diag_color if diag_color is not None else "#00ffaa", s=14, depthshade=False)
    ax.set_xlim(-1.2, 1.2); ax.set_ylim(-1.0, 1.0); ax.set_zlim(-1.35, 1.0)
    ax.set_box_aspect((1, 1, 1.1))
    ax.set_axis_off()
    ax.view_init(elev=0, azim=-90)  # фронтальная проекция (смотрим вдоль глубины)
    ax.text2D(0.03, 0.95, year_label, transform=ax.transAxes, fontsize=13, color="#e6edf3")
    ax_manager["fig"] = fig
    ax_manager["ax"] = ax
    return fig


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=str(NPZ_PATH))
    ap.add_argument("--out", default=str(ROOT / ".runtime" / "output" / "chronology_morph.mp4"))
    ap.add_argument("--frontal", type=float, default=None, help="фильтр по |yaw|, градусы (напр. 20)")
    ap.add_argument("--drop-smiles", action="store_true")
    ap.add_argument("--per-month", action="store_true", help="по одному кейфрейму в месяц")
    ap.add_argument("--per-year", type=int, default=0, help="до N кейфреймов на год (равномерно по дате)")
    ap.add_argument("--stride", type=int, default=1, help="каждый N-й кейфрейм (если не --per-month/--per-year)")
    ap.add_argument("--interp", type=int, default=8, help="вставок между соседними кейфреймами")
    ap.add_argument("--smooth", type=int, default=3, help="окно сглаживания по времени")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--preview", action="store_true", help="мало кадров + PNG-пробы")
    args = ap.parse_args()

    lm_all, dates, pids = load_timeline(Path(args.npz), args.frontal, args.drop_smiles)
    print(f"Кандидатов после фильтра: {len(dates)} | диапазон {dates[0]} → {dates[-1]}")

    if args.preview:
        key_idx = select_keyframes(lm_all, dates, per_month=False, stride=max(1, len(dates) // 40))
        out_dir = Path(ROOT / ".runtime" / "output")
        out_dir.mkdir(parents=True, exist_ok=True)
        # пара статичных PNG для проверки кадрирования
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        for tag, k in (("start", key_idx[0]), ("end", key_idx[-1])):
            fig = plt.figure(figsize=(5, 5), dpi=90)
            am = {"fig": fig, "ax": None}
            fr = render_frame(am, lm_all[k], str(dates[k]), None)
            fr.savefig(out_dir / f"preview_{tag}.png"); plt.close(fig)
            print("PNG:", out_dir / f"preview_{tag}.png")

    key_idx = select_keyframes(lm_all, dates, args.per_month, args.stride, args.per_year)
    if args.preview:
        key_idx = key_idx[:: max(1, len(key_idx) // 40)]
    key_lm = lm_all[key_idx]
    key_dates = [dates[i] for i in key_idx]
    if args.smooth > 1:
        key_lm = smooth(key_lm, args.smooth)
    print(f"Кейфреймов: {len(key_lm)} → кадров видео с интерполяцией: {(len(key_lm)-1)*args.interp + 1}")

    frames, _ = build_frames(key_lm, args.interp)
    # подписи по времени: интерполяция дат между кейфреймами
    d0 = key_dates[0]
    total = len(frames)

    tmp = Path(tempfile.mkdtemp(prefix="morphframes_"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    am = {"fig": plt.figure(figsize=(5, 5), dpi=90), "ax": None}
    step = max(1, total // 400) if not args.preview else 1
    for i, lm in enumerate(frames):
        frac = i / max(1, total - 1)
        span_days = (key_dates[-1] - key_dates[0]).days
        cur = key_dates[0] + dt.timedelta(days=int(frac * span_days))
        fig = render_frame(am, lm, f"{cur.isoformat()}  ·  {1998 + frac*(2026-1998):.1f} г.", None)
        fig.savefig(tmp / f"frame_{i:05d}.png", facecolor="#0b0c10")
        plt.close(fig)
        if i % 200 == 0:
            print(f"  кадр {i}/{total}")

    out_path = Path(args.out)
    if args.preview:
        out_path = out_path.with_name("chronology_morph_preview.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(tmp / "frame_%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("VIDEO:", out_path)


if __name__ == "__main__":
    main()
