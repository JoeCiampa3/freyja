"""analysis/shoulder_axis_search.py (shoulder axis search brief): where the shoulder gimbal's fixed axis points.

V1 (the conditioning formula) and V7 (the humeral-direction convention against the model) come first; nothing downstream is meaningful
if either fails.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from input_sets import SHOULDER  # noqa: E402
SPEC = importlib.util.spec_from_file_location("shoulder_axis_search", ROOT / "analysis" / "shoulder_axis_search.py")
sas = importlib.util.module_from_spec(SPEC)
sys.modules["shoulder_axis_search"] = sas
SPEC.loader.exec_module(sas)

TOL = 1e-9  # the brief's tolerance for V1, V3, V4 and V7


# ---- d(phi, theta) ------------------------------------------------------------------------------------------------------------------

def test_d_of_phi_theta_gives_the_brief_s_reference_directions():
    assert np.allclose(sas.d_of(0.0, 0.0), (0, 0, -1), atol=1e-15)
    assert np.allclose(sas.d_of(0.0, 90.0), (0, -1, 0), atol=1e-15)
    assert np.allclose(sas.d_of(90.0, 90.0), (1, 0, 0), atol=1e-15)
    assert np.allclose(sas.d_of(37.0, 180.0), (0, 0, 1), atol=1e-15)
    assert np.allclose(sas.d_of(0.0, 90.0, side="left"), (0, 1, 0), atol=1e-15)


def test_phi_theta_inverts_d_of():
    for phi in (-170.0, -65.0, 0.0, 30.0, 105.0, 179.0):
        for theta in (1.0, 45.0, 90.0, 135.0, 179.0):
            for side in ("right", "left"):
                p, t = sas.phi_theta(sas.d_of(phi, theta, side=side), side=side)
                assert p == pytest.approx(phi, abs=1e-9) and t == pytest.approx(theta, abs=1e-9)


# ---- the gimbal ---------------------------------------------------------------------------------------------------------------------

def test_the_neutral_arm_has_q1_zero_and_the_zero_pose_points_along_d0():
    u1 = sas.unit((-0.3, -0.5, 0.8))
    d0, u2 = sas.gimbal_frame(u1)
    assert abs(d0 @ u1) < 1e-15 and abs(u2 @ u1) < 1e-15 and abs(u2 @ d0) < 1e-15
    assert np.allclose(sas.gimbal_fk(u1, 0.0, 0.0), d0, atol=1e-15)
    q1, q2 = sas.gimbal_ik(u1, np.array([0.0, 0.0, -1.0]))
    assert q1 == pytest.approx(0.0, abs=1e-12)
    assert abs(math.sin(q2)) == pytest.approx(abs(u1[2]), abs=1e-12)


def test_ik_then_fk_reproduces_random_directions_and_q2_is_on_the_branch():
    rng = np.random.default_rng(1)
    for _ in range(2000):
        u1, d = sas.unit(rng.normal(size=3)), sas.unit(rng.normal(size=3))
        q1, q2 = sas.gimbal_ik(u1, d)
        assert -math.pi / 2 <= q2 <= math.pi / 2
        assert np.linalg.norm(sas.gimbal_fk(u1, q1, q2) - d) < TOL


def test_v1_sigma_min_of_the_axis_matrix_equals_the_closed_form():
    """V1: on 10 000 random (u1, d) pairs, the SVD of [u1, u2(q1), d] gives sqrt(1 - |u1.d|) to 1e-9."""
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(10_000):
        u1, d = sas.unit(rng.normal(size=3)), sas.unit(rng.normal(size=3))
        q1, q2 = sas.gimbal_ik(u1, d)
        J = sas.axis_matrix(u1, q1, q2)
        assert np.allclose(J[:, 0], u1) and np.linalg.norm(J[:, 2] - d) < TOL
        s = np.linalg.svd(J, compute_uv=False)
        worst = max(worst, abs(s.min() - sas.sigma_min(u1, d)))
    print(f"V1 worst |SVD sigma_min - sqrt(1-|u1.d|)| over 10000 pairs: {worst:.3e}")
    assert worst < TOL


# ---- the inputs file ----------------------------------------------------------------------------------------------------------------

def _entries(node, path=()):
    """Every {value, unit, ...} entry under a mapping, with its path."""
    if isinstance(node, dict) and "value" in node:
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _entries(v, path + (k,))


def test_the_inputs_file_holds_b1_and_s1_to_s3_with_sources_and_flags():
    doc = yaml.safe_load((ROOT / sas.INPUTS).read_text(encoding="utf-8"))
    assert doc["schema"] == "shoulder-axis-search-inputs/1" and doc["side"] == "right"
    entries = dict(_entries(doc))
    assert entries, "no entries"
    for path, e in entries.items():
        assert set(e) >= {"value", "unit", "source"}, path
        assert e["source"], path
    b1 = doc["required"]["B1"]
    assert (b1["plane_min"]["value"], b1["plane_max"]["value"], b1["elevation_min"]["value"], b1["elevation_max"]["value"]) == (-65, 105, 0, 108)
    assert not any(e.get("source_needed") for p, e in entries.items() if p[:2] == ("required", "B1"))
    assert len(b1["cautions"]) == 2
    sens = doc["sensitivity"]
    assert (sens["S1"]["plane"]["value"], sens["S1"]["elevation_max"]["address"]) == (30, "snapshot#/shoulder_flexion")
    assert (sens["S2"]["plane"]["value"], sens["S2"]["elevation"]["value"]) == (130, 90)
    assert (sens["S3"]["plane"]["value"], sens["S3"]["elevation"]["value"]) == (20, 120)
    for name in ("S1", "S2", "S3"):
        typed = [e for p, e in entries.items() if p[:2] == ("sensitivity", name)]
        assert typed and all(e.get("source_needed") is True for e in typed), name


def test_the_rom_addresses_resolve_to_the_snapshot_values():
    rom = sas.read_rom(ROOT)
    assert rom == {"snapshot#/shoulder_flexion": 172.0, "snapshot#/shoulder_extension": 57.3, "snapshot#/shoulder_abduction": 182.7}


# ---- V7: the convention against the model -------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def model():
    return mujoco.MjModel.from_xml_path(str(ROOT / "sim" / "models" / "freyja.xml"))


def _humeral_direction(m, side: str, angles_deg: dict):
    """The upper arm's elbow-ward axis in the thorax frame, from mujoco forward kinematics with every other joint at its qpos0."""
    d = mujoco.MjData(m)
    d.qpos[:] = m.qpos0
    for name, deg in angles_deg.items():
        d.qpos[m.jnt_qposadr[m.joint(name).id]] = math.radians(deg)
    mujoco.mj_kinematics(m, d)
    th = d.xmat[m.body("thorax").id].reshape(3, 3)
    elbow = d.xpos[m.body(f"forearm_{side}").id] - d.xpos[m.body(f"upper_arm_{side}").id]
    return th.T @ (elbow / np.linalg.norm(elbow))


