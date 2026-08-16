"""Сборка воспроизводимого исходного ZIP без весов и локальных зависимостей."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "coverage",
    "__MACOSX",
    "runs",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pth",
}


def excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    if any(part.startswith("._") for part in relative.parts):
        return True
    if path.name == ".DS_Store":
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    # Папки весов не входят в исходный архив.
    if "assets" in relative.parts:
        return True
    return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="deeputin-source-lite.zip")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve()

    files = sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and path.resolve() != out
        and not excluded(path, root)
    )

    # Фиксированная дата делает ZIP бинарно воспроизводимым.
    fixed_time = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(
        out,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=fixed_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())

    with zipfile.ZipFile(out) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"повреждённая запись ZIP: {bad}")

    print("archive:", out)
    print("files:", len(files))
    print("bytes:", out.stat().st_size)
    print("sha256:", sha256(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
