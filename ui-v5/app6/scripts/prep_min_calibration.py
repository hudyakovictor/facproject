"""Подготовка минимального калибровочного набора: 3 фото от каждой персоны,
переименованные в формат YYYY_MM_DD."""
import shutil
import pathlib

src = pathlib.Path("calibration_dataset/photos")
dst = pathlib.Path("calibration_min/photos")
dst.mkdir(parents=True, exist_ok=True)
for old in dst.iterdir():
    if old.is_file():
        old.unlink()

persons = sorted(p for p in src.iterdir() if p.is_dir())
count = 0
# Несколько фото на персону (для начала), с валидными датами YYYY_MM_DD.
# Берём кадры с шагом, чтобы покрыть разные позы (не только первые профили).
for pi, person in enumerate(persons, start=1):
    frames = sorted(person.glob("*.jpg"))
    step = max(1, len(frames) // 8)
    selected = frames[::step][:8]
    for fi, f in enumerate(selected, start=1):
        new_name = f"20{pi:02d}_01_{fi:02d}.jpg"
        shutil.copy2(f, dst / new_name)
        count += 1
print("copied:", count)
print(sorted(p.name for p in dst.iterdir()))