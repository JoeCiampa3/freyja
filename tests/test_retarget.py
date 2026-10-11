"""
Stage 2 T2: retargeting a stride of Camargo kinematics onto Freyja and deriving smooth, periodic qpos/qvel/qacc.

Checks: the derivatives are the derivatives of the positions (finite differences), integrating qvel with mj_integratePos
(which handles the free joint's quaternion) reproduces qpos to 1e-9, the root rule keeps the lowest foot point on the floor,
held joints stay at the standing pose, and a flipped velocity breaks the integration check.

Run from the repo root:
    python -m pytest tests/test_retarget.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import ingest_camargo as ic  # noqa: E402
import leanpose  # noqa: E402
import retarget  # noqa: E402

MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
data_needed = pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


@pytest.fixture(scope="module")
def stand(model):
    return leanpose.solve_lean(model, 0.0, FEET).qpos


@pytest.fixture(scope="module")
def stride():
    z = np.load(PROCESSED)
    return {"ik": z["1.4_ik"][3], "T": float(z["1.4_duration_s"][3]), "fp": z["1.4_fp"][3]}


@pytest.fixture(scope="module")
def cycle(model, stand, stride):
    return retarget.Cycle(model, MAPPING, stand, stride["ik"], stride["T"], scale=0.9)


def rot_diff_rad(q1, q2):
    r = np.zeros(3)
    mujoco.mju_subQuat(r, q1, q2)
    return np.linalg.norm(r)


# ---------- synthetic: a standing "stride" must stay standing ----------

def standing_ik(stand_deg=0.0):
    ik = np.zeros((101, len(ic.IK_CHANNELS)))
    ik[:, ic.IK_CHANNELS.index("pelvis_rotation")] = 90.0  # the lab frame's baseline (subject faces -z)
    ik[:, ic.IK_CHANNELS.index("pelvis_ty")] = 0.97
    return ik


def test_standing_input_gives_zero_velocity_and_flat_feet(model, stand):
    c = retarget.Cycle(model, MAPPING, stand, standing_ik(), 1.0, scale=1.0)
    q, qd, qdd = c.eval(0.37)
    assert np.abs(qd).max() < 1e-9 and np.abs(qdd).max() < 1e-7
    low = c.lowest_foot_z(q)
    assert abs(low) < 1e-9  # the root rule puts the lowest foot point on the floor
    # the dataset's 90 degree lab baseline maps to a forward-facing pelvis, i.e. exactly the model's standing orientation
    assert rot_diff_rad(q[3:7], stand[3:7]) < 1e-9


@pytest.mark.parametrize("rule", retarget.ROOT_RULES)
def test_both_root_rules_put_a_standing_foot_on_the_floor(model, stand, rule):
    c = retarget.Cycle(model, MAPPING, stand, standing_ik(), 1.0, scale=0.9, root_rule=rule)
    assert abs(c.lowest_foot_z(c.eval(0.4)[0])) < 1e-9


def pitch_forward_rad(q, stand):
    """Rotation of the pelvis relative to the standing orientation about the model's lateral (+y) axis, forward positive."""
    r = np.zeros(3)
    mujoco.mju_subQuat(r, q[3:7], stand[3:7])
    return r[1]


def test_a_numeric_pitch_mean_sets_the_mean_and_only_the_oscillation_comes_from_the_dataset(model, stand):
    ik = standing_ik()
    col = ic.IK_CHANNELS.index("pelvis_list")  # the sagittal pitch in this lab frame (pelvis_tilt is the roll)
    ik[:, col] = -7.0  # a constant pitch is removed: the standing orientation results
    flat = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pitch_mean=0.0)
    assert rot_diff_rad(flat.eval(0.3)[0][3:7], stand[3:7]) < 1e-9
    fwd = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pitch_mean=0.0, pitch_offset_deg=5.0)
    assert pitch_forward_rad(fwd.eval(0.3)[0], stand) == pytest.approx(np.deg2rad(5.0), abs=1e-9)  # positive = anterior
    back = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pitch_mean=0.0, pitch_offset_deg=-5.0)
    assert pitch_forward_rad(back.eval(0.3)[0], stand) == pytest.approx(-np.deg2rad(5.0), abs=1e-9)
    ik[:, col] = -7.0 - 2.0 * np.sin(2 * np.pi * np.linspace(0, 1, 101))  # an oscillation survives; forward = minus list
    osc = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pitch_mean=0.0)
    p = [pitch_forward_rad(osc.eval(t)[0], stand) for t in np.linspace(0, 1, 50, endpoint=False)]
    assert max(p) == pytest.approx(np.deg2rad(2.0) * 0.99, rel=0.05)