def _polarity():
    return yaml.safe_load((ROOT / "checks" / "joint_polarity.yaml").read_text(encoding="utf-8"))["joints"]


def _signs(side: str):
    """+1 or -1 for flexion on shoulder_fe and for abduction on shoulder_aa, read from the polarity file's `positive` field."""
    pol = _polarity()
    fe, aa = pol[f"shoulder_fe_{side}"]["positive"], pol[f"shoulder_aa_{side}"]["positive"]
    assert fe in ("flexion", "extension") and aa in ("adduction", "abduction")
    return (1 if fe == "flexion" else -1), (1 if aa == "abduction" else -1)


@pytest.mark.parametrize("side", ["right", "left"])
def test_v7_the_humeral_direction_formula_matches_the_model(model, side):
    flex, abd = _signs(side)
    poses = [
        ({}, (0.0, 0.0)),                                                   # all joints 0: straight down
        ({f"shoulder_fe_{side}": 90.0 * flex}, (90.0, 90.0)),               # flexion 90: anterior
        ({f"shoulder_aa_{side}": 90.0 * abd}, (0.0, 90.0)),                 # abduction 90 (sign from the polarity file): lateral
        ({f"shoulder_fe_{side}": -30.0 * flex}, (-90.0, 30.0)),             # extension 30: posterior-down
    ]
    worst = 0.0
    for angles, (phi, theta) in poses:
        got = _humeral_direction(model, side, angles)
        want = sas.d_of(phi, theta, side=side)
        worst = max(worst, float(np.linalg.norm(got - want)))
        assert np.linalg.norm(got - want) < TOL, (side, angles, got, want)
    print(f"V7 {side}: worst |FK - d(phi, theta)| over 4 poses: {worst:.3e}")


