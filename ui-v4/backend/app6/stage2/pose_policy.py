"""⚙️ CONFIG → Загрузка нормативной политики применимости зон по ракурсам.

`app6/AGENTS.md` объявляет `app6/atlas/pose_policy_v3_9bins.csv` единственной
нормативной схемой ракурсов. До этого модуля файл лежал в репозитории, но не
читался ни одним рантайм-модулем (дефект D4): политика видимости фактически не
применялась.

Модуль отвечает на один вопрос: *применима ли текстурная зона A01–A20 в данном
ракурсе и с каким весом*. Он *не* назначает pose_bin кадру и не касается
геометрических mesh-зон (`mesh_zone_indices.json`) — это разные пространства имён:

  - `A01..A20`  — UV-текстурные зоны (`face_model.npy: primary_zone_ids`);
  - `forehead`, `orbit_L`, ... — геометрические mesh-зоны Stage 2.

🚨 WARNING (D5): между `pose_policy_9bins.csv` и `pose_policy_v3_9bins.csv`
конвенция знака yaw **инвертирована** — 96 из 180 ячеек различаются. Здесь
нормативной считается только версия v3, где положительный yaw соответствует
повороту к правому профилю. Смешивать версии в одном прогоне запрещено.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

POSE_POLICY_SCHEMA: Final[str] = "deeputin-pose-policy-v3-9bins"

#: Нормативный файл политики. Порядок отражает приоритет из AGENTS.md.
POLICY_FILENAME: Final[str] = "pose_policy_v3_9bins.csv"
LEGACY_POLICY_FILENAME: Final[str] = "pose_policy_9bins.csv"

#: 🚨 D6: комментарий «совпадают с canonical_yaw калибровочного набора» неверен.
#: Замер на 943 кадрах: 757 расхождений. Stage 1 пишет ±70/±45/±32.5/±17.5,
#: политика объявляла ±60/±40/±25/±10. Нормативными признаны центры Stage 1 —
#: именно к ним выполняется каноническое выравнивание в извлечённых данных.
YAW_BIN_CENTERS: Final[tuple[float, ...]] = (-70.0, -45.0, -32.5, -17.5, 0.0, 17.5, 32.5, 45.0, 70.0)

#: Легаси-центры до миграции. Оставлены только для чтения старых артефактов.
LEGACY_YAW_BIN_CENTERS: Final[tuple[float, ...]] = (-60.0, -40.0, -25.0, -10.0, 0.0, 10.0, 25.0, 40.0, 60.0)

#: Соответствие имени бина проекта и центра yaw в политике.
#: Знак: отрицательный yaw — левый профиль, положительный — правый (конвенция v3).
BIN_NAME_TO_YAW: Final[dict[str, float]] = {
    "left_profile": -70.0,
    "left_deep": -45.0,
    "left_mid": -32.5,
    "left_light": -17.5,
    "frontal": 0.0,
    "right_light": 17.5,
    "right_mid": 32.5,
    "right_deep": 45.0,
    "right_profile": 70.0,
}

LEGACY_BIN_NAME_TO_YAW: Final[dict[str, float]] = {
    "left_profile": -60.0, "left_deep": -40.0, "left_mid": -25.0,
    "left_light": -10.0, "frontal": 0.0, "right_light": 10.0,
    "right_mid": 25.0, "right_deep": 40.0, "right_profile": 60.0,
}

#: Профильные бины сравниваются внутри 10° подбинов (см. profile_sub_bin).
#: Причина (2026-08-03, замер на 212 кадрах): left_profile yaw −79.9..−50.1
#: (IQR 19.7°), right_profile +50.1..+81.8 (IQR 15.5°) — бин шириной ~45° с
#: SNR3-порогом 0.0° вычёркивает почти весь профильный материал (right_profile
#: accept 0.0 на 2926 парах). Подбины по 10° восстанавливают измеримый допуск.
PROFILE_BINS: Final[frozenset[str]] = frozenset({"left_profile", "right_profile"})
PROFILE_SUB_BIN_WIDTH: Final[float] = 10.0
PROFILE_RANGE: Final[tuple[float, float]] = (50.0, 95.0)


def profile_sub_bin(yaw: float) -> str | None:
    """Отобразить |yaw| в 10° профильный подбин внутри [50, 95).

    Возвращает ключ вида ``right_profile_60_70`` (зеркальные имена для левой
    стороны) либо None, если |yaw| вне профильного диапазона. Используется
    pose-гейтом, чтобы профильные пары сравнивались только внутри узкой полосы.
    """
    y = float(yaw)
    if not math.isfinite(y):
        return None
    side = "right_profile" if y >= 0 else "left_profile"
    mag = min(abs(y), PROFILE_RANGE[1])
    if mag < PROFILE_RANGE[0] or mag >= PROFILE_RANGE[1]:
        return None
    start = PROFILE_RANGE[0] + PROFILE_SUB_BIN_WIDTH * int(
        (mag - PROFILE_RANGE[0]) // PROFILE_SUB_BIN_WIDTH)
    end = min(start + PROFILE_SUB_BIN_WIDTH, PROFILE_RANGE[1])
    return f"{side}_{int(start)}_{int(end)}"


def assert_canonical_yaw(pose_bin: str, canonical_yaw: float, *, tol: float = 0.5) -> None:
    """Fail-closed сверка canonical_yaw кадра с нормативным центром бина."""
    expected = BIN_NAME_TO_YAW.get(pose_bin)
    if expected is None:
        raise ValueError(f"неизвестный pose_bin: {pose_bin!r}")
    if abs(float(canonical_yaw) - expected) <= tol:
        return
    legacy = LEGACY_BIN_NAME_TO_YAW.get(pose_bin)
    if legacy is not None and abs(float(canonical_yaw) - legacy) <= tol:
        raise ValueError(
            f"кадр использует легаси-центры бинов ({pose_bin}@{canonical_yaw}); "
            "требуется переизвлечение Stage 1 или миграция артефакта")
    raise ValueError(f"canonical_yaw {canonical_yaw} не соответствует {pose_bin} "
                     f"(ожидалось {expected})")

#: Статусы применимости, разрешённые политикой.
VALID_STATUSES: Final[frozenset[str]] = frozenset({"primary", "support", "limited", "exclude"})


def _atlas_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "atlas"


@lru_cache(maxsize=2)
def load_pose_policy(path: str | None = None) -> dict[tuple[str, float], dict[str, Any]]:
    """⚙️ CONFIG → Прочитать нормативную политику в отображение (зона, yaw) → правило.

    Raises:
        FileNotFoundError: нормативный CSV отсутствует.
        ValueError: неизвестный статус, нечисловой вес или дублирующая ячейка.
    """
    policy_path = Path(path) if path else _atlas_dir() / POLICY_FILENAME
    if not policy_path.is_file():
        raise FileNotFoundError(f"нормативная политика ракурсов не найдена: {policy_path}")

    table: dict[tuple[str, float], dict[str, Any]] = {}
    with policy_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            zone = str(row["zone_code"]).strip()
            yaw = float(row["yaw_bin_center_deg"])
            status = str(row["status"]).strip().lower()
            if status not in VALID_STATUSES:
                raise ValueError(f"недопустимый status {status!r} для {zone}@{yaw}")
            weight = float(row["weight"])
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"вес вне [0,1]: {weight} для {zone}@{yaw}")
            key = (zone, yaw)
            if key in table:
                raise ValueError(f"дублирующая ячейка политики: {zone}@{yaw}")
            table[key] = {"status": status, "weight": weight,
                          "convention": str(row.get("convention", "")).strip()}
    if not table:
        raise ValueError(f"пустая политика ракурсов: {policy_path}")
    return table


def yaw_for_bin(pose_bin: str) -> float:
    """Центр yaw для имени бина.

    Raises:
        ValueError: неизвестное имя ракурса.
    """
    key = str(pose_bin).strip().lower()
    if key not in BIN_NAME_TO_YAW:
        raise ValueError(f"неизвестный pose_bin: {pose_bin!r}")
    return BIN_NAME_TO_YAW[key]


def zone_applicability(zone_code: str, pose_bin: str) -> dict[str, Any]:
    """🚧 GATE → Применимость текстурной зоны в ракурсе.

    Returns:
        `{"status": ..., "weight": ..., "applicable": bool}`. Зона со статусом
        `exclude` (вес 0.0) непригодна: её нельзя молча считать с нулевым весом
        как «измеренную», она должна быть исключена из агрегата.
    """
    table = load_pose_policy()
    yaw = yaw_for_bin(pose_bin)
    rule = table.get((str(zone_code).strip(), yaw))
    if rule is None:
        return {"zone_code": zone_code, "pose_bin": pose_bin, "status": "unknown",
                "weight": 0.0, "applicable": False, "reason": "zone_not_in_policy"}
    return {"zone_code": zone_code, "pose_bin": pose_bin, "status": rule["status"],
            "weight": rule["weight"], "applicable": rule["status"] != "exclude"}


def applicable_zones(pose_bin: str, *, min_status: str = "limited") -> list[str]:
    """🔍 QUERY → Зоны, пригодные в данном ракурсе, по возрастанию строгости."""
    rank = {"exclude": 0, "limited": 1, "support": 2, "primary": 3}
    floor = rank.get(str(min_status).lower(), 1)
    table = load_pose_policy()
    yaw = yaw_for_bin(pose_bin)
    return sorted(z for (z, y), rule in table.items()
                  if y == yaw and rank[rule["status"]] >= floor)


def policy_summary() -> dict[str, Any]:
    """📤 Сводка политики для манифеста прогона (провенанс)."""
    table = load_pose_policy()
    zones = sorted({z for z, _ in table})
    counts: dict[str, int] = {}
    for rule in table.values():
        counts[rule["status"]] = counts.get(rule["status"], 0) + 1
    return {"schema": POSE_POLICY_SCHEMA, "source": POLICY_FILENAME,
            "zone_count": len(zones), "yaw_bin_count": len(YAW_BIN_CENTERS),
            "cell_count": len(table), "status_counts": counts,
            "yaw_convention": "negative yaw = left profile; positive yaw = right profile (v3)"}
