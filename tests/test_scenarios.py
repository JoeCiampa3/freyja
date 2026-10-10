"""
Stage 1 T3: the first two scenarios, run on the committed model (read-only: runs go to a temporary directory).

rom_sweep is checked against independent numbers (the model's own range, the model's gravity bias, the left/right
mirror). hold_pose carries the brief's two acceptance tests. The committed model does not stand: the neutral CoM sits
1.29 mm in front of the heel edge, so the hold topples backward at about 1.35 s, before its measurement window. That
is a finding, not a bug to tune away (CONVENTIONS section 9.5), so the two acceptance tests are strict xfails that
carry the measured numbers: they start failing the day the model, and not the controller, changes.

Run from the repo root:
    python -m pytest tests
"""
import datetime as dt
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "checks"))

import mujoco  # noqa: E402

import metrics  # noqa: E402
import runrecord as rr  # noqa: E402
import simrun  # noqa: E402

NOW = dt.datetime(2026, 10, 12, 14, 30)
MIRROR_TORQUE_REL = 2e-2  # of the larger of a left/right pair (the brief's 2%)
MIRROR_TORQUE_FLOOR_NM = 0.05  # N m. Below this a torque is round-off and a ratio means nothing (e.g. ankle inversion)
FORCE_CLOSURE_REL = 5e-3  # of body weight (the brief's 0.5%)


def pairs(joint_names):
    return [(n, n.replace("_right", "_left")) for n in joint_names if n.endswith("_right")]


class RomSweep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.result = simrun.run_scenario(simrun.load_scenario("rom_sweep"), runs_dir=cls.tmp.name, now=NOW)
        cls.rec = cls.result.record
        cls.model = mujoco.MjModel.from_xml_path(str(simrun.MODEL_FILE))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_completes_gantry_inverse_dynamics_and_validates(self):
        self.assertEqual(self.rec["outcome"], "completed")
        self.assertEqual(self.rec["support"], "gantry")
        self.assertEqual({j["torque_source"] for j in self.rec["joints"].values()}, {"inverse_dynamics"})
        rr.validate(self.rec)

    def test_every_limited_joint_is_swept_and_every_unlimited_joint_is_skipped_not_invented(self):
        limited, unlimited = set(), set()
        for j in range(self.model.njnt):
            if self.model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE:
                continue
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, j)
            (limited if self.model.jnt_limited[j] else unlimited).add(name)
        self.assertEqual(set(self.rec["joints"]), limited)
        self.assertEqual(set(self.rec["skipped"]), unlimited)
        self.assertEqual(set(self.rec["skipped"].values()), {"unlimited"})
        self.assertEqual((len(limited), len(unlimited)), (18, 13))  # the 7 missing sheet ROM values and the template's bare joints

    def test_each_joint_moves_across_99_percent_of_its_model_range_without_touching_the_limit(self):
        for name, j in self.rec["joints"].items():
            lo, hi = j["rom_limit_deg"]
            self.assertAlmostEqual(j["rom_used_deg"][0], 0.99 * lo, places=6, msg=name)
            self.assertAlmostEqual(j["rom_used_deg"][1], 0.99 * hi, places=6, msg=name)
            # 99% of a limit under 10 degrees is closer to it than the 0.1 deg that counts as a hit (the knee's -1.6 deg)
            near = [lim for lim in (lo, hi) if abs(0.01 * lim) < metrics.LIMIT_TOL_DEG]
            if near:
                self.assertGreater(j["limit_hit_fraction"], 0.0, name)
            else:
                self.assertEqual(j["limit_hit_fraction"], 0.0, name)

    def test_first_sample_of_each_sweep_is_the_models_gravity_bias_plus_inertia_times_the_ease_in(self):
        # at the first sample the joint is at neutral and still, but accelerating: tau = bias + M_jj * qdd, with bias and
        # M from forward kinematics of the model and qdd from the cosine ease of the first leg (not from mj_inverse)
        data = mujoco.MjData(self.model)
        mujoco.mj_forward(self.model, data)
        mass = np.zeros((self.model.nv, self.model.nv))
        mujoco.mj_fullM(self.model, data, mass)
        names = list(self.result.raw["joint_names"])
        sweep_s = self.rec["scenario"]["params"]["params"]["sweep_s"]
        dt_ = self.rec["timestep_s"]
        for name in ("hip_fe_right", "knee_right", "ankle_pdflex_right", "shoulder_fe_left", "wrist_left"):
            j = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
            dof = self.model.jnt_dofadr[j]
            lo, hi = self.model.jnt_range[j]
            legs = np.abs(np.diff([0.0, 0.99 * hi, 0.99 * lo, 0.0]))
            leg0 = round(sweep_s * legs[0] / legs.sum() / dt_) * dt_
            qdd0 = 0.99 * hi * math.pi ** 2 / (2 * leg0 ** 2)
            k0 = int(round(sweep_s * names.index(name) / dt_))
            expected = data.qfrc_bias[dof] + mass[dof, dof] * qdd0
            self.assertAlmostEqual(self.result.raw["tau"][k0, names.index(name)], expected, places=9, msg=name)

    def test_the_mirror_image_joints_carry_identical_torques(self):
        # the model's axes follow the mirror rule, so one sweep on each side must give the same scalar torque curve
        for right, left in pairs(self.rec["joints"]):
            a, b = self.rec["joints"][right], self.rec["joints"][left]
            for key in ("torque_peak_nm", "torque_rms_nm", "speed_peak_rad_s", "power_peak_w"):
                self.assertAlmostEqual(a[key], b[key], delta=1e-9 * max(1.0, abs(a[key])), msg=f"{right} {key}")

    def test_sweep_is_slow(self):
        peak = max(j["speed_peak_rad_s"] for j in self.rec["joints"].values())
        self.assertLess(math.degrees(peak), 45.0)  # deg/s: ends are eased, no joint is thrown across its range

    def test_the_rom_check_passes_on_this_sweep(self):
        import checklib
        import sim_checks
        from unittest import mock
        ctx = checklib.Context.from_files()
        with mock.patch.object(sim_checks, "RUNS_DIR", Path(self.tmp.name)):
            (result,) = checklib.call(checklib.REGISTRY["check.sim.rom_reachable"], ctx)
        self.assertEqual((result.status, result.measured["joints_checked"]), (checklib.PASS, 18), result.message)


