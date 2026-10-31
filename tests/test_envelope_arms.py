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


# ---- adr-0042: the D1 nodes, the D4 roll and the 8% gate, on two tubes whose centre lines are known --------------------------------------------

def _tube(a, b, r, rings, n=24):
    """A closed tube from a to b: `rings` + 1 rings of n vertices and an end vertex at each end. Vertex k of a ring lies at angle 2 pi k / n from the first perpendicular."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    e1 = np.cross(u, [1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    V = [a + t * (b - a) + r * (np.cos(th) * e1 + np.sin(th) * e2) for t in np.linspace(0, 1, rings + 1) for th in 2 * np.pi * np.arange(n) / n]
    V += [a, b]
    F = []
    for i in range(rings):
        for k in range(n):
            p, q = i * n + k, i * n + (k + 1) % n
            F += [(p, q, q + n), (p, q + n, p + n)]
    lo, hi = (rings + 1) * n, (rings + 1) * n + 1
    F += [(lo, (k + 1) % n, k) for k in range(n)] + [(hi, rings * n + k, rings * n + (k + 1) % n) for k in range(n)]
    return np.array(V), np.array(F)


class TwoTubes:
    """Left and right arms of two tubes each. The Ruler chords run on the skin, one radius off the centre lines, as the sculpt's do."""
    N, R = 24, 28.0

    def __init__(self):
        n = self.N
        self.sjc = np.array([15.0, 192.0, 1349.0])
        self.u = np.array([0.1, 0.7, -0.7]) / np.linalg.norm([0.1, 0.7, -0.7])
        self.v = np.array([0.55, 0.45, -0.7]) / np.linalg.norm([0.55, 0.45, -0.7])
        self.elbow = self.sjc + 230.0 * self.u
        self.wrist = self.elbow + 230.0 * self.v
        Vu, Fu = _tube(self.sjc - 60.0 * self.u, self.elbow, self.R, 29)        # rings every 10 mm; ring 29 is the elbow's
        Vf, Ff = _tube(self.elbow, self.wrist + 100.0 * self.v, self.R, 33)      # ring 23 is the wrist's
        Vl, Fl = np.vstack([Vu, Vf]), np.vstack([Fu, Ff + len(Vu)])
        self.V = np.vstack([Vl, Vl * np.array([1.0, -1.0, 1.0])])
        self.F = np.vstack([Fl, Fl[:, ::-1] + len(Vl)])
        self.rm = {arms.UPPER_ID: [0, 29 * n], arms.FORE_ID: [len(Vu), len(Vu) + 23 * n]}
        self.inp = SimpleNamespace(V=self.V, F=self.F)
        self.tb = SimpleNamespace(acc={"spheres": {"centre_height_mm": 1349.0, "centre_x_mesh_mm": 15.0}}, tm=SimpleNamespace(inverse=lambda z: z), sjc={"lateral_mm": 192.0},
                                  arm_mask=np.ones(len(self.V), bool))

    def sheet(self, up=1.0, fore=1.0):
        return {"upper_arm": {"length_mm": 230.0 * up, "mass_kg": 1.0}, "forearm": {"length_mm": 230.0 * fore, "mass_kg": 1.0}, "hand": {"length_mm": 74.0, "mass_kg": 0.3}}


def _off_line(p, a, u):
    d = np.asarray(p, float) - a
    return float(np.linalg.norm(d - (d @ u) * u))


MIRROR = np.array([1.0, -1.0, 1.0])       # the right arm's nodes against the left tubes' axes


def _assert_nodes_on_the_centre_lines(t, reg):
    assert _off_line(reg["nodes_mesh_mm"]["elbow"] * MIRROR, t.sjc, t.u) < 0.2 and _off_line(reg["nodes_mesh_mm"]["wrist"] * MIRROR, t.elbow, t.v) < 0.2


