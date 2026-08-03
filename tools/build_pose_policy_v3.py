"""⚙️ CONFIG → Сборка нормативной политики ракурсов из геометрии атласа зон.

Дефект: app6/stage2/pose_policy.py объявляет app6/atlas/pose_policy_v3_9bins.csv
единственной нормативной схемой и падает FileNotFoundError без него. В поставке
в app6/atlas/ присутствует только texture_zones_bfm35709_v3.npz, и в нём нет
вершин/нормалей (треугольные маски).

Поэтому геометрия берётся из face_model.npy (u — вершины, tri — треугольники,
primary_triangle_zone — индекс зоны на треугольник, primary_zone_ids — коды
A01..A20). Политика выводится из видимости вершин зоны при повороте головы на
центр бина, а не назначается вручную. Конвенция v3: положительный yaw — правый
профиль.

Запуск:  python -m tools.build_pose_policy_v3 --check
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np

from app6.stage2.pose_policy import BIN_NAME_TO_YAW, POSE_POLICY_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "app6" / "atlas"
FACE_MODEL_NPY = ROOT / "3ddfa_v3" / "assets" / "face_model.npy"
OUT_CSV = ATLAS / "pose_policy_v3_9bins.csv"

#: Пороги доли видимых вершин зоны → статус применимости.
PRIMARY_MIN = 0.70
SUPPORT_MIN = 0.40
LIMITED_MIN = 0.15

#: Минимальная Z-компонента нормали (после поворота), считающаяся видимой.
NORMAL_Z_EPS = 0.15


def _rotation_y(deg: float) -> np.ndarray:
    r = np.deg2rad(float(deg))
    c, s = np.cos(r), np.sin(r)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _visible_fraction(zone_tri_normals: np.ndarray, yaw: float) -> float:
    """Доля треугольников зоны, обращённых к камере после поворота на yaw."""
    rot = _rotation_y(yaw)
    n = zone_tri_normals @ rot.T
    # Камера смотрит вдоль -Z; треугольник видим при положительной Z-компоненте
    # нормали с запасом на скользящие углы.
    return float(np.mean(n[:, 2] > NORMAL_Z_EPS))


def _status(fraction: float) -> tuple[str, float]:
    if fraction >= PRIMARY_MIN:
        return "primary", round(min(1.0, fraction), 3)
    if fraction >= SUPPORT_MIN:
        return "support", round(fraction, 3)
    if fraction >= LIMITED_MIN:
        return "limited", round(fraction, 3)
    return "exclude", 0.0


def _load_geometry() -> tuple[np.ndarray, list[str]]:
    if not FACE_MODEL_NPY.is_file():
        raise FileNotFoundError(f"модель лица отсутствует: {FACE_MODEL_NPY}")
    data = np.load(FACE_MODEL_NPY, allow_pickle=True).item()
    required = {"u", "tri", "primary_triangle_zone", "primary_zone_ids"}
    missing = required - set(data.keys())
    if missing:
        raise KeyError(f"в face_model.npy нет ключей {sorted(missing)}; доступно: {list(data.keys())}")
    vertices = np.asarray(data["u"]).reshape(-1, 3)
    triangles = np.asarray(data["tri"]).astype(np.int64)
    zone_per_tri = np.asarray(data["primary_triangle_zone"]).reshape(-1)
    codes = [str(c) for c in np.asarray(data["primary_zone_ids"]).reshape(-1)]
    if zone_per_tri.shape[0] != triangles.shape[0]:
        raise ValueError("primary_triangle_zone и tri должны совпадать по длине")
    # Нормали треугольников из геометрии сетки.
    v = vertices[triangles]
    normals = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    return zone_per_tri, normals, codes


def build() -> list[dict[str, object]]:
    zone_per_tri, tri_normals, codes = _load_geometry()
    # primary_zone_ids дают коды A01..A20; индекс зоны на треугольник — 0..19.
    expected = [f"A{i:02d}" for i in range(1, 21)]
    if codes != expected:
        raise ValueError(f"ожидались зоны {expected}, получено {codes}")
    rows: list[dict[str, object]] = []
    for zone_index in range(20):
        code = expected[zone_index]
        mask = zone_per_tri == zone_index
        if not mask.any():
            raise ValueError(f"зона {code} отсутствует в геометрии")
        for bin_name, yaw in BIN_NAME_TO_YAW.items():
            frac = _visible_fraction(tri_normals[mask], yaw)
            status, weight = _status(frac)
            rows.append({"zone_code": code,
                         "yaw_bin_center_deg": f"{yaw:.1f}",
                         "pose_bin": bin_name,
                         "status": status,
                         "weight": f"{weight:.3f}",
                         "visible_fraction": f"{frac:.3f}",
                         "convention": "v3_positive_is_right"})
    if len(rows) != 180:
        raise ValueError(f"ожидалось 180 ячеек (20 зон × 9 бинов), получено {len(rows)}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="только проверить детерминизм")
    args = ap.parse_args()
    rows = build()
    fields = ["zone_code", "yaw_bin_center_deg", "pose_bin", "status",
              "weight", "visible_fraction", "convention"]
    payload = "".join(",".join(str(r[f]) for f in fields) + "\n" for r in rows)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    if args.check:
        print(f"{POSE_POLICY_SCHEMA} rows={len(rows)} sha256={digest}")
        return
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"записано {OUT_CSV} rows={len(rows)} sha256={digest}")


if __name__ == "__main__":
    main()