def test_the_offset_is_a_pitch_not_a_roll(model, stand):
    """The reason pelvis_list, not pelvis_tilt, carries the offset: a roll would load the right and left lateral torques in
    opposite directions, a pitch loads both limbs alike. Here: the offset changes no roll."""
    ik = standing_ik()
    q = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pitch_mean=0.0, pitch_offset_deg=5.0).eval(0.2)[0]
    r = np.zeros(3)
    mujoco.mju_subQuat(r, q[3:7], stand[3:7])
    assert abs(r[0]) < 1e-9 and abs(r[2]) < 1e-9 and abs(r[1]) == pytest.approx(np.deg2rad(5.0), abs=1e-9)


def test_wrap_gap_is_reported_per_joint(model, stand):
    ik = standing_ik()
    ik[:, ic.IK_CHANNELS.index("knee_angle_r")] = -np.linspace(0, 12.0, 101)  # a 12 degree drift over the stride
    gaps = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0).wrap_gap_deg()
    assert abs(abs(gaps["knee_right"]) - 12.0) < 1e-9
    assert abs(gaps["knee_left"]) < 1e-12


def test_held_joints_stay_at_the_standing_pose(model, stand, cycle):
    q, _, _ = cycle.eval(0.21 * cycle.T)
    for name in MAPPING["held"]:
        adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]
        assert q[adr] == stand[adr]


# ---------- derivatives ----------

@data_needed
def test_velocity_and_acceleration_match_finite_differences(model, cycle):
    eps = 1e-5
    for t in (0.05, 0.31, 0.62 * cycle.T, 0.93):
        q, qd, qdd = cycle.eval(t)
        qp, qdp, _ = cycle.eval(t + eps)
        qm, qdm, _ = cycle.eval(t - eps)
        # velocity: integrate the central difference of positions through mj_differentiatePos (quaternion-aware)
        fd = np.zeros(model.nv)
        mujoco.mj_differentiatePos(model, fd, 2 * eps, qm, qp)
        assert np.abs(fd - qd).max() < 1e-5 * max(1.0, np.abs(qd).max()), t
        # acceleration is the derivative of the (local-frame) velocity the model uses
        assert np.abs((qdp - qdm) / (2 * eps) - qdd).max() < 1e-4 * max(1.0, np.abs(qdd).max()), t


@data_needed
def test_cycle_is_periodic_to_second_derivative(cycle):
    a, b = cycle.eval(0.0), cycle.eval(cycle.T)
    assert np.abs(a[0][7:] - b[0][7:]).max() < 1e-9 and np.abs(a[0][:3] - b[0][:3]).max() < 1e-9
    assert rot_diff_rad(a[0][3:7], b[0][3:7]) < 1e-9
    assert np.abs(a[1] - b[1]).max() < 1e-7 and np.abs(a[2] - b[2]).max() < 1e-5


# ---------- integrating qvel returns qpos ----------

def integrate(model, cycle, t0, t1, substeps_per_s=4000, sign=1.0):
    """Fourth-order Magnus integration of qvel on the manifold with mj_integratePos. The free joint's angular velocity is in
    the body frame, so the increment over a step is h/2 (w1 + w2) +/- sqrt(3)/12 h^2 (w1 x w2) (two Gauss points)."""
    n = max(1, int(np.ceil((t1 - t0) * substeps_per_s)))
    h = (t1 - t0) / n
    g = np.sqrt(3) / 6
    q, _, _ = cycle.eval(t0)
    q = q.copy()
    for i in range(n):
        ta = t0 + i * h
        _, v1, _ = cycle.eval(ta + (0.5 - g) * h)
        _, v2, _ = cycle.eval(ta + (0.5 + g) * h)
        inc = 0.5 * h * (v1 + v2)
        inc[3:6] += sign * (np.sqrt(3) / 12) * h * h * np.cross(v1[3:6], v2[3:6])
        mujoco.mj_integratePos(model, q, inc, 1.0)
    return q


@data_needed
def test_integrating_qvel_reproduces_qpos(model, cycle):
    for t1 in (0.2 * cycle.T, 0.55 * cycle.T, cycle.T):
        q = integrate(model, cycle, 0.0, t1)
        ref, _, _ = cycle.eval(t1)
        assert np.abs(q[:3] - ref[:3]).max() < 1e-9
        assert rot_diff_rad(q[3:7], ref[3:7]) < 1e-9
        assert np.abs(q[7:] - ref[7:]).max() < 1e-9


