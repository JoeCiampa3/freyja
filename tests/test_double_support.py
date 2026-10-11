"""
Stage 2 T3c.3: double-support feasibility. The total CoP is fixed by the root rows whatever the force split; a frame is feasible when it
lies in the convex hull of the two feet's contact polygons; the feasible set is every split alpha and every pair of CoPs inside their own
polygons whose alpha-weighted mean is the total CoP.

Run from the repo root:
    python -m pytest tests/test_double_support.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import dynamics  # noqa: E402

G = 9.81


def box(cx, cy, hx=0.1, hy=0.05):
    return [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]


RIGHT, LEFT = box(0.0, -0.3), box(0.0, 0.3)  # two feet 0.6 m apart sideways


def test_a_cop_between_two_separated_feet_is_feasible_only_in_double_support():
    p = np.array([0.0, 0.0])
    assert dynamics.margin_in_polygon(RIGHT, p) < 0 and dynamics.margin_in_polygon(LEFT, p) < 0  # in neither foot
    s = dynamics.double_support_set(RIGHT, LEFT, p)
    assert s["feasible"] and s["solutions"]
    # a CoP in one foot is feasible with the whole force on that foot
    assert dynamics.double_support_set(RIGHT, LEFT, np.array([0.0, -0.3]))["feasible"]


def test_every_solution_satisfies_the_weighted_mean_identity_and_lies_in_its_polygons():
    for p in (np.array([0.02, -0.1]), np.array([-0.05, 0.12]), np.array([0.0, 0.0]), np.array([0.09, -0.27])):
        s = dynamics.double_support_set(RIGHT, LEFT, p, n_alpha=21, n_pr=5)
        assert s["feasible"] and len(s["solutions"]) >= 5
        for alpha, p_r, p_l in s["solutions"]:
            assert 0.0 <= alpha <= 1.0
            assert np.abs(alpha * p_r + (1 - alpha) * p_l - p).max() < 1e-12
            assert dynamics.margin_in_polygon(RIGHT, p_r) >= -1e-9 and dynamics.margin_in_polygon(LEFT, p_l) >= -1e-9


def test_a_cop_outside_the_hull_is_infeasible_and_reports_its_distance():
    p = np.array([0.5, 0.0])  # 0.4 m ahead of the feet's toes (x = 0.1)
    s = dynamics.double_support_set(RIGHT, LEFT, p)
    assert not s["feasible"] and s["solutions"] == []
    assert s["outside_m"] == pytest.approx(0.4, abs=1e-12)
    q = np.array([0.0, 0.6])  # beyond the left foot's outer edge (y = 0.35)
    assert dynamics.double_support_set(RIGHT, LEFT, q)["outside_m"] == pytest.approx(0.25, abs=1e-12)


def test_mutation_shrinking_a_polygon_turns_a_feasible_frame_infeasible():
    p = np.array([0.0, 0.05])
    assert dynamics.double_support_set(RIGHT, LEFT, p)["feasible"]
    tiny_left = box(0.0, 0.3, 0.001, 0.001)
    tiny_right = box(0.0, -0.3, 0.001, 0.001)
    shrunk = dynamics.double_support_set(tiny_right, tiny_left, np.array([0.05, 0.05]))
    assert not shrunk["feasible"]  # the hull of two small patches no longer reaches the point


def test_feasibility_is_the_hull_test_and_a_thin_set_between_grid_points_is_still_feasible():
    tiny_r, tiny_l = box(0.0, -0.3, 0.001, 0.001), box(0.0, 0.3, 0.001, 0.001)
    s = dynamics.double_support_set(tiny_r, tiny_l, np.array([0.0, 0.1]), n_alpha=3)  # needs alpha = 1/3, between the grid points 0, 0.5, 1
    assert s["feasible"] and s["solutions"] == [] and s["alpha_range"] is None
    assert dynamics.share_in_set(tiny_r, tiny_l, np.array([0.0, 0.1]), 1.0 / 3.0)  # and 1/3 does work


def test_the_alpha_range_is_bounded_by_where_the_hull_allows():
    p = np.array([0.0, -0.25])  # inside the right foot (y from -0.35 to -0.25): even alpha = 1 is allowed
    s = dynamics.double_support_set(RIGHT, LEFT, p, n_alpha=21)
    assert s["alpha_range"][1] == 1.0
    p2 = np.array([0.0, 0.0])  # exactly between: alpha must balance the two feet
    lo, hi = dynamics.double_support_set(RIGHT, LEFT, p2, n_alpha=21)["alpha_range"]
    assert 0.0 < lo <= 0.5 <= hi < 1.0  # neither foot can take the whole load when the CoP is 0.25 m from each


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def neutral(model):
    d = mujoco.MjData(model)
    mujoco.mj_resetData(model, d)
    return d.qpos.copy()


def test_the_total_cop_is_unchanged_by_the_split_and_every_solution_closes_the_root_rows(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), sweep=True)
    assert r.support == "double" and r.total_cop is not None
    qfrc = dynamics.inverse_frame(model, q, np.zeros(model.nv), np.zeros(model.nv))
    full, _, _ = dynamics.cop_decomposition(model, q, qfrc)
    assert np.abs(r.total_cop - full).max() < 1e-12
    assert r.ds_solutions, "the neutral standing pose has its total CoP between the feet"
    for alpha, p_r, p_l in r.ds_solutions[:: max(1, len(r.ds_solutions) // 12)]:
        torque, res, _ = dynamics.solve_given(model, q, qfrc, {"foot_right": alpha * qfrc[:3], "foot_left": (1 - alpha) * qfrc[:3]},
                                              {"foot_right": np.r_[p_r, 0.0], "foot_left": np.r_[p_l, 0.0]})
        assert np.abs(res[:5]).max() < 1e-7 * r.weight_n


def test_the_worst_case_torque_is_at_least_the_nominal_torque_where_the_nominal_case_is_feasible(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), sweep=True)
    assert r.feasible_nominal, "the neutral pose with an equal split is feasible"
    for name, (lo, hi) in r.torque_range.items():
        assert max(abs(lo), abs(hi)) >= abs(r.torque[name]) - 1e-9
        assert lo - 1e-9 <= r.torque[name] <= hi + 1e-9


def test_the_nominal_and_a_measured_share_are_tested_against_the_feasible_set(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), sweep=True)
    assert r.nominal_in_set is True
    far = dynamics.double_support_set(*r.polygons, r.total_cop[:2])
    assert dynamics.share_in_set(r.polygons[0], r.polygons[1], r.total_cop[:2], 0.5) is True
    assert dynamics.share_in_set(r.polygons[0], r.polygons[1], r.total_cop[:2] + np.array([0.0, 5.0]), 0.5) is False
    assert far["feasible"]


# ---- T3c.4: one outside-distance function for single and double support, with the polygon band as a parameter

def test_polygon_outside_distance_single_and_double_support(model):
    q = neutral(model)
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    corners, _ = dynamics._foot_boxes(model, d, mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "foot_right"))
    front = corners[:, 0].max()  # the box reaches 165 mm ahead of the ankle
    inside = np.array([0.057, -0.092])
    ahead = np.array([front + 0.10, -0.092])
    assert dynamics.polygon_outside_m(model, q, ("foot_right",), inside) == 0.0
    assert dynamics.polygon_outside_m(model, q, ("foot_right",), ahead) == pytest.approx(0.10, abs=1e-6)
    assert dynamics.polygon_outside_m(model, q, ("foot_left",), inside) == pytest.approx(0.1343, abs=1e-3)  # the right foot's spot, 134 mm from the left foot's inner edge
    both = ("foot_right", "foot_left")
    assert dynamics.polygon_outside_m(model, q, both, np.array([0.057, 0.0])) == 0.0  # between the feet: inside their hull
    assert dynamics.polygon_outside_m(model, q, both, ahead) == pytest.approx(0.10, abs=1e-6)


def test_the_band_decides_which_vertices_make_the_polygon(model):
    """Rolled onto the toe edge the polygon is a segment; a wider band lets the heel-side vertices in and the polygon grows."""
    q = neutral(model)
    d = mujoco.MjData(model)
    d.qpos[:] = q
    ankle = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "ankle_pdflex_right")]
    q[ankle] = -0.35  # plantarflexed about 20 degrees: the toe edge is lowest
    q[2] += 0.05
    point = np.array([0.057, -0.092])  # over the ankle: behind the toe edge
    narrow = dynamics.polygon_outside_m(model, q, ("foot_right",), point, band_m=0.010)
    wide = dynamics.polygon_outside_m(model, q, ("foot_right",), point, band_m=0.200)
    assert narrow > 0.05 and wide == 0.0