def test_v7_the_left_arm_is_the_y_mirror_of_the_right(model):
    fr, ar = _signs("right")
    fl, al = _signs("left")
    for (r_ang, l_ang) in [({}, {}), ({"shoulder_fe_right": 90 * fr}, {"shoulder_fe_left": 90 * fl}),
                           ({"shoulder_aa_right": 90 * ar}, {"shoulder_aa_left": 90 * al}),
                           ({"shoulder_fe_right": -30 * fr}, {"shoulder_fe_left": -30 * fl})]:
        r, l = _humeral_direction(model, "right", r_ang), _humeral_direction(model, "left", l_ang)
        assert np.linalg.norm(l - r * np.array([1, -1, 1])) < TOL


def test_v7_the_model_chain_is_the_one_the_brief_describes(model):
    """fe first with its axis along -y in the thorax for both arms; aa about x; ier about z (the Purpose section)."""
    for side in ("right", "left"):
        names = [model.joint(j).name for j in range(model.njnt) if model.joint(j).name.startswith("shoulder_") and model.joint(j).name.endswith(side)]
        assert names == [f"shoulder_fe_{side}", f"shoulder_aa_{side}", f"shoulder_ier_{side}"]
        assert np.allclose(model.joint(f"shoulder_fe_{side}").axis, (0, -1, 0))
        assert np.allclose(np.abs(model.joint(f"shoulder_aa_{side}").axis), (1, 0, 0))
        assert np.allclose(np.abs(model.joint(f"shoulder_ier_{side}").axis), (0, 0, 1))


# ---- T2: the required set -----------------------------------------------------------------------------------------------------------

def test_arc_values_step_from_zero_and_keep_an_end_off_the_step():
    a = sas.arc_values(172.0, 0.5)
    assert len(a) == 345 and a[0] == 0.0 and a[-1] == 172.0
    a = sas.arc_values(57.3, 0.5)
    assert len(a) == 116 and a[-2] == 57.0 and a[-1] == 57.3
    a = sas.arc_values(182.7, 0.5)
    assert len(a) == 367 and a[-2] == 182.5 and a[-1] == 182.7


@pytest.fixture(scope="module")
def required():
    rom = sas.read_rom(ROOT)
    return rom, sas.read_inputs(ROOT), sas.entries(rom, sas.read_inputs(ROOT), "right")


