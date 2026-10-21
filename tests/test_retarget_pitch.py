"""
Stage 2c T2: with pitch_mean 'measured' the model's pelvis pitch is the dataset's (anterior pitch = minus pelvis_list) plus
pelvis_pitch_offset_deg, with no standing lean added. memo9 found the root orientation was R_stand @ (the dataset's pelvis
rotation), 2.608 degrees of extra forward lean, which put the legs 2.4 to 2.8 degrees behind the dataset's.

Requirements (docs/briefs/stage2c-brief.md, Decisions): (a) the model's world thigh and shank pitch equal the dataset's (hip angle
plus pelvis_list, planar); (b) the hip midpoint's horizontal path is unchanged by the fix; (c) joint angles are unchanged;
(d) a numeric pitch_mean keeps its meaning (relative to the standing pose's orientation).

Run from the repo root:
    python -m pytest tests/test_retarget_pitch.py
"""
import json
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml
from scipy.spatial.transform import Rotation

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import ingest_camargo as ic  # noqa: E402
import leanpose  # noqa: E402
import retarget  # noqa: E402

MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
MANIFEST = REPO / "data" / "camargo2021" / "manifest.json"
PROCESSED = REPO / "data" / "camargo2021" / "processed"
data_needed = pytest.mark.skipif(not (MANIFEST.exists() and (PROCESSED / "AB06.npz").exists()), reason="processed Camargo arrays not present")

# Requirement (a), real strides: the signed difference between the model's world segment pitch and the dataset's, averaged over the
# cycle and over the subject-strides, in degrees. 0.5 degrees is 7 mm at the ankle of a 0.8 m leg, against the 36 mm (2.608 degrees)
# that the old composition added, so the fix must remove at least four fifths of it. That number was chosen from the lever argument
# before any measurement. The first metric written was the mean absolute difference per stride; it failed on the 3D terms (hip
# ab/adduction and rotation, pelvis roll and yaw, a 2 degree oscillation within the stride that a planar oracle cannot follow and
# that the pitch does not touch), so the test uses the mean, which is the quantity a constant pitch offset moves (memo10 says so).
# The synthetic test below is exact (1e-9) and is the guard against the composition.
SEGMENT_PITCH_TOL_DEG = 0.5
N_STRIDES_PER_SUBJECT = 3  # the first three strides of each subject at 1.4 m/s: 51 strides, 100 phase points each


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


@pytest.fixture(scope="module")
def stand(model):
    return leanpose.solve_lean(model, 0.0, FEET).qpos


def _joint_anchor(model, data, name):
    return data.xanchor[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]


def segment_pitch_deg(model, q, side="right"):
    """World thigh and shank pitch in the sagittal plane: the angle of the hip-to-knee and knee-to-ankle vectors from straight down,
    forward (model +x) positive, in degrees."""
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    hip, knee, ankle = (_joint_anchor(model, d, n) for n in (f"hip_fe_{side}", f"knee_{side}", f"ankle_pdflex_{side}"))
    ang = lambda v: np.degrees(np.arctan2(v[0], -v[2]))
    return ang(knee - hip), ang(ankle - knee)


@pytest.fixture(scope="module")
def neutral(model):
    """The model's own thigh and shank angle with an upright root and every joint at zero (its geometry, not the retargeting's)."""
    q = np.zeros(model.nq)
    q[3] = 1.0
    return segment_pitch_deg(model, q)


def synthetic_ik(hip_flexion=0.0, knee_angle=0.0, pelvis_list=0.0):
    ik = np.zeros((101, len(ic.IK_CHANNELS)))
    col = ic.IK_CHANNELS.index
    ik[:, col("pelvis_rotation")] = 90.0  # the lab frame's baseline
    ik[:, col("pelvis_ty")] = 0.97
    ik[:, col("pelvis_list")] = pelvis_list
    ik[:, col("hip_flexion_r")] = hip_flexion
    ik[:, col("knee_angle_r")] = knee_angle
    return ik


@pytest.mark.parametrize("hip,knee,lst", [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 0.0, -8.0), (-12.0, -30.0, 5.0), (0.0, 0.0, 7.5)])
def test_world_thigh_and_shank_pitch_are_the_datasets_for_synthetic_ik(model, stand, neutral, hip, knee, lst):
    q = retarget.Cycle(model, MAPPING, stand, synthetic_ik(hip, knee, lst), 1.0, 1.0).eval(0.3)[0]
    thigh, shank = segment_pitch_deg(model, q)
    # forward thigh angle = hip flexion + pelvis_list (anterior pitch is minus list); the shank swings back by the knee flexion,
    # which the dataset gives as knee_angle (negative flexion)
    assert thigh == pytest.approx(neutral[0] + hip + lst, abs=1e-9)
    assert shank == pytest.approx(neutral[1] + hip + lst + knee, abs=1e-9)


def test_standing_pelvis_is_upright_not_leaning_for_a_measured_pitch(model, stand):
    q = retarget.Cycle(model, MAPPING, stand, synthetic_ik(), 1.0, 1.0).eval(0.3)[0]
    assert np.abs(q[3:7] - np.array([1.0, 0, 0, 0])).max() < 1e-9  # the dataset's baseline, with no 2.608 degrees added
    lean_deg = Rotation.from_quat(np.r_[stand[4:7], stand[3]]).as_euler("YZX", degrees=True)[0]
    assert lean_deg > 1.0  # the stand fixture's own lean is what the old code added (2.608 degrees on the Stage 2 model, read from the model since Stage 2g)


