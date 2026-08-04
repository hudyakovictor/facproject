"""Regression tests for iteration 06: profile preview, analysis runs, job phases.

Cover:
- ``app6.api.profile_preview.build_profile_preview`` for the missing profile,
  blocking conditions, and Stage 1 pose-bin breakdown;
- ``app6.api.analysis_runs`` listing and per-run pair access;
- ``Job`` + ``PhaseTracker`` mechanics used by ``make_analysis_runner``.

Не запускает Stage 2 или Stage 3 — проверяет только подготовку данных,
блокирующие условия и сериализацию для UI.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app6.api.job_phases import PROFILE_ANALYSIS_PHASES, PhaseTracker  # noqa: E402
from app6.api.jobs import Job, JobManager  # noqa: E402
from app6.api.profile_preview import (  # noqa: E402
    PREVIEW_SCHEMA,
    _pairs_for_bin,
    build_profile_preview,
)
from app6.api.analysis_runs import (  # noqa: E402
    RUN_SCHEMA,
    get_analysis_run,
    list_analysis_run_pairs,
    list_analysis_runs,
)


def _make_runtime_paths(storage_root: Path) -> object:
    from dataclasses import dataclass

    from app6.api.runtime_config import RuntimePaths

    return RuntimePaths(
        storage_root=storage_root,
        stage1_root=storage_root / "stage1",
        stage2_root=storage_root / "stage2",
        stage3_root=storage_root / "stage3",
        calibration_root=storage_root / "calibration",
        uploads_root=storage_root / "api_uploads",
        registry_root=storage_root / "registry",
        settings_path=storage_root / "registry" / "api_settings.json",
    )


def _write_manifest(profile_id: str, storage_root: Path, included_ids: list[str]) -> Path:
    profile_dir = storage_root / "profiles" / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = profile_dir / "selection_manifest.json"
    payload = {
        "schema": "deeputin-selection-manifest-v1.1",
        "not_a_verdict": True,
        "profile_id": profile_id,
        "profile_name": "test profile",
        "label": "test",
        "stage1_root": str(storage_root / "stage1"),
        "filter_state": {},
        "curation_snapshot": {"photos": {}},
        "included_ids": list(included_ids),
        "excluded_ids": [],
        "included_count": len(included_ids),
        "excluded_count": 0,
        "status_counts": {},
        "photo_statuses": {},
        "filter_reason_counts": {},
        "immutable_stage1": True,
        "frozen_at": "2026-08-04T00:00:00Z",
        "locked_after_freeze": False,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    config = profile_dir / "config.json"
    config.write_text(json.dumps({"name": "test profile"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


class PairsForBinTests(unittest.TestCase):
    def test_zero_records(self):
        self.assertEqual(_pairs_for_bin(0), {"adjacent": 0, "baseline": 0, "total": 0})

    def test_single_record(self):
        self.assertEqual(_pairs_for_bin(1), {"adjacent": 0, "baseline": 0, "total": 0})

    def test_two_records(self):
        self.assertEqual(_pairs_for_bin(2), {"adjacent": 1, "baseline": 0, "total": 1})

    def test_many_records(self):
        # 10 records → 9 adjacent + 8 baseline = 17 total
        self.assertEqual(_pairs_for_bin(10), {"adjacent": 9, "baseline": 8, "total": 17})


class ProfilePreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        storage = Path(self.tmp.name)
        # Mimic "Stage 1 ready" so blockers reduce to manifest/calibration.
        (storage / "stage1").mkdir(parents=True, exist_ok=True)
        (storage / "stage1" / "main_timeline.csv").write_text("x", encoding="utf-8")
        (storage / "calibration").mkdir(parents=True, exist_ok=True)
        (storage / "calibration" / "all_calibration_index.csv").write_text(
            "pose_bin\nfrontal\nfrontal\nleft_profile\n", encoding="utf-8",
        )
        self.paths = _make_runtime_paths(storage)
        self.photos = [
            {"id": "p1", "bucket": "frontal"},
            {"id": "p2", "bucket": "frontal"},
            {"id": "p3", "bucket": "frontal"},
            {"id": "p4", "bucket": "left_profile"},
            {"id": "p5", "bucket": "left_profile"},
            {"id": "p6", "bucket": "frontal", "alignment_quality": 0.95},
        ]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_profile_blocks(self):
        preview = build_profile_preview("ghost", paths=self.paths)
        self.assertEqual(preview["schema"], PREVIEW_SCHEMA)
        self.assertFalse(preview["is_runnable"])
        self.assertIn(
            "Профиль не имеет замороженной выборки (вызовите freeze)",
            preview["blockers"],
        )
        self.assertEqual(preview["total_pairs"], 0)

    def test_frozen_manifest_with_paired_pose_bins(self):
        storage_path = self.paths.storage_root  # type: ignore[attr-defined]
        _write_manifest("prof", storage_path, ["p1", "p2", "p3", "p4", "p5"])
        preview = build_profile_preview("prof", photos=self.photos, paths=self.paths)
        self.assertTrue(preview["is_runnable"])
        self.assertEqual(preview["included_count"], 5)
        # frontal: 3 records → 2 adjacent + 1 baseline = 3 pairs
        # left_profile: 2 records → 1 adjacent + 0 baseline = 1 pair
        # total: 4
        self.assertEqual(preview["total_pairs"], 4)
        by_bin = {row["pose_bin"]: row for row in preview["pair_breakdown"]}
        self.assertEqual(by_bin["frontal"]["total_pairs"], 3)
        self.assertEqual(by_bin["left_profile"]["total_pairs"], 1)

    def test_estimated_runtime_is_deterministic(self):
        storage_path = self.paths.storage_root  # type: ignore[attr-defined]
        _write_manifest("prof", storage_path, [f"p{i}" for i in range(1, 6)])
        preview_a = build_profile_preview("prof", photos=self.photos, paths=self.paths)
        preview_b = build_profile_preview("prof", photos=self.photos, paths=self.paths)
        self.assertEqual(
            preview_a["estimated_runtime"]["total_seconds"],
            preview_b["estimated_runtime"]["total_seconds"],
        )
        self.assertGreater(preview_a["estimated_runtime"]["total_seconds"], 0)

    def test_blockers_when_calibration_missing(self):
        storage_path = self.paths.storage_root  # type: ignore[attr-defined]
        _write_manifest("prof", storage_path, ["p1", "p2"])
        # Очищаем calibration root полностью, чтобы триггернуть блокер.
        import shutil

        shutil.rmtree(storage_path / "calibration")
        preview = build_profile_preview("prof", photos=self.photos, paths=self.paths)
        self.assertFalse(preview["is_runnable"])
        self.assertTrue(any("Калибровочный датасет" in b for b in preview["blockers"]))


class JobPhaseTrackerTests(unittest.TestCase):
    def test_phases_lifecycle(self):
        tracker = PhaseTracker(PROFILE_ANALYSIS_PHASES)
        names = [p.name for p in tracker.phases]
        self.assertEqual(names, ["selection_load", "stage2", "stage3", "summary_persist"])

        tracker.start("selection_load")
        tracker.update("selection_load", done=1, total=2)
        phases = tracker.to_list()
        sel = next(p for p in phases if p["name"] == "selection_load")
        self.assertEqual(sel["status"], "running")
        self.assertEqual(sel["progress"]["done"], 1)

        tracker.finish("selection_load", note="ok")
        tracker.start("stage2", total=1)
        tracker.finish("stage2", status="complete", note="3 pairs")
        tracker.finish("stage3", status="blocked", note="calibration error")

        final = {p["name"]: p for p in tracker.to_list()}
        self.assertEqual(final["selection_load"]["status"], "complete")
        self.assertEqual(final["stage2"]["status"], "complete")
        self.assertEqual(final["stage3"]["status"], "blocked")
        self.assertEqual(final["summary_persist"]["status"], "pending")

    def test_job_to_dict_includes_phases(self):
        job = Job(id="abc123", kind="profile_analysis")
        phases = job.attach_phase_tracker(list(PROFILE_ANALYSIS_PHASES))
        phases.start("selection_load")
        payload = job.to_dict()
        self.assertEqual(payload["schema"], "deeputin-api-job-v1.0")
        self.assertEqual(payload["id"], "abc123")
        self.assertIn("phases", payload)
        self.assertEqual(len(payload["phases"]), 4)


class JobManagerRunMetaTests(unittest.TestCase):
    def test_submit_passes_run_id_and_profile_id(self):
        manager = JobManager()
        captured: dict[str, Job] = {}

        def runner(job: Job) -> None:
            captured["job"] = job

        job_id = manager.submit("profile_analysis", runner, run_id="run_xyz", profile_id="prof")
        # ждём завершения потока
        import time

        for _ in range(50):
            job = manager.get(job_id)
            if job and job["status"] in ("complete", "failed", "blocked", "cancelled"):
                break
            time.sleep(0.05)
        self.assertIsNotNone(captured.get("job"))
        self.assertEqual(captured["job"].run_id, "run_xyz")
        self.assertEqual(captured["job"].profile_id, "prof")


class AnalysisRunsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name)
        (self.storage / "analysis_runs").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_run(self, run_id: str, profile_id: str | None = None, *,
                  with_pair_metrics: bool = False, pair_count: int = 0) -> Path:
        run_dir = self.storage / "analysis_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": RUN_SCHEMA,
            "not_a_verdict": True,
            "profile_id": profile_id,
            "included_count": 10,
            "selection_manifest_digest": "deadbeef",
            "phases": [{"name": "selection_load", "status": "complete"}],
        }
        (run_dir / "run_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        if with_pair_metrics:
            stage2 = run_dir / "stage2"
            stage2.mkdir(parents=True, exist_ok=True)
            path = stage2 / "pair_metrics.csv"
            rows = ["photo_a,photo_b,pose_bin,landmark_distance\n"]
            for i in range(pair_count):
                rows.append(f"p{i}a,p{i}b,frontal,{0.5 + i * 0.1}\n")
            path.write_text("".join(rows), encoding="utf-8")
            (stage2 / "analysis_manifest.json").write_text('{"ok": true}', encoding="utf-8")
        return run_dir

    def test_list_analysis_runs_filters_by_profile(self):
        self._make_run("run_a", profile_id="profA")
        self._make_run("run_b", profile_id="profB")
        listing = list_analysis_runs(paths=_make_runtime_paths(self.storage))
        ids = [r["run_id"] for r in listing["runs"]]
        self.assertIn("run_a", ids)
        self.assertIn("run_b", ids)
        filtered = list_analysis_runs(profile_id="profB", paths=_make_runtime_paths(self.storage))
        self.assertEqual([r["run_id"] for r in filtered["runs"]], ["run_b"])

    def test_get_analysis_run_summary(self):
        self._make_run("run_a", profile_id="profA", with_pair_metrics=True, pair_count=3)
        details = get_analysis_run("run_a", paths=_make_runtime_paths(self.storage))
        self.assertEqual(details["schema"], RUN_SCHEMA)
        self.assertTrue(details["has_summary"])
        self.assertTrue(details["has_stage2"])
        self.assertIn("summary", details)
        self.assertEqual(details["summary"]["profile_id"], "profA")

    def test_get_analysis_run_invalid_id(self):
        with self.assertRaises(ValueError):
            get_analysis_run("../etc", paths=_make_runtime_paths(self.storage))

    def test_get_analysis_run_missing(self):
        with self.assertRaises(FileNotFoundError):
            get_analysis_run("missing", paths=_make_runtime_paths(self.storage))

    def test_list_pairs_pagination(self):
        self._make_run("run_a", with_pair_metrics=True, pair_count=5)
        page = list_analysis_run_pairs("run_a", paths=_make_runtime_paths(self.storage))
        self.assertEqual(page["schema"], RUN_SCHEMA)
        self.assertEqual(page["count"], 5)
        self.assertEqual(len(page["pairs"]), 5)

    def test_list_pairs_missing_stage2(self):
        self._make_run("run_b")
        payload = list_analysis_run_pairs("run_b", paths=_make_runtime_paths(self.storage))
        self.assertEqual(payload["count"], 0)
        self.assertIn("missing", payload)


if __name__ == "__main__":
    unittest.main()
