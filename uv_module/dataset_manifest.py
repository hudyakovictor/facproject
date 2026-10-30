"""UV-quality dataset registry and immutable grouped splits; no material labels."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageOps

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_metadata(data: bytes) -> tuple[int, int, str]:
    with Image.open(io.BytesIO(data)) as image:
        oriented = ImageOps.exif_transpose(image)
        width, height = oriented.size
        thumbnail = np.asarray(oriented.convert("L").resize((32, 32)), dtype=float)
    # This hash is only a near-copy screening aid, never a face/identity descriptor.
    import cv2
    low = cv2.dct(thumbnail.astype(np.float32))[:8, :8]
    bits = low > np.median(low.ravel()[1:])
    perceptual = f"{int(''.join('1' if value else '0' for value in bits.ravel()), 2):016x}"
    return width, height, perceptual


def source_stem(texture: Path) -> str:
    return re.sub(r"__[0-9a-fA-F]{8,64}$", "", texture.stem)


def filename_date(stem: str) -> str | None:
    match = re.match(r"^(\d{4})_(\d{2})_(\d{2})", stem)
    if not match:
        return None
    date = "-".join(match.groups())
    try:
        return pd.Timestamp(date).strftime("%Y-%m-%d")
    except ValueError:
        return None


def assign_grouped_splits(frame: pd.DataFrame, seed: int = 20261027) -> dict[str, str]:
    groups = sorted(frame.split_group.unique())
    if len(groups) < 3:
        raise ValueError("at least three independent groups required for train/validation/test")
    rng = np.random.default_rng(seed)
    best, best_score = None, np.inf
    fractions = {"train": 0.6, "validation": 0.2, "test": 0.2}
    train_count = max(1, min(len(groups) - 2, int(round(len(groups) * 0.6))))
    validation_count = max(1, min(len(groups) - train_count - 1, int(round(len(groups) * 0.2))))
    # Optimize only label/group counts, before any image-quality features are computed.
    for _ in range(500):
        order = rng.permutation(groups)
        mapping = {group: ("train" if index < train_count else "validation" if index < train_count + validation_count else "test")
                   for index, group in enumerate(order)}
        split = frame.split_group.map(mapping)
        score = 0.0
        for label in ("normal", "distorted"):
            total = int(frame.quality_label_reference.eq(label).sum())
            if not total:
                continue
            for name, fraction in fractions.items():
                count = int((frame.quality_label_reference.eq(label) & split.eq(name)).sum())
                score += abs(count / total - fraction) + (10 if count == 0 else 0)
        if score < best_score:
            best, best_score = mapping, score
    return best


def build_manifest(normal: Path, anomaly: Path, originals: Path, output: Path,
                   seed: int = 20261027, restore_zip: bool = True) -> tuple[pd.DataFrame, dict]:
    roots = {"normal": normal, "distorted": anomaly}
    for root in roots.values():
        if not root.is_dir():
            raise FileNotFoundError(root)
    output.mkdir(parents=True, exist_ok=True)
    original_index = {}
    for path in originals.iterdir():
        if path.is_file() and not path.name.startswith("._") and path.suffix.lower() in IMAGE_EXTENSIONS:
            original_index.setdefault(path.stem, []).append(path)
    archive_path = originals / "frontal_photos.zip"
    archive = zipfile.ZipFile(archive_path) if archive_path.is_file() else None
    archive_index = {}
    if archive:
        for member in archive.namelist():
            path = Path(member)
            if path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.startswith("._"):
                archive_index.setdefault(path.stem, []).append(member)
    records = []
    try:
        for label, root in roots.items():
            for texture in sorted(root.iterdir()):
                if not texture.is_file() or texture.name.startswith("._") or texture.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                stem = source_stem(texture)
                reference_data = texture.read_bytes()
                reference_hash = sha256_bytes(reference_data)
                uv_width, uv_height, _ = image_metadata(reference_data)
                paths = original_index.get(stem, [])
                match, source_data, status = None, None, "missing_original"
                if len(paths) == 1:
                    match, status = paths[0], "basename_match_user_supplied"
                    source_data = match.read_bytes()
                elif len(paths) > 1:
                    versions = [(image_metadata(path.read_bytes())[:2], path) for path in paths]
                    # Keep the maximum available resolution, recording that multiple variants exist.
                    _, match = max(versions, key=lambda value: value[0][0] * value[0][1])
                    source_data, status = match.read_bytes(), "multiple_versions_max_resolution_requires_review"
                elif archive and len(archive_index.get(stem, [])) == 1:
                    member = archive_index[stem][0]
                    source_data = archive.read(member)
                    if restore_zip:
                        destination = output / "originals_from_archive"
                        destination.mkdir(exist_ok=True)
                        match = destination / Path(member).name
                        match.write_bytes(source_data)
                        status = "restored_matching_archive_member"
                    else:
                        status = "archive_member_available"
                if source_data:
                    width, height, phash = image_metadata(source_data)
                    source_hash = sha256_bytes(source_data)
                else:
                    width, height, phash, source_hash = None, None, None, None
                date = filename_date(stem)
                sample_id = sha256_bytes((stem + ":" + reference_hash).encode())[:20]
                records.append({
                    "sample_id": sample_id, "original_stem": stem, "original_path": str(match.resolve()) if match else None,
                    "reference_uv_path": str(texture.resolve()), "reference_uv_sha256": reference_hash,
                    "source_sha256": source_hash, "source_match_status": status,
                    "quality_label_reference": label, "quality_label_current": None, "label_status": "needs_review_after_pinned_regeneration",
                    "capture_date": date, "date_source": "filename_annotation" if date else "unknown",
                    "session_id": date or f"unresolved_{stem}", "image_source": "user_supplied_rakurs_frontal",
                    "source_width": width, "source_height": height, "source_phash_screening": phash,
                    "reference_uv_width": uv_width, "reference_uv_height": uv_height,
                    "duplicate_group": source_hash or f"stem_{stem}", "near_duplicate_review": False,
                    "face_resolution_px": None, "yaw_deg": None, "pitch_deg": None, "roll_deg": None,
                    "expression_status": "unknown", "external_occlusion_status": "unknown",
                    "generation_parameters_json": None, "generation_id": None,
                    "reference_generation_id": "legacy_directory_33_unverified_configuration",
                    "defect_causes_json": "[\"unknown\"]", "region_annotations_json": "[]",
                    "material_presence_independently_confirmed": None, "material_evidence": None,
                })
    finally:
        if archive:
            archive.close()
    frame = pd.DataFrame(records)
    if frame.empty or frame.sample_id.duplicated().any():
        raise ValueError("empty dataset or duplicate/conflicting sample IDs")
    # Join duplicate-content groups and same-day capture groups conservatively.
    parent = {sample: sample for sample in frame.sample_id}

    def find(sample):
        while parent[sample] != sample:
            parent[sample] = parent[parent[sample]]
            sample = parent[sample]
        return sample

    for column in ("duplicate_group", "session_id", "original_stem"):
        for _, group in frame.groupby(column):
            members = group.sample_id.tolist()
            root = find(members[0])
            for sample in members[1:]:
                parent[find(sample)] = root
    for first in range(len(frame)):
        if frame.iloc[first].source_phash_screening is None:
            continue
        for second in range(first + 1, len(frame)):
            a, b = frame.iloc[first], frame.iloc[second]
            if b.source_phash_screening is not None:
                distance = (int(a.source_phash_screening, 16) ^ int(b.source_phash_screening, 16)).bit_count()
                if distance <= 3 and a.source_sha256 != b.source_sha256:
                    frame.loc[[first, second], "near_duplicate_review"] = True
                    parent[find(b.sample_id)] = find(a.sample_id)
    frame["split_group"] = [find(sample) for sample in frame.sample_id]
    split_path = output / "split_lock.json"
    if split_path.exists():
        lock = json.loads(split_path.read_text())
        if set(lock["sample_partitions"]) != set(frame.sample_id):
            raise ValueError("dataset membership changed; use an explicit new study directory rather than reshuffling closed test")
        frame["partition"] = frame.sample_id.map(lock["sample_partitions"])
        if frame.groupby("split_group").partition.nunique().gt(1).any():
            raise ValueError("newly discovered duplicate/session links cross the frozen split")
    else:
        groups = assign_grouped_splits(frame, seed)
        frame["partition"] = frame.split_group.map(groups)
        lock = {"schema_version": "uv-quality-split-v1", "seed": seed, "fractions": [0.6, 0.2, 0.2],
                "sample_partitions": dict(zip(frame.sample_id, frame.partition, strict=True)),
                "policy": "same source bytes, source stem, capture-date session and conservative near-copy links remain in one partition; test is not for tuning"}
        split_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    frame.to_parquet(output / "manifest.parquet", index=False)
    frame.to_csv(output / "manifest.csv", index=False)
    summary = {"n_samples": len(frame), "labels_reference": frame.quality_label_reference.value_counts().to_dict(),
               "source_match_status": frame.source_match_status.value_counts().to_dict(),
               "missing_originals": frame.loc[frame.original_path.isna(), "original_stem"].tolist(),
               "near_copy_review_samples": int(frame.near_duplicate_review.sum()),
               "partition_labels": pd.crosstab(frame.partition, frame.quality_label_reference).to_dict(),
               "annotations_available": 0, "current_labels_verified": 0,
               "classifier_ready": False, "classifier_blocker": "legacy labels require review after technical fixes and pinned regeneration",
               "material_label_policy": "no material labels are inferred or used for UV quality prediction"}
    (output / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return frame, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal", type=Path, default=Path("/Volumes/SDCARD/test_photos/uv/33/normal"))
    parser.add_argument("--anomaly", type=Path, default=Path("/Volumes/SDCARD/test_photos/uv/33/aomaly"))
    parser.add_argument("--originals", type=Path, default=Path("/Volumes/SDCARD/rakurs/frontal"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/uv_quality"))
    parser.add_argument("--seed", type=int, default=20261027)
    args = parser.parse_args()
    _, summary = build_manifest(args.normal, args.anomaly, args.originals, args.output, args.seed)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
