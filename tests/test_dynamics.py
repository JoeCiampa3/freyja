"""
Stage 2 T3 (first part): the inverse-dynamics frame solver used for the force-level report. Contacts and joint-limit
constraints are disabled for the call and restored afterwards.

Run from the repo root:
    python -m pytest tests/test_dynamics.py
"""
import copy
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import dynamics  # noqa: E402


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def neutral(model):
    d = mujoco.MjData(model)
    mujoco.mj_resetData(model, d)
    return d.qpos.copy()


def test_free_fall_has_zero_root_rows_and_zero_joint_torque(model):
    q = neutral(model)
    qacc = np.zeros(model.nv)
    qacc[:3] = model.opt.gravity
    f = dynamics.inverse_frame(model, q, np.zeros(model.nv), qacc)
    assert np.abs(f).max() < 1e-9


def test_at_rest_the_vertical_root_force_is_body_weight(model):
    f = dynamics.inverse_frame(model, neutral(model), np.zeros(model.nv), np.zeros(model.nv))
    assert f[2] == pytest.approx(model.body_mass.sum() * 9.81, rel=1e-12)
    assert abs(f[0]) < 1e-9 and abs(f[1]) < 1e-9


def test_vertical_root_force_follows_the_acceleration(model):
    qacc = np.zeros(model.nv)
    qacc[2] = 2.5
    f = dynamics.inverse_frame(model, neutral(model), np.zeros(model.nv), qacc)
    assert f[2] == pytest.approx(model.body_mass.sum() * (9.81 + 2.5), rel=1e-12)


def test_flags_are_restored_and_the_model_is_not_modified(model):
    before = int(model.opt.disableflags)
    dynamics.inverse_frame(model, neutral(model), np.zeros(model.nv), np.zeros(model.nv))
    assert int(model.opt.disableflags) == before


def test_a_pose_beyond_a_limit_gives_the_torque_of_a_model_without_the_limit(model):
    j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "knee_right")
    q = neutral(model)
    q[model.jnt_qposadr[j]] = model.jnt_range[j][0] - 0.2  # 11 degrees past the extension stop
    qd, qdd = np.zeros(model.nv), np.zeros(model.nv)
    got = dynamics.inverse_frame(model, q, qd, qdd)
    free = copy.copy(model)
    free = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    free.jnt_limited[j] = 0
    free.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    d = mujoco.MjData(free)
    d.qpos[:], d.qvel[:], d.qacc[:] = q, qd, qdd
    mujoco.mj_inverse(free, d)
    assert np.abs(got - d.qfrc_inverse).max() < 1e-12
    # and the stop would have changed the answer, so the test can fail
    keep = mujoco.MjData(model)
    keep.qpos[:] = q
    model.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    try:
        mujoco.mj_inverse(model, keep)
    finally:
        model.opt.disableflags &= ~int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    assert np.abs(keep.qfrc_inverse - got).max() > 1e-3


# ======================================================================== ground-wrench solve (T3)

import yaml  # noqa: E402

sys.path.insert(0, str(REPO / "analysis"))
import leanpose  # noqa: E402
import retarget  # noqa: E402

G = 9.81
ZMP_XML = """
<mujoco><option gravity="0 0 -9.81"/>
<worldbody><body name="foot_right" pos="0 0 0.5"><freejoint/>
<inertial pos="0 0 0" mass="10" diaginertia="0.3 0.5 0.2"/>
<geom type="box" size="0.1 0.05 0.03" pos="0 0 -0.5" contype="0" conaffinity="0" mass="0"/>
</body></worldbody></mujoco>"""
A, B, THETA, W = 0.05, 0.01, 0.1, 2 * np.pi * 0.8


def zmp_state(t, pitch):
    x, xd, xdd = A * np.sin(W * t), A * W * np.cos(W * t), -A * W ** 2 * np.sin(W * t)
    z, zd, zdd = 0.5 + B * np.sin(2 * W * t), 2 * B * W * np.cos(2 * W * t), -4 * B * W ** 2 * np.sin(2 * W * t)
    th, thd, thdd = ((THETA * np.sin(W * t + 0.3), THETA * W * np.cos(W * t + 0.3), -THETA * W ** 2 * np.sin(W * t + 0.3))
                     if pitch else (0.0, 0.0, 0.0))
    q = np.array([x, 0, z, np.cos(th / 2), 0, np.sin(th / 2), 0])
    return q, np.array([xd, 0, zd, 0, thd, 0]), np.array([xdd, 0, zdd, 0, thdd, 0]), (x, z, xdd, zdd, thdd)


