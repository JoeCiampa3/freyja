"""Volume-extractor brief 8, Phase A: the arm frames (a rigid rotation about the proximal node and an axial stretch), the stretch gate rule and the ANSUR arm lengths. The committed result of
`fy envelope gates` (`data/envelope/arm_bodies.json`) is tested in test_envelope_arm_bodies.py."""
import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import anthro, arms  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402


def test_rotation_turns_the_axis_down_and_is_proper():
    for u in ([0.01, -0.68, -0.73], [0.68, -0.47, -0.56], [0, 0, -1], [0, 0, 1], [1, 0, 0]):
        R = arms.rotation_to_down(u)
        assert R @ (np.array(u) / np.linalg.norm(u)) == pytest.approx([0, 0, -1], abs=1e-12)
        assert np.linalg.det(R) == pytest.approx(1.0) and R @ R.T == pytest.approx(np.eye(3), abs=1e-12)


def test_the_frame_puts_the_far_node_at_minus_k_times_the_length_and_inverts():
    o, far = np.array([15.0, -192.0, 1349.0]), np.array([19.0, -347.0, 1184.0])
    L = np.linalg.norm(far - o)
    f = arms.ArmFrame(o, far - o, 1.124)
    assert f.forward(o)[0] == pytest.approx([0, 0, 0], abs=1e-12)
    assert f.forward(far)[0] == pytest.approx([0, 0, -1.124 * L], abs=1e-9)
    P = np.random.default_rng(0).normal(size=(50, 3)) * 100 + o
    assert f.inverse(f.forward(P)) == pytest.approx(P, abs=1e-9)


def test_a_rotation_leaves_sections_alone_and_the_stretch_changes_only_the_axial_length():
    o = np.zeros(3)
    f = arms.ArmFrame(o, [0.5, -0.5, -0.7], 1.1)
    a, b = np.array([30.0, 0, 0]), np.array([0, 40.0, 0])
    # two points in a plane perpendicular to the axis keep their distance; two along the axis scale by k
    u = np.array([0.5, -0.5, -0.7]) / np.linalg.norm([0.5, -0.5, -0.7])
    p, q = np.cross(u, [1, 0, 0]) * 20, np.cross(u, [0, 1, 0]) * 30
    d0 = np.linalg.norm(p - q)
    assert np.linalg.norm(f.forward(p)[0] - f.forward(q)[0]) == pytest.approx(d0, rel=1e-12)
    assert np.linalg.norm(f.forward(u * 100)[0] - f.forward(u * 0)[0]) == pytest.approx(110.0, rel=1e-12)
    assert arms.angle_from_vertical_deg([0, 0, -1]) == pytest.approx(0.0) and arms.angle_from_vertical_deg([0, -1, -1]) == pytest.approx(45.0)


def test_the_gate_is_two_sigma_over_the_sheet_length():
    assert arms.GATE_SIGMAS * arms.SIGMA_MM / 398.08 == pytest.approx(0.0869, abs=1e-4)           # the legs' rule: 2 x 17.3 / 398 = 8.7%
    assert arms.SIGMA_MM == 17.3 and arms.GATE_SIGMAS == 2.0


def test_registration_stops_when_a_stretch_exceeds_its_own_gate():
    left = np.array([[0, 185, 1388], [0, 345, 1170], [38, 350, 1190], [177, 457, 1055]], float)       # upper-arm chord, forearm chord (left arm)
    hand = np.array([[190, -460, 1040], [200, -470, 1000], [205, -475, 960]], float)                    # right-hand vertices beyond the wrist
    V = np.vstack([left, left * np.array([1, -1, 1]), hand, [[0, -300, 1300]]])
    arm = np.zeros(len(V), bool)
    arm[4:12] = True
    inp = SimpleNamespace(V=V)
    tb = SimpleNamespace(acc={"spheres": {"centre_height_mm": 1347.0, "centre_x_mesh_mm": 15.0}}, tm=SimpleNamespace(inverse=lambda z: z), sjc={"lateral_mm": 192.0}, arm_mask=arm)
    rm = {arms.UPPER_ID: [0, 1], arms.FORE_ID: [2, 3]}
    ok = {"upper_arm": {"length_mm": 230.0, "mass_kg": 1.0}, "forearm": {"length_mm": 235.0, "mass_kg": 1.0}, "hand": {"length_mm": 74.0, "mass_kg": 0.3}}
    bad = {**ok, "upper_arm": {"length_mm": 270.0, "mass_kg": 1.0}}
    with pytest.raises(StopAndAsk, match="upper_arm"):
        arms.registration(inp, tb, rm, bad, "R")
    out = arms.registration(inp, tb, rm, ok, "R")
    assert set(out["stretch"]) == {"upper_arm", "forearm"} and out["exceeding_gate"] == [] and out["mirror_gap_mm"] == pytest.approx(0.0, abs=1e-9)
    assert out["gate"]["upper_arm"] == pytest.approx(2 * 17.3 / 230.0)
    assert out["hand"]["stretch"] == 1.0 and out["hand"]["vertices"] == 3


def test_ansur_arm_lengths_are_in_the_summary_and_come_from_the_raw_columns():
    d = anthro.ARM_COLUMNS
    assert set(d) == {"shoulder_elbow", "radiale_stylion", "forearm_hand", "hand_length"}
    assert d["shoulder_elbow"] == "shoulderelbowlength" and d["radiale_stylion"] == "radialestylionlength" and d["forearm_hand"] == "forearmhandlength"
    import json
    s = json.loads((REPO / "data/ansur2/ratios.json").read_text())
    assert set(s["arm_lengths"]) == set(d)
    assert s["arm_lengths"]["radiale_stylion"]["ratio"]["mean"] == pytest.approx(0.1482, abs=5e-4)


def test_the_sheet_arm_lengths_and_masses_are_read_from_the_snapshot():
    a = arms.sheet_arm(REPO / "params/snapshot.csv")
    snap = {r["placeholder"]: float(r["value"]) for r in csv.DictReader(open(REPO / "params/snapshot.csv"))}
    for n in arms.NAMES:
        assert a[n]["length_mm"] == pytest.approx(snap[f"{n}_right_length"] * 1000.0) and a[n]["mass_kg"] == pytest.approx(snap[f"{n}_right_mass"])
