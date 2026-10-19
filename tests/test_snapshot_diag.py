"""
Stage 2 diagnostics ahead of the snapshot change (sim/scripts/snapshot_diag.py, report only): the pure functions on synthetic input with known
answers, and the static-trial reads on the real archives when the raw folder is present (skipped otherwise).

Run from the repo root:
    python -m pytest tests/test_snapshot_diag.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import snapshot_diag as sd  # noqa: E402


def _rot(yaw_deg, pitch_deg=0.0):
    """A rotation about the vertical (y) by yaw, then about x by pitch: an arbitrary lab pose."""
    a, b = np.deg2rad(yaw_deg), np.deg2rad(pitch_deg)
    ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    return ry @ rx


# ------------------------------------------------------------------------------ rigid fit and the foot

def test_kabsch_recovers_a_known_rigid_motion():
    rng = np.random.default_rng(0)
    P = rng.normal(size=(5, 3))
    R0, t0 = _rot(37.0, 11.0), np.array([0.3, -0.2, 1.1])
    R, t, rms = sd.kabsch(P, P @ R0.T + t0)
    assert np.allclose(R, R0, atol=1e-9) and np.allclose(t, t0, atol=1e-9) and rms < 1e-9


def test_kabsch_reports_the_residual_and_never_returns_a_reflection():
    P = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1.0]])
    Q = P * np.array([-1.0, 1, 1])  # a mirror image: no rotation fits it exactly
    R, t, rms = sd.kabsch(P, Q)
    assert np.isclose(np.linalg.det(R), 1.0) and rms > 0.1


# a calcaneus frame in metres (x forward, y up, z right) with the model's points in it
CALCN = {"R_Heel": [-0.02, 0.03, -0.02], "R_Toe_Lat": [0.15, -0.01, 0.06], "R_Toe_Med": [0.19, 0.0, -0.05], "R_Toe_Tip": [0.20, 0.02, -0.02]}
AJC, MTP = [0.05, 0.045, -0.01], [0.19, 0.0, 0.0]


def _lab_foot(yaw, offset=(0.4, 0.0, -0.2)):
    """The same foot flat in the lab (x right, y up, forward is minus z when yaw = 0, as the treadmill trials), yawed."""
    to_lab = np.array([[0, 0, 1.0], [0, 1, 0], [-1, 0, 0]])  # model (fwd, up, right) -> lab (right = +x, up = +y, back = +z)
    R = _rot(yaw) @ to_lab
    mk = {n: R @ np.array(p) + offset for n, p in CALCN.items()}
    return mk, R @ np.array(AJC) + offset, R @ np.array(MTP) + offset


def test_foot_geometry_is_the_calcaneus_frame_distances_whatever_the_facing():
    for yaw in (0.0, 90.0, 213.0):
        mk, ajc_lab, mtp_lab = _lab_foot(yaw)
        g = sd.foot_geometry(mk, CALCN, AJC, MTP)
        assert g["fit_rms_m"] < 1e-9 and np.isclose(np.linalg.norm(g["fwd"]), 1.0) and abs(g["fwd"][1]) < 1e-12  # forward is a horizontal unit vector
        assert np.allclose(g["ajc_lab"], ajc_lab, atol=1e-9) and np.allclose(g["mtp_lab"], mtp_lab, atol=1e-9)
        # forward is the horizontal heel-to-toe-tip direction; heel at x = -0.02, toe tip at 0.20, the ankle at 0.05
        assert g["foot_length_m"] == pytest.approx(0.22, abs=1e-9)
        assert g["ajc_to_heel_fwd_m"] == pytest.approx(0.07, abs=1e-9)
        assert g["ajc_to_toe_tip_fwd_m"] == pytest.approx(0.15, abs=1e-9)
        assert g["ajc_to_mtp_fwd_m"] == pytest.approx(0.14, abs=1e-9)
        assert g["toe_tip_fraction"] == pytest.approx(0.15 / 0.22, abs=1e-9)
        assert g["ajc_to_toe_tip_m"] == pytest.approx(np.linalg.norm(np.array(CALCN["R_Toe_Tip"]) - AJC), abs=1e-9)
        assert g["ajc_to_heel_up_m"] == pytest.approx(0.045 - 0.03, abs=1e-9) and g["ajc_height_above_toe_tip_m"] == pytest.approx(0.045 - 0.02, abs=1e-9)


def test_foot_geometry_uses_only_the_markers_of_the_foot_it_is_given():
    mk, _, _ = _lab_foot(30.0)
    other = {n.replace("R_", "L_"): np.array(v) + np.array([-0.5, 0.0, 0.7]) for n, v in _lab_foot(-100.0)[0].items()}  # the other foot, elsewhere and facing another way
    both = sd.foot_geometry({**other, **mk}, CALCN, AJC, MTP)
    alone = sd.foot_geometry(mk, CALCN, AJC, MTP)
    for k in ("foot_length_m", "ajc_to_heel_fwd_m", "ajc_to_toe_tip_fwd_m", "ajc_to_mtp_fwd_m", "ajc_to_heel_m", "ajc_to_toe_tip_m", "toe_tip_fraction"):
        assert both[k] == pytest.approx(alone[k], abs=1e-9)


def test_foot_geometry_sees_a_marker_that_does_not_fit_the_model():
    mk, _, _ = _lab_foot(10.0)
    mk["R_Toe_Tip"] = mk["R_Toe_Tip"] + np.array([0.0, 0.0, 0.03])  # 3 cm off along the lab's fore-aft axis
    assert sd.foot_geometry(mk, CALCN, AJC, MTP)["fit_rms_m"] > 0.005


# ------------------------------------------------------------------------------ the osim reader

OSIM = """<OpenSimDocument><Model><JointSet><objects>
<CustomJoint name="ankle_r"><FrameSet><objects>
<PhysicalOffsetFrame name="tibia_r_offset"><socket_parent>/bodyset/tibia_r</socket_parent><translation>0 -0.46 0</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
<PhysicalOffsetFrame name="talus_r_offset"><socket_parent>/bodyset/talus_r</socket_parent><translation>0.001 0.002 0.003</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
</objects></FrameSet></CustomJoint>
<CustomJoint name="subtalar_r"><FrameSet><objects>
<PhysicalOffsetFrame name="talus_r_offset"><socket_parent>/bodyset/talus_r</socket_parent><translation>-0.05 -0.04 0.008</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
<PhysicalOffsetFrame name="calcn_r_offset"><socket_parent>/bodyset/calcn_r</socket_parent><translation>0 0 0</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
</objects></FrameSet></CustomJoint>
<CustomJoint name="mtp_r"><FrameSet><objects>
<PhysicalOffsetFrame name="calcn_r_offset"><socket_parent>/bodyset/calcn_r</socket_parent><translation>0.19 -0.002 0.001</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
<PhysicalOffsetFrame name="toes_r_offset"><socket_parent>/bodyset/toes_r</socket_parent><translation>0 0 0</translation><orientation>0 0 0</orientation></PhysicalOffsetFrame>
</objects></FrameSet></CustomJoint>
</objects></JointSet>
<MarkerSet><objects>
<Marker name="R_Heel"><socket_parent_frame>/bodyset/calcn_r</socket_parent_frame><location>-0.02 0.03 0.0065</location></Marker>
<Marker name="R_Ankle_Lat"><socket_parent_frame>/bodyset/tibia_r</socket_parent_frame><location>0 -0.45 0.05</location></Marker>
</objects></MarkerSet></Model></OpenSimDocument>"""


def test_osim_foot_points_chain_the_fixed_offsets_to_the_calcaneus():
    p = sd.osim_foot_points(OSIM.encode(), "r")
    # ankle centre in the talus frame is the talus offset of the ankle; the subtalar joint places the talus origin at Q - P + that
    assert np.allclose(p["ajc"], np.array([0.0, 0.0, 0.0]) - np.array([-0.05, -0.04, 0.008]) + np.array([0.001, 0.002, 0.003]))
    assert np.allclose(p["mtp"], [0.19, -0.002, 0.001])
    assert np.allclose(p["markers"]["R_Heel"], [-0.02, 0.03, 0.0065]) and "R_Ankle_Lat" not in p["markers"]  # calcaneus markers only


def test_osim_foot_points_refuses_a_rotated_offset_frame():
    with pytest.raises(ValueError, match="orientation"):
        sd.osim_foot_points(OSIM.replace("<orientation>0 0 0</orientation>", "<orientation>0 0 0.1</orientation>", 1).encode(), "r")


# ------------------------------------------------------------------------------ the Dumas pelvic frame

def _pelvis(tilt_deg, yaw_deg=0.0, obliquity_deg=0.0, n=3):
    """ASIS and PSIS markers (lab: x right, y up, z back at yaw 0; so the pelvis faces -z) of a pelvis tilted anteriorly by tilt_deg: the anterior axis
    points down by that angle (ASIS below the PSIS), rotated about the vertical by yaw and about the anterior axis by the obliquity."""
    th, ob = np.deg2rad(tilt_deg), np.deg2rad(obliquity_deg)
    fwd = np.array([0.0, -np.sin(th), -np.cos(th)])
    up = np.array([0.0, np.cos(th), -np.sin(th)])
    right = np.array([1.0, 0.0, 0.0])
    right, up = right * np.cos(ob) + up * np.sin(ob), up * np.cos(ob) - right * np.sin(ob)
    R = _rot(yaw_deg)
    mid = np.array([0.0, 1.0, 0.0])
    asis_r, asis_l = mid + 0.12 * right + 0.10 * fwd, mid - 0.12 * right + 0.10 * fwd
    psis_r, psis_l = mid + 0.04 * right - 0.06 * fwd + 0.03 * up, mid - 0.04 * right - 0.06 * fwd + 0.03 * up
    tile = lambda p: np.tile(R @ p, (n, 1))
    return tile(asis_r), tile(asis_l), tile(psis_r), tile(psis_l)


PSIS_DIP_DEG = float(np.degrees(np.arctan2(0.03, 0.16)))  # the fixture's PSIS midpoint is 0.03 m above the ASIS plane along the pelvis's up axis and 0.16 m behind the ASIS midpoint;
# the Dumas anterior axis lies in the plane through the ASIS and the PSIS midpoint, so it dips this much further than the pelvis's own forward axis


@pytest.mark.parametrize("tilt", [-10.0, 0.0, 6.5, 25.0])
def test_dumas_tilt_is_the_anterior_axis_dip_anterior_positive_whatever_the_facing(tilt):
    for yaw in (0.0, 77.0, 180.0):
        got = sd.dumas_pelvic_tilt_deg(*_pelvis(tilt, yaw))
        assert np.allclose(got, got[0]) and got[0] == pytest.approx(tilt + PSIS_DIP_DEG, abs=1e-9)


def test_dumas_tilt_changes_by_the_tilt_change_and_is_small_for_modest_obliquity():
    base = sd.dumas_pelvic_tilt_deg(*_pelvis(5.0))[0]
    assert sd.dumas_pelvic_tilt_deg(*_pelvis(12.0))[0] - base == pytest.approx(7.0, abs=1e-9)
    assert abs(sd.dumas_pelvic_tilt_deg(*_pelvis(5.0, obliquity_deg=5.0))[0] - base) < 0.2  # the lateral tilt of a few degrees barely moves the sagittal angle


def test_dumas_tilt_sign_asis_below_the_psis_is_positive():
    a_r, a_l, p_r, p_l = _pelvis(0.0)
    flat = sd.dumas_pelvic_tilt_deg(a_r, a_l, p_r, p_l)[0]
    lowered = sd.dumas_pelvic_tilt_deg(a_r - [0, 0.03, 0], a_l - [0, 0.03, 0], p_r, p_l)[0]
    assert lowered > flat


def test_nan_frames_stay_nan_and_the_mean_ignores_them():
    a_r, a_l, p_r, p_l = _pelvis(8.0, n=4)
    a_r[1] = np.nan
    t = sd.dumas_pelvic_tilt_deg(a_r, a_l, p_r, p_l)
    assert np.isnan(t[1]) and np.isfinite(t[[0, 2, 3]]).all()


# ------------------------------------------------------------------------------ hip extension against a stop

def test_extension_demand_counts_strictly_beyond_the_stop():
    v = np.array([10.0, 20.0, 31.0, 31.5, 40.0])
    d = sd.extension_demand(v, 31.0)
    assert d["n"] == 5 and d["beyond"] == 2 and d["fraction_beyond"] == pytest.approx(0.4)
    assert d["median"] == 31.0 and d["max"] == 40.0 and d["p95"] == pytest.approx(np.percentile(v, 95))


def test_hip_stop_report_uses_the_models_own_stop_and_both_references():
    strides = [{"hip_r": np.array([5.0, -35.0]), "hip_l": np.array([0.0, 2.0]), "list": np.array([0.0, 0.0])},     # 35 relative, 35 from vertical
               {"hip_r": np.array([5.0, -25.0]), "hip_l": np.array([0.0, 2.0]), "list": np.array([-10.0, -10.0])}]  # 25 relative, 35 from vertical
    r = sd.hip_stop_demand(strides, 31.0)
    assert r["pelvis_relative"]["beyond"] == 1 and r["vertical"]["beyond"] == 2 and r["stop_deg"] == 31.0


def test_the_stop_is_read_from_the_model_not_typed():
    import mujoco
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    assert sd.model_hip_stop_deg(model) == pytest.approx(-np.degrees(model.jnt_range[model.joint("hip_fe_right").id][0]))


# ------------------------------------------------------------------------------ the strides behind a maximum

def test_top_strides_ranks_by_peak_and_gives_the_ratio_to_the_p95():
    rows = [{"subject": f"S{i}", "index": i, "peak": float(p)} for i, p in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 100])]
    p95 = float(np.percentile([r["peak"] for r in rows], 95))
    top = sd.top_strides(rows, 3)
    assert [t["subject"] for t in top] == ["S19", "S18", "S17"] and top[0]["ratio_to_p95"] == pytest.approx(100 / p95)
    assert all(t["p95"] == pytest.approx(p95) for t in top)


def test_peak_frame_phase_and_the_stance_foot_at_it():
    tau = np.zeros(100)
    tau[37] = -9.0
    stance = {"R": np.zeros(100, bool), "L": np.zeros(100, bool)}
    stance["R"][10:60] = True
    stance["L"][50:100] = True
    p = sd.peak_context(tau, stance)
    assert p["frame"] == 37 and p["stride_phase_pct"] == 37.0 and p["support"] == "single"
    assert p["stance_foot"] == "R" and p["stance_pct"] == pytest.approx(100 * (37 - 10) / 50)
    tau2 = np.zeros(100)
    tau2[55] = 4.0
    q = sd.peak_context(tau2, stance)
    assert q["support"] == "double" and set(q["stance_pct_by_foot"]) == {"R", "L"}


# ------------------------------------------------------------------------------ the stamp, the marker inventory, ANSUR

def test_stamp_fields_reads_the_two_keys_and_marks_a_missing_file(tmp_path):
    f = tmp_path / "rec.json"
    f.write_text(json.dumps({"git_dirty": True, "diff_sha256": "ab" * 32, "other": 1}))
    assert sd.stamp_fields(f) == {"git_dirty": True, "diff_sha256": "ab" * 32}
    assert sd.stamp_fields(tmp_path / "nope.json") is None


def test_trunk_markers_are_found_by_name():
    legs = {"R_ASIS", "L_ASIS", "R_PSIS", "L_PSIS", "R_Heel", "R_Toe_Tip"}
    assert sd.trunk_marker_names(legs) == []
    assert sd.trunk_marker_names(legs | {"C7", "R_Shoulder", "Head_Top"}) == ["C7", "Head_Top", "R_Shoulder"]


def test_chord_inclination_is_from_the_vertical_in_the_forward_plane():
    fwd = np.array([0.0, 0.0, -1.0])
    lo, hi = np.array([[0.0, 1.0, 0.0]]), np.array([[0.0, 1.0 + np.cos(np.deg2rad(8)) * 0.5, -np.sin(np.deg2rad(8)) * 0.5]])
    assert sd.chord_inclination_deg(lo, hi, fwd)[0] == pytest.approx(8.0)  # leaning forward: positive


def test_ansur_stats_n_mean_sd(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("SubjectId,stature,footlength\n1,1600,240\n2,1700,250\n3,1650,260\n", encoding="latin-1")
    s = sd.ansur_stats(f, ["stature", "footlength", "missing"])
    assert s["stature"]["n"] == 3 and s["stature"]["mean"] == pytest.approx(1650) and s["stature"]["sd"] == pytest.approx(50)
    assert s["footlength"]["mean"] == pytest.approx(250) and s["missing"] is None


# ------------------------------------------------------------------------------ the real static trials

def _raw():
    import ingest_camargo as ic
    r = ic.raw_dir()
    return r if (r / "AB06.zip").exists() else None


@pytest.mark.skipif(_raw() is None, reason="the raw Camargo folder is not available")
def test_real_static_trial_foot_fit_and_tilt_for_one_subject():
    import ingest_camargo as ic
    out = sd.subject_static("AB06", _raw())
    assert 0 < out["foot"]["R"]["fit_rms_m"] < 0.01 and 0.15 < out["foot"]["R"]["foot_length_m"] < 0.32
    assert np.isfinite(out["dumas_tilt_mean_deg"]) and -30 < out["dumas_tilt_mean_deg"] < 40 and out["dumas_tilt_sd_deg"] >= 0
    assert "R_Toe_Tip" in out["markers"] and "C7" not in out["markers"]