def test_measured_pitch_offset_is_added_to_the_datasets_pitch_in_the_anterior_direction(model, stand):
    for off in (-5.0, 3.0):
        q = retarget.Cycle(model, MAPPING, stand, synthetic_ik(pelvis_list=-6.0), 1.0, 1.0, pitch_offset_deg=off).eval(0.3)[0]
        pitch = Rotation.from_quat(np.r_[q[4:7], q[3]]).as_euler("YZX", degrees=True)[0]
        assert pitch == pytest.approx(6.0 + off, abs=1e-9)  # anterior pitch = minus pelvis_list, plus the offset


def test_a_numeric_pitch_mean_is_still_relative_to_the_standing_pose(model, stand):
    q = retarget.Cycle(model, MAPPING, stand, synthetic_ik(pelvis_list=-9.0), 1.0, 1.0, pitch_mean=0.0).eval(0.3)[0]
    r = np.zeros(3)
    mujoco.mju_subQuat(r, q[3:7], stand[3:7])
    assert np.linalg.norm(r) < 1e-9
    q4 = retarget.Cycle(model, MAPPING, stand, synthetic_ik(pelvis_list=-9.0), 1.0, 1.0, pitch_mean=4.0).eval(0.3)[0]
    mujoco.mju_subQuat(r, q4[3:7], stand[3:7])
    assert np.linalg.norm(r) == pytest.approx(np.deg2rad(4.0), abs=1e-9)


def _cycle_pair(model, stand):
    ik = synthetic_ik(hip_flexion=15.0, pelvis_list=-6.0)
    ik[:, ic.IK_CHANNELS.index("pelvis_tx")] = np.linspace(0, 0.1, 101)
    ik[:, ic.IK_CHANNELS.index("pelvis_tz")] = np.linspace(0, -1.2, 101)
    hip = np.array([-0.06, -0.07, 0.0])
    mk = lambda **kw: retarget.Cycle(model, MAPPING, stand, ik, 1.0, 0.95, hip_in_pelvis_os=hip, root_ref="hip_midpoint", **kw)
    return mk(), mk(pitch_offset_deg=float(Rotation.from_quat(np.r_[stand[4:7], stand[3]]).as_euler("YZX", degrees=True)[0]))


def test_the_hip_midpoint_horizontal_path_is_the_datasets_whatever_the_pitch(model, stand):
    a, b = _cycle_pair(model, stand)
    nj = a._nj
    for t in np.linspace(0.0, 1.0, 11):
        xy = a._spl(t)[nj + 3:nj + 5]  # the filtered dataset hip midpoint, scaled (the root reference)
        for c in (a, b):
            assert np.abs(retarget.model_hip_mid(model, c.eval(t)[0])[:2] - xy).max() < 1e-9
    # and the body does rotate about that point: the two cycles' roots differ, their hip midpoints do not
    assert np.abs(a.eval(0.4)[0][:3] - b.eval(0.4)[0][:3]).max() > 1e-3


def test_joint_angles_and_velocities_are_the_datasets_not_the_roots(model, stand):
    a, b = _cycle_pair(model, stand)
    qa, qda, qdda = a.eval(0.37)
    qb, qdb, qddb = b.eval(0.37)
    assert np.abs(qa[7:] - qb[7:]).max() < 1e-12 and np.abs(qda[6:] - qdb[6:]).max() < 1e-12 and np.abs(qdda[6:] - qddb[6:]).max() < 1e-12
    v = a._spl(0.37)
    for i, adr in enumerate(a.joint_adr):
        assert qa[adr] == pytest.approx(v[i], abs=1e-12)
    assert np.abs(qda[3:6] - qdb[3:6]).max() < 1e-12  # the body-frame angular velocity does not depend on a world rotation of the pelvis


@data_needed
def test_world_thigh_and_shank_pitch_follow_the_datasets_over_the_17_subjects(model, stand, neutral):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = list(ic.IK_CHANNELS)
    signed = {"thigh": [], "shank": []}
    n = 0
    for s, d in manifest["subjects"].items():
        z = np.load(PROCESSED / f"{s}.npz")
        ratio = retarget.leg_length_ratio(model, d["height_m"])
        for i in range(min(N_STRIDES_PER_SUBJECT, d["strides"]["1.4"])):
            ik = z["1.4_ik"][i]
            cyc = retarget.Cycle(model, MAPPING, stand, ik, float(z["1.4_duration_s"][i]), ratio, hip_in_pelvis_os=d["hip_in_pelvis_os_m"])
            hip, knee, lst = (ik[:, names.index(c)] for c in ("hip_flexion_r", "knee_angle_r", "pelvis_list"))
            diff = {"thigh": [], "shank": []}
            for k in range(0, 100, 5):
                thigh, shank = segment_pitch_deg(model, cyc.eval(cyc.T * k / 100)[0])
                diff["thigh"].append(thigh - (neutral[0] + hip[k] + lst[k]))
                diff["shank"].append(shank - (neutral[1] + hip[k] + lst[k] + knee[k]))
            for seg in diff:
                signed[seg].append(float(np.mean(diff[seg])))
            n += 1
    assert n >= 17
    mean = {seg: float(np.mean(v)) for seg, v in signed.items()}
    assert abs(mean["thigh"]) < SEGMENT_PITCH_TOL_DEG and abs(mean["shank"]) < SEGMENT_PITCH_TOL_DEG, mean
