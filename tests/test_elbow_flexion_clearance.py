"""analysis/elbow_flexion_clearance.py (upper-arm characterization brief, T7 and Amendment 1, T7a and T7b): the forearm envelope swept over elbow flexion against the
upper arm's, with the elbow joint zones excluded (M1, M2), the keep-out (M3), the sculpt reassembly and twist (T7b, V2), and the validation gates V1 to V4.

The synthetic tests (V1) build fields of known shape (field.Segment with an exact cylinder distance) and need no cache. The output tests read the committed JSON; the one
that rebuilds it needs data/envelope/cache/ (gitignored) and skips without it, saying so."""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("elbow_flexion_clearance", ROOT / "analysis" / "elbow_flexion_clearance.py")
efc = importlib.util.module_from_spec(SPEC)
sys.modules["elbow_flexion_clearance"] = efc
SPEC.loader.exec_module(efc)

from envelope import field, foreign, joint_poses  # noqa: E402

H = 2.0                  # the synthetic voxel, the cache's
VOXEL_TOL = H            # the brief: each synthetic case within one voxel
OUT = ROOT / efc.OUT
CACHE = [ROOT / "data" / "envelope" / "cache" / f"{n}.npz" for n in (efc.HOST, efc.OWNER)]


def cylinder(r, length, z_top=0.0, margin=40.0, half_width=None, h=H, x0=0.0):
    """A field.Segment of an infinite cylinder of radius r about the line x = x0, y = 0 (sd exact), with the region the slab z in [z_top - length, z_top]."""
    hw = half_width or (abs(x0) + r + margin)
    n = [int(np.ceil(2 * hw / h)), int(np.ceil(2 * (r + margin) / h)), int(np.ceil((length + 2 * margin) / h))]
    o = np.array([-hw, -(r + margin), z_top - length - margin])
    C = [o[i] + h * (np.arange(n[i]) + 0.5) for i in range(3)]
    X, Y, Z = np.meshgrid(*C, indexing="ij")
    sd = r - np.hypot(X - x0, Y)
    zw = np.clip((C[2] - (z_top - length)) / h + 0.5, 0, 1) * np.clip((z_top - C[2]) / h + 0.5, 0, 1)
    region = np.broadcast_to((zw > 0)[None, None, :], sd.shape) & (sd > -h)
    return field.Segment(o=o, h=h, sd=sd, region=np.ascontiguousarray(region), length=float(length), z_top=float(z_top), zweight=zw)


def translate(d):
    T = np.eye(4)
    T[:3, 3] = d
    return T


def hinge(theta_deg, at):
    """Rotation by theta about -y (the model's elbow axis, flexion positive) about the point `at`, as a 4x4."""
    from scipy.spatial.transform import Rotation
    T = np.eye(4)
    T[:3, :3] = Rotation.from_rotvec(np.radians(theta_deg) * np.array([0.0, -1.0, 0.0])).as_matrix()
    T[:3, 3] = at
    return T


# ---- V1: the measure on shapes of known answer ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("t", [0.0, 5.0])
def test_v1_parallel_cylinders_side_by_side_read_their_analytic_gap(t):
    """Two radius-20 cylinders with axes 50 mm apart: the skins 10 mm apart, the 5 mm inner shells 20 mm."""
    a, b = cylinder(20.0, 200.0), cylinder(20.0, 200.0)
    m = efc.measure(efc.Clipped(a, t), efc.Clipped(b, t), translate([50.0, 0.0, 0.0]))["m"]
    assert -m == pytest.approx(10.0 + 2 * t, abs=VOXEL_TOL)


@pytest.mark.parametrize("t", [0.0, 5.0])
def test_v1_overlapping_cylinders_read_their_overlap(t):
    a, b = cylinder(20.0, 200.0), cylinder(20.0, 200.0)
    m = efc.measure(efc.Clipped(a, t), efc.Clipped(b, t), translate([30.0, 0.0, 0.0]))["m"]
    assert m == pytest.approx(10.0 - 2 * t, abs=VOXEL_TOL)