def test_the_arcs_are_the_brief_s_formulas_and_b1_is_its_box(required):
    _, _, es = required
    b = es["A1"].params["beta_deg"]
    assert np.allclose(es["A1"].d, np.column_stack([np.sin(np.radians(b)), 0 * b, -np.cos(np.radians(b))]), atol=1e-15)
    b = es["A2"].params["beta_deg"]
    assert np.allclose(es["A2"].d, np.column_stack([-np.sin(np.radians(b)), 0 * b, -np.cos(np.radians(b))]), atol=1e-15)
    a = es["A3"].params["alpha_deg"]
    assert np.allclose(es["A3"].d, np.column_stack([0 * a, -np.sin(np.radians(a)), -np.cos(np.radians(a))]), atol=1e-15)
    assert (len(es["A1"].d), len(es["A2"].d), len(es["A3"].d), len(es["B1"].d)) == (345, 116, 367, 171 * 109)
    assert (es["B1"].phi.min(), es["B1"].phi.max(), es["B1"].theta.min(), es["B1"].theta.max()) == (-65, 105, 0, 108)
    assert len(es["S1"].d) == 345 and set(es["S1"].phi) == {30.0}
    assert (es["S2"].phi[0], es["S2"].theta[0], es["S3"].phi[0], es["S3"].theta[0]) == (130, 90, 20, 120)


def test_widening_b1_moves_only_its_plane_bounds(required):
    rom, inputs, _ = required
    w = sas.entries(rom, inputs, "right", b1_widen_deg=10.0)["B1"]
    assert (w.phi.min(), w.phi.max(), w.theta.min(), w.theta.max()) == (-75, 115, 0, 108)


# ---- T2: the floor and the search ---------------------------------------------------------------------------------------------------

def test_floor_numbers_give_sigma_angle_and_gain():
    f = sas.floor_numbers(math.cos(math.radians(30.0)))
    assert f["angle_deg"] == pytest.approx(30.0, abs=1e-12)
    assert f["sigma_min"] == pytest.approx(math.sqrt(1 - math.cos(math.radians(30.0))), abs=1e-15)
    assert f["rate_gain"] == pytest.approx(1 / f["sigma_min"])
    assert sas.floor_numbers(1.0)["rate_gain"] is None


def test_the_fibonacci_grid_is_on_the_upper_hemisphere():
    U = sas.fibonacci_hemisphere(1000)
    assert U.shape == (1000, 3) and np.allclose(np.linalg.norm(U, axis=1), 1.0) and (U[:, 2] > 0).all()


def test_the_search_finds_the_line_farthest_from_the_three_coordinate_axes():
    """Known answer: the farthest lines from x, y and z are the four body diagonals, at arccos(1/sqrt 3) = 54.7356 deg from each axis; each is
    a three-point vertex. The search must return one of them exactly and find all four as basins (they are 70.5 deg apart)."""
    r = sas.search(np.eye(3), 2000)
    u, g = r["basins"][0]
    diagonals = [sas.unit(s) for s in ((1, 1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1))]
    assert min(sas.line_angle_deg(u, d) for d in diagonals) < 1e-9
    assert len(r["basins"]) >= 4 and all(min(sas.line_angle_deg(b, d) for b, _ in r["basins"][:4]) < 1e-9 for d in diagonals)
    assert sas.floor_numbers(g)["angle_deg"] == pytest.approx(math.degrees(math.acos(1 / math.sqrt(3))), abs=1e-9)
    c = sas.certificate(u, np.eye(3))
    assert c["active"] == 3 and c["local_maximum"]


def test_the_search_reaches_the_equidistant_vertex_of_a_skewed_triple():
    """Three lines, two of them orthogonal and the third tilted: the best line is equidistant from all three (a three-point vertex), reached
    along the ridge between the first two."""
    D = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], sas.unit((0.2, 0.1, 1.0))])
    u, g = sas.search(D, 500)["basins"][0]
    c = np.abs(D @ u)
    assert c.max() - c.min() < 1e-12
    assert sas.certificate(u, D)["local_maximum"]