@data_needed
def test_a_flipped_angular_velocity_fails_the_integration_check(model, cycle):
    class Flipped:
        T = cycle.T
        def eval(self, t):
            q, v, a = cycle.eval(t)
            v = v.copy(); v[3:6] *= -1
            return q, v, a
    q = integrate(model, Flipped(), 0.0, 0.5 * cycle.T)
    ref, _, _ = cycle.eval(0.5 * cycle.T)
    assert rot_diff_rad(q[3:7], ref[3:7]) > 1e-3


# ---------- root rule and reporting ----------

@data_needed
def test_root_rule_penetration_and_clearance_are_reported_consistently(model, cycle, stride):
    m = retarget.foot_metrics(model, cycle, stride["fp"][:, :, 6] > 0.5, belt_speed_mps=1.4)
    qs = cycle.grid()[0]
    low = np.array([[cycle.lowest_foot_z(q, foot=f) for f in (0, 1)] for q in qs])
    stance = stride["fp"][:, :, 6].T > 0.5
    assert m["stance_penetration_max_m"] == pytest.approx(max(0.0, float(-low[stance].min())), abs=1e-12)
    assert m["swing_clearance_min_m"] == pytest.approx(float(low[~stance].min()), abs=1e-12)
    assert np.isfinite(m["stance_slip_rms_mps"]) and m["stance_slip_max_mps"] >= m["stance_slip_rms_mps"]


@data_needed
def test_limit_fraction_counts_frames_outside_the_model_range(model, cycle):
    frac = retarget.limit_fraction(model, cycle.grid()[0])
    assert set(frac) <= {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j) for j in range(model.njnt)}
    assert all(0.0 <= v <= 1.0 for v in frac.values())
    q = cycle.grid()[0].copy()
    adr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "knee_right")]
    q[:, adr] = model.jnt_range[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "knee_right")][1] + 0.1
    assert retarget.limit_fraction(model, q)["knee_right"] == 1.0


def test_filter_cycle_passes_slow_content_and_removes_fast_content():
    ph = np.linspace(0, 1, 101)
    T = 1.0
    slow = np.sin(2 * np.pi * 1.0 * ph * T)          # 1 Hz
    fast = np.sin(2 * np.pi * 30.0 * ph * T)         # 30 Hz
    assert np.abs(retarget.filter_cycle(slow, T)[:, 0] - slow).max() < 0.01
    assert np.abs(retarget.filter_cycle(fast, T)[:, 0]).max() < 0.01
    out = retarget.filter_cycle(np.full(101, 3.0), T)
    assert np.allclose(out, 3.0) and out.shape == (101, 1)


# ---------- reference to the midpoint of the hip joint centres

HIP = [-0.0737, -0.0689, 0.0871]  # AB06: hip centre in the OpenSim pelvis frame (x forward, y up, half separation)


def test_hip_midpoint_of_the_model_follows_the_dataset_hip_midpoint_scaled(model, stand):
    ik = standing_ik()
    ik[:, ic.IK_CHANNELS.index("pelvis_tilt")] = 5.0  # the pelvis origin and the hip midpoint differ more when the pelvis is tilted
    ik[:, ic.IK_CHANNELS.index("pelvis_tx")] = 0.3
    ik[:, ic.IK_CHANNELS.index("pelvis_tz")] = -0.8
    c = retarget.Cycle(model, MAPPING, stand, ik, 1.0, scale=0.9, hip_in_pelvis_os=HIP)
    q = c.eval(0.3)[0]
    hm_lab = retarget.dataset_hip_mid_lab(ik, HIP)[0]
    expected = 0.9 * (np.array(MAPPING["frame"]["lab_to_model"]) @ hm_lab)
    got = retarget.model_hip_mid(model, q)
    assert got[:2] == pytest.approx(expected[:2], abs=1e-9)
    # an offset between the two origins really exists: 74 mm and 69 mm in the dataset, 57 mm and 98 mm in Freyja
    assert retarget.model_hip_offset(model) == pytest.approx([0.0566, 0.0, -0.0975], abs=2e-4)