class HoldPose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.result = simrun.run_scenario(simrun.load_scenario("hold_pose"), runs_dir=cls.tmp.name, now=NOW)
        cls.rec = cls.result.record
        cls.diag = cls.rec["diagnostics"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_record_validates_and_reports_the_standing_numbers_even_when_the_run_falls(self):
        rr.validate(self.rec)
        self.assertEqual(self.rec["support"], "ground")
        self.assertEqual(self.rec["scenario"]["params"]["options"]["timestep_s"], 0.0002)
        for key in ("body_weight_n", "support_margin_first_step_m", "penetration_max_run_m"):
            self.assertIn(key, self.diag)
        self.assertAlmostEqual(self.diag["body_weight_n"], 64.935 * 9.81, places=6)

    def test_inverse_dynamics_joint_rows_recover_the_applied_torque_with_contacts_too(self):
        # forward dynamics, then mj_inverse on the same state and acceleration: the joint rows close to round-off,
        # contacts included (it is only a PRESCRIBED trajectory with contacts that does not close)
        peak = float(np.max(np.abs(self.result.raw["tau"])))
        self.assertLess(self.diag["inverse_closure_max_joint_abs_nm"], simrun.INVERSE_CLOSURE_REL * peak)

    def test_pd_gains_are_recorded(self):
        self.assertEqual(self.rec["scenario"]["params"]["params"]["kp_nm_per_rad"], 2000.0)

    @pytest.mark.xfail(strict=True, raises=AssertionError,
                       reason="FINDING: hold_pose topples backward at 1.355 s (before its 2-3 s window); neutral CoM is 1.29 mm "
                              "in front of the heel edge, so there is no standing equilibrium to measure")
    def test_mean_vertical_contact_force_equals_body_weight_within_half_a_percent(self):
        self.assertEqual(self.rec["outcome"], "completed")
        ratio = self.diag["vertical_force_mean_n"] / self.diag["body_weight_n"]
        self.assertAlmostEqual(ratio, 1.0, delta=FORCE_CLOSURE_REL)

    @pytest.mark.xfail(strict=True, raises=AssertionError,
                       reason="FINDING: the run falls before its measurement window, so there are no joint torques to compare")
    def test_mirror_image_joints_carry_equal_torques_within_2_percent(self):
        # mirror rule: axes (ax, ay, az) -> (-ax, ay, -az), so a mirror-symmetric load gives the SAME scalar torque on
        # each side (the world-frame torque vectors are the ones that are mirror images, with opposite x and z)
        self.assertEqual(self.rec["outcome"], "completed")
        joints = self.rec["joints"]
        self.assertTrue(joints)
        for right, left in pairs(joints):
            a, b = joints[right]["torque_rms_nm"], joints[left]["torque_rms_nm"]
            self.assertLessEqual(abs(a - b), max(MIRROR_TORQUE_REL * max(a, b), MIRROR_TORQUE_FLOOR_NM), right)


if __name__ == "__main__":
    unittest.main()
