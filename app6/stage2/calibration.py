"""🎯 CRITICAL → Калибровка скоров: matched-null распределения + референсы.
🚪 API: matched_null(), reference(), consistency_check(), score()
📊 METRIC: все калиброванные z-скоры проходят через эту семью функций
🚨 WARNING: калибровка валидна только внутри своего pose bin (distance-guard `_pose_distance`).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np

from .core import Record, compare_landmarks
from .analysis_policy import pose_gap
from .robustness import balanced_reference, cluster_bootstrap_ci


class CalibrationModel:
    #: Максимум использований одного калибровочного кадра в matched-null.
    MAX_REUSE: int = 3
    #: Штраф (в единицах pose-distance) за каждое повторное использование.
    REUSE_PENALTY: float = 0.75

    def __init__(self, records: list[Record], zone106: np.ndarray,
                 zone134: np.ndarray, *, max_reuse: int | None = None):
        self.records = records; self.zone106 = zone106; self.zone134 = zone134
        self.max_reuse = int(max_reuse) if max_reuse is not None else self.MAX_REUSE
        self._use_count: Counter[str] = Counter()
        self.by_dataset_bin: dict[tuple[str, str], list[Record]] = defaultdict(list)
        for record in records:
            self.by_dataset_bin[(record.dataset_id, record.pose_bin)].append(record)
        self.datasets = sorted({r.dataset_id for r in records})
        # Keep the per-dataset observations.  LOPO sensitivity can then remove
        # one calibration person from the aggregates without recomputing every
        # landmark comparison from scratch.
        self.values_by_pose_metric_dataset = self._collect_reference_values()
        self.references: dict[str, dict[str, dict[str, float | int]]] = self._build_references(
            self.values_by_pose_metric_dataset
        )

    @staticmethod
    def _pose_distance(a: Record, b: Record) -> float:
        gap = pose_gap(a.angles, b.angles, pose_bin=a.pose_bin)
        if not gap.accepted: return float("inf")
        return float(np.linalg.norm((a.angles - b.angles) / np.array([15.0, 20.0, 15.0])))

    def _collect_reference_values(self) -> dict[str, dict[str, dict[str, list[float]]]]:
        values: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for (dataset, pose_bin), group in self.by_dataset_bin.items():
            if len(group) < 2: continue
            group = sorted(group, key=lambda r: (float(r.angles[1]), float(r.angles[0]), r.sequence))
            for offset in (1, 2, 3, 5, 10, 20, 50):
                for a, b in zip(group, group[offset:], strict=False):
                    if self._pose_distance(a, b) > 2.5: continue
                    comp = compare_landmarks(a, b, self.zone106, self.zone134)
                    if comp.status != "measured": continue
                    for key, value in comp.metrics.items():
                        values[pose_bin][key][dataset].append(value)
                    for zone in comp.zones:
                        if zone.get("status") == "measured":
                            values[pose_bin][f"zone::{zone['zone']}::rmse"][dataset].append(float(zone["rmse"]))
        return values

    @staticmethod
    def _build_references(
        values: dict[str, dict[str, dict[str, list[float]]]],
    ) -> dict[str, dict[str, dict[str, float | int]]]:
        references: dict[str, dict[str, dict[str, float | int]]] = {}
        for pose, metrics in values.items():
            pose_refs: dict[str, dict[str, float | int]] = {}
            for metric, by_dataset in metrics.items():
                ref = dict(balanced_reference(by_dataset))
                # 🚧 Патч 10/21: cluster-bootstrap CI на уровне датасетов.
                # Пары из одного субъекта зависимы; наивный bootstrap занижает
                # ширину CI (width_underestimate_factor). Кластеры = датасеты.
                obs: list[float] = []
                ids: list[str] = []
                for dataset, vals in by_dataset.items():
                    obs.extend(float(v) for v in vals)
                    ids.extend([dataset] * len(vals))
                if len(set(ids)) >= 2:
                    # Filter to finite values and check cluster count
                    finite_ids = [id_ for v, id_ in zip(obs, ids, strict=True) if np.isfinite(v)]
                    if len(set(finite_ids)) >= 2:
                        ci = cluster_bootstrap_ci(obs, ids)
                        ref["ci_lo"] = ci["ci_lo"]
                        ref["ci_hi"] = ci["ci_hi"]
                        ref["ci_width"] = ci["width"]
                        ref["ci_naive_width"] = ci["naive_width"]
                        ref["ci_width_underestimate_factor"] = ci["width_underestimate_factor"]
                        ref["ci_n_observations"] = ci["n_observations"]
                        ref["ci_n_clusters"] = ci["n_clusters"]
                        ref["ci_method"] = ci["method"]
                    else:
                        ref["ci_status"] = "insufficient_clusters_after_filter"
                    ref["ci_lo"] = ci["ci_lo"]
                    ref["ci_hi"] = ci["ci_hi"]
                    ref["ci_width"] = ci["width"]
                    ref["ci_naive_width"] = ci["naive_width"]
                    ref["ci_width_underestimate_factor"] = ci["width_underestimate_factor"]
                    ref["ci_n_observations"] = ci["n_observations"]
                    ref["ci_n_clusters"] = ci["n_clusters"]
                    ref["ci_method"] = ci["method"]
                else:
                    ref["ci_status"] = "insufficient_clusters"
                pose_refs[metric] = ref
            references[pose] = pose_refs
        return references

    def references_excluding_dataset(
        self, holdout_dataset: str,
    ) -> dict[str, dict[str, dict[str, float | int]]]:
        """Build LOPO references from cached observations.

        The landmark comparisons are immutable for a given calibration bundle;
        only the person-level aggregation changes when one dataset is held out.
        """
        filtered: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for pose, metrics in self.values_by_pose_metric_dataset.items():
            for metric, by_dataset in metrics.items():
                for dataset, observations in by_dataset.items():
                    if dataset != holdout_dataset:
                        filtered[pose][metric][dataset].extend(observations)
        return self._build_references(filtered)

    def _nearest(self, target: Record, dataset: str, exclude: str | None = None) -> Record | None:
        candidates = [r for r in self.by_dataset_bin.get((dataset, target.pose_bin), []) if r.record_id != exclude]
        if not candidates: return None
        # 📊 Калиброванный z-скор с pose-distance guard
        def score(record: Record) -> float:
            pose = self._pose_distance(target, record)
            vis = abs(float(target.visible134.mean()) - float(record.visible134.mean()))
            # 🚨 D7 (патч 9): повторное использование одного кадра раздувает
            # null-распределение и прячет хабы. Каждый повтор штрафуется, а при
            # исчерпании лимита кадр исключается из кандидатов вовсе.
            reuse = self.REUSE_PENALTY * self._use_count[record.record_id]
            return pose + 1.5 * vis + reuse
        if self.max_reuse > 0:
            fresh = [r for r in candidates if self._use_count[r.record_id] < self.max_reuse]
            if fresh:
                candidates = fresh
        best = min(candidates, key=score)
        if self.max_reuse > 0:
            self._use_count[best.record_id] += 1
        return best

    # 📊 Matched-null распределение для пары (same-subject null)
    def matched_null(self, a: Record, b: Record) -> dict[str, list[float]]:
        values: dict[str, list[float]] = defaultdict(list)
        for dataset in self.datasets:
            ca = self._nearest(a, dataset)
            cb = self._nearest(b, dataset, exclude=ca.record_id if ca else None)
            if ca is None or cb is None: continue
            comp = compare_landmarks(ca, cb, self.zone106, self.zone134)
            if comp.status != "measured": continue
            for key, value in comp.metrics.items(): values[key].append(value)
            for zone in comp.zones:
                if zone.get("status") == "measured":
                    values[f"zone::{zone['zone']}::rmse"].append(float(zone["rmse"]))
        return dict(values)

    # 📊 Референс-калибровка из sidecar
    def reference(self, pose_bin: str, metric: str, *, stratum: str | None = None) -> dict[str, float | int]:
        # 🚧 Стратификация (патч 18): ключ калибровки расширяется суффиксом
        # качества. Если стратифицированного референса ещё нет — честный
        # fallback на общий (count=0 сигнализирует об отсутствии слоя).
        key = pose_bin if not stratum else f"{pose_bin}::q_{stratum}"
        return self.references.get(key, {}).get(metric, {"count": 0, "median": 0.0, "mad": 0.0, "p95": 0.0, "p99": 0.0})

    def has_stratified_references(self) -> bool:
        """True если построены стратифицированные (``pose_bin::q_*``) референсы.

        Стратифицированные референсы появляются только после пересборки
        калибровки с учётом quality stratum. Пока их нет, движок обязан
        передавать ``stratum=None`` (общий пул), иначе ``calibrated_score``
        деградирует в ``insufficient_calibration`` из-за count=0.
        """
        return any("::q_" in k for k in self.references)

    def reuse_report(self) -> dict[str, Any]:
        """📤 Сводка использования калибровочных кадров (патч 9: hubs)."""
        counts = dict(self._use_count)
        cap = max(self.max_reuse, 1)
        return {
            "schema": "deeputin-calibration-reuse-v1.0",
            "policy": "max_reuse_cap_v1",
            "max_reuse": self.max_reuse,
            "reuse_penalty": self.REUSE_PENALTY,
            "distinct_used": len(counts),
            "max_use_count": max(counts.values()) if counts else 0,
            "hubs": sorted(rid for rid, c in counts.items() if c >= cap) if counts else [],
            "notes": "кадры, исчерпавшие лимит, исключаются из matched-null",
        }

    def consistency_check(self) -> dict[str, Any]:
        """📊 METRIC → Consistency check for calibration dataset.

        Checks that all calibration photos are likely of the same person.
        High variance in landmarks may indicate mixed identities.

        ⚠️ IN PROGRESS:
        - Simple heuristic based on landmark variance
        - No ground truth for validation

        Returns:
            dict with consistency metrics per pose_bin
        """
        results = {}
        for (dataset, pose_bin), group in self.by_dataset_bin.items():
            if len(group) < 2:
                continue

            # Compute pairwise distances between all photos in group
            distances = []
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if self._pose_distance(a, b) > 2.5:
                        continue
                    # Compare landmarks
                    common = np.asarray(a.visible134, bool) & np.asarray(b.visible134, bool)
                    if common.sum() < 30:
                        continue
                    diff = np.linalg.norm(a.ldm134[common] - b.ldm134[common], axis=1)
                    distances.append(float(np.median(diff)))

            if distances:
                results[f"{dataset}_{pose_bin}"] = {
                    "pair_count": len(distances),
                    "median_distance": float(np.median(distances)),
                    "max_distance": float(np.max(distances)),
                    "std_distance": float(np.std(distances)),
                    # High max_distance may indicate mixed identities
                    "consistency_flag": "ok" if np.max(distances) < 0.1 else "review",
                }
            else:
                results[f"{dataset}_{pose_bin}"] = {
                    "pair_count": 0,
                    "consistency_flag": "insufficient_data",
                }

        return results
