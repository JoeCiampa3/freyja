"""
Stage 2g T1: the dataset-to-model pelvis frame offset (decisions/0004-hip-stop-pelvis-pose.md, point 2).

The model's pelvis frame is the Dumas frame; the dataset's IK pelvis sits delta degrees posterior of it (delta = the subject's static Dumas
tilt minus its static IK pitch). With `pelvis_frame_offset_deg = delta` the retargeting turns the pelvis body forward by delta about its own
lateral axis, adds delta to the hip flexion and extends the lumbosacral joint by delta, so that, in the world, the thighs, the hip centres,
the shanks, the feet and the trunk are where they were and only the pelvis body (and with it the lumbosacral joint's position) moves.

Run from the repo root:
    python -m pytest tests/test_retarget_frame_offset.py
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

import leanpose  # noqa: E402
import retarget  # noqa: E402

MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
MANIFEST = REPO / "data" / "camargo2021" / "manifest.json"
PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
data_needed = pytest.mark.skipif(not (PROCESSED.exists() and MANIFEST.exists()), reason="processed Camargo arrays not present")
TOL = 1e-9  # exact geometry: the offset is a rotation about one axis, so the only error is round-off
DELTA_DEG = 13.57  # the dataset's mean (memo 23, D2)


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


@pytest.fixture(scope="module")
def stand(model):
    return leanpose.solve_lean(model, 0.0, FEET).qpos


@pytest.fixture(scope="module")
def stride():
    import json
    z = np.load(PROCESSED)
    hip = json.loads(MANIFEST.read_text())["subjects"]["AB06"]["hip_in_pelvis_os_m"]
    return {"ik": z["1.4_ik"][3], "T": float(z["1.4_duration_s"][3]), "hip": hip}


def cycle(model, stand, stride, delta, trunk="rigid"):
    return retarget.Cycle(model, MAPPING, stand, stride["ik"], stride["T"], scale=0.9, hip_in_pelvis_os=stride["hip"], trunk=trunk,
                          pelvis_frame_offset_deg=delta)


def poses(model, c):
    """Per phase point: {body: (xpos, xmat)}."""
    q, _, _ = c.grid()
    d = mujoco.MjData(model)
    out = []
    for k in range(q.shape[0]):
        d.qpos[:] = q[k]
        mujoco.mj_kinematics(model, d)
        out.append({mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, b): (d.xpos[b].copy(), d.xmat[b].reshape(3, 3).copy()) for b in range(1, model.nbody)})
    return out


LEG = ("thigh_right", "thigh_left", "shank_right", "shank_left", "foot_right", "foot_left")
UPPER = ("abdomen", "thorax", "head_and_neck", "upper_arm_right", "upper_arm_left", "forearm_right", "forearm_left", "hand_right", "hand_left")


@data_needed
@pytest.mark.parametrize("trunk", ["rigid", "counter_rotate"])
def test_the_legs_do_not_move_and_the_upper_body_keeps_its_orientation_and_is_displaced_as_one(model, stand, stride, trunk):
    """Only the pelvis body turns. Every body above it keeps its orientation and moves by one common vector (the lumbosacral joint's displacement)."""
    base, off = poses(model, cycle(model, stand, stride, 0.0, trunk)), poses(model, cycle(model, stand, stride, DELTA_DEG, trunk))
    for pa, pb in zip(base, off):
        for name in LEG:
            assert np.abs(pa[name][1] - pb[name][1]).max() < TOL and np.abs(pa[name][0] - pb[name][0]).max() < TOL, name
        shift = pb["abdomen"][0] - pa["abdomen"][0]
        for name in UPPER:
            assert np.abs(pa[name][1] - pb[name][1]).max() < TOL, name
            assert np.abs((pb[name][0] - pa[name][0]) - shift).max() < TOL, name
        assert np.abs(pa["pelvis"][1] - pb["pelvis"][1]).max() > 0.1  # the pelvis did turn (13.57 degrees)


@data_needed
def test_each_thigh_keeps_its_world_orientation_and_the_hip_centre_its_position(model, stand, stride):
    base, off = poses(model, cycle(model, stand, stride, 0.0)), poses(model, cycle(model, stand, stride, DELTA_DEG))
    for pa, pb in zip(base, off):
        for side in ("right", "left"):
            xa, ra = pa[f"thigh_{side}"]
            xb, rb = pb[f"thigh_{side}"]
            assert np.abs(ra - rb).max() < TOL and np.abs(xa - xb).max() < TOL


@data_needed
def test_the_pelvis_body_turns_by_delta_about_its_lateral_axis(model, stand, stride):
    base, off = poses(model, cycle(model, stand, stride, 0.0)), poses(model, cycle(model, stand, stride, DELTA_DEG))
    want = np.radians(DELTA_DEG)
    for pa, pb in zip(base, off):
        rel = pa["pelvis"][1].T @ pb["pelvis"][1]  # the pelvis body's own frame, before to after
        angle = np.arccos(np.clip((np.trace(rel) - 1) / 2, -1, 1))
        axis = np.array([rel[2, 1] - rel[1, 2], rel[0, 2] - rel[2, 0], rel[1, 0] - rel[0, 1]])
        assert angle == pytest.approx(want, abs=1e-9)
        assert abs(axis[1] / np.linalg.norm(axis)) == pytest.approx(1.0, abs=1e-9)  # about y of the model's pelvis frame


@data_needed
def test_the_lumbosacral_joint_moves_with_the_pelvis_and_the_trunk_does_not(model, stand, stride):
    """The lumbosacral joint's position follows the pelvis body (it rotates forward about the hips), the abdomen and thorax keep their orientation."""
    base, off = poses(model, cycle(model, stand, stride, 0.0)), poses(model, cycle(model, stand, stride, DELTA_DEG))
    for pa, pb in zip(base, off):
        assert np.abs(pa["abdomen"][1] - pb["abdomen"][1]).max() < TOL
        assert np.abs(pa["thorax"][1] - pb["thorax"][1]).max() < TOL
        assert np.abs(pa["abdomen"][0] - pb["abdomen"][0]).max() > 1e-3  # the trunk base moved (millimetres): that is the point of the correction


@data_needed
def test_the_hip_flexion_rises_by_delta_and_the_lumbosacral_flexion_falls_by_it(model, stand, stride):
    qa, _, _ = cycle(model, stand, stride, 0.0).grid()
    qb, _, _ = cycle(model, stand, stride, DELTA_DEG).grid()
    adr = lambda n: int(model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)])  # noqa: E731
    sgn = lambda n: leanpose.flexion_sign(model, n)  # noqa: E731
    for hip in ("hip_fe_right", "hip_fe_left"):
        assert np.allclose(sgn(hip) * (qb[:, adr(hip)] - qa[:, adr(hip)]), np.radians(DELTA_DEG), atol=1e-12)
    assert np.allclose(sgn("lsj_fe") * (qb[:, adr("lsj_fe")] - qa[:, adr("lsj_fe")]), -np.radians(DELTA_DEG), atol=1e-12)
    for other in ("knee_right", "ankle_pdflex_right", "hip_aa_right", "hip_ier_right", "lsj_lat", "lsj_ax", "tj_fe", "cj_fe"):
        assert np.allclose(qa[:, adr(other)], qb[:, adr(other)], atol=1e-12), other


