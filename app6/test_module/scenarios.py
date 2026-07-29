"""🏭 FACTORY → Реестр минимальных сценариев ТЗ (`docs/future_testing_module.txt`).

Каждый сценарий отвечает на один вопрос о поведении пайплайна, а не о
конкретной функции (см. `app6/AGENTS.md`, раздел «Этап 6»). Модуль не
запускает Stage 1 и не изобретает недостающие данные: он собирает роли
(`A`, `B`, ...) в комбинации из уже загруженных `Record`, оставляя источник
данных (архив или свежий Stage-1-прогон) вызывающему коду.

🚪 API: SCENARIOS, build_combinations(), timeline_from_combo()
🔗 DEPENDS ON: app6.stage2.core.Record, app6.test_module.archive_adapter
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any, Final

from app6.stage2.core import Record

SCENARIOS_SCHEMA: Final[str] = "deeputin-test-scenarios-v1.0"

#: Девять нормативных ракурсов проекта (совпадает с app6/atlas/pose_policy_v3_9bins.csv).
POSE_BINS: Final[tuple[str, ...]] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)

#: Реестр сценариев: вопрос, паттерн ролей и ожидаемый результат.
#: `pattern` — последовательность ролей во времени; повторяющаяся роль означает
#: "тот же человек". `cross_pose=True` — роли берутся из разных pose bins
#: одного человека (проверка pose_mismatch, а не смены личности).
#: `min_people` — сколько различных ролей (следовательно, различных людей в
#: наборе) требуется, чтобы сценарий вообще был применим к источнику данных.
SCENARIOS: Final[dict[str, dict[str, Any]]] = {
    "S01": {
        "question": "Отличает ли система шум от реального изменения?",
        "pattern": ("A", "A", "A"),
        "expect": "без аномалий: стабильная серия одного человека",
        "min_people": 1,
        "check": "stable_series",
    },
    "S02": {
        "question": "Замечает ли система смену личности?",
        "pattern": ("A", "A", "B"),
        "expect": "расхождение на переходе A→B заметно выше внутригруппового",
        "min_people": 2,
        "check": "transition_divergence",
    },
    "S03": {
        "question": "Детектируется ли возврат A→B→A?",
        "pattern": ("A", "B", "A"),
        "expect": "irreversible_return_anomaly",
        "min_people": 2,
        "check": "irreversible_return",
    },
    "S04": {
        "question": "Не путает ли система смену ракурса со сменой лица?",
        "pattern": ("A", "A"),
        "cross_pose": True,
        "expect": "pose_mismatch, а не геометрическая аномалия",
        "min_people": 1,
        "check": "cross_pose_rejected",
    },
    "S05": {
        "question": "Устойчив ли вывод при чередовании носителей?",
        "pattern": ("A", "B", "A", "B"),
        "expect": "несколько независимых переходов, без сглаживания в среднее",
        "min_people": 2,
        "check": "repeated_alternation",
    },
    "S06": {
        "question": "Копится ли постепенный дрейф?",
        "pattern": ("A", "A", "A", "A", "A"),
        "expect": "без cumulative_drift на подлинно стабильной серии",
        "min_people": 1,
        "check": "no_false_drift",
    },
}


def scenario_ids() -> tuple[str, ...]:
    return tuple(SCENARIOS)


def resolve_poses(pose: str) -> tuple[str, ...]:
    """🚧 GATE → Нормализовать аргумент `--pose` в кортеж валидных bins."""
    if pose == "all":
        return POSE_BINS
    if pose not in POSE_BINS:
        raise ValueError(f"неизвестный ракурс {pose!r}; доступны {POSE_BINS} или 'all'")
    return (pose,)


def with_synthetic_dates(records: list[Record], start_year: int = 1999,
                          step_days: int = 400) -> list[Record]:
    """🔄 Последовательные синтетические даты для проверки порядка хронологии.

    🚨 WARNING: даты задают только порядок и интервалы для теста алгоритма,
    это не датировка реальной съёмки (см. archive_adapter.with_synthetic_dates,
    с которым эта функция контрактно идентична и который может использовать
    те же входные Record).
    """
    base = date(start_year, 1, 11)
    return [replace(record, date=(base + timedelta(days=index * step_days)).isoformat())
            for index, record in enumerate(records)]


def timeline_from_combo(records: list[Record], *, min_total_years: float = 6.0) -> list[dict[str, Any]]:
    """📤 Преобразовать комбинацию в формат timeline для irreversible_return/drift.

    Шаг между синтетическими датами подбирается так, чтобы разрыв между
    первым и последним кадром комбинации был не меньше `min_total_years`:
    иначе `detect_irreversible_return` (порог ТЗ — не менее 5 лет между
    возвращающимися состояниями) молчаливо не находил бы то, что сценарий
    призван продемонстрировать.
    """
    n = len(records)
    step_days = 400 if n < 2 else max(400, int((min_total_years * 365.25) / (n - 1)) + 1)
    dated = with_synthetic_dates(records, step_days=step_days)
    return [{"date": r.date, "shape": r.ldm134.reshape(-1), "photo_id": r.record_id}
            for r in dated]


def build_combinations(
    scenario: str,
    pose: str,
    grouped: dict[tuple[str, str], list[Record]],
    people: list[str],
    combinations: int,
) -> list[dict[str, Any]]:
    """🏭 FACTORY → Построить до `combinations` независимых наборов ролей.

    Комбинация `n` (0-indexed) сдвигает выбор кадров/людей на `n`, чтобы
    последовательные ступени лестницы (`--combinations 1, 2, 3, ...`)
    проверяли разные, а не повторяющиеся данные. Комбинация, для которой не
    хватает людей или кадров нужного pose bin, помечается `"available":
    False` вместо того, чтобы тихо повториться или упасть.

    Returns:
        Список словарей `{"index", "available", "records", "role_map", "reason"}`.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"неизвестный сценарий {scenario!r}; доступны {scenario_ids()}")
    if combinations < 1:
        raise ValueError("combinations должно быть >= 1")

    spec = SCENARIOS[scenario]
    pattern = list(spec["pattern"])
    roles = sorted(set(pattern))
    cross_pose = bool(spec.get("cross_pose", False))

    out: list[dict[str, Any]] = []
    for combo_index in range(combinations):
        if cross_pose:
            # S04: одна и та же персона в двух разных pose bins (сам ракурс —
            # это "B" сравнения, роли в pattern всегда про одного человека).
            person_index = combo_index % max(len(people), 1)
            if not people:
                out.append({"index": combo_index, "available": False,
                            "records": [], "role_map": {}, "reason": "no_people_in_source"})
                continue
            person = people[person_index]
            primary = grouped.get((person, pose), [])
            other_pose = next((p for p in POSE_BINS if p != pose
                                and grouped.get((person, p))), None)
            if not primary or other_pose is None:
                out.append({"index": combo_index, "available": False, "records": [],
                            "role_map": {"A": person},
                            "reason": "missing_second_pose_for_same_person"})
                continue
            secondary = grouped[(person, other_pose)]
            frame_offset = combo_index // max(len(people), 1)
            first = primary[frame_offset % len(primary)]
            second = secondary[frame_offset % len(secondary)]
            out.append({"index": combo_index, "available": True,
                        "records": [first, second], "role_map": {"A": person},
                        "cross_pose_target": other_pose, "reason": ""})
            continue

        available_people = [p for p in people if grouped.get((p, pose))]
        if len(available_people) < len(roles):
            out.append({"index": combo_index, "available": False, "records": [],
                        "role_map": {}, "reason": "not_enough_people_in_pose"})
            continue

        # Сдвигаем назначение роль→человек по кругу, чтобы разные комбинации
        # не совпадали, пока хватает различных людей в источнике.
        rotation = combo_index % len(available_people)
        rotated = available_people[rotation:] + available_people[:rotation]
        role_to_person = dict(zip(roles, rotated))

        selected: list[Record] = []
        ok = True
        for step, role in enumerate(pattern):
            person = role_to_person[role]
            pool = grouped[(person, pose)]
            frame_offset = combo_index // max(len(available_people), 1)
            index_in_pool = (step + frame_offset) % len(pool)
            selected.append(pool[index_in_pool])
        if not ok:  # pragma: no cover - defensive; loop above cannot fail silently
            out.append({"index": combo_index, "available": False, "records": [],
                        "role_map": role_to_person, "reason": "frame_selection_failed"})
            continue
        out.append({"index": combo_index, "available": True, "records": selected,
                    "role_map": role_to_person, "reason": ""})
    return out