@data_needed
def test_hip_reference_derivatives_match_finite_differences_and_integrate_back(model, stand, stride):
    c = retarget.Cycle(model, MAPPING, stand, stride["ik"], stride["T"], scale=0.9, hip_in_pelvis_os=HIP)
    eps = 1e-5
    for t in (0.1, 0.4 * c.T, 0.8):
        q, qd, qdd = c.eval(t)
        qp, qdp, _ = c.eval(t + eps)
        qm, qdm, _ = c.eval(t - eps)
        fd = np.zeros(model.nv)
        mujoco.mj_differentiatePos(model, fd, 2 * eps, qm, qp)
        assert np.abs(fd - qd).max() < 1e-5 * max(1.0, np.abs(qd).max())
        assert np.abs((qdp - qdm) / (2 * eps) - qdd).max() < 1e-4 * max(1.0, np.abs(qdd).max())
    got = integrate(model, c, 0.0, 0.5 * c.T)
    ref, _, _ = c.eval(0.5 * c.T)
    assert np.abs(got[:3] - ref[:3]).max() < 1e-9 and rot_diff_rad(got[3:7], ref[3:7]) < 1e-9


def test_counter_rotate_keeps_the_thorax_upright_while_the_pelvis_rolls_and_yaws(model, stand):
    ik = standing_ik()
    ik[:, ic.IK_CHANNELS.index("pelvis_tilt")] = 4.0 * np.sin(2 * np.pi * np.linspace(0, 1, 101))  # roll (obliquity), a few degrees
    ik[:, ic.IK_CHANNELS.index("pelvis_rotation")] = 90.0 + 5.0 * np.cos(2 * np.pi * np.linspace(0, 1, 101))
    thorax = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "thorax")

    def thorax_tilt(compensate):
        c = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, trunk="counter_rotate" if compensate else "rigid")
        worst = 0.0
        for t in np.linspace(0, 1, 20, endpoint=False):
            d = mujoco.MjData(model)
            d.qpos[:] = c.eval(t)[0]
            mujoco.mj_kinematics(model, d)
            ref = mujoco.MjData(model)
            ref.qpos[:] = stand
            mujoco.mj_kinematics(model, ref)
            r = np.zeros(3)
            q1, q2 = np.zeros(4), np.zeros(4)
            mujoco.mju_mat2Quat(q1, d.xmat[thorax]); mujoco.mju_mat2Quat(q2, ref.xmat[thorax])
            mujoco.mju_subQuat(r, q1, q2)
            worst = max(worst, abs(r[0]), abs(r[2]))  # roll and yaw of the thorax
        return worst
    assert thorax_tilt(False) > np.deg2rad(3.0)
    assert thorax_tilt(True) < np.deg2rad(0.3)


# ======================================================================== T3c.1 trunk modes

def roll_yaw_ik(roll_deg=4.0, yaw_deg=5.0, pitch_deg=2.0):
    ph = np.linspace(0, 1, 101)
    ik = standing_ik()
    ik[:, ic.IK_CHANNELS.index("pelvis_tilt")] = roll_deg * np.sin(2 * np.pi * ph)          # roll
    ik[:, ic.IK_CHANNELS.index("pelvis_rotation")] = 90.0 + yaw_deg * np.cos(2 * np.pi * ph)  # yaw about the baseline
    ik[:, ic.IK_CHANNELS.index("pelvis_list")] = -pitch_deg * np.sin(4 * np.pi * ph + 0.4)  # anterior pitch = minus list
    return ik


def world_rotvec(model, q, stand, body):
    """Rotation vector (model axes) of `body` in the world for pose q, relative to the same body in the standing pose."""
    d, ref = mujoco.MjData(model), mujoco.MjData(model)
    d.qpos[:], ref.qpos[:] = q, stand
    mujoco.mj_kinematics(model, d); mujoco.mj_kinematics(model, ref)
    b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body)
    q1, q2, r = np.zeros(4), np.zeros(4), np.zeros(3)
    mujoco.mju_mat2Quat(q1, d.xmat[b]); mujoco.mju_mat2Quat(q2, ref.xmat[b])
    mujoco.mju_subQuat(r, q1, q2)
    return r


def phase_points(c):
    return [c.eval(c.T * k / 100)[0] for k in range(100)]


