"""📇 Пул кадров: индекс углов + детерминированный подбор кадров под сценарий.
Источник углов — all_calibration_index.csv калибровочного датасета (943 кадра, 7 человек)."""
from __future__ import annotations
import csv
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import CALIB_INDEX, MIN_FRAME_GAP, PHOTOS_ROOT, POOL_INDEX
from app6.stage1.config import POSE_BINS


def target_pose_bin(yaw: float) -> str:
    """Return the exact Stage 1 pose bin required by a scenario yaw."""
    for name, lo, hi, _canonical in POSE_BINS:
        if lo <= float(yaw) < hi:
            return name
    raise ValueError(f"unsupported scenario yaw: {yaw}")


def person_tag(person: str, record_id: str) -> str:
    """person_01 + frame_000205 -> p01f000205 (метка кадра внутри photo_id)."""
    return "p" + person.split("_")[-1] + "f" + record_id.split("_")[-1]


def load_pool() -> list[dict]:
    if not CALIB_INDEX.is_file():
        raise SystemExit(f"нет индекса калибровочного датасета: {CALIB_INDEX}")
    out: list[dict] = []
    with CALIB_INDEX.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            person = r["dataset_id"]
            fname = r["source_filename"]
            photo = PHOTOS_ROOT / person / fname
            out.append({
                "person": person, "record_id": r["record_id"], "file": fname,
                "frame_index": int(r["frame_index"]), "yaw": float(r["yaw"]),
                "pitch": float(r["pitch"]), "roll": float(r["roll"]),
                "pose_bin": r["pose_bin"], "tag": person_tag(person, r["record_id"]),
                "photo_exists": photo.is_file(), "photo_path": str(photo),
            })
    return out


def write_pool_index() -> dict:
    pool = load_pool()
    with POOL_INDEX.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(pool[0].keys()))
        w.writeheader()
        w.writerows(pool)
    return {
        "total": len(pool),
        "with_photo": sum(1 for r in pool if r["photo_exists"]),
        "persons": sorted({r["person"] for r in pool}),
    }


class FramePicker:
    """Подбор кадров: ближе всего к целевому yaw, но не ближе min_gap кадров видео
    к уже выбранным кадрам того же человека (соседние кадры видео дают нулевой шум
    и тест нечестный). Детерминирован: без случайности, стабильная сортировка."""

    def __init__(self, pool: list[dict]):
        self.pool = pool
        self.used: dict[str, list[int]] = {}

    def pick(self, person: str, yaw: float, min_gap: int = MIN_FRAME_GAP, require_photo: bool = True) -> dict:
        wanted_bin = target_pose_bin(yaw)
        cands = [r for r in self.pool if r["person"] == person
                 and r["pose_bin"] == wanted_bin
                 and (r["photo_exists"] or not require_photo)]
        if not cands:
            raise RuntimeError(f"нет кадров {person} в обязательном pose_bin={wanted_bin}")
        cands.sort(key=lambda r: (abs(r["yaw"] - yaw), r["frame_index"]))
        used = self.used.setdefault(person, [])
        # плавно ослабляем зазор, если кадры нужного ракурса идут плотной пачкой видео
        for gap in (min_gap, max(min_gap // 2, 1), 10, 5, 2, 1):
            for r in cands:
                if all(abs(r["frame_index"] - u) >= gap for u in used):
                    if gap < min_gap:
                        print(f"⚠️ {person} yaw≈{yaw}: зазор ослаблен до {gap} кадров (мало кадров этого ракурса)")
                    used.append(r["frame_index"])
                    return r
        # Все кадры уже израсходованы — повторно используем ближайший к yaw
        best = min(cands, key=lambda r: (abs(r["yaw"] - yaw), r["frame_index"]))
        print(f"⚠️ {person} yaw≈{yaw}: все {len(cands)} кадров pose_bin={wanted_bin} "
              f"уже использованы — повторный выбор frame {best['frame_index']}")
        used.append(best["frame_index"])
        return best

    def pick_extremes(self, person: str, yaw: float, count: int, min_gap: int = MIN_FRAME_GAP, require_photo: bool = True) -> list[dict]:
        """Вернуть `count` кадров этого ракурса, покрывающих весь доступный диапазон frame_index.
        Сначала фильтруем кандидатов по близости к целевому yaw (±25°), затем сортируем по frame_index,
        разбиваем на `count` групп и берём из каждой группы по одному кадру (ближайший к центру группы).
        Это обеспечивает равномерный coverage всего диапазона данного ракурса."""
        wanted_bin = target_pose_bin(yaw)
        all_cands = [r for r in self.pool if r["person"] == person
                     and r["pose_bin"] == wanted_bin
                     and (r["photo_exists"] or not require_photo)]
        if len(all_cands) < count:
            if len(all_cands) == 0:
                raise RuntimeError(
                    f"нет кадров {person} в pose_bin={wanted_bin}"
                )
            print(f"⚠️ {person} yaw≈{yaw}: pose_bin={wanted_bin} — "
                  f"нужно {count} кадров, доступно {len(all_cands)} (берём все)")
            count = len(all_cands)
        all_cands.sort(key=lambda r: abs(r["yaw"] - yaw))
        used = self.used.setdefault(person, [])
        if count <= 0:
            return []
        # Never broaden into neighbouring pose bins. Stage 2 intentionally
        # compares only within one bin, so cross-bin selection makes a test
        # vacuous (pair_metrics=no_pairs).
        cands = all_cands
        if count == 1:
            for gap in (min_gap, max(min_gap // 2, 1), 10, 5, 2, 1):
                for r in cands:
                    if all(abs(r["frame_index"] - u) >= gap for u in used):
                        if gap < min_gap:
                            print(f"⚠️ {person} yaw≈{yaw}: зазор ослаблен до {gap} кадров (мало кадров этого ракурса)")
                        used.append(r["frame_index"])
                        return [r]
            raise RuntimeError(f"не удалось подобрать кадр: {person} yaw≈{yaw}; фото выложены?")
        by_idx = sorted(cands, key=lambda r: r["frame_index"])
        groups: list[list[dict]] = []
        for i in range(count):
            start = i * len(by_idx) // count
            end = (i + 1) * len(by_idx) // count
            grp = by_idx[start:end] if start < end else by_idx[-1:]
            groups.append(grp)
        chosen: list[dict] = []
        for grp in groups:
            if not grp:
                continue
            center = (grp[0]["frame_index"] + grp[-1]["frame_index"]) / 2
            best = min(grp, key=lambda r: (abs(r["frame_index"] - center), r["frame_index"]))
            chosen.append(best)
        chosen.sort(key=lambda r: r["frame_index"])
        for gap in (min_gap, max(min_gap // 2, 1), 10, 5, 2, 1):
            ok = True
            for i in range(len(chosen)):
                for j in range(i + 1, len(chosen)):
                    if abs(chosen[i]["frame_index"] - chosen[j]["frame_index"]) < gap:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                if gap < min_gap:
                    print(f"⚠️ {person} yaw≈{yaw}: зазор ослаблен до {gap} кадров (мало кадров этого ракурса)")
                for r in chosen:
                    used.append(r["frame_index"])
                return chosen
        # Не удалось обеспечить зазор — возвращаем что есть с предупреждением
        print(f"⚠️ {person} yaw≈{yaw}: зазор не обеспечен, возвращаем {len(chosen)} кадров")
        for r in chosen:
            used.append(r["frame_index"])
        return chosen
