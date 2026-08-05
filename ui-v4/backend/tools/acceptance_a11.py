"""Приёмка A11 на полном наборе из 943 калибровочных кадров.

Запуск:
    python3 tools/acceptance_a11.py \
      --calibration-root /path/to/calibration_dataset

Код возврата 0 выдаётся только при полном PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.rebuild_landmark_utility import (  # noqa: E402
    BINS,
    build,
    build_visibility_prior,
    load_nested_calibration,
)


EXPECTED_BIN_COUNTS = {
    "left_profile": 187,
    "left_deep": 49,
    "left_mid": 63,
    "left_light": 69,
    "frontal": 186,
    "right_light": 77,
    "right_mid": 68,
    "right_deep": 56,
    "right_profile": 188,
}

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def arrays_equal(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.array_equal(
        np.nan_to_num(a, nan=-1.0, posinf=-2.0, neginf=-3.0),
        np.nan_to_num(b, nan=-1.0, posinf=-2.0, neginf=-3.0),
    ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration-root", required=True)
    parser.add_argument(
        "--utility",
        default=str(ROOT / "app6/atlas/landmark_utility.npy"),
    )
    parser.add_argument(
        "--prior",
        default=str(ROOT / "app6/atlas/visibility_prior.npy"),
    )
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "app6/atlas/landmark_utility_manifest.json"),
    )
    args = parser.parse_args()

    calibration_root = pathlib.Path(args.calibration_root)
    utility_path = pathlib.Path(args.utility)
    prior_path = pathlib.Path(args.prior)
    manifest_path = pathlib.Path(args.manifest)

    rows = load_nested_calibration(calibration_root)
    check("A11 загружено 943 кадра", len(rows) == 943, str(len(rows)))

    subjects = sorted({
        str(row.get("subject") or "")
        for row in rows
    })
    check("A11 семь субъектов", len(subjects) == 7, repr(subjects))

    bin_counts = {
        bin_name: sum(row["bin"] == bin_name for row in rows)
        for bin_name in BINS
    }
    check(
        "A11 распределение по девяти бинам",
        bin_counts == EXPECTED_BIN_COUNTS,
        json.dumps(bin_counts, ensure_ascii=False, sort_keys=True),
    )

    def loader(row):
        return (
            np.asarray(row["points"], dtype=np.float64),
            np.asarray(row["visible"], dtype=bool),
        )

    utility_1, report_1 = build(rows, loader)
    prior_1 = build_visibility_prior(rows, loader)

    # Полностью независимая повторная сборка из тех же sidecar.
    rows_2 = load_nested_calibration(calibration_root)

    def loader_2(row):
        return (
            np.asarray(row["points"], dtype=np.float64),
            np.asarray(row["visible"], dtype=bool),
        )

    utility_2, report_2 = build(rows_2, loader_2)
    prior_2 = build_visibility_prior(rows_2, loader_2)

    check(
        "A11 utility детерминирован",
        arrays_equal(utility_1, utility_2),
        f"{report_1['sha256']} / {report_2['sha256']}",
    )
    check(
        "A11 visibility prior детерминирован",
        arrays_equal(prior_1, prior_2),
    )
    check(
        "A11 utility имеет форму 9x134",
        utility_1.shape == (9, 134),
        str(utility_1.shape),
    )
    check(
        "A11 visibility prior имеет форму 9x134",
        prior_1.shape == (9, 134),
        str(prior_1.shape),
    )

    all_nan_rows = np.flatnonzero(
        ~np.isfinite(utility_1).any(axis=1)
    ).tolist()
    check(
        "A11 нет полностью NaN-бинов",
        not all_nan_rows,
        repr(all_nan_rows),
    )
    check(
        "A11 visibility prior конечен",
        bool(np.isfinite(prior_1).all()),
    )

    check("A11 utility-файл существует", utility_path.is_file(), str(utility_path))
    check("A11 prior-файл существует", prior_path.is_file(), str(prior_path))
    check("A11 manifest существует", manifest_path.is_file(), str(manifest_path))

    if utility_path.is_file():
        supplied_utility = np.load(utility_path, allow_pickle=False)
        check(
            "A11 поставочный utility совпадает с пересборкой",
            arrays_equal(supplied_utility, utility_1),
        )

    if prior_path.is_file():
        supplied_prior = np.load(prior_path, allow_pickle=False)
        check(
            "A11 поставочный prior совпадает с пересборкой",
            arrays_equal(supplied_prior, prior_1),
        )

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        check(
            "A11 manifest schema",
            manifest.get("schema")
            == "deeputin-landmark-utility-manifest-v1.0",
            str(manifest.get("schema")),
        )
        check(
            "A11 manifest record_count=943",
            manifest.get("record_count") == 943,
            str(manifest.get("record_count")),
        )
        check(
            "A11 manifest subject_count=7",
            manifest.get("subject_count") == 7,
            str(manifest.get("subject_count")),
        )
        check(
            "A11 manifest bin_counts",
            manifest.get("bin_counts") == EXPECTED_BIN_COUNTS,
        )
        check(
            "A11 manifest utility hash",
            utility_path.is_file()
            and manifest.get("utility_sha256") == sha256(utility_path),
        )
        check(
            "A11 manifest prior hash",
            prior_path.is_file()
            and manifest.get("visibility_prior_sha256") == sha256(prior_path),
        )

    width = max(len(name) for name, _, _ in RESULTS)
    failed = []
    for name, passed, detail in RESULTS:
        print(f"[{'PASS' if passed else 'FAIL'}] {name:<{width}}  {detail}")
        if not passed:
            failed.append(name)

    print()
    print(
        f"A11 ACCEPTANCE: {'PASS' if not failed else 'FAIL'} "
        f"({len(RESULTS) - len(failed)}/{len(RESULTS)})"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
