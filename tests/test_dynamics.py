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
