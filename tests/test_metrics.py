"""
Stage 1 T1: metric extractors against hand-computed arrays, and the support margin against hand-drawn hulls.
No MuJoCo, no files.

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

import metrics as mt  # noqa: E402

DEG = math.pi / 180


class JointMetrics(unittest.TestCase):
    def setUp(self):
        # angle in rad, deliberately including negative extremes
        self.q = np.array([0.0, -0.2, 0.1, 0.3, -0.5])
        self.qd = np.array([1.0, -4.0, 2.0, 0.5, -1.0])
        self.tau = np.array([2.0, -10.0, 4.0, 1.0, -3.0])

    def test_peak_uses_absolute_value(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied")
        self.assertEqual(m["torque_peak_nm"], 10.0)  # the negative extreme, not the +4
        self.assertEqual(m["speed_peak_rad_s"], 4.0)

    def test_rms_is_time_rms(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied")
        self.assertAlmostEqual(m["torque_rms_nm"], math.sqrt((4 + 100 + 16 + 1 + 9) / 5), places=12)

    def test_power_peak_is_max_abs_of_product(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied")
        # products: 2, 40, 8, 0.5, 3 -> 40 (both factors negative, so the product is positive)
        self.assertEqual(m["power_peak_w"], 40.0)
        m = mt.joint_metrics(self.q, -self.qd, self.tau, "applied")
        self.assertEqual(m["power_peak_w"], 40.0)  # sign of the product does not matter

    def test_rom_used_is_signed_min_and_max_in_degrees(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied")
        self.assertAlmostEqual(m["rom_used_deg"][0], -0.5 / DEG, places=12)
        self.assertAlmostEqual(m["rom_used_deg"][1], 0.3 / DEG, places=12)

    def test_rom_used_when_always_negative(self):
        m = mt.joint_metrics(np.array([-0.4, -0.1]), np.zeros(2), np.zeros(2), "applied")
        self.assertAlmostEqual(m["rom_used_deg"][1], -0.1 / DEG, places=12)  # max is negative, not clipped to 0

    def test_constant_signal(self):
        m = mt.joint_metrics(np.full(6, 0.25), np.zeros(6), np.full(6, -7.0), "inverse_dynamics")
        self.assertEqual(m["torque_peak_nm"], 7.0)
        self.assertAlmostEqual(m["torque_rms_nm"], 7.0, places=12)
        self.assertEqual(m["speed_peak_rad_s"], 0.0)
        self.assertEqual(m["power_peak_w"], 0.0)
        self.assertAlmostEqual(m["rom_used_deg"][0], m["rom_used_deg"][1], places=12)
        self.assertEqual(m["torque_source"], "inverse_dynamics")

    def test_unlimited_joint_has_null_limits(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied", limit_rad=None)
        self.assertIsNone(m["rom_limit_deg"])
        self.assertIsNone(m["limit_hit_fraction"])

    def test_limit_hit_fraction_counts_steps_within_tolerance_of_either_limit(self):
        lim = (-0.5, 0.3)
        tol = mt.LIMIT_TOL_DEG * DEG
        q = np.array([0.0, 0.3 - 0.5 * tol, -0.5 + 0.5 * tol, 0.3 - 2 * tol, 0.1])  # steps 1 and 2 are within 0.1 deg
        m = mt.joint_metrics(q, np.zeros(5), np.zeros(5), "applied", limit_rad=lim)
        self.assertAlmostEqual(m["limit_hit_fraction"], 2 / 5, places=12)
        self.assertAlmostEqual(m["rom_limit_deg"][0], -0.5 / DEG, places=12)
        self.assertAlmostEqual(m["rom_limit_deg"][1], 0.3 / DEG, places=12)

    def test_limit_tolerance_is_0p1_degree(self):
        self.assertEqual(mt.LIMIT_TOL_DEG, 0.1)

    def test_results_are_plain_floats(self):
        m = mt.joint_metrics(self.q, self.qd, self.tau, "applied", limit_rad=(-1, 1))
        for key in ("torque_peak_nm", "torque_rms_nm", "speed_peak_rad_s", "power_peak_w", "limit_hit_fraction"):
            self.assertIs(type(m[key]), float, key)
        self.assertTrue(all(type(v) is float for v in m["rom_used_deg"]))

    def test_mismatched_lengths_are_an_error(self):
        with self.assertRaises(ValueError):
            mt.joint_metrics(self.q, self.qd[:3], self.tau, "applied")

    def test_empty_window_is_an_error(self):
        with self.assertRaises(ValueError):
            mt.joint_metrics(np.array([]), np.array([]), np.array([]), "applied")


class FootContact(unittest.TestCase):
    def test_peak_normal_and_friction_ratio(self):
        normal = np.array([0.0, 100.0, 200.0, 50.0])
        tangential = np.array([0.0, 20.0, 10.0, 25.0])  # ratios 0.2, 0.05, 0.5
        m = mt.foot_metrics(normal, tangential)
        self.assertEqual(m["normal_force_peak_n"], 200.0)
        self.assertAlmostEqual(m["friction_ratio_peak"], 0.5, places=12)

    def test_steps_below_one_newton_are_ignored_for_the_ratio(self):
        normal = np.array([0.5, 0.9, 100.0])
        tangential = np.array([5.0, 5.0, 10.0])  # the first two would give ratios above 5
        self.assertAlmostEqual(mt.foot_metrics(normal, tangential)["friction_ratio_peak"], 0.1, places=12)

    def test_exactly_one_newton_counts(self):
        m = mt.foot_metrics(np.array([1.0]), np.array([0.5]))
        self.assertAlmostEqual(m["friction_ratio_peak"], 0.5, places=12)

    def test_never_loaded_gives_null_ratio(self):
        m = mt.foot_metrics(np.array([0.0, 0.5]), np.array([0.0, 0.1]))
        self.assertIsNone(m["friction_ratio_peak"])
        self.assertEqual(m["normal_force_peak_n"], 0.5)


SQUARE = [(0, 0), (2, 0), (2, 2), (0, 2)]


class SupportMargin(unittest.TestCase):
    def test_inside_the_square(self):
        self.assertAlmostEqual(mt.support_margin(SQUARE, (1.0, 1.0)), 1.0, places=12)
        self.assertAlmostEqual(mt.support_margin(SQUARE, (0.5, 1.0)), 0.5, places=12)  # nearest edge wins

    def test_on_the_boundary(self):
        self.assertAlmostEqual(mt.support_margin(SQUARE, (1.0, 0.0)), 0.0, places=12)
        self.assertAlmostEqual(mt.support_margin(SQUARE, (2.0, 2.0)), 0.0, places=12)  # a corner

    def test_outside_is_negative_distance_to_the_boundary(self):
        self.assertAlmostEqual(mt.support_margin(SQUARE, (3.0, 1.0)), -1.0, places=12)
        self.assertAlmostEqual(mt.support_margin(SQUARE, (3.0, 3.0)), -math.sqrt(2), places=12)  # nearest is the corner

    def test_interior_points_do_not_change_the_hull(self):
        pts = SQUARE + [(1.0, 1.0), (0.2, 0.3), (1.9, 0.1)]
        self.assertAlmostEqual(mt.support_margin(pts, (1.0, 1.0)), 1.0, places=12)

    def test_duplicate_and_collinear_boundary_points(self):
        pts = SQUARE + [(1.0, 0.0), (2.0, 0.0), (0.0, 0.0)]
        self.assertAlmostEqual(mt.support_margin(pts, (1.0, 1.0)), 1.0, places=12)

    def test_point_order_does_not_matter(self):
        pts = [SQUARE[2], SQUARE[0], SQUARE[3], SQUARE[1]]
        self.assertAlmostEqual(mt.support_margin(pts, (1.0, 0.5)), 0.5, places=12)

    def test_triangle(self):
        tri = [(0, 0), (3, 0), (0, 4)]  # inradius 1, incentre (1, 1)
        self.assertAlmostEqual(mt.support_margin(tri, (1.0, 1.0)), 1.0, places=12)

    def test_degenerate_hulls_are_never_positive(self):
        self.assertEqual(mt.support_margin([], (0.0, 0.0)), -math.inf)  # no contact: nothing supports the body
        self.assertAlmostEqual(mt.support_margin([(1.0, 1.0)], (1.0, 1.0)), 0.0, places=12)
        self.assertAlmostEqual(mt.support_margin([(1.0, 1.0)], (4.0, 5.0)), -5.0, places=12)
        segment = [(0.0, 0.0), (2.0, 0.0)]
        self.assertAlmostEqual(mt.support_margin(segment, (1.0, 0.0)), 0.0, places=12)  # on the segment: zero, not positive
        self.assertAlmostEqual(mt.support_margin(segment, (1.0, 0.5)), -0.5, places=12)
        self.assertAlmostEqual(mt.support_margin(segment, (3.0, 0.0)), -1.0, places=12)  # beyond its end
        collinear = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        self.assertAlmostEqual(mt.support_margin(collinear, (1.5, 1.5)), 0.0, places=12)
        self.assertLess(mt.support_margin(collinear, (0.0, 3.0)), 0.0)

    def test_nearly_collinear_points_are_treated_as_a_segment(self):
        pts = [(0.0, 0.0), (1.0, 1e-15), (2.0, 0.0)]
        self.assertLessEqual(mt.support_margin(pts, (1.0, 0.0)), 1e-9)

    def test_min_over_steps(self):
        steps = [(SQUARE, (1.0, 1.0)), (SQUARE, (1.5, 1.0)), ([], (0.0, 0.0))]  # the last step has no contact
        self.assertAlmostEqual(mt.min_support_margin(steps), 0.5, places=12)  # steps without contact are skipped

    def test_min_over_no_contact_steps_is_none(self):
        self.assertIsNone(mt.min_support_margin([([], (0.0, 0.0))]))
        self.assertIsNone(mt.min_support_margin([]))


class Hull(unittest.TestCase):
    def test_counter_clockwise_and_minimal(self):
        h = mt.convex_hull(SQUARE + [(1.0, 0.0), (1.0, 1.0)])
        self.assertEqual(sorted(h), sorted(SQUARE))
        area2 = sum(h[i][0] * h[(i + 1) % 4][1] - h[(i + 1) % 4][0] * h[i][1] for i in range(4))
        self.assertGreater(area2, 0)  # counter-clockwise

    def test_degenerate_inputs(self):
        self.assertEqual(mt.convex_hull([]), [])
        self.assertEqual(mt.convex_hull([(1.0, 2.0), (1.0, 2.0)]), [(1.0, 2.0)])
        self.assertEqual(len(mt.convex_hull([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])), 2)


if __name__ == "__main__":
    unittest.main()