@pytest.mark.parametrize("body", ["abdomen", "thorax", "head_and_neck"])
def test_counter_rotate_holds_roll_and_yaw_at_the_standing_values_and_pitch_follows_the_pelvis(model, stand, body):
    c = retarget.Cycle(model, MAPPING, stand, roll_yaw_ik(), 1.0, 1.0, trunk="counter_rotate")
    for q in phase_points(c):
        r = world_rotvec(model, q, stand, body)
        assert abs(r[0]) < 1e-9 and abs(r[2]) < 1e-9, (body, r)  # roll (x) and yaw (z) in the world: constant at the standing value
    pitch_trunk = [world_rotvec(model, q, stand, "abdomen")[1] for q in phase_points(c)]
    pitch_pelvis = [world_rotvec(model, q, stand, "pelvis")[1] for q in phase_points(c)]
    assert np.ptp(pitch_trunk) > np.deg2rad(2.0)  # it moves ...
    # ... as the pelvis's sagittal pitch does (the pelvis's own y rotation differs from the Y-Z-X pitch by second-order roll/yaw terms)
    assert np.abs(np.array(pitch_trunk) - np.array(pitch_pelvis)).max() < np.deg2rad(0.1)


def test_counter_rotate_off_the_grid_stays_within_the_spline_error(model, stand):
    c = retarget.Cycle(model, MAPPING, stand, roll_yaw_ik(), 1.0, 1.0, trunk="counter_rotate")
    worst = max(max(abs(world_rotvec(model, c.eval(t)[0], stand, "thorax")[[0, 2]])) for t in np.linspace(0.003, 0.997, 57))
    assert worst < np.deg2rad(0.02)  # between phase points the cancellation is a cubic spline of exact values


def test_counter_rotate_is_zero_when_the_pelvis_does_not_roll_or_yaw(model, stand):
    ik = roll_yaw_ik(roll_deg=0.0, yaw_deg=0.0, pitch_deg=3.0)
    c = retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, trunk="counter_rotate")
    lat = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "lsj_lat")]
    ax = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "lsj_ax")]
    for q in phase_points(c):
        assert abs(q[lat]) < 1e-12 and abs(q[ax]) < 1e-12
    standing = retarget.Cycle(model, MAPPING, stand, standing_ik(), 1.0, 1.0, trunk="counter_rotate").eval(0.3)
    assert np.abs(standing[1]).max() < 1e-9 and np.abs(standing[0][7:] - retarget.Cycle(model, MAPPING, stand, standing_ik(), 1.0, 1.0).eval(0.3)[0][7:]).max() < 1e-12


def test_counter_rotate_qvel_integrates_back_to_qpos(model, stand):
    c = retarget.Cycle(model, MAPPING, stand, roll_yaw_ik(), 1.0, 1.0, trunk="counter_rotate")
    for t1 in (0.3, 1.0):
        got = integrate(model, c, 0.0, t1)
        ref, _, _ = c.eval(t1)
        assert np.abs(got[:3] - ref[:3]).max() < 1e-9 and rot_diff_rad(got[3:7], ref[3:7]) < 1e-9
        assert np.abs(got[7:] - ref[7:]).max() < 1e-9  # includes lsj_lat and lsj_ax


def test_mutation_flipping_the_compensation_sign_breaks_world_constancy(model, stand, monkeypatch):
    orig = retarget.Cycle._counter_rotation
    monkeypatch.setattr(retarget.Cycle, "_counter_rotation", lambda self, Xf: -orig(self, Xf))
    c = retarget.Cycle(model, MAPPING, stand, roll_yaw_ik(), 1.0, 1.0, trunk="counter_rotate")
    worst = max(max(abs(world_rotvec(model, q, stand, "thorax")[[0, 2]])) for q in phase_points(c))
    assert worst > np.deg2rad(1.0)


@data_needed
def test_rigid_trunk_output_is_unchanged_from_before_the_trunk_modes(model, stand):
    import hashlib
    z = np.load(PROCESSED)
    c = retarget.Cycle(model, MAPPING, stand, z["1.4_ik"][3], float(z["1.4_duration_s"][3]), 0.92, hip_in_pelvis_os=HIP)
    g = np.concatenate([a.ravel() for a in c.grid()])
    assert hashlib.sha256((np.round(g, 9) + 0.0).tobytes()).hexdigest()[:16] == "6b81fb135022033b"  # recorded at cf658f5, before T3c.1
    same = retarget.Cycle(model, MAPPING, stand, z["1.4_ik"][3], float(z["1.4_duration_s"][3]), 0.92, hip_in_pelvis_os=HIP, trunk="rigid")
    assert all(np.array_equal(a, b) for a, b in zip(c.grid(), same.grid()))