@pytest.mark.parametrize("pitch", [False, True])
def test_single_body_cop_equals_the_zmp_formula(pitch):
    m = mujoco.MjModel.from_xml_string(ZMP_XML)
    mass, iyy = 10.0, 0.5
    for t in np.linspace(0.0, 1.2, 9):
        q, qd, qdd, (x, z, xdd, zdd, thdd) = zmp_state(t, pitch)
        r = dynamics.solve_frame(m, q, qd, qdd, stance=("foot_right",), feet=("foot_right",))
        zmp_x = x - (z * xdd + (iyy * thdd) / mass) / (zdd + G)
        assert r.cop["foot_right"][0] == pytest.approx(zmp_x, abs=1e-9)
        assert abs(r.cop["foot_right"][1]) < 1e-9
        assert r.force["foot_right"][2] == pytest.approx(mass * (zdd + G), rel=1e-12)
        assert abs(r.yaw_moment_nm) < 1e-9


def test_rotational_inertia_moves_the_cop_in_the_zmp_test():
    m = mujoco.MjModel.from_xml_string(ZMP_XML)
    q, qd, qdd, _ = zmp_state(0.3, True)
    with_rot = dynamics.solve_frame(m, q, qd, qdd, stance=("foot_right",), feet=("foot_right",)).cop["foot_right"][0]
    qdd2 = qdd.copy(); qdd2[4] = 0.0
    without = dynamics.solve_frame(m, q, qd, qdd2, stance=("foot_right",), feet=("foot_right",)).cop["foot_right"][0]
    assert abs(with_rot - without) > 1e-4


def test_symmetric_double_support_with_the_com_centred_splits_equally(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv))
    w = model.body_mass.sum() * G
    # the model's whole-body CoM sits 0.16 mm to one side (Stage 1c: 319.1 N / 317.9 N), i.e. 0.16 / 184 = 0.0009 of the split
    assert r.split_right == pytest.approx(0.5, abs=1.5e-3)
    for f in ("foot_right", "foot_left"):
        assert r.force[f][2] == pytest.approx(w / 2, rel=3e-3)
    assert np.abs(r.residual[:5]).max() < 1e-8  # force rows and the two horizontal moments close


def test_flipping_the_ground_wrench_breaks_the_root_residual_and_is_detected(model):
    q = neutral(model)
    good = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv))
    bad = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), _ground_sign=-1.0)
    assert np.abs(good.residual[:5]).max() < 1e-8
    assert np.abs(bad.residual[:3]).max() > 0.5 * model.body_mass.sum() * G
    assert not dynamics.root_closes(bad) and dynamics.root_closes(good)


def test_a_swing_foot_carries_no_force(model):
    r = dynamics.solve_frame(model, neutral(model), np.zeros(model.nv), np.zeros(model.nv), stance=("foot_right",))
    assert "foot_left" not in r.force or np.abs(r.force["foot_left"]).max() == 0.0
    assert r.support == "single_right"


def test_double_support_sweep_brackets_the_nominal_torque(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), sweep=True)
    for name, (lo, hi) in r.torque_range.items():
        assert lo - 1e-9 <= r.torque[name] <= hi + 1e-9


# ---- independent bottom-up Newton-Euler check of the stance-leg torques

MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
FEET2 = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}


