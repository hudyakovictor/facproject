"""🎯 GUARD → Альфа-хронология (ER-158, волна сигналов).

apply_alpha_chronology: alpha_id/alpha_exp — диагностические каналы, не identity
вердикт. Отсутствующий alpha_exp не подменяется нулём (NOT_OBSERVED != 0);
alpha_id-прыжок переводит within_noise/uncertain строку в alpha_id_jump_candidate;
событие комментируется как «not an identity verdict».
"""
from __future__ import annotations

import unittest

from app6.stage2.alpha_chronology import apply_alpha_chronology


class _StubNoiseModel:
    """Мини-модель калибровки: reference(pose, channel) -> калибровочное описание."""

    def reference(self, pose: str, channel: str) -> dict:
        # median=0, mad=1, p95=20, count=100 — детерминированный фон.
        return {"median": 0.0, "mad": 1.0, "p95": 20.0, "count": 100}


def _row(alpha_id=None, alpha_exp=None, status="within_reconstruction_noise", pair_type="adjacent"):
    return {
        "pose_bin": "frontal",
        "alpha_id_l2": alpha_id,
        "alpha_exp_l2": alpha_exp,
        "status": status,
        "pair_type": pair_type,
        "pair_id": "p1",
        "photo_a": "A", "photo_b": "B",
        "date_a": "2020-01-01", "date_b": "2020-06-01",
    }


class AlphaChronologyTests(unittest.TestCase):
    model = _StubNoiseModel()

    def test_missing_alpha_id_is_unavailable_not_measurement(self):
        out = apply_alpha_chronology([_row(alpha_id=None)], self.model)
        self.assertEqual(out["schema"], "deeputin-stage2-alpha-chronology-v1.0")
        self.assertEqual(out["event_count"], 0)
        # Отсутствующий канал не фабрикуется как «в пределах шума»: события нет.

    def test_nonfinite_alpha_id_not_treated_as_elevated(self):
        rows = [_row(alpha_id=float("nan"), alpha_exp=float("nan"))]
        out = apply_alpha_chronology(rows, self.model)
        self.assertEqual(out["event_count"], 0)
        self.assertNotIn("alpha_id_jump_candidate", rows[0]["status"])

    def test_missing_alpha_exp_not_substituted_by_zero(self):
        # NOT_OBSERVED (NaN) не подменяется 0.0 → не должен дать ложный
        # «within_noise» статус и не должен участвовать в событии.
        row = _row(alpha_id=float("nan"), alpha_exp=None)
        out = apply_alpha_chronology([row], self.model)
        self.assertEqual(out["event_count"], 0)
        self.assertEqual(row.get("alpha_exp_status"), "unavailable")

    def test_alpha_id_jump_escalates_noise_row_to_candidate(self):
        # value=100 → robust_z>3.5 и >p95 → elevated → alpha_id_jump_candidate.
        row = _row(alpha_id=100.0, alpha_exp=float("nan"))
        out = apply_alpha_chronology([row], self.model)
        self.assertEqual(row["status"], "alpha_id_jump_candidate")
        self.assertEqual(out["event_count"], 1)
        self.assertEqual(out["events"][0]["interpretation"].find("not an identity verdict") >= 0, True)

    def test_quiet_alpha_id_does_not_create_event(self):
        # value=5 → z<3.5 и <p95 → within_calibration_noise → без прыжка.
        out = apply_alpha_chronology([
            _row(alpha_id=5.0, alpha_exp=float("nan"), status="within_reconstruction_noise"),
        ], self.model)
        self.assertEqual(out["event_count"], 0)

    def test_non_adjacent_pair_does_not_emit_event_on_jump(self):
        row = _row(alpha_id=100.0, alpha_exp=float("nan"), pair_type="cross_bin")
        out = apply_alpha_chronology([row], self.model)
        self.assertEqual(out["event_count"], 0)  # событие только для adjacent


if __name__ == "__main__":
    unittest.main()