def test_refinement_leaves_the_ridge_where_a_compass_search_crawled(required):
    """Regression: on the arcs alone (R without B1), a 16-direction compass search seeded at (-0.707, -0.707, -0.003) moved 1e-6 rad at a
    time along the ridge between the A1 and A3 lines and hit its iteration cap. Refinement must finish at a certified local maximum."""
    _, _, es = required
    D = sas.unique_dirs(sas.stack(es, ("A1", "A2", "A3")))
    u, g = sas.refine(sas.unit((-0.70710342, -0.70710342, -0.00308406)), D)
    assert sas.floor_numbers(g)["angle_deg"] >= 45.0
    assert sas.certificate(u, D)["local_maximum"]


def test_the_certificate_rejects_a_point_that_is_not_a_local_maximum():
    D = np.eye(3)
    c = sas.certificate(sas.unit((1.0, 1.0, 0.2)), D)
    assert not c["local_maximum"]


def test_v2_baseline_the_model_chain_is_singular_on_the_abduction_arc(required):
    _, _, es = required
    b = sas.baseline(es, sas.unique_dirs(sas.stack(es, sas.BASIS)))
    assert b["floor"]["sigma_min"] <= math.sqrt(1 - math.cos(math.radians(0.5)))
    assert any(p["entry"] == "A3" and p["alpha_deg"] == 90.0 for p in b["at"])
    assert b["pass"]


# ---- T2: the committed result (V3, V4, V5 and the certificate) ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def result():
    return json.loads((ROOT / sas.OUT).read_text(encoding="utf-8"))


def test_the_result_names_its_generator_and_inputs(result):
    assert result["schema"] == "shoulder-axis-search/1" and result["generated_by"] == "analysis/shoulder_axis_search.py"
    assert result["inputs"] == f"sha256:{sas.inputs_hash(ROOT)}"


def test_the_committed_optimum_s_floor_reproduces_on_a_fresh_required_set(result, required):
    _, _, es = required
    u = np.array(result["optimum"]["u1"])
    g = float(sas.gmax(u, sas.stack(es, sas.BASIS))[0])
    assert sas.floor_numbers(g)["sigma_min"] == pytest.approx(result["optimum"]["floor"]["sigma_min"], abs=1e-9)
    assert result["optimum"]["certificate"]["local_maximum"]
    assert all(b["floor"]["sigma_min"] <= result["optimum"]["floor"]["sigma_min"] for b in result["basins"])


def test_v3_round_trip_on_the_optimum(result, required):
    _, _, es = required
    u = np.array(result["optimum"]["u1"]) / np.linalg.norm(result["optimum"]["u1"])
    rt = sas.round_trip(u, sas.stack(es, sas.BASIS + ("S1", "S2", "S3")))
    print(f"V3: {rt['directions']} directions, {rt['excluded']} within 1 deg of +/-u1, max |FK(IK(d)) - d| = {rt['max_error']:.3e}")
    assert rt["max_error"] < TOL and rt["excluded"] == result["v3_round_trip"]["excluded"]


def test_v4_the_left_optimum_is_the_mirror_of_the_right(result):
    v4 = result["v4_mirror"]
    print(f"V4: mirror difference {v4['mirror_difference']:.3e}, sigma difference {v4['sigma_difference']:.3e}")
    assert np.abs(sas.mirror(v4["u1_left"]) - np.array(result["optimum"]["u1"])).max() < TOL
    assert v4["sigma_difference"] < TOL and v4["pass"]


def test_v5_the_20000_and_80000_seeded_optima_agree(result):
    v5 = result["v5_convergence"]
    print(f"V5: optima {v5['angle_between_deg']:.3e} deg apart, floors {v5['sigma_difference']:.3e} apart in sigma")
    assert v5["angle_between_deg"] < 0.1 and v5["sigma_difference"] < 1e-6 and v5["pass"]


@pytest.mark.inputs(*SHOULDER)
def test_v6_a_fresh_build_equals_the_committed_file_byte_for_byte():
    """V6: the committed file was written by a separate run; an in-process build must equal it byte for byte."""
    assert sas.render(sas.build(ROOT)) == (ROOT / sas.OUT).read_text(encoding="utf-8")