def _body_kin(model, cycle, t):
    q, qd, _ = cycle.eval(t)
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)
    out = {}
    for name in ("foot_right", "shank_right", "thigh_right"):
        b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacBodyCom(model, d, jp, jr, b)
        out[name] = (jp @ qd, jr @ qd)
    return d, out


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_stance_leg_torques_equal_a_bottom_up_newton_euler_recursion(model):
    z = np.load(PROCESSED)
    stand = leanpose.solve_lean(model, 0.0, FEET2).qpos
    cyc = retarget.Cycle(model, MAPPING, stand, z["1.4_ik"][3], float(z["1.4_duration_s"][3]), 0.92)
    g = np.array([0.0, 0.0, -G])
    eps = 1e-6
    chain = ["foot_right", "shank_right", "thigh_right"]
    for ph in (0.2, 0.25, 0.3, 0.35, 0.4):  # right single support
        t = ph * cyc.T
        q, qd, qdd = cyc.eval(t)
        res = dynamics.solve_frame(model, q, qd, qdd, stance=("foot_right",))
        f_g, p_g = res.force["foot_right"], res.cop["foot_right"]
        d, kin = _body_kin(model, cyc, t)
        _, kp = _body_kin(model, cyc, t + eps)
        _, km = _body_kin(model, cyc, t - eps)
        F_child = np.zeros(3); M_child = np.zeros(3); x_child = None
        torques = {}
        for name in chain:
            b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
            m_b, com = model.body_mass[b], d.xipos[b]
            R = d.ximat[b].reshape(3, 3)
            I = R @ np.diag(model.body_inertia[b]) @ R.T
            a = (kp[name][0] - km[name][0]) / (2 * eps)
            alpha = (kp[name][1] - km[name][1]) / (2 * eps)
            w = kin[name][1]
            joints = [j for j in range(model.njnt) if model.jnt_bodyid[j] == b]
            xj = d.xanchor[joints[0]]
            F_ext = f_g if name == "foot_right" else np.zeros(3)
            F_in = m_b * a - m_b * g - F_ext + F_child
            M_in = I @ alpha + np.cross(w, I @ w) - np.cross(xj - com, F_in)
            if name == "foot_right":
                M_in -= np.cross(p_g - com, f_g)
            else:
                M_in += np.cross(x_child - com, F_child) + M_child
            for j in joints:
                torques[mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)] = float(d.xaxis[j] @ M_in)
            F_child, M_child, x_child = F_in, M_in, xj
        for joint in ("hip_fe_right", "hip_aa_right", "hip_ier_right", "knee_right", "ankle_pdflex_right", "ankle_ie_right"):
            ref = res.torque[joint]
            assert torques[joint] == pytest.approx(ref, rel=1e-6, abs=1e-6), (ph, joint)


# ---- T3b: split override, segment tolerance, CoP decomposition

def test_a_split_override_sets_the_force_share(model):
    q = neutral(model)
    r = dynamics.solve_frame(model, q, np.zeros(model.nv), np.zeros(model.nv), split_right_override=0.8)
    w = model.body_mass.sum() * G
    assert r.split_right == 0.8
    assert r.force["foot_right"][2] == pytest.approx(0.8 * w, rel=1e-12) and r.force["foot_left"][2] == pytest.approx(0.2 * w, rel=1e-12)
    assert np.abs(r.residual[:5]).max() < 1e-8  # the CoPs re-solve, so the wrench still closes


def test_segment_polygon_gets_a_named_tolerance_band():
    # a box rolled onto its toe edge: only the two toe-side bottom vertices are within the band of the lowest one
    corners = np.array([[0.1, -0.05, 0.0], [0.1, 0.05, 0.0], [-0.1, -0.05, 0.06], [-0.1, 0.05, 0.06],
                        [0.1, -0.05, 0.06], [0.1, 0.05, 0.06], [-0.1, -0.05, 0.12], [-0.1, 0.05, 0.12]])
    margin, degenerate = dynamics.contact_margin(corners, np.array([0.1, 0.0]), band_m=0.025)
    assert degenerate and margin == pytest.approx(0.0, abs=1e-12)  # on the edge
    margin, _ = dynamics.contact_margin(corners, np.array([0.1, 0.12]), band_m=0.025)
    assert margin == pytest.approx(-0.07)  # 70 mm beyond the toe-edge segment's end
    near = dynamics.contact_margin(corners, np.array([0.08, 0.0]), band_m=0.025)[0]
    assert near < 0 and dynamics.contact_margin(corners, np.array([0.08, 0.0]), 0.025, segment_tol_m=dynamics.SEGMENT_TOL_M)[0] >= 0
    assert dynamics.contact_margin(corners, np.array([0.0, 0.0]), 0.025, segment_tol_m=dynamics.SEGMENT_TOL_M)[0] < 0  # 100 mm away stays outside


@pytest.mark.parametrize("pitch", [False, True])
def test_cop_decomposition_point_mass_term_and_angular_momentum_term(pitch):
    m = mujoco.MjModel.from_xml_string(ZMP_XML)
    for t in (0.2, 0.5, 0.9):
        q, qd, qdd, (x, z, xdd, zdd, thdd) = zmp_state(t, pitch)
        qfrc = dynamics.inverse_frame(m, q, qd, qdd)
        full, pm, am = dynamics.cop_decomposition(m, q, qfrc)
        assert pm[0] == pytest.approx(x - z * xdd / (zdd + G), abs=1e-9)
        assert am[0] == pytest.approx(-(0.5 * thdd) / (10.0 * (zdd + G)), abs=1e-9)
        assert full[0] == pytest.approx(pm[0] + am[0], abs=1e-12)
        if not pitch:
            assert abs(am[0]) < 1e-9
