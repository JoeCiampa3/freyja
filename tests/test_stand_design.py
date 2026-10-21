"""
Stage 2g T4: the standing posture as a sheet input (`stand_pelvis_tilt_deg`, decisions/0004). The pelvis is tilted forward by it, the hips flexed by it so the
thighs hang plumb, the lumbosacral joint extended by it so the trunk stack is plumb, and leanpose then sets the ankle for flat soles and the centre of mass over the ankle.
The model is the fixture of tests/foot_help.py.

Run from the repo root:
    python -m pytest tests/test_stand_design.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import foot_help as fh  # noqa: E402
import gait  # noqa: E402
import leanpose  # noqa: E402

FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
TILT = fh.SPEC_DESIGN["stand_pelvis_tilt_deg"]
VERTICAL_TOL_DEG = 0.05  # the brief: trunk and thighs vertical within this
FLAT_TOL = 1e-9  # the foot's x axis has no vertical component
COM_TOL_M = 1e-9


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))


def world(model, q):
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_forward(model, d)
    return d


def lean_deg(d, model, body):
    """Forward lean of a body's up axis from the vertical, degrees (a plumb thigh or trunk is 0)."""
    up = d.xmat[model.body(body).id].reshape(3, 3)[:, 2]
    return np.degrees(np.arctan2(up[0], up[2]))


def test_the_upright_design_stance_has_plumb_thighs_and_trunk_and_a_pelvis_tilted_by_the_sheet_value(model):
    lean = leanpose.design_stance(model, TILT, FEET, upright=True)
    d = world(model, lean.qpos)
    for body in ("thigh_right", "thigh_left", "abdomen", "thorax", "head_and_neck"):
        assert abs(lean_deg(d, model, body)) < VERTICAL_TOL_DEG, body
    assert lean_deg(d, model, "pelvis") == pytest.approx(TILT, abs=1e-6)  # the pelvis is tilted forward by the design tilt
    assert lean.lean_rad == 0.0
    hips = [lean.qpos[model.jnt_qposadr[model.joint(n).id]] for n in ("hip_fe_right", "hip_fe_left")]
    assert np.degrees(hips) == pytest.approx([TILT, TILT], abs=1e-6)  # flexed by the tilt (the model's flexion is positive)
    assert np.degrees(lean.qpos[model.jnt_qposadr[model.joint("lsj_fe").id]]) == pytest.approx(-TILT, abs=1e-6)  # extended by it


def test_the_leaned_design_stance_has_flat_soles_and_the_centre_of_mass_over_the_ankle_and_a_trunk_aligned_with_the_thighs(model):
    lean = leanpose.design_stance(model, TILT, FEET, com_x_rel_ankle_m=0.0)
    d = world(model, lean.qpos)
    for foot in FEET:
        assert abs(d.xmat[model.body(foot).id].reshape(3, 3)[2, 0]) < FLAT_TOL  # sole flat
    assert abs(d.subtree_com[0][0] - d.xpos[model.body("foot_right").id][0]) < COM_TOL_M
    # the whole stack leans rigidly about the ankle by the solved angle: thighs and trunk are parallel, and plumb to within that lean
    thigh, trunk = lean_deg(d, model, "thigh_right"), lean_deg(d, model, "thorax")
    assert abs(thigh - trunk) < VERTICAL_TOL_DEG
    assert abs(thigh) == pytest.approx(abs(np.degrees(lean.lean_rad)), abs=VERTICAL_TOL_DEG)


def test_mutation_without_the_lumbosacral_extension_the_trunk_leans_forward_by_the_tilt(model):
    offsets = leanpose.pose_offsets(model, {"pelvic_tilt_deg": TILT})  # hips flexed, the lumbosacral joint left at zero
    lean = leanpose.solve_lean(model, None, FEET, offsets, ankle_rad=0.0)
    d = world(model, lean.qpos)
    assert lean_deg(d, model, "thorax") == pytest.approx(TILT, abs=1e-6) and abs(lean_deg(d, model, "thigh_right")) < VERTICAL_TOL_DEG


def test_a_tilt_beyond_a_joint_range_is_an_error_not_a_clipped_pose(model):
    with pytest.raises(leanpose.LeanError):
        leanpose.design_stance(model, 150.0, FEET, upright=True)  # past the hip flexion limit (133.8 degrees in the sheet)


def test_the_gait_context_stands_in_the_design_stance_and_in_the_old_one_without_a_tilt(model):
    path = fh.fixture_model_path()
    c = gait.Context(path, stand_tilt_deg=TILT)
    assert np.allclose(c.stand, leanpose.design_stance(c.model, TILT, gait.STANDING_FEET).qpos, atol=1e-12)
    old = gait.Context(path, stand_tilt_deg=0.0)
    assert np.allclose(old.stand, leanpose.solve_lean(old.model, 0.0, gait.STANDING_FEET).qpos, atol=1e-12)
    assert not np.allclose(c.stand, old.stand)


def test_without_the_key_in_the_snapshot_the_context_keeps_the_old_standing_pose(tmp_path):
    """A snapshot without stand_pelvis_tilt_deg (before Stage 2g) gives the old pose: a rigid lean about the ankle, every other joint at zero. The lean is read from the
    model (it was 2.608 degrees on the Stage 2 model)."""
    snap = tmp_path / "snapshot.csv"
    snap.write_text("placeholder,value,sheet_source\ntarget_mass,60,x\n", encoding="utf-8", newline="\n")
    assert gait.snapshot_stand_tilt_deg(snap) == 0.0 and gait.snapshot_stand_tilt_deg(tmp_path / "absent.csv") == 0.0
    c = gait.Context(REPO / "sim" / "models" / "freyja.xml", stand_tilt_deg=gait.snapshot_stand_tilt_deg(snap))
    lean = leanpose.solve_lean(c.model, 0.0, gait.STANDING_FEET)
    assert np.allclose(c.stand, lean.qpos, atol=1e-12)
    assert 0.0 < np.degrees(lean.lean_rad) < 10.0
    assert np.abs(c.stand[7:]).max() < 1e-12 + np.abs(lean.qpos[7:]).max()  # only the ankle moves: the other hinges are zero
    assert np.count_nonzero(np.abs(c.stand[7:]) > 1e-12) == 2  # the two ankles