@pytest.mark.parametrize("gap", [0.0, 6.0, 20.0])
def test_v1_an_axial_gap_across_the_slab_planes_is_read_from_the_region_not_the_skin(gap):
    """Coaxial cylinders end to end: the sd of the extended solid says nothing about the cut, so the region boundary must carry the gap."""
    a, b = cylinder(20.0, 100.0), cylinder(20.0, 100.0)
    m = efc.measure(efc.Clipped(a, 5.0), efc.Clipped(b, 5.0), translate([0.0, 0.0, -100.0 - gap]))["m"]
    assert -m == pytest.approx(gap, abs=VOXEL_TOL)


def test_v1_reassembly_of_one_solid_cut_in_two_reads_zero():
    """One cylinder cut at z = -100 into two fields, each in its own frame, posed by the exact relative transform: the parts reassemble, m = 0 at t = 0 and 5 (V2's logic)."""
    a, b = cylinder(20.0, 100.0), cylinder(20.0, 100.0)
    for t in (0.0, 5.0):
        assert efc.measure(efc.Clipped(a, t), efc.Clipped(b, t), translate([0.0, 0.0, -100.0]))["m"] == pytest.approx(0.0, abs=VOXEL_TOL)


@pytest.mark.parametrize("zone", [25.0, 35.0])
def test_v1_zone_exclusion_at_zero_leaves_two_parallel_faces_two_zones_apart(zone):
    """V3's logic: the host's last `zone` mm and the owner's first `zone` mm excluded; at zero the faces are 2 x zone apart."""
    a, b = cylinder(20.0, 100.0), cylinder(20.0, 100.0)
    m = efc.measure(efc.Clipped(a, 5.0, zone, "distal"), efc.Clipped(b, 5.0, zone, "proximal"), translate([0.0, 0.0, -100.0]))["m"]
    assert -m == pytest.approx(2 * zone, abs=VOXEL_TOL)


def test_v1_hinged_pair_at_90_degrees_reads_the_measures_analytic_value():
    """Radius 20, t = 5 (rho = 15), zones 25, hinged at the host's end node by 90 degrees. The inner sets are a truncated vertical cylinder and a truncated horizontal one.
    In the hinge plane, with a the distance from the host's axis and b the height above the host's end plane: S_host = min(rho - a, b - 25) <= (b - a - 10) / 2 and
    S_owner = min(rho - b, a - 25) <= (a - b - 10) / 2, so m <= -10, reached at a = b = 20. The Euclidean separation of the two corners is sqrt(2) x 10 = 14.1: at a corner
    the measure reads closer than the Euclidean distance, never farther (conservative)."""
    a, b = cylinder(20.0, 100.0), cylinder(20.0, 100.0)
    m = efc.measure(efc.Clipped(a, 5.0, 25.0, "distal"), efc.Clipped(b, 5.0, 25.0, "proximal"), hinge(90.0, [0.0, 0.0, -100.0]))["m"]
    assert m == pytest.approx(-10.0, abs=VOXEL_TOL)
    assert -m <= math.sqrt(2) * 10.0 + 1e-9


def test_v1_the_measure_is_symmetric_in_host_and_owner():
    a, b = cylinder(20.0, 100.0), cylinder(18.0, 120.0)
    T = hinge(60.0, [0.0, 0.0, -100.0])
    m1 = efc.measure(efc.Clipped(a, 5.0), efc.Clipped(b, 5.0), T)["m"]
    m2 = efc.measure(efc.Clipped(b, 5.0), efc.Clipped(a, 5.0), np.linalg.inv(T))["m"]
    assert m1 == pytest.approx(m2, abs=VOXEL_TOL)


@pytest.fixture(scope="module")
def model():
    return foreign.load_model()


