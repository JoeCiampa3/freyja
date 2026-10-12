"""
Stage 2 T9.2: the trunk-group centre-of-mass offset and the in-memory shifted copy. Synthetic osim files with known answers, and the real model.

Run from the repo root:
    python -m pytest tests/test_trunkcom.py
"""
import io
import sys
import zipfile
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import datasetmass  # noqa: E402
import trunkcom  # noqa: E402

MODEL = REPO / "sim" / "models" / "freyja.xml"


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(MODEL))


OSIM = """<OpenSimDocument><Model><BodySet><objects>
<Body name="pelvis"><mass>10</mass><mass_center>-0.07 0 0</mass_center></Body>
<Body name="torso"><mass>30</mass><mass_center>-0.03 0.35 0</mass_center></Body>
<Body name="femur_r"><mass>10</mass><mass_center>0 -0.2 0</mass_center></Body>
</objects></BodySet><JointSet><objects>
<CustomJoint name="hip_r"><frames><PhysicalOffsetFrame name="pelvis_offset"><socket_parent>/bodyset/pelvis</socket_parent><translation>-0.07 -0.06 0.08</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame></frames></CustomJoint>
<CustomJoint name="hip_l"><frames><PhysicalOffsetFrame name="pelvis_offset"><socket_parent>/bodyset/pelvis</socket_parent><translation>-0.07 -0.06 -0.08</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame></frames></CustomJoint>
<CustomJoint name="back"><frames>
<PhysicalOffsetFrame name="pelvis_offset"><socket_parent>/bodyset/pelvis</socket_parent><translation>-0.10 0.08 0</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
<PhysicalOffsetFrame name="torso_offset"><socket_parent>/bodyset/torso</socket_parent><translation>{torso_t}</translation><orientation>{torso_o}</orientation></PhysicalOffsetFrame>
</frames></CustomJoint></objects></JointSet></Model></OpenSimDocument>"""


def osim_zip(torso_t="0 0 0", torso_o="0 0 0"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("osimxml/AB99.osim", OSIM.format(torso_t=torso_t, torso_o=torso_o))
    return zipfile.ZipFile(io.BytesIO(buf.getvalue()))


def test_the_torso_offset_is_the_back_joint_plus_the_mass_centre_minus_the_hip_midpoint():
    r = trunkcom.read_torso_offset(osim_zip(), "AB99")
    # torso COM in the pelvis frame: (-0.10 - 0.03, 0.08 + 0.35) = (-0.13, 0.43); hip midpoint (-0.07, -0.06)
    assert r["offset_xy"] == pytest.approx([-0.06, 0.49], abs=1e-12)
    assert r["mass_fraction"] == pytest.approx(30.0 / 50.0)


def test_a_torso_origin_that_is_not_at_the_joint_moves_the_centre_of_mass_with_it():
    r = trunkcom.read_torso_offset(osim_zip(torso_t="0.01 -0.02 0"), "AB99")  # the joint sits (0.01, -0.02) from the torso origin: the origin is at joint minus that
    assert r["offset_xy"] == pytest.approx([-0.06 - 0.01, 0.49 + 0.02], abs=1e-12)


def test_a_rotated_back_frame_is_refused_rather_than_silently_mishandled():
    with pytest.raises(ValueError):
        trunkcom.read_torso_offset(osim_zip(torso_o="0 0 0.1"), "AB99")


def test_the_trunk_offset_of_freyja_is_behind_and_above_the_hip_midpoint(model):
    off = trunkcom.trunk_offset(model)
    assert off[2] > 0.2  # well above the hips
    assert -0.12 < off[0] < 0.0  # behind them: the ramrod stack (memo3 puts the upper body about 50 mm behind the hip centres)


def test_the_shift_moves_the_group_centre_of_mass_by_exactly_the_requested_amount_and_nothing_else(model):
    delta = np.array([0.031, 0.0, -0.012])
    shifted = trunkcom.with_trunk_com_shift(model, delta)
    assert trunkcom.trunk_offset(shifted) - trunkcom.trunk_offset(model) == pytest.approx(delta, abs=1e-12)
    assert shifted.body_mass.sum() == model.body_mass.sum()
    assert np.array_equal(shifted.body_mass, model.body_mass) and np.array_equal(shifted.body_inertia, model.body_inertia)
    group = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in datasetmass.TRUNK_GROUP}
    for b in range(model.nbody):
        same = np.array_equal(shifted.body_ipos[b], model.body_ipos[b])
        assert same == (b not in group), b  # only the group's bodies move


def test_the_input_model_is_not_touched_and_no_file_is_written(model):
    before = model.body_ipos.copy()
    xml = MODEL.read_bytes()
    trunkcom.with_trunk_com_shift(model, np.array([0.05, 0.0, 0.0]))
    assert np.array_equal(model.body_ipos, before) and MODEL.read_bytes() == xml


def test_shift_to_puts_the_group_at_the_target_offset(model):
    shifted, delta = trunkcom.shift_to(model, (-0.067, 0.50))
    off = trunkcom.trunk_offset(shifted)
    assert off[0] == pytest.approx(-0.067, abs=1e-12) and off[2] == pytest.approx(0.50, abs=1e-12)
    assert off[1] == pytest.approx(trunkcom.trunk_offset(model)[1], abs=1e-12)  # the lateral offset is left alone
    assert delta[1] == 0.0


def test_a_shifted_copy_changes_the_whole_body_com_by_the_group_mass_fraction(model):
    shifted = trunkcom.with_trunk_com_shift(model, np.array([0.04, 0.0, 0.0]))
    ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n) for n in datasetmass.TRUNK_GROUP]
    frac = model.body_mass[ids].sum() / model.body_mass.sum()
    com = lambda m: (lambda d: (m.body_mass[:, None] * d.xipos).sum(axis=0) / m.body_mass.sum())(trunkcom._neutral(m))
    assert (com(shifted) - com(model))[0] == pytest.approx(0.04 * frac, rel=1e-9)  # mutation guard: a shift of the wrong bodies would give another fraction
