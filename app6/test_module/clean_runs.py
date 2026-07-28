#!/usr/bin/env python3
"""🧹 Очистка директорий runs/ от тяжёлых артефактов Stage 1.

После того как сценарий проверен и check_result.json сохранён, `stage1/`
внутри каждого run занимает ~15 МБ на кадр (mesh.obj, uv_texture.png,
reconstruction.npz, uv.npz и пр.) — в сумме до 1.3+ ГБ.

Эти данные не нужны:
- для отображения результатов в UI (читает только check_result.json)
- для повторного запуска `check` (читает только stage2/)

Нужны только если перезапускать Stage 2→2B→3 с нуля.

Использование:
  python -m test_module.clean_runs              # сухой прогон (что будет удалено)
  python -m test_module.clean_runs --apply      # реально удалить stage1/
  python -m test_module.clean_runs --heavy-only # удалить только mesh.obj, uv*, reconstruction.npz
  python -m test_module.clean_runs --list       # только показать размеры
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"

# Тяжёлые файлы, которые можно удалить, оставив лёгкие (landmarks, info.json и т.д.)
HEAVY_PATTERNS = {
    "mesh.obj",
    "mesh.mtl",
    "uv_texture.png",
    "uv.npz",
    "reconstruction.npz",
    "face_mask.png",
    "face_crop.jpg",
    "semantic_channels.npz",
}


def _size_str(path: Path | int) -> str:
    if isinstance(path, int):
        size = path
    else:
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def list_runs() -> list[tuple[str, Path, Path | None]]:
    """Return (name, run_dir, stage1_dir) for each run that has stage1/."""
    results = []
    for d in sorted(RUNS_DIR.iterdir()):
        if d.is_dir():
            s1 = d / "stage1"
            results.append((d.name, d, s1 if s1.is_dir() else None))
    return results


def dry_run() -> None:
    """Show what would be deleted."""
    total_before = 0
    total_after = 0
    rows = []
    for name, rdir, s1 in list_runs():
        before = sum(f.stat().st_size for f in rdir.rglob("*") if f.is_file())
        total_before += before
        if s1:
            s1_size = sum(f.stat().st_size for f in s1.rglob("*") if f.is_file())
            rows.append((name, _size_str(rdir), _size_str(s1), ""))
            total_after += before - s1_size
        else:
            rows.append((name, _size_str(rdir), "—", "stage1 уже удалён"))
            total_after += before
    print(f"{'Run':45s} {'Сейчас':>8s} {'stage1':>8s}  Заметки")
    print("-" * 75)
    for name, now, s1sz, note in rows:
        print(f"{name:45s} {now:>8s} {s1sz:>8s}  {note}")
    saved = total_before - total_after
    print("-" * 75)
    print(f"{'ИТОГО':45s} {_size_str(total_before):>8s}              "
          f"освободится {_size_str(saved) if saved else '—'}")
    print(f"После очистки: {_size_str(total_after)}")


def remove_stage1(apply: bool = False) -> None:
    """Delete entire stage1/ from each run dir."""
    total_saved = 0
    for name, rdir, s1 in list_runs():
        if s1 is None:
            continue
        size = sum(f.stat().st_size for f in s1.rglob("*") if f.is_file())
        print(f"  {'🗑 удаляю' if apply else '  будет удалён'} {_size_str(size):>8s}  {name}/stage1/")
        if apply:
            shutil.rmtree(s1)
        total_saved += size
    print(f"  {'Освобождено' if apply else 'Освободится'}: {_size_str(total_saved)}")


def remove_heavy_only(apply: bool = False) -> None:
    """Remove only heavy render/texture files, keep landmarks & metadata."""
    total_saved = 0
    for name, rdir, s1 in list_runs():
        if s1 is None:
            continue
        for f in s1.rglob("*"):
            if f.is_file() and f.name in HEAVY_PATTERNS:
                sz = f.stat().st_size
                total_saved += sz
                if apply:
                    f.unlink()
                print(f"  {'🗑' if apply else '  '} {_size_str(sz):>8s}  {f.relative_to(RUNS_DIR)}")
    print(f"  {'Освобождено' if apply else 'Освободится'}: {_size_str(total_saved)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Очистка runs/ от артефактов Stage 1")
    ap.add_argument("--apply", action="store_true", help="Реально удалить (иначе сухой прогон)")
    ap.add_argument("--heavy-only", action="store_true", help="Удалить только mesh.obj, uv*, reconstruction, маски")
    ap.add_argument("--list", action="store_true", help="Показать размеры всех runs и выйти")
    args = ap.parse_args()

    if args.list:
        dry_run()
        return

    print(f"🧹 Очистка {RUNS_DIR}")
    if args.apply:
        print("   — ПРИМЕНЕНИЕ —")
    else:
        print("   — СУХОЙ ПРОГОН — (добавьте --apply для реального удаления)")
    print()

    if args.heavy_only:
        remove_heavy_only(apply=args.apply)
    else:
        remove_stage1(apply=args.apply)

    if not args.apply:
        print()
        print("💡 Запустите с --apply для реального удаления")
    else:
        print()
        print("✅ Готово")


if __name__ == "__main__":
    main()
