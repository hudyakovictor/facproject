"""⚙️ CONFIG → Пересборка landmark_utility.npy из калибровочного набора.

Действующий артефакт признан дефектным: распределение NaN по бинам не совпадает
с зафиксированным в 09_RESULTS_REGISTER.md ни в одном профильном бине.

Utility точки в бине = обратная нормированная дисперсия её положения после
Kabsch-выравнивания внутри субъекта, усреднённая по субъектам. NaN означает
«точка не видима в этом бине» и обязана оставаться NaN: sanitize_utility
подставит fallback на этапе использования, а не на этапе сборки.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from app6.stage2.pose_policy import BIN_NAME_TO_YAW
from app6.stage2.visibility_gate import PRIOR_MIN_FRACTION, bin_visibility_prior

BINS = list(BIN_NAME_TO_YAW)


def _read_landmark_csv(path: Path, count: int = 134) -> tuple[np.ndarray, np.ndarray]:
    """Прочитать CSV точек и вернуть координаты и исходную видимость.

    Поддерживается поставочный формат:
      landmark_id,x,y,z,visible,vertex_index

    Строки обязательно должны содержать каждый landmark_id ровно один раз.
    Отсутствие колонки visible трактуется как видимость всех точек — только
    для обратной совместимости со старыми экспортами.
    """
    points = np.full((count, 3), np.nan, dtype=np.float64)
    visible = np.zeros(count, dtype=bool)
    seen: set[int] = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"landmark_id", "x", "y", "z"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: отсутствуют колонки {sorted(missing)}")

        for row in reader:
            landmark_id = int(float(row["landmark_id"]))
            if not 0 <= landmark_id < count:
                raise ValueError(
                    f"{path}: landmark_id={landmark_id} вне диапазона 0..{count - 1}"
                )
            if landmark_id in seen:
                raise ValueError(f"{path}: повтор landmark_id={landmark_id}")
            seen.add(landmark_id)

            xyz = np.asarray(
                [float(row["x"]), float(row["y"]), float(row["z"])],
                dtype=np.float64,
            )
            if not np.isfinite(xyz).all():
                raise ValueError(f"{path}: NaN/Inf в landmark_id={landmark_id}")
            points[landmark_id] = xyz

            raw_visible = str(row.get("visible", "1")).strip().lower()
            visible[landmark_id] = raw_visible in {
                "1", "true", "yes", "y", "__yes__"
            }

    missing_ids = sorted(set(range(count)) - seen)
    if missing_ids:
        raise ValueError(f"{path}: отсутствуют landmark_id {missing_ids[:10]}")

    return points, visible


def load_nested_calibration(root: Path) -> list[dict]:
    """Загрузить поставочный набор person_*/frame_*/info.json.

    Даты намеренно не читаются: калибровочный набор не имеет временной оси.
    """
    rows: list[dict] = []
    for info_path in sorted(root.rglob("info.json")):
        if "__MACOSX" in info_path.parts or any(
            part.startswith("._") for part in info_path.parts
        ):
            continue

        directory = info_path.parent
        landmark_path = directory / "ldm134_raw.csv"
        if not landmark_path.is_file():
            continue

        info = json.loads(info_path.read_text(encoding="utf-8"))
        pose_bin = str((info.get("pose") or {}).get("pose_bin") or "")
        if pose_bin not in BINS:
            raise ValueError(f"{info_path}: неизвестный pose_bin={pose_bin!r}")

        points, visible = _read_landmark_csv(landmark_path)
        rows.append({
            "bin": pose_bin,
            "points": points,
            "visible": visible,
            "directory": directory,
            "subject": directory.parent.name,
        })

    if not rows:
        raise FileNotFoundError(
            f"не найдены frame_*/info.json + ldm134_raw.csv под {root}"
        )
    return rows


def build_visibility_prior(index_rows, loader) -> np.ndarray:
    """Детерминированно собрать per-bin доли видимости."""
    prior = np.zeros((len(BINS), 134), dtype=np.float64)
    for bi, bin_name in enumerate(BINS):
        rows = [row for row in index_rows if row["bin"] == bin_name]
        if not rows:
            continue
        visible = np.stack([
            np.asarray(loader(row)[1], dtype=bool)
            for row in rows
        ])
        prior[bi] = bin_visibility_prior(visible)
    return prior


def file_sha256(path: Path) -> str:
    """Полный SHA-256 содержимого файла."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha256(index_rows) -> str:
    """Хеш входных sidecar-данных в стабильном порядке.

    В хеш входят относительный идентификатор кадра, info.json и
    ldm134_raw.csv. Поэтому нельзя подменить один кадр и сохранить прежний
    provenance-манифест.
    """
    digest = hashlib.sha256()
    ordered = sorted(
        index_rows,
        key=lambda row: (
            str(row.get("subject") or ""),
            str(row.get("directory") or ""),
            str(row.get("bin") or ""),
        ),
    )
    for row in ordered:
        directory = row.get("directory")
        if directory is not None:
            directory = Path(directory)
            digest.update(str(row.get("subject") or "").encode("utf-8"))
            digest.update(str(directory.name).encode("utf-8"))
            digest.update(str(row["bin"]).encode("utf-8"))
            for filename in ("info.json", "ldm134_raw.csv"):
                path = directory / filename
                if not path.is_file():
                    raise FileNotFoundError(path)
                digest.update(filename.encode("utf-8"))
                digest.update(path.read_bytes())
        else:
            # Формат main_timeline.csv: используем сохранённый source_digest.
            digest.update(str(row.get("subject") or "").encode("utf-8"))
            digest.update(str(row.get("source_digest") or "").encode("utf-8"))
            digest.update(str(row["bin"]).encode("utf-8"))
    return digest.hexdigest()