def test_v1_sign_mutation_through_the_sweep(model):
    """An anterior block on the host at the elbow: flexion (the polarity file's sign) swings the owner into it; the reversed sign swings it away. The sweep must see the
    difference, so a sign error in the pose cannot pass silently."""
    a = cylinder(20.0, 100.0, half_width=140.0)
    X = a.o[0] + H * (np.arange(a.sd.shape[0]) + 0.5)
    Z = a.o[2] + H * (np.arange(a.sd.shape[2]) + 0.5)
    block = (X[:, None, None] > 60.0) & (X[:, None, None] < 120.0) & (Z[None, None, :] < -60.0) & (Z[None, None, :] > -100.0)
    a.region = np.ascontiguousarray(a.region | (np.broadcast_to(block, a.sd.shape)))
    a.sd = np.where(np.broadcast_to(block, a.sd.shape), 30.0, a.sd)
    b = cylinder(15.0, 120.0, z_top=0.0)
    L = 100.0
    fore = efc.Clipped(b, 5.0, 25.0, "proximal")             # the owner's zone out, so the shared end plane does not decide
    ok = efc.sweep_inner(model, efc.Clipped(a, 5.0), fore, [90.0], origin=[0.0, 0.0, -L])
    bad = efc.sweep_inner(model, efc.Clipped(a, 5.0), fore, [90.0], origin=[0.0, 0.0, -L], polarity={"elbow_right": -1})
    assert ok[0]["m"] > 0.0 > bad[0]["m"]
    assert bad[0]["m"] == pytest.approx(-10.0, abs=VOXEL_TOL)  # backwards: the owner's face at x = -25 against the host's inner radius 15


def test_v1_poses_are_the_models_hinge_moved_to_the_given_origin(model):
    T = efc.poses(model, [0.0, 90.0], origin=[0.0, 0.0, -100.0])
    assert np.allclose(T[0][:3, 3], [0.0, 0.0, -100.0]) and np.allclose(T[0][:3, :3], np.eye(3))
    assert joint_poses.apply(T[1], [[0.0, 0.0, -50.0]])[0] == pytest.approx([50.0, 0.0, -100.0], abs=1e-9)


# ---- M3: the keep-out ------------------------------------------------------------------------------------------------------------------------

def test_keep_out_is_empty_when_nothing_crosses_and_located_where_it_does():
    """Radius 20, t = 5, zones 10, flexed 0 to 90 degrees: a point of the owner's inner set inside the host's (z >= -90) has u >= (10 + d cos a) / sin a > 0 in the hinge plane,
    so x = d sin a + u cos a > 0: the keep-out is on the host's anterior side only, and spans stations above the zone only."""
    a, b = cylinder(20.0, 100.0), cylinder(20.0, 100.0)
    ca, cb = efc.Clipped(a, 5.0, 10.0, "distal"), efc.Clipped(b, 5.0, 10.0, "proximal")
    none = efc.keep_out(ca, cb, [translate([0.0, 0.0, -100.0])])
    assert none["host"]["volume_l"] == 0.0 and none["owner"]["volume_l"] == 0.0
    hit = efc.keep_out(ca, cb, [hinge(a_, [0.0, 0.0, -100.0]) for a_ in range(0, 91, 5)])
    h = hit["host"]
    assert h["volume_l"] > 0.0
    assert h["sides_l"]["ant"] > 0.0 and h["sides_l"]["post"] == 0.0           # flexion swings the owner anterior: it takes the host's anterior side only
    assert h["stations_mm"][1] <= a.length - 10.0 + H / 2                        # never inside the excluded zone (station = z_top - z)
    assert 0.0 < h["deepest_mm"] <= 15.0 + H                                     # no deeper than the inner radius
    assert hit["owner"]["volume_l"] > 0.0


