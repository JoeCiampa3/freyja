"""
Stage 1c T4: the gain-dependent bias of the PD hold, measured against the gain-independent static solve on the same pose.
Slow (two 8 s holds). It asserts only the qualitative claims; the numbers are in the Stage 1c recap.

Run from the repo root:
    python -m pytest tests -m slow
"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import simrun  # noqa: E402

JOINTS = ("ankle_pdflex_right", "hip_fe_right")


def rms(record):
    return {n: j["torque_rms_nm"] for n, j in record["joints"].items()}


@pytest.mark.slow
class HoldBias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.static = rms(simrun.run_scenario(simrun.load_scenario("stand_static"), runs_dir=cls.tmp.name,
                                             now=dt.datetime(2026, 10, 12, 9, 0)).record)
        cls.held = {}
        for i, kp in enumerate((1000.0, 2000.0)):
            scn = simrun.apply_overrides(simrun.load_scenario("hold_pose"), [f"params.kp_nm_per_rad={kp}", "options.verify_inverse=false"])
            record = simrun.run_scenario(scn, runs_dir=cls.tmp.name, now=dt.datetime(2026, 10, 12, 9, 1 + i)).record
            assert record["outcome"] == "completed", (kp, record["outcome"])
            cls.held[kp] = rms(record)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_held_ankle_torque_falls_as_the_gain_rises(self):
        self.assertGreater(self.held[1000.0]["ankle_pdflex_right"], self.held[2000.0]["ankle_pdflex_right"])

    def test_the_hold_minus_static_difference_shrinks_with_the_gain_at_the_ankle_and_hip(self):
        for joint in JOINTS:
            d1000 = abs(self.held[1000.0][joint] - self.static[joint])
            d2000 = abs(self.held[2000.0][joint] - self.static[joint])
            self.assertLess(d2000, d1000, joint)

    def test_the_hold_overstates_the_ankle_torque_by_an_order_of_magnitude(self):
        # with the CoM over the ankle the static torque is the weight of the feet only
        self.assertGreater(self.held[2000.0]["ankle_pdflex_right"], 5 * self.static["ankle_pdflex_right"])
