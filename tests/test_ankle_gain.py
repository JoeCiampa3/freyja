"""
Stage 2b T6 (report only): the diagnostics behind docs/memos/memo9-ankle-gain.md, in sim/scripts/ankle_gain.py.
The pure helpers are tested on synthetic input; the model-dependent parts are exercised by the diagnostic itself.

Run from the repo root:
    python -m pytest tests/test_ankle_gain.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import ankle_gain as ag  # noqa: E402


def test_the_marker_reader_aliases_the_lateral_malleolus_to_the_heel_slot_and_changes_nothing_else():
    table = {f"{f}_{m}_{c}": np.full(3, 10.0 * i + j) for i, f in enumerate("RL") for j, m in enumerate(("Heel", "Toe_Tip", "Ankle_Lat")) for c in "xyz"}
    table["Header"] = np.arange(3.0)
    read = ag.ankle_marker_reader(lambda blob: dict(table))
    out = read(b"")
    for f in "RL":
        for c in "xyz":
            assert np.array_equal(out[f"{f}_Heel_{c}"], table[f"{f}_Ankle_Lat_{c}"])  # the slot ingest reads as the heel now holds the malleolus
            assert np.array_equal(out[f"{f}_Toe_Tip_{c}"], table[f"{f}_Toe_Tip_{c}"])
    assert np.array_equal(out["Header"], table["Header"])
    assert table["R_Heel_x"][0] != table["R_Ankle_Lat_x"][0]  # the original table was not modified


def test_the_marker_reader_leaves_tables_without_the_malleolus_marker_alone():
    t = {"Header": np.arange(3.0), "speed": np.ones(3)}
    assert ag.ankle_marker_reader(lambda blob: dict(t))(b"") == t


OSIM = """<OpenSimDocument><Model><BodySet><objects/></BodySet><JointSet><objects>
<CustomJoint name="ankle_r"><frames><PhysicalOffsetFrame name="tibia_r_offset"><socket_parent>/bodyset/tibia_r</socket_parent><translation>0 -0.4 0</translation></PhysicalOffsetFrame>
<PhysicalOffsetFrame name="talus_r_offset"><socket_parent>/bodyset/talus_r</socket_parent><translation>0 0 0</translation></PhysicalOffsetFrame></frames></CustomJoint>
<CustomJoint name="ankle_l"><frames><PhysicalOffsetFrame name="tibia_l_offset"><socket_parent>/bodyset/tibia_l</socket_parent><translation>0 -0.41 0</translation></PhysicalOffsetFrame></frames></CustomJoint>
</objects></JointSet><MarkerSet><objects>
<Marker name="R_Ankle_Lat"><socket_parent_frame>/bodyset/tibia_r</socket_parent_frame><location>-0.005 -0.39 0.05</location></Marker>
<Marker name="L_Ankle_Lat"><socket_parent_frame>/bodyset/tibia_l</socket_parent_frame><location>-0.01 -0.40 -0.05</location></Marker>
</objects></MarkerSet></Model></OpenSimDocument>"""


def test_the_joint_centre_offset_from_the_malleolus_marker_is_read_from_the_tibia_frame():
    off = ag.ankle_jc_offsets(OSIM.encode())
    assert off.shape == (2, 3)
    assert off[0] == pytest.approx([0.005, -0.01, -0.05], abs=1e-12)  # joint centre minus marker, tibia frame (x forward, y up, z right), right then left
    assert off[1] == pytest.approx([0.01, -0.01, 0.05], abs=1e-12)


def test_the_ground_torque_about_a_hinge_is_the_axis_component_of_r_cross_f():
    axis = np.array([0.0, -1.0, 0.0])
    anchor = np.array([0.0, 0.0, 0.06])
    cop = np.array([0.2, 0.0, 0.0])
    assert ag.ground_torque(axis, anchor, cop, np.array([0.0, 0.0, 100.0])) == pytest.approx(20.0, abs=1e-12)  # vertical force times the lever
    assert ag.ground_torque(axis, anchor, cop, np.array([50.0, 0.0, 0.0])) == pytest.approx(3.0, abs=1e-12)  # horizontal force times the ankle height
    assert ag.ground_torque(axis, anchor, cop, np.array([50.0, 0.0, 100.0])) == pytest.approx(23.0, abs=1e-12)  # linear


def test_the_correlation_interval_uses_the_fisher_transform():
    lo, hi = ag.correlation_interval(0.0, 17)
    assert (lo, hi) == pytest.approx((-0.4807, 0.4807), abs=1e-3)  # 1.96 / sqrt(14) = 0.5238, tanh = 0.4807
    lo, hi = ag.correlation_interval(0.9, 17)
    assert 0.9 > lo > 0.7 and 0.9 < hi < 0.97


PROCESSED = REPO / "data" / "camargo2021" / "processed" / "AB06.npz"


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed Camargo arrays not present")
@pytest.mark.parametrize("cop_mode", ["hip_reference", "foot_frame"])
def test_the_terms_worker_reproduces_run_strides_a_filtered_torques_and_splits_them_exactly(cop_mode):
    """The decomposition is only worth reporting if its total is the pipeline's own A_filtered torque: equal to 1e-9 N m, for both CoP mappings."""
    import json
    import gait
    spec = gait.load_spec("walk_treadmill")
    spec.update({"subjects": ["AB06"], "speeds_mps": [1.4], "stride_cap_per_subject": 1, "cop_mode": cop_mode})
    manifest = json.loads((REPO / spec["dataset"]["manifest"]).read_text(encoding="utf-8"))
    task = gait._tasks(spec, manifest, gait.simrun.MODEL_FILE, REPO / spec["dataset"]["processed"], ["A_filtered"], float(spec["smoothing"]["cutoff_hz"]),
                       float(spec["pelvis_pitch_offset_deg"]), 1, False, False, False, trunk="rigid")[0]
    ref = gait.run_stride(dict(task, keep_torque=True))["torque"]["A_filtered"]
    got = ag.stride_terms(task)
    assert set(ag.TERM_JOINTS) <= set(got["tau"])
    for j in ag.TERM_JOINTS:
        assert np.max(np.abs(np.asarray(ref[j]) - got["tau"][j])) < 1e-9
        assert np.max(np.abs(got["inertial"][j] - got["g_vert"][j] - got["g_horiz"][j] - got["tau"][j])) < 1e-12  # the split is exact
    # the ankle's ground part equals r x F about the hinge, from the recorded positions and forces (the Jacobian route and the geometric one agree)
    for side in ("right", "left"):
        j, foot = f"ankle_pdflex_{side}", f"foot_{side}"
        geo = np.array([ag.ground_torque(got["axis"][j][k], got["anchor"][j][k], got["cop"][foot][k], got["force"][foot][k]) for k in range(len(got["tau"][j]))])
        assert np.max(np.abs(geo - (got["g_vert"][j] + got["g_horiz"][j]))) < 1e-9


