"""
Stage 2g follow-up (memo 26): sim/scripts/float_diag.py, the report-only diagnostics of the stance float and of method A's sensitivity to it. Pure functions on synthetic
input with known answers, the counterfactual model edits, and one real stride tied to the record's own metric.

Run from the repo root:
    python -m pytest tests/test_float_diag.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import float_diag as fd  # noqa: E402
import gait  # noqa: E402

XML = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
MODEL = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def test_stance_deciles_split_each_contiguous_stance_interval_in_ten_and_join_one_that_wraps():
    m = np.zeros(100, bool)
    m[20:70] = True
    d = fd.stance_deciles(m)
    assert (d[:20] == -1).all() and (d[70:] == -1).all()
    assert list(d[20:70][::5]) == list(range(10)) and d[69] == 9
    w = np.zeros(100, bool)
    w[90:] = True
    w[:10] = True  # one interval of 20 frames across the end of the grid
    d = fd.stance_deciles(w)
    assert d[90] == 0 and d[99] == 4 and d[0] == 5 and d[9] == 9 and (d[10:90] == -1).all()
    assert (fd.stance_deciles(np.zeros(100, bool)) == -1).all()
    assert fd.stance_deciles(np.ones(100, bool))[0] == 0 and fd.stance_deciles(np.ones(100, bool))[-1] == 9


def pose(ankle_rad=0.0, side="right"):
    d = mujoco.MjData(MODEL)
    d.qpos[:] = MODEL.qpos0
    d.qpos[MODEL.jnt_qposadr[MODEL.joint(f"ankle_pdflex_{side}").id]] = ankle_rad
    mujoco.mj_kinematics(MODEL, d)
    return d


def test_the_lowest_corner_is_the_heel_when_the_toes_are_up_and_the_toe_tip_when_they_are_down():
    z, which, sx = fd.lowest_corner(MODEL, pose(0.3), 0)  # dorsiflexion: the toes rise
    assert (which, sx) == ("foot", -1)
    z2, which2, sx2 = fd.lowest_corner(MODEL, pose(-0.3), 0)  # plantarflexion: the toe tip dips below the heel
    assert (which2, sx2) == ("toe", 1)
    assert z2 < z  # the tip reaches lower than the heel did, because the box is longer than the heel offset


def test_stride_floats_reports_the_float_of_stance_frames_and_the_stride_s_lowest_corner():
    d = mujoco.MjData(MODEL)
    d.qpos[:] = MODEL.qpos0
    mujoco.mj_kinematics(MODEL, d)
    z0 = fd.lowest_corner(MODEL, d, 0)[0]
    heights = np.array([0.0, 0.01, 0.02, 0.03])
    q = np.tile(MODEL.qpos0, (4, 1))
    q[:, 2] += heights - z0  # the lowest corner of the (flat) feet at 0, 10, 20, 30 mm
    stance = np.zeros((2, 4), bool)
    stance[0, 1:] = True  # right foot in stance for the last three frames
    out = fd.stride_floats(MODEL, q, stance)
    assert out["float_max_m"] == pytest.approx(0.03) and out["float_mean_m"] == pytest.approx(0.02)
    assert out["min_frame"] == 0 and out["min_in_stance"] is False and out["min_z_m"] == pytest.approx(0.0, abs=1e-12)
    n = np.array(out["decile_n"])
    assert n.sum() == 3 and list(np.flatnonzero(n)) == [0, 3, 6]
    assert np.array(out["decile_sum_m"])[[0, 3, 6]] == pytest.approx([0.01, 0.02, 0.03])


def test_summarise_strides_counts_which_corner_sets_the_root_height_in_swing_and_in_stance():
    rows = [dict(float_max_m=0.05, float_mean_m=0.03, decile_sum_m=[0.1] * 10, decile_n=[2] * 10, min_in_stance=False, min_box="toe", min_side=1),
            dict(float_max_m=0.07, float_mean_m=0.04, decile_sum_m=[0.2] * 10, decile_n=[2] * 10, min_in_stance=False, min_box="toe", min_side=1),
            dict(float_max_m=0.01, float_mean_m=0.00, decile_sum_m=[0.0] * 10, decile_n=[2] * 10, min_in_stance=True, min_box="foot", min_side=-1)]
    s = fd.summarise_strides(rows)
    assert s["float_max_mean_m"] == pytest.approx(0.04333, abs=1e-4) and s["float_max_max_m"] == 0.07
    assert s["root_point"] == {"swing: toe tip": 2, "stance: heel (foot box, rear)": 1}
    assert s["by_decile_mean_m"] == pytest.approx([0.05] * 10)


def test_the_counterfactual_models_change_only_what_they_say():
    ankle = fd.with_ankle_height(XML, 0.0627, 0.025)
    m = mujoco.MjModel.from_xml_string(ankle)
    g = next(g for g in range(m.ngeom) if m.geom_bodyid[g] == m.body("foot_right").id)
    assert m.geom_pos[g][2] - m.geom_size[g][2] == pytest.approx(-0.0627) and m.geom_pos[g][2] + m.geom_size[g][2] == pytest.approx(0.0, abs=1e-12)
    assert m.body("toe_right").pos[2] == pytest.approx(-(0.0627 - 0.0125))
    others = [i for i in range(m.nbody) if not mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i).startswith("toe")]
    assert np.array_equal(m.body_mass, MODEL.body_mass) and np.array_equal(m.body_pos[others], MODEL.body_pos[others]) and np.array_equal(m.jnt_range, MODEL.jnt_range)
    notoe = mujoco.MjModel.from_xml_string(fd.without_toe_boxes(XML))
    assert notoe.ngeom == MODEL.ngeom - 2 and np.array_equal(notoe.body_mass, MODEL.body_mass)
    rear = mujoco.MjModel.from_xml_string(fd.with_rear(XML, 0.04125, 0.12812461473))
    g = next(g for g in range(rear.ngeom) if rear.geom_bodyid[g] == rear.body("foot_right").id)
    assert rear.geom_pos[g][0] - rear.geom_size[g][0] == pytest.approx(-0.04125) and rear.geom_pos[g][0] + rear.geom_size[g][0] == pytest.approx(0.12812461473)
    assert rear.ngeom == MODEL.ngeom
    for bad in (lambda: fd.with_ankle_height(XML.replace('<body name="toe_right"', '<body name="toes_right"'), 0.06, 0.025), lambda: fd.without_toe_boxes("<mujoco/>"),
                lambda: fd.with_rear("<mujoco/>", 0.04, 0.12)):
        with pytest.raises(ValueError):
            bad()


PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_the_stance_float_of_a_real_stride_equals_the_records_own_metric():
    """float_diag's per-stride maximum is retarget.foot_metrics' `stance_float_max_m`, from the same welded cycle."""
    import json

    import gaitloads
    import retarget
    man = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    spec = dict(gait.load_spec("walk_treadmill"), speeds_mps=[1.4], subjects=["AB06"])
    task = next(t for t in fd.gait._tasks(spec, man, gait.simrun.MODEL_FILE, REPO / "data" / "camargo2021" / "processed", ["A_filtered"], 6.0, 0.0, None, False, False, False, trunk="rigid")
                if t["index"] == 3)
    mine = fd.float_task(task)
    c = gait._ctx(task["model_path"])
    z = gait._subject_arrays(task["processed"], "AB06")
    fp = z["1.4_fp"][3]
    sub = task["subject_info"]
    cyc = retarget.Cycle(c.model, c.mapping, c.stand, z["1.4_ik"][3], float(z["1.4_duration_s"][3]), retarget.leg_length_ratio(c.model, sub["height_m"]), cutoff_hz=6.0,
                         root_rule=task["root_rule"], hip_in_pelvis_os=sub["hip_in_pelvis_os_m"], root_ref="hip_midpoint", pitch_mean="measured", trunk="rigid",
                         pelvis_frame_offset_deg=gait.frame_offset_deg(task["pelvis_frame_offset"], sub), toe="welded")
    ref = retarget.foot_metrics(c.model, cyc, fp[:, :, 6] >= gaitloads.STANCE_FLAG, 1.4)["stance_float_max_m"]
    assert mine["float_max_m"] == pytest.approx(ref, abs=1e-9)
    assert mine["min_z_m"] == pytest.approx(0.0, abs=1e-6)  # the root rule puts the stride's lowest corner on the floor


# ------------------------------------------------------------------------------ method A with the force applied at the sole (T2)

import dynamics  # noqa: E402


def test_sole_height_is_the_lowest_foot_or_toe_corner_of_the_named_foot():
    q = MODEL.qpos0.copy()
    d = mujoco.MjData(MODEL)
    d.qpos[:] = q
    mujoco.mj_kinematics(MODEL, d)
    z0 = dynamics.sole_height(MODEL, q, "foot_right")
    assert z0 == pytest.approx(fd.lowest_corner(MODEL, d, 0)[0])
    q[2] += 0.03
    assert dynamics.sole_height(MODEL, q, "foot_right") == pytest.approx(z0 + 0.03)
    q[MODEL.jnt_qposadr[MODEL.joint("ankle_pdflex_left").id]] = -0.3  # the left toe tip dips: the right foot's answer does not move
    assert dynamics.sole_height(MODEL, q, "foot_right") == pytest.approx(z0 + 0.03)
    assert dynamics.sole_height(MODEL, q, "foot_left") < dynamics.sole_height(MODEL, q, "foot_right")


def test_lifting_the_force_point_by_h_changes_the_joint_rows_by_h_times_the_horizontal_force_lever():
    """The contact moment about a joint is axis . ((p - joint) x F). Raising p by h along z adds axis . (h z x F) = h * axis . (z x F) and nothing else, which is what method A's
    `cop_lift: sole` does; checked here against the joint axes and an arbitrary horizontal force."""
    q = MODEL.qpos0.copy()
    q[2] += 0.05
    qfrc = np.zeros(MODEL.nv)
    F = np.array([40.0, -15.0, 600.0])
    p = np.array([0.1, -0.09, 0.0])
    t0, _, _ = dynamics.solve_given(MODEL, q, qfrc, {"foot_right": F}, {"foot_right": p})
    h = 0.04
    t1, _, _ = dynamics.solve_given(MODEL, q, qfrc, {"foot_right": F}, {"foot_right": p + np.array([0.0, 0.0, h])})
    d = mujoco.MjData(MODEL)
    d.qpos[:] = q
    mujoco.mj_kinematics(MODEL, d)
    for name in ("ankle_pdflex_right", "knee_right", "hip_fe_right"):
        j = MODEL.joint(name)
        axis = d.xaxis[j.id]
        assert (t0[name] - t1[name]) == pytest.approx(h * float(axis @ np.cross([0.0, 0.0, 1.0], F)), abs=1e-9), name


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
def test_cop_lift_floor_is_the_default_and_sole_moves_only_method_a_by_the_float():
    import json
    man = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    spec = dict(gait.load_spec("walk_treadmill"), speeds_mps=[1.4], subjects=["AB06"])
    base = next(t for t in gait._tasks(spec, man, gait.simrun.MODEL_FILE, REPO / "data" / "camargo2021" / "processed", ["A_filtered", "H"], 6.0, 0.0, None, False, False, False, trunk="rigid")
                if t["index"] == 3)
    default, floor, sole = gait.run_stride(dict(base)), gait.run_stride(dict(base, cop_lift="floor")), gait.run_stride(dict(base, cop_lift="sole"))
    assert default["peaks"] == floor["peaks"]
    for j in default["peaks"]["A_filtered"]:
        assert sole["peaks"]["H"][j] == default["peaks"]["H"][j]  # H is not A: it is left alone
    moved = [j for j in default["peaks"]["A_filtered"] if sole["peaks"]["A_filtered"][j]["peak_torque_nm"] != default["peaks"]["A_filtered"][j]["peak_torque_nm"]]
    assert "ankle_pdflex_right" in moved or "ankle_pdflex_left" in moved
    with pytest.raises(gait.GaitError):
        gait.run_stride(dict(base, cop_lift="air"))
