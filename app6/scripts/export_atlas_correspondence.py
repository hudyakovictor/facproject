#!/usr/bin/env python3
"""📤 Экспорт соответствия ТРЕУГОЛЬНИКОВ между двумя mesh'ами (source→target face map).
🔗 DEPENDS ON: входные .npy треугольники + карта вершин (source_to_target_vertex.npy) —
   внешние артефакты, передаются через CLI (модули атласа НЕ импортируются)
🚨 WARNING (AUDIT-5 fix): docstring исправлен — ранее ошибочно ссылался на skin_zone_atlas_final
💡 NOTE: FAIL-LOUD при coverage < --min-coverage или не-биективном маппинге.

🔧 FIX (D14): раньше argparse и вся работа выполнялись на уровне модуля, поэтому
любой `import` этого файла завершал процесс с `SystemExit: 2`. Логика перенесена
в функции под `__main__`-guard: скрипт остаётся CLI-инструментом, но становится
безопасным для импорта, статического анализа и сборки тестов.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np


def build_face_map(source_tri: np.ndarray, target_tri: np.ndarray,
                   vertex_map: np.ndarray) -> tuple[np.ndarray, float]:
    """🔢 Построить отображение треугольник→треугольник и его покрытие."""
    lut = {tuple(sorted(map(int, tri))): index for index, tri in enumerate(target_tri)}
    face_map = np.full(len(source_tri), -1, np.int64)
    for index, tri in enumerate(source_tri):
        mapped = vertex_map[tri]
        if np.all(mapped >= 0):
            face_map[index] = lut.get(tuple(sorted(map(int, mapped))), -1)
    return face_map, float(np.mean(face_map >= 0))


def export(source_tri: Path, target_tri: Path, source_to_target_vertex: Path,
           output: Path, min_coverage: float = 0.995) -> dict[str, Any]:
    """📤 Проверить и сохранить соответствие; FAIL-LOUD при нарушении контракта.

    Raises:
        SystemExit: покрытие ниже порога или маппинг не биективен.
    """
    face_map, coverage = build_face_map(np.load(source_tri), np.load(target_tri),
                                        np.load(source_to_target_vertex))
    if coverage < min_coverage:
        raise SystemExit(f"FAIL-LOUD: exact face coverage {coverage:.3%} "
                         f"below {min_coverage:.3%}; no output")
    if len(np.unique(face_map[face_map >= 0])) != int(np.sum(face_map >= 0)):
        raise SystemExit("FAIL-LOUD: mapping is not bijective")
    np.savez_compressed(output, source_face_to_target_face=face_map,
                        coverage=np.array(coverage))
    return {"coverage": coverage, "output": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--source-tri", required=True, type=Path)
    parser.add_argument("--target-tri", required=True, type=Path)
    parser.add_argument("--source-to-target-vertex", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-coverage", type=float, default=0.995)
    args = parser.parse_args()
    result = export(args.source_tri, args.target_tri, args.source_to_target_vertex,
                    args.output, args.min_coverage)
    print(result["coverage"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