# ---- T7b: the sculpt decomposition -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flex,carry,twist", [(40.0, 0.0, 0.0), (40.0, 8.0, 0.0), (40.0, 5.0, 3.0), (30.0, -4.0, -2.5)])
def test_decomposition_recovers_flexion_carrying_angle_and_twist(model, flex, carry, twist):
    from scipy.spatial.transform import Rotation
    Rf = joint_poses.relative_transforms(model, "upper_arm_right", "forearm_right", ["elbow_right"], [[flex]])[0][:3, :3]
    R = Rf @ Rotation.from_euler("XZ", [carry, twist], degrees=True).as_matrix()
    d = efc.decompose(model, R)
    assert d["flexion_deg"] == pytest.approx(flex, abs=1e-9)
    assert d["carrying_deg"] == pytest.approx(carry, abs=1e-9)
    assert d["twist_deg"] == pytest.approx(twist, abs=1e-9)
    assert d["axes_angle_deg"] == pytest.approx(math.degrees(math.acos(R[2, 2])), abs=1e-9)


# ---- the committed output ------------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def committed():
    if not OUT.exists():
        pytest.fail(f"{efc.OUT} is not committed")
    return json.loads(OUT.read_text(encoding="utf-8"))


def test_output_names_the_current_ledgers_and_its_banner(committed):
    import yaml
    assert committed["generated_by"] == "analysis/elbow_flexion_clearance.py" and committed["inputs"] == f"sha256:{efc.inputs_hash(ROOT)}"
    for n in (efc.HOST, efc.OWNER):
        led = yaml.safe_load((ROOT / "data" / "envelope" / f"{n}.yaml").read_text(encoding="utf-8"))
        assert committed["provenance"]["ledgers"][n]["inputs_sha256_12"] == led["inputs_sha256_12"]
        assert committed["provenance"]["ledgers"][n]["mesh_file"] == led["mesh_file"]


def test_output_v_gates_pass_and_the_basis_zone_is_the_ledgers(committed):
    v = committed["validation"]
    assert v["v2_reassembly"]["pass"] and all(abs(x) <= v["v2_reassembly"]["tolerance_mm"] for x in v["v2_reassembly"]["m_mm"].values())
    assert v["v3_zero_pose"]["pass"] and abs(v["v3_zero_pose"]["inner_separation_mm"] - v["v3_zero_pose"]["expected_mm"]) <= v["v3_zero_pose"]["tolerance_mm"]
    hc = committed["hardware_clearance"]
    assert hc["zone_h_mm"] == committed["provenance"]["zone_h_mm"]["value"] == 25.0
    assert [r["angle_deg"] for r in hc["rows"]] == [r["angle_deg"] for r in committed["skin"]["rows"]] == [r["angle_deg"] for r in committed["no_exclusion"]["rows"]]
    assert {s["zone_h_mm"] for s in committed["sensitivity"]["rows"]} == {35.0, 50.0} and committed["sensitivity"]["label"].startswith("sensitivity")


def test_the_literal_table_angles_are_memo_64s(committed):
    want = [0.0, 30.0, 60.0, 90.0] + [float(a) for a in range(120, 158)]
    assert [r["angle_deg"] for r in committed["no_exclusion"]["rows"]] == want


@pytest.mark.slow
def test_a_fresh_build_equals_the_committed_file_byte_for_byte():
    """V4. Needs the envelope cache (gitignored)."""
    missing = [str(p.relative_to(ROOT)) for p in CACHE if not p.exists()]
    if missing:
        pytest.skip(f"the envelope cache is absent ({', '.join(missing)}); run `fy envelope build` to rebuild it; the committed file is checked against the ledgers above")
    assert efc.render(efc.build(ROOT)) == OUT.read_text(encoding="utf-8")


def test_the_script_takes_no_arguments():
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "analysis" / "elbow_flexion_clearance.py"), "--out", "x"], capture_output=True, cwd=ROOT)
    assert r.returncode == 2