def test_d1_puts_the_elbow_and_wrist_on_the_proximal_segments_centre_lines():
    t = TwoTubes()
    reg = arms.registration(t.inp, t.tb, t.rm, t.sheet(), "R")
    _assert_nodes_on_the_centre_lines(t, reg)
    assert _off_line(reg["chord_nodes_mesh_mm"]["elbow"] * MIRROR, t.sjc, t.u) > 10.0                    # the chord elbow is on the skin
    assert reg["lengths_mesh_mm"]["upper_arm"] == pytest.approx(np.linalg.norm(reg["nodes_mesh_mm"]["elbow"] - reg["nodes_mesh_mm"]["sjc"]))
    assert reg["stretch"]["forearm"] == pytest.approx(230.0 / np.linalg.norm(reg["nodes_mesh_mm"]["wrist"] - reg["nodes_mesh_mm"]["elbow"]))
    assert reg["hand"]["vertices"] > 0 and reg["hand"]["stretch"] == 1.0 and reg["mirror_gap_mm"] == pytest.approx(0.0, abs=1e-9)


def test_mutation_a_skin_vertex_node_fails_the_d1_check(monkeypatch):
    t = TwoTubes()
    monkeypatch.setattr(arms, "d1_nodes", lambda V, F, sjc, elbow, wrist, L: {"elbow": elbow, "wrist": wrist, "residual_rms_mm": {}})
    reg = arms.registration(t.inp, t.tb, t.rm, t.sheet(), "R")
    with pytest.raises(AssertionError):
        _assert_nodes_on_the_centre_lines(t, reg)


def test_the_d1_fit_is_one_pass_on_the_decisions_window():
    assert (arms.SECTION_TRIM_MM, arms.SECTION_STEP_MM) == (40.0, 5.0)
    t = TwoTubes()
    c = arms.centre_line(t.V, t.F, arms.ArmFrame(t.sjc, t.u, 1.0), 230.0)
    assert (c["first_station_mm"], c["last_station_mm"], c["stations"]) == (-40.0, -190.0, 31)
    assert max(c["residual_rms_mm"]) < 0.05


FOREARM_AXIS = np.array([0.68, -0.47, -0.56])


def _assert_anterior_preserving(u):
    u = np.asarray(u, float) / np.linalg.norm(u)
    x = np.array([1.0, 0.0, 0.0]) - u[0] * u
    assert arms.ArmFrame(np.zeros(3), u).R @ (x / np.linalg.norm(x)) == pytest.approx([1.0, 0.0, 0.0], abs=1e-9)


@pytest.mark.parametrize("u", ([0.01, -0.68, -0.73], FOREARM_AXIS, [0.2, 0.5, -0.84]))
def test_d4_the_frame_keeps_the_axis_proper_and_the_projected_anterior_is_its_x(u):
    _assert_anterior_preserving(u)
    f = arms.ArmFrame(np.zeros(3), u)
    assert f.R @ (np.asarray(u) / np.linalg.norm(u)) == pytest.approx([0, 0, -1], abs=1e-12)
    assert np.linalg.det(f.R) == pytest.approx(1.0) and f.R @ f.R.T == pytest.approx(np.eye(3), abs=1e-12)


def test_mutation_the_shortest_arc_roll_fails_the_d4_check(monkeypatch):
    monkeypatch.setattr(arms, "rotation_to_frame", arms.rotation_to_down)
    with pytest.raises(AssertionError):
        _assert_anterior_preserving(FOREARM_AXIS)


def _assert_the_gate_is_8_percent(t):
    arms.registration(t.inp, t.tb, t.rm, t.sheet(1.07, 1.07), "R")
    with pytest.raises(StopAndAsk, match="upper_arm"):
        arms.registration(t.inp, t.tb, t.rm, t.sheet(1.10, 1.0), "R")


def test_the_arms_take_the_8_percent_gate():
    assert arms.ARM_STRETCH_GATE == 0.08
    t = TwoTubes()
    _assert_the_gate_is_8_percent(t)
    assert arms.registration(t.inp, t.tb, t.rm, t.sheet(), "R")["gate"] == {"upper_arm": 0.08, "forearm": 0.08}


def test_mutation_the_retired_sigma_gate_fails_the_8_percent_check(monkeypatch):
    monkeypatch.setattr(arms, "ARM_STRETCH_GATE", 2 * 17.3 / 255.2)                  # the retired 2 x 17.3 mm / L: 13.6%, so a 10% stretch would pass
    with pytest.raises(pytest.fail.Exception):
        _assert_the_gate_is_8_percent(TwoTubes())


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
