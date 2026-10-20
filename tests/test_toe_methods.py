"""
Stage 2g T3: the toe in the loads. Method A holds it flat (welded): the ankle then carries the moment of the rigid whole foot. Methods B and H let it roll: its
angle follows the foot's pitch while the foot is on the ground, the contact polygon includes the toe box at that angle, and the ground force acts on the toe when it is
ahead of the hinge. The model is the fixture of tests/foot_help.py (committed snapshot plus the sheet spec's design range); the tracked model has no toe.

Run from the repo root:
    python -m pytest tests/test_toe_methods.py
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import dynamics  # noqa: E402
import foot_help as fh  # noqa: E402
import gait  # noqa: E402
import leanpose  # noqa: E402
import pre_processor as pp  # noqa: E402
import retarget  # noqa: E402

MAPPING = yaml.safe_load((REPO / "sim" / "scenarios" / "gait" / "camargo_mapping.yaml").read_text())
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}
PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"
MANIFEST = REPO / "data" / "camargo2021" / "manifest.json"
data_needed = pytest.mark.skipif(not (PROCESSED.exists() and MANIFEST.exists()), reason="processed Camargo arrays not present")
MARGIN = 5  # phase points: see test_the_rolling_toe_lies_flat_on_the_floor_while_the_foot_is_in_stance
WELDED_TOL_NM = 1e-6  # the brief: the welded toe's ankle moment equals the rigid whole-foot moment to this


@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))


@pytest.fixture(scope="module")
def stand(model):
    return leanpose.solve_lean(model, 0.0, FEET).qpos


@pytest.fixture(scope="module")
def stride():
    z = np.load(PROCESSED)
    info = json.loads(MANIFEST.read_text())["subjects"]["AB06"]
    m = mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))
    return {"ik": z["1.4_ik"][3], "T": float(z["1.4_duration_s"][3]), "hip": info["hip_in_pelvis_os_m"], "ratio": retarget.leg_length_ratio(m, info["height_m"]),
            "stance": z["1.4_fp"][3][:, :, 6] >= 0.5}


def cycle(model, stand, stride, toe):
    return retarget.Cycle(model, MAPPING, stand, stride["ik"], stride["T"], scale=stride["ratio"], hip_in_pelvis_os=stride["hip"], toe=toe, stance=stride["stance"])


def rigid_foot_model(tmp_path):
    """The fixture model with each toe body removed and the whole-foot row of the sheet put on the foot body: the rigid foot the dataset has."""
    root = ET.fromstring(fh.fixture_model_path().read_text(encoding="utf-8"))
    t = fh.tables()
    names = [pp.column_key(h) for h in t["bsip"].rows[0]]
    row = next(r for r in t["bsip"].rows[1:] if pp.ident(r[0]) == "foot")
    get = lambda col: float(row[names.index(col)])  # noqa: E731
    for foot in root.iter("body"):
        if foot.get("name") in ("foot_right", "foot_left"):
            sign = 1.0 if foot.get("name").endswith("right") else -1.0
            for toe in [b for b in foot.findall("body") if b.get("name", "").startswith("toe_")]:
                foot.remove(toe)
            inertial = foot.find("inertial")
            inertial.set("mass", f"{get('mass'):.12g}")
            inertial.set("pos", f"{get('com_x'):.12g} {sign * get('com_y'):.12g} {get('com_z'):.12g}")
            inertial.set("fullinertia", f"{get('ixx'):.12g} {get('iyy'):.12g} {get('izz'):.12g} {get('ixy') * sign:.12g} {get('ixz'):.12g} {get('iyz') * sign:.12g}")
    path = tmp_path / "rigid.xml"
    path.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
    return mujoco.MjModel.from_xml_path(str(path))


def drop_toe_dofs(model, a):
    keep = [i for i in range(model.nq) if i not in {int(model.jnt_qposadr[model.joint(f"toe_{s}").id]) for s in ("right", "left")}]
    return a[keep]


@data_needed
def test_the_welded_toe_gives_the_ankle_the_moment_of_the_rigid_whole_foot(model, stand, stride, tmp_path):
    rigid = rigid_foot_model(tmp_path)
    c = cycle(model, stand, stride, "welded")
    worst = 0.0
    for t in np.linspace(0.0, c.T, 12, endpoint=False):
        q, qd, qdd = c.eval(t)
        dofs = [i for i in range(model.nv) if i not in {int(model.jnt_dofadr[model.joint(f"toe_{s}").id]) for s in ("right", "left")}]
        qr, qdr, qddr = drop_toe_dofs(model, q), qd[dofs], qdd[dofs]
        f_toe = dynamics.inverse_frame(model, q, qd, qdd)
        f_rig = dynamics.inverse_frame(rigid, qr, qdr, qddr)
        forces = {"foot_right": np.array([20.0, 5.0, 400.0]), "foot_left": np.array([-10.0, 2.0, 300.0])}
        cops = {"foot_right": np.array([q[0] + 0.05, q[1] - 0.09, 0.0]), "foot_left": np.array([q[0] + 0.10, q[1] + 0.09, 0.0])}  # one behind and one ahead of the hinge
        t_toe, res_toe, _ = dynamics.solve_given(model, q, f_toe, forces, cops)
        t_rig, res_rig, _ = dynamics.solve_given(rigid, qr, f_rig, forces, cops)
        for name, value in t_rig.items():
            worst = max(worst, abs(t_toe[name] - value))
        worst = max(worst, float(np.abs(res_toe - res_rig).max()))
    assert worst < WELDED_TOL_NM, worst


@data_needed
def test_mutation_a_toe_that_is_not_welded_changes_the_ankle_moment(model, stand, stride, tmp_path):
    """The comparison above must be able to fail: a toe turned 40 degrees changes the ankle moment by far more than the tolerance."""
    rigid = rigid_foot_model(tmp_path)
    q, qd, qdd = cycle(model, stand, stride, "welded").eval(0.3)
    q = q.copy()
    q[int(model.jnt_qposadr[model.joint("toe_right").id])] = np.radians(40.0)
    dofs = [i for i in range(model.nv) if i not in {int(model.jnt_dofadr[model.joint(f"toe_{s}").id]) for s in ("right", "left")}]
    ankle = int(model.jnt_dofadr[model.joint("ankle_pdflex_right").id])
    a = dynamics.inverse_frame(model, q, qd, qdd)[ankle]
    b = dynamics.inverse_frame(rigid, drop_toe_dofs(model, q), qd[dofs], qdd[dofs])[int(rigid.jnt_dofadr[rigid.joint("ankle_pdflex_right").id])]
    assert abs(a - b) > 1e-3


def foot_corners(model, q, side="right"):
    d = mujoco.MjData(model)
    d.qpos[:] = q
    mujoco.mj_kinematics(model, d)
    return dynamics._foot_boxes(model, d, model.body(f"foot_{side}").id)


def test_the_contact_polygon_includes_the_toe_box_at_its_current_angle(model):
    q = model.qpos0.copy()
    corners, first = foot_corners(model, q)
    assert len(corners) == 16  # the foot box and the toe box
    tip = fh.SPEC_DESIGN["toe_tip_ahead_ankle_mm"] / 1000
    heel = fh.SPEC_DESIGN["foot_heel_behind_ankle_mm"] / 1000
    foot_x = corners[:, 0].min() + heel  # the ankle's x
    assert corners[:, 0].max() - foot_x == pytest.approx(tip, abs=1e-9)  # the sole reaches the toe tip
    centre, half, _ = first
    assert 2 * np.linalg.norm(half) == pytest.approx(heel + tip, abs=1e-9)  # the sole spans heel to toe tip along the foot's axis
    q[int(model.jnt_qposadr[model.joint("toe_right").id])] = np.radians(60.0)  # the toe lifted: its front is off the floor
    lifted, _ = foot_corners(model, q)
    flat_poly = dynamics.contact_polygon(corners)
    lifted_poly = dynamics.contact_polygon(lifted)
    assert max(p[0] for p in lifted_poly) < max(p[0] for p in flat_poly) - 0.02  # the contact polygon no longer reaches the toe tip


def test_a_ground_force_ahead_of_the_hinge_acts_on_the_toe_and_the_ankle_rows_do_not_care(model):
    d = mujoco.MjData(model)
    d.qpos[:] = model.qpos0
    mujoco.mj_kinematics(model, d)
    mujoco.mj_comPos(model, d)  # the Jacobians need the motion axes
    foot, toe = model.body("foot_right").id, model.body("toe_right").id
    hinge_x = d.xpos[toe][0]
    ahead, behind = np.array([hinge_x + 0.02, d.xpos[toe][1], 0.0]), np.array([hinge_x - 0.02, d.xpos[toe][1], 0.0])
    assert dynamics._contact_body(model, d, foot, ahead) == toe and dynamics._contact_body(model, d, foot, behind) == foot
    jt, jf = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    mujoco.mj_jac(model, d, jt, None, ahead, toe)
    mujoco.mj_jac(model, d, jf, None, ahead, foot)
    ankle = [int(model.jnt_dofadr[model.joint(n).id]) for n in ("ankle_pdflex_right", "ankle_ie_right")]
    assert np.allclose(jt[:, ankle], jf[:, ankle], atol=1e-12)  # the same point moves the same way about the ankle
    assert np.abs(jt[:, int(model.jnt_dofadr[model.joint("toe_right").id])]).max() > 0.01 and np.abs(jf[:, int(model.jnt_dofadr[model.joint("toe_right").id])]).max() == 0


@data_needed
def test_the_welded_cycle_never_moves_the_toe_and_the_rolling_one_does_in_push_off(model, stand, stride):
    welded, rolling = cycle(model, stand, stride, "welded"), cycle(model, stand, stride, "rolling")
    adr = [int(model.jnt_qposadr[model.joint(f"toe_{s}").id]) for s in ("right", "left")]
    qw, _, _ = welded.grid()
    qr, _, _ = rolling.grid()
    assert np.all(qw[:, adr] == 0.0)
    assert np.degrees(qr[:, adr].max()) > 20  # extension in push-off (the filter's undershoot below the flat stop is reported by retarget.limit_fraction, not clipped)
    assert np.degrees(qr[:, adr].max()) < 80  # inside the range for this stride (a frame beyond it would be reported by limit_fraction, not clipped)
    # everything else is the same cycle
    rest = [i for i in range(model.nq) if i not in adr]
    assert np.array_equal(qw[:, rest], qr[:, rest])


@data_needed
def test_the_rolling_toe_lies_flat_on_the_floor_while_the_foot_is_in_stance(model, stand, stride):
    """The toe's sole is parallel to the floor in the frames where the foot is pitched heel-up in stance, away from the ends of stance. The toe angle is filtered like every
    signal (6 Hz, about two time constants of 27 ms are MARGIN = 5 phase points of this stride), so within MARGIN of the end of stance it is smeared across the step the
    rule makes there; those frames are not part of this claim (they average 5.6 degrees off flat, 33 at worst, on this stride)."""
    c = cycle(model, stand, stride, "rolling")
    q, _, _ = c.grid()
    d = mujoco.MjData(model)
    errs = []
    for k in range(100):
        d.qpos[:] = q[k]
        mujoco.mj_kinematics(model, d)
        for side in ("right", "left"):
            foot = d.xmat[model.body(f"foot_{side}").id].reshape(3, 3)[:, 0]
            toe = d.xmat[model.body(f"toe_{side}").id].reshape(3, 3)[:, 0]
            pitch_foot, pitch_toe = np.degrees(np.arctan2(-foot[2], foot[0])), np.degrees(np.arctan2(-toe[2], toe[0]))
            f = 0 if side == "right" else 1
            if pitch_foot > 10 and all(stride["stance"][f, (k + j) % 100] for j in range(-MARGIN, MARGIN + 1)):
                errs.append(abs(pitch_toe))
    assert errs and np.mean(errs) < 5.0, (len(errs), np.mean(errs) if errs else None)  # degrees; the toe is within a few degrees of flat on the floor


@data_needed
def test_derivatives_of_the_rolling_cycle_are_those_of_its_positions(model, stand, stride):
    c = cycle(model, stand, stride, "rolling")
    eps = 1e-5
    for t in (0.05, 0.31, 0.62 * c.T, 0.93):
        _, qd, qdd = c.eval(t)
        qp, qdp, _ = c.eval(t + eps)
        qm, qdm, _ = c.eval(t - eps)
        fd = np.zeros(model.nv)
        mujoco.mj_differentiatePos(model, fd, 2 * eps, qm, qp)
        assert np.abs(fd - qd).max() < 1e-5 * max(1.0, np.abs(qd).max())
        assert np.abs((qdp - qdm) / (2 * eps) - qdd).max() < 1e-4 * max(1.0, np.abs(qdd).max())


def test_a_rolling_toe_without_stance_flags_is_refused(model, stand):
    with pytest.raises(ValueError, match="stance flags"):
        retarget.Cycle(model, MAPPING, stand, np.zeros((101, 18)), 1.0, 1.0, toe="rolling")


def test_a_model_without_a_toe_is_unchanged_by_the_toe_option():
    old = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    if retarget.Cycle._toe_hinges(old):
        pytest.skip("the tracked model has a toe")
    assert retarget.Cycle._toe_hinges(old) == []


@data_needed
def test_a_stride_through_run_stride_gives_a_toe_summary_and_a_welded_a(tmp_path):
    """run_stride on the fixture model: A_filtered from the welded cycle, B and H from the rolling one, the toe's peak angle and time at the stops reported."""
    manifest = json.loads(MANIFEST.read_text())
    spec = gait.load_spec("walk_treadmill")
    spec = dict(spec, subjects=["AB06"], speeds_mps=[1.4], stride_cap_per_subject=1)
    tasks = gait._tasks(spec, manifest, fh.fixture_model_path(), REPO / "data" / "camargo2021" / "processed", ["A_filtered", "B", "H"], 6.0, 0.0, 1, False, True, False, trunk="rigid")
    out = gait.run_stride(dict(tasks[0], keep_torque=True))
    toe = out["toe"]["right"]
    assert 0.0 <= toe["peak_deg"] < 90 and 0.0 <= toe["at_flexion_stop"] <= 1.0 and toe["at_extension_stop"] == 0.0
    # the A torque is what the same stride gives when only A is asked for (then there is no rolling cycle at all)
    only_a = gait.run_stride(dict(gait._tasks(spec, manifest, fh.fixture_model_path(), REPO / "data" / "camargo2021" / "processed", ["A_filtered"], 6.0, 0.0, 1, False, True, False, trunk="rigid")[0], keep_torque=True))
    assert "toe" not in only_a
    for j, v in out["torque"]["A_filtered"].items():
        assert np.allclose(v, only_a["torque"]["A_filtered"][j], atol=1e-9)


def test_toe_stats_counts_frames_at_the_stops():
    m = mujoco.MjModel.from_xml_path(str(fh.fixture_model_path()))
    q = np.zeros((10, m.nq))
    adr = int(m.jnt_qposadr[m.joint("toe_right").id])
    q[3:6, adr] = np.radians([30.0, 80.0, 90.0])  # 80 is the stop, 90 is beyond it
    st = np.array([[False] * 5 + [True] * 5, [True] * 10])
    s = gait.toe_stats(m, q, st)["right"]
    assert s["peak_deg"] == pytest.approx(90.0) and s["at_flexion_stop"] == pytest.approx(0.7) and s["at_extension_stop"] == pytest.approx(0.2)
    assert s["stance_at_extension_stop"] == pytest.approx(0.2) and s["stance_at_flexion_stop"] == pytest.approx(0.8) and s["stance_peak_deg"] == pytest.approx(90.0)
