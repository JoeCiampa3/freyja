"""
Stage 1c T1: the static equilibrium solver. Joint torques from mj_inverse with contacts disabled and the ground
reaction supplied as generalized forces through the foot Jacobians. Checked against an analytic pendulum and against an
independent subtree-moment formula that never calls mj_inverse.

Run from the repo root:
    python -m pytest tests
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import mujoco  # noqa: E402

import leanpose  # noqa: E402
import statics  # noqa: E402
from test_leanpose import TWO_LINK  # noqa: E402

FEET2 = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}


def freyja():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def foot_edges(model):
    """(front, rear) edges of the right foot's sole relative to the ankle, along x at neutral, read from the model's boxes (the foot and its toe)."""
    import dynamics
    d = mujoco.MjData(model)
    mujoco.mj_forward(model, d)
    corners, _ = dynamics._foot_boxes(model, d, model.body("foot_right").id)
    ankle = d.xpos[model.body("foot_right").id][0]
    return float(corners[:, 0].max() - ankle), float(corners[:, 0].min() - ankle)


def pose_data(model, target=0.0):
    lean = leanpose.solve_lean(model, target, FEET2)
    data = mujoco.MjData(model)
    data.qpos[:] = lean.qpos
    mujoco.mj_forward(model, data)
    return data


def descendants(model, body):
    out = {body}
    for b in range(model.nbody):
        p = model.body_parentid[b]
        while p != 0 and b not in out:
            if p in out:
                out.add(b)
            p = model.body_parentid[p]
    return out


def independent_torques(model, data):
    """tau_j = -axis . ( sum over bodies distal to j of (c - p) x (m g)  +  sum over feet in the subtree of (r - p) x F )
    written from statics alone: no mj_inverse. The ground force on each foot is vertical, at the CoM's x and the foot's y."""
    g = np.array([0.0, 0.0, model.opt.gravity[2]])
    weight = model.body_mass.sum() * abs(g[2])
    com = data.subtree_com[0]
    feet = {n: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in ("foot_right", "foot_left")}
    y = {n: data.xpos[b][1] for n, b in feet.items()}
    f_right = weight * (com[1] - y["foot_left"]) / (y["foot_right"] - y["foot_left"])
    force = {"foot_right": f_right, "foot_left": weight - f_right}
    out = {}
    for j in range(model.njnt):
        if model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE:
            continue
        p, axis = data.xanchor[j], data.xaxis[j]
        distal = descendants(model, model.jnt_bodyid[j])
        moment = np.zeros(3)
        for b in distal:
            moment += np.cross(data.xipos[b] - p, model.body_mass[b] * g)
        for n, b in feet.items():
            if b in distal:
                moment += np.cross(np.array([com[0], y[n], 0.0]) - p, np.array([0.0, 0.0, force[n]]))
        out[mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)] = float(-axis @ moment)
    return out


class Pendulum(unittest.TestCase):
    def test_ankle_torque_is_the_analytic_value(self):
        model = mujoco.MjModel.from_xml_string(TWO_LINK)
        weight = 50.0 * 9.81 + 1e-6 * 9.81
        axis_y = model.jnt_axis[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "ankle_pdflex_right")][1]
        for target in (0.0, 0.03, -0.02, 0.1):
            lean = leanpose.solve_lean(model, target, {"foot_right": "ankle_pdflex_right"})
            data = mujoco.MjData(model)
            data.qpos[:] = lean.qpos
            mujoco.mj_forward(model, data)
            result = statics.solve_static(model, data, feet=("foot_right",))
            expected = axis_y * weight * target  # tau = axis_y * W * d for a CoM d in front of the ankle
            # the foot is massless to 1e-6 kg, which moves the whole-body CoM by under 1e-9 m
            self.assertAlmostEqual(result.torque["ankle_pdflex_right"], expected, delta=1e-9 * max(1.0, abs(expected)) + 1e-6 * 9.81 * 0.1)
            self.assertLess(result.residual_force_n, 1e-9 * weight)


class FreyjaTorques(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = freyja()
        cls.weight = float(cls.model.body_mass.sum() * 9.81)

    def test_every_hinge_matches_the_independent_subtree_moment_formula(self):
        for target in (0.0, 0.02):
            data = pose_data(self.model, target)
            result = statics.solve_static(self.model, data)
            expected = independent_torques(self.model, data)
            self.assertEqual(set(result.torque), set(expected))
            scale = max(abs(v) for v in expected.values())
            for name, value in expected.items():
                self.assertAlmostEqual(result.torque[name], value, delta=1e-9 * max(abs(value), 1e-3 * scale), msg=f"{name} at {target}")

    def test_root_rows_close_to_round_off(self):
        result = statics.solve_static(self.model, pose_data(self.model))
        self.assertLess(result.residual_force_n, 1e-9 * self.weight)
        self.assertLess(result.residual_moment_nm, 1e-9 * self.weight)

    def test_mutation_flipping_the_ground_force_breaks_the_residual(self):
        result = statics.solve_static(self.model, pose_data(self.model), _ground_sign=-1.0)
        self.assertGreater(result.residual_force_n, 1e-9 * self.weight)  # the same assertion as above must fail

    def test_force_split_sums_to_weight_and_is_symmetric_for_a_symmetric_pose(self):
        result = statics.solve_static(self.model, pose_data(self.model))
        self.assertAlmostEqual(sum(result.force_split.values()), self.weight, delta=1e-9 * self.weight)
        self.assertAlmostEqual(result.force_split["foot_right"], result.force_split["foot_left"], delta=5e-3 * self.weight)  # 0.16 mm lateral CoM offset

    def test_mirror_pairs_carry_the_same_scalar_torque(self):
        result = statics.solve_static(self.model, pose_data(self.model))
        for name, value in result.torque.items():
            if name.endswith("_right"):
                self.assertAlmostEqual(value, result.torque[name.replace("_right", "_left")], delta=2e-2 * max(1.0, abs(value)), msg=name)  # 2%: the CoM is 0.16 mm right of centre, so the right foot carries 0.18% more


class Feasibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = freyja()

    def test_standing_pose_is_feasible_with_positive_margins(self):
        result = statics.solve_static(self.model, pose_data(self.model))
        self.assertTrue(result.feasible, result.reasons)
        self.assertGreater(result.support_margin_m, 0.02)
        # Joints standing on a zero-width stop (a range edge of exactly 0 at the neutral) are listed apart (memo 25, Q4): the sheet's shoulder adduction limit is a deliberate 0,
        # a placeholder, and the toe's flexion stop is the flat toe of ADR 0001. The margin is the smallest among the others: the knee at neutral is 1.6 deg from its -1.6 deg stop.
        self.assertEqual(sorted(result.zero_width_stops), ["shoulder_aa_left", "shoulder_aa_right", "toe_left", "toe_right"])
        self.assertIn(result.limit_joint, ("knee_right", "knee_left"))
        self.assertAlmostEqual(result.limit_margin_deg, 1.6, places=3)
        self.assertEqual(result.reasons, [])

    def test_com_beyond_the_toe_edge_is_infeasible_with_a_negative_margin(self):
        front, _ = foot_edges(self.model)
        result = statics.solve_static(self.model, pose_data(self.model, front + 0.025))  # 25 mm beyond the toe edge of the foot box
        self.assertFalse(result.feasible)
        self.assertLess(result.support_margin_m, 0.0)
        self.assertTrue(any("support" in r for r in result.reasons))

    def test_com_behind_the_heel_is_infeasible(self):
        _, rear = foot_edges(self.model)
        result = statics.solve_static(self.model, pose_data(self.model, rear - 0.019))  # 19 mm behind the heel edge of the foot box
        self.assertFalse(result.feasible)
        self.assertLess(result.support_margin_m, 0.0)

    def test_a_limited_joint_outside_its_range_is_infeasible_and_named(self):
        data = pose_data(self.model)
        j = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "knee_right")
        data.qpos[self.model.jnt_qposadr[j]] = -0.5  # the knee stops at -1.6 degrees
        mujoco.mj_forward(self.model, data)
        result = statics.solve_static(self.model, data)
        self.assertFalse(result.feasible)
        self.assertEqual(result.limit_joint, "knee_right")
        self.assertLess(result.limit_margin_deg, 0.0)
        self.assertTrue(any("knee_right" in r for r in result.reasons))

    def test_limit_margin_names_the_closest_joint(self):
        result = statics.solve_static(self.model, pose_data(self.model))
        q = result.qpos
        best = min(((min(math.degrees(q[self.model.jnt_qposadr[j]] - self.model.jnt_range[j][0]),
                         math.degrees(self.model.jnt_range[j][1] - q[self.model.jnt_qposadr[j]])), j)
                    for j in range(self.model.njnt) if self.model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE and self.model.jnt_limited[j]
                    and mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, j) not in result.zero_width_stops))  # the zero-width stops are reported apart
        self.assertAlmostEqual(result.limit_margin_deg, best[0], places=9)
        self.assertEqual(result.limit_joint, mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, best[1]))


class ZeroWidthStops(unittest.TestCase):
    def test_a_joint_off_its_zero_edge_is_not_a_zero_width_stop_and_one_beyond_a_nonzero_edge_is_still_a_limit_violation(self):
        model = freyja()
        data = pose_data(model)
        j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder_aa_right")
        data.qpos[model.jnt_qposadr[j]] = -0.1  # abducted by 5.7 degrees: off the stop, 5.7 deg margin to it
        mujoco.mj_forward(model, data)
        result = statics.solve_static(model, data)
        self.assertNotIn("shoulder_aa_right", result.zero_width_stops)
        self.assertIn("shoulder_aa_left", result.zero_width_stops)
        data.qpos[model.jnt_qposadr[j]] = 0.05  # past the zero edge: outside its range, so a violation, not a stop
        mujoco.mj_forward(model, data)
        result = statics.solve_static(model, data)
        self.assertNotIn("shoulder_aa_right", result.zero_width_stops)
        self.assertEqual(result.limit_joint, "shoulder_aa_right")
        self.assertLess(result.limit_margin_deg, 0.0)
        self.assertFalse(result.feasible)


class NoLeaks(unittest.TestCase):
    def test_contact_flag_restored_data_untouched_and_deterministic(self):
        model = freyja()
        data = pose_data(model)
        flags = int(model.opt.disableflags)
        before = (data.qpos.copy(), data.qvel.copy(), data.qacc.copy(), data.qfrc_applied.copy(), data.ncon, data.time)
        a = statics.solve_static(model, data)
        b = statics.solve_static(model, data)
        self.assertEqual(int(model.opt.disableflags), flags)
        self.assertEqual(a.torque, b.torque)
        self.assertEqual((a.residual_force_n, a.support_margin_m), (b.residual_force_n, b.support_margin_m))
        for was, now in zip(before, (data.qpos, data.qvel, data.qacc, data.qfrc_applied, data.ncon, data.time)):
            self.assertTrue(np.array_equal(was, now))

    def test_flag_is_restored_even_when_the_solve_fails(self):
        model = freyja()
        flags = int(model.opt.disableflags)
        with self.assertRaises(Exception):
            statics.solve_static(model, pose_data(model), feet=("no_such_foot",))
        self.assertEqual(int(model.opt.disableflags), flags)


if __name__ == "__main__":
    unittest.main()