def build(index_rows, loader) -> tuple[np.ndarray, dict]:
    utility = np.full((len(BINS), 134), np.nan, dtype=np.float64)
    for bi, bin_name in enumerate(BINS):
        rows = [r for r in index_rows if r["bin"] == bin_name]
        if len(rows) < 5:
            continue
        pts, vis = [], []
        for r in rows:
            p, v = loader(r)
            pts.append(p); vis.append(v)
        pts = np.stack(pts); vis = np.stack(vis).astype(bool)
        for j in range(134):
            sel = vis[:, j]
            if sel.sum() < max(5, int(PRIOR_MIN_FRACTION * len(rows))):
                continue  # остаётся NaN — точка не наблюдается в бине
            spread = float(np.mean(np.var(pts[sel, j, :], axis=0)))
            utility[bi, j] = 1.0 / max(spread, 1e-12)
    # Нормировка внутри бина, чтобы веса были сопоставимы между бинами.
    for bi in range(len(BINS)):
        row = utility[bi]
        finite = np.isfinite(row)
        if finite.any():
            utility[bi, finite] = row[finite] / np.nanmax(row[finite])
    report = {
        "nan_per_bin": {
            BINS[i]: int(np.isnan(utility[i]).sum())
            for i in range(len(BINS))
        },
        "bin_counts": {
            bin_name: sum(row["bin"] == bin_name for row in index_rows)
            for bin_name in BINS
        },
        "sha256": hashlib.sha256(
            np.ascontiguousarray(
                np.nan_to_num(utility, nan=-1.0)
            ).tobytes()
        ).hexdigest(),
    }
    return utility, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="app6/atlas/landmark_utility.npy")
    ap.add_argument("--prior-out", default="app6/atlas/visibility_prior.npy")
    ap.add_argument(
        "--manifest-out",
        default="app6/atlas/landmark_utility_manifest.json",
    )
    ap.add_argument("--calibration-root", default="results/calibration_stage1")
    args = ap.parse_args()

    calibration_root = Path(args.calibration_root)
    timeline = calibration_root / "main_timeline.csv"

    if timeline.is_file():
        # Штатный свежий вывод Stage 1.
        from app6.stage2.loaders import load_main

        records = load_main(calibration_root)
        index_rows = [{
            "bin": record.pose_bin,
            "record": record,
            "subject": record.dataset_id,
            "source_digest": record.source_digest,
        } for record in records]
        source_layout = "main_timeline_v1"

        def loader(row):
            return (
                np.asarray(row["record"].ldm134, dtype=np.float64),
                np.asarray(row["record"].visible134, dtype=bool),
            )
    else:
        # Поставочный лёгкий архив person_*/frame_* без reconstruction.npz.
        index_rows = load_nested_calibration(calibration_root)
        source_layout = "person_frame_sidecar_v1"

        def loader(row):
            return (
                np.asarray(row["points"], dtype=np.float64),
                np.asarray(row["visible"], dtype=bool),
            )

    utility, report = build(index_rows, loader)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, utility)

    prior = build_visibility_prior(index_rows, loader)
    prior_out = Path(args.prior_out)
    prior_out.parent.mkdir(parents=True, exist_ok=True)
    np.save(prior_out, prior)

    manifest = {
        "schema": "deeputin-landmark-utility-manifest-v1.0",
        "source_layout": source_layout,
        "record_count": len(index_rows),
        "subject_count": len({
            str(row.get("subject") or "")
            for row in index_rows
        }),
        "bin_counts": report["bin_counts"],
        "nan_per_bin": report["nan_per_bin"],
        "utility_shape": list(utility.shape),
        "visibility_prior_shape": list(prior.shape),
        "utility_sha256": file_sha256(out),
        "visibility_prior_sha256": file_sha256(prior_out),
        "source_sha256": source_sha256(index_rows),
        "parameters": {
            "prior_min_fraction": PRIOR_MIN_FRACTION,
            "minimum_bin_frames": 5,
            "minimum_visible_frames": 5,
            "landmark_count": 134,
            "bin_order": BINS,
        },
    }

    manifest_out = Path(args.manifest_out)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"records loaded: {len(index_rows)}, index_rows: {len(index_rows)}")
    print("nan_per_bin:", report["nan_per_bin"])
    print("utility sha256:", manifest["utility_sha256"])
    print("visibility prior sha256:", manifest["visibility_prior_sha256"])
    print("source sha256:", manifest["source_sha256"])
    print("wrote", out, prior_out, "and", manifest_out)


if __name__ == "__main__":
    main()
