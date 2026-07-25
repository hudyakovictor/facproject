"""🏗 Сборка теста: сценарий → tests/<base_id>/<id>/input/ (переименованные копии фото по хронологии)
+ build_manifest.json (какие кадры выбраны и под какими именами).
Имя файла: YYYY_MM_DD[_N].ext — без тега кадра, только дата и порядковый номер.
Группы src_*: разные люди в рамках одного теста попадают в разные src_* директории."""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import MIN_FRAME_GAP, TESTS_DIR
from test_module.pool import FramePicker
from test_module.pool import target_pose_bin


def _base_id(sid: str) -> str:
    m = re.match(r"^(.*?)(?:_v\d+)?$", sid)
    return m.group(1) if m else sid


def _group_frames(frames: list[dict]) -> list[tuple[int, int, str, float]]:
    """Вернуть список contiguous-блоков (start, end, person, yaw).
    Блоки идут подряд, внутри блока person и yaw одинаковые."""
    if not frames:
        return []
    groups = []
    i = 0
    while i < len(frames):
        j = i + 1
        while j < len(frames) and frames[j]["person"] == frames[i]["person"] and abs(float(frames[j]["yaw"]) - float(frames[i]["yaw"])) < 1.0:
            j += 1
        groups.append((i, j, frames[i]["person"], float(frames[i]["yaw"])))
        i = j
    return groups


def _assign_groups(frames: list[dict]) -> list[dict]:
    """Назначить group (src_a, src_b, ...) каждому кадру по person.
    Первый встреченный человек → src_a, второй уникальный → src_b и т.д."""
    person_to_group: dict[str, str] = {}
    next_idx = 0

    def gname() -> str:
        nonlocal next_idx
        name = f"src_{chr(ord('a') + next_idx)}"
        next_idx += 1
        return name

    out = []
    for fr in frames:
        p = fr["person"]
        explicit = str(fr.get("group") or "auto")
        if explicit != "auto":
            nf = dict(fr)
            nf["group"] = explicit
            out.append(nf)
            continue
        if p not in person_to_group:
            person_to_group[p] = gname()
        nf = dict(fr)
        nf["group"] = person_to_group[p]
        out.append(nf)
    return out


def build_scenario(scn: dict, pool: list[dict], plan_only: bool = False) -> dict:
    picker = FramePicker(pool)
    seq: dict[str, int] = {}
    frames = []
    groups = _group_frames(scn["frames"])
    for start, end, person, yaw in groups:
        count = end - start
        if count == 1:
            r = picker.pick(person, yaw, require_photo=not plan_only)
            picked = [r]
        else:
            picked = picker.pick_extremes(person, yaw, count, require_photo=not plan_only)
        for k, r in enumerate(picked):
            if start + k >= len(scn["frames"]):
                break
            fs = scn["frames"][start + k]
            expected_bin = target_pose_bin(float(fs["yaw"]))
            if r["pose_bin"] != expected_bin:
                raise RuntimeError(
                    f"scenario {scn['id']} frame {start+k+1}: "
                    f"expected pose_bin={expected_bin}, selected {r['pose_bin']}"
                )
            date = fs["date"]
            n = seq[date] = seq.get(date, 0) + 1
            stem = date + (f"_{n}" if n > 1 else "")
            ext = Path(r["file"]).suffix.lower()
            frames.append({
                "n": start + k + 1, "person": fs["person"], "tag": r["tag"], "record_id": r["record_id"],
                "yaw_target": fs["yaw"], "yaw_actual": r["yaw"], "date": date,
                "pose_bin_target": expected_bin, "pose_bin_actual": r["pose_bin"],
                "date_iso": date.replace("_", "-"), "seq": n,
                "group": fs.get("group", "auto"),
                "src": r["photo_path"], "filename": stem + ext, "stem": stem,
            })
    # Preserve explicitly declared independent source groups (e.g. S18/S19).
    # Only "auto" groups are assigned deterministically by person.
    frames = _assign_groups(frames)
    base = _base_id(scn["id"])
    variant = scn["id"].replace(base, "").lstrip("_")
    if not variant:
        variant = "v00"
    tdir = TESTS_DIR / base / variant
    tdir.mkdir(parents=True, exist_ok=True)
    manifest = {"scenario": scn, "frames": frames, "planned_only": plan_only}
    (tdir / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if not plan_only:
        for fr in frames:
            dst = tdir / fr["filename"]
            shutil.copy2(fr["src"], dst)
    return manifest