@data_needed
def test_counter_rotation_rows_are_unchanged_by_the_offset(model, stand, stride):
    """The lumbosacral lateral and axial angles come from the pelvis roll and yaw; the offset is a pitch about the lateral axis and leaves them alone."""
    qa, _, _ = cycle(model, stand, stride, 0.0, "counter_rotate").grid()
    qb, _, _ = cycle(model, stand, stride, DELTA_DEG, "counter_rotate").grid()
    for n in ("lsj_lat", "lsj_ax"):
        a = int(model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)])
        assert np.allclose(qa[:, a], qb[:, a], atol=1e-9)


@data_needed
def test_velocity_and_acceleration_stay_the_derivatives_of_the_pose(model, stand, stride):
    """The finite-difference check of tests/test_retarget.py, with the offset on (the root's angular velocity and acceleration are rotated with it)."""
    c = cycle(model, stand, stride, DELTA_DEG)
    eps = 1e-5
    for t in (0.05, 0.31, 0.62 * c.T, 0.93):
        _, qd, qdd = c.eval(t)
        qp, qdp, _ = c.eval(t + eps)
        qm, qdm, _ = c.eval(t - eps)
        fd = np.zeros(model.nv)
        mujoco.mj_differentiatePos(model, fd, 2 * eps, qm, qp)
        assert np.abs(fd - qd).max() < 1e-5 * max(1.0, np.abs(qd).max()), t
        assert np.abs((qdp - qdm) / (2 * eps) - qdd).max() < 1e-4 * max(1.0, np.abs(qdd).max()), t


@data_needed
def test_zero_offset_is_the_old_behaviour_exactly(model, stand, stride):
    """The default keeps the cycle as it was: not passing the option and passing zero give the same pose, velocity and acceleration."""
    plain = retarget.Cycle(model, MAPPING, stand, stride["ik"], stride["T"], scale=0.9, hip_in_pelvis_os=stride["hip"])
    zero = cycle(model, stand, stride, 0.0)
    for a, b in zip(plain.grid(), zero.grid()):
        assert np.array_equal(a, b)
    adr = int(model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "lsj_fe")])
    assert np.all(plain.grid()[0][:, adr] == stand[adr])  # held at the standing pose, as the mapping says


def test_a_non_numeric_offset_is_refused(model, stand):
    ik = np.zeros((101, 18))
    for bad in ("measured", None, float("nan")):
        with pytest.raises(ValueError):
            retarget.Cycle(model, MAPPING, stand, ik, 1.0, 1.0, pelvis_frame_offset_deg=bad)