def test_the_gain_factors_multiply_back_to_the_torque_ratio_and_each_isolates_one_cause():
    tA, gA, gX, gD, tD, ratio = 131.0, 128.0, 105.0, 110.0, 104.0, 0.96
    f = ag.gain_factors(tA, gA, gX, gD, tD, ratio)
    assert set(f) == {"inertia", "lever", "force", "leg_ratio", "data_closure"}
    assert np.prod(list(f.values())) == pytest.approx(tA / tD, rel=1e-12)
    assert f["inertia"] == pytest.approx(131.0 / 128.0)
    assert f["leg_ratio"] == 0.96
    same = ag.gain_factors(96.0, 96.0, 96.0, 100.0, 100.0, 0.96)  # no inertia, an exactly scaled lever, equal force, a consistent dataset: A is just the leg ratio times the dataset
    assert all(v == pytest.approx(1.0) for k, v in same.items() if k != "leg_ratio") and same["leg_ratio"] == 0.96


def test_the_force_weighted_lever_ignores_frames_without_load():
    fz = np.array([0.0, 100.0, 300.0, 0.0])
    dx = np.array([9.0, 0.1, 0.3, -9.0])  # the swing frames carry no weight, whatever the lever there
    assert ag.force_weighted_lever(fz, dx) == pytest.approx((100 * 0.1 + 300 * 0.3) / 400.0)
    assert np.isnan(ag.force_weighted_lever(np.zeros(3), np.ones(3)))


def test_the_root_pitch_of_a_pose_is_the_rotation_about_the_lateral_axis_with_forward_lean_positive():
    h = np.radians(3.0) / 2
    qpos = np.array([0, 0, 1.0, np.cos(h), 0, np.sin(h), 0])  # +3 degrees about +y (x forward, y left, z up): the top of the body tips forward
    assert ag.stand_pitch_deg(qpos) == pytest.approx(3.0, abs=1e-9)
    qpos[5] = -np.sin(h)
    assert ag.stand_pitch_deg(qpos) == pytest.approx(-3.0, abs=1e-9)
    assert ag.stand_pitch_deg(np.array([0, 0, 1.0, 1, 0, 0, 0])) == 0.0


def test_the_segment_masses_are_read_from_the_subjects_opensim_bodies():
    xml = ("<OpenSimDocument><Model><BodySet><objects>" + "".join(
        f'<Body name="{n}_r"><mass>{m}</mass></Body>' for n, m in (("femur", 9.0), ("tibia", 3.5), ("talus", 0.1), ("calcn", 1.2), ("toes", 0.2), ("pelvis", 11.0)))
        + "</objects></BodySet></Model></OpenSimDocument>")
    got = ag.segment_masses(xml.encode())
    assert got == {"femur": 9.0, "tibia": 3.5, "foot": pytest.approx(1.5)}  # talus + calcn + toes
