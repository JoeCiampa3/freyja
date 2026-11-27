"""analysis/shoulder_room.py (shoulder-room brief, Group B with Amendments 1 and 2): gates G-B1 to G-B6 and the units the measures are built from.

The synthetic tests (G-B2, the bounds of R6 to R8, R9's axis exit, runs and shaft test, G-B6's ball disc) need no cache. The output tests read the committed
data/shoulder/room.json; the one that rebuilds it (G-B5) needs data/envelope/cache/ (gitignored) and skips without it, saying so."""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("shoulder_room", ROOT / "analysis" / "shoulder_room.py")
sr = importlib.util.module_from_spec(SPEC)
sys.modules["shoulder_room"] = sr
SPEC.loader.exec_module(sr)

from envelope import field, synthetic  # noqa: E402

H = 2.0                          # the synthetic voxel, the cache's
VOXEL_TOL = H                    # G-B2: within one voxel
OUT = ROOT / sr.OUT
CACHE = [ROOT / "data" / "envelope" / "cache" / f"{n}.npz" for n in (sr.THORAX, sr.ARM)]
T = 5.0


# ---- G-B2: the bisection on a synthetic cylinder of known answer ---------------------------------------------------------------------------

R_CYL, L_CYL, Z_MID = 45.0, 300.0, -150.0


@pytest.fixture(scope="module")
def cylinder_room():
    v, f = synthetic.frustum(R_CYL, R_CYL, 80.0, -L_CYL - 80.0)
    seg = field.build_segment(v, f, length=L_CYL, voxel=H, z_top=0.0, margin=40.0)
    body = sr.Body("cylinder", seg, (0.0, 0.0, 0.0))
    return sr.Room(body, None, None, T, (0.0, 0.0, Z_MID), 0.0, [])


def analytic_r(s, tilt_deg):
    """The largest disc (thickness DISC_LENGTH_MM) normal to u = (sin a, 0, cos a), centred at s u from the cylinder axis point (0, 0, Z_MID), whose every
    point lies at least T inside a cylinder of radius R_CYL about z: the distance of a disc point from the axis is sqrt((d + r cos a cos p)^2 + r^2 sin^2 p) with
    d = |s| sin a plus half the thickness times sin a, maximised over p numerically."""
    a = math.radians(tilt_deg)
    d = abs(s) * math.sin(a) + 0.5 * sr.DISC_LENGTH_MM * math.sin(a)
    p = np.linspace(0.0, 2 * np.pi, 3601)

    def worst(r):
        return float(np.sqrt((d + r * math.cos(a) * np.cos(p)) ** 2 + (r * np.sin(p)) ** 2).max())
    lo, hi = 0.0, R_CYL * 2
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if worst(mid) <= R_CYL - T else (lo, mid)
    return lo


@pytest.mark.parametrize("tilt_deg", [0.0, 30.0])
def test_gb2_the_bisection_reproduces_the_analytic_revolution_budget_within_one_voxel(cylinder_room, tilt_deg):
    a = math.radians(tilt_deg)
    u = np.array([math.sin(a), 0.0, math.cos(a)])
    s_values = [-40.0, -20.0, 0.0, 20.0, 40.0]
    got = sr.profile(cylinder_room, u, s_values, "T", False)
    want = [analytic_r(s, tilt_deg) for s in s_values]
    assert max(abs(g - w) for g, w in zip(got, want)) <= VOXEL_TOL, list(zip(s_values, got, want))
    if tilt_deg == 0.0:
        assert all(abs(w - (R_CYL - T)) < 1e-6 for w in want)


def test_a_disc_outside_the_body_has_no_room_and_a_feasible_bracket_stops(cylinder_room):
    assert sr.disc_radius(cylinder_room, (0.0, 120.0, Z_MID), np.array([0.0, 0.0, 1.0]), "T", False) == 0.0
    with pytest.raises(sr.StopAndAsk):
        sr.bisect(lambda r: True, 10.0)


def test_the_shape_frame_puts_the_shape_axis_on_u():
    for u in ([0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [-0.43808827, -0.57087653, 0.69439086]):
        u = np.asarray(u) / np.linalg.norm(u)
        R = sr.frame_about(u)
        assert np.allclose(R[:, 2], u) and np.allclose(R.T @ R, np.eye(3)) and abs(np.linalg.det(R) - 1.0) < 1e-12


# ---- R6 to R8: the bounds, on stub bodies of known answer ---------------------------------------------------------------------------------

class Stub:
    """A body for the bound tests: sd = 100 - |p| (a sphere of skin 100 mm about the origin), held where `hold(p)` says, every point in its slab."""

    def __init__(self, hold):
        self.hold = hold

    def held(self, P):
        return np.array([bool(self.hold(p)) for p in np.atleast_2d(P)])

    def sd(self, P):
        return 100.0 - np.linalg.norm(np.atleast_2d(P), axis=1)

    def in_slab(self, P):
        return np.ones(len(np.atleast_2d(P)), bool)


R_B_STUB = 20.0


@pytest.fixture()
def stub_room():
    """The thorax holds x >= 0 and the union (thorax and arm by region) everything, both but a hole: the slab 2 < x < 4 for y > 0 (the wedge). The
    ball of radius 20 about the origin covers part of the hole."""
    def hole(p):
        return 2.0 < p[0] < 4.0 and p[1] > 0.0
    thorax = Stub(lambda p: p[0] >= 0.0 and not hole(p))                     # as skin_field's: what the thorax holds, the union holds
    union = Stub(lambda p: not hole(p))
    return sr.Room(thorax, Stub(lambda p: p[0] < 0.0), union, T, (0.0, 0.0, 0.0), R_B_STUB, [])


def test_r6_n_is_the_region_union_and_the_ball_so_a_point_in_the_wedge_inside_the_ball_is_room(stub_room):
    inside, outside = np.array([[3.0, 10.0, 0.0]]), np.array([[3.0, 30.0, 0.0]])
    assert stub_room.margin(inside, "N", False)[0] >= 0.0
    e, code = stub_room.excess(outside, "N", False)
    assert e[0] < 0.0 and code[0] == sr.CUT                                    # R8: outside B the cut binds as usual


def test_r6_s_is_inside_n_at_every_point(stub_room):
    rng = np.random.default_rng(0)
    P = rng.uniform(-110.0, 110.0, size=(4000, 3))
    assert np.all(stub_room.margin(P, "S", False) <= stub_room.margin(P, "N", False) + 1e-12)


def test_r7_s_counts_a_point_on_the_ball_and_takes_t_off_once(stub_room):
    on_ball = np.array([[-R_B_STUB, 0.0, 0.0]])                                # beyond the thorax region, on the ball's surface
    beyond = np.array([[-R_B_STUB - 0.01, 0.0, 0.0]])
    assert stub_room.margin(on_ball, "S", False)[0] == pytest.approx(0.0)
    assert stub_room.margin(beyond, "S", False)[0] < 0.0
    with pytest.raises(ValueError):
        stub_room.margin(on_ball, "S_literal", False)                          # R7: the brief's literal formula is not used


def test_r8_a_binding_is_reported_outside_the_ball_only(stub_room):
    P = sr.placed(sr.disc(25.0), (0.0, 0.0, 0.0), np.array([0.0, 0.0, 1.0]))  # rim beyond the ball, crossing the hole
    b = stub_room.binding(P, "N", False)
    assert b["surface"] == sr.CUT
    assert np.linalg.norm(b["point_mm"]) > R_B_STUB


# ---- R9: the axis's exit from the skin, the runs and the shaft test ----------------------------------------------------------------------

def test_r9_the_axis_exit_is_where_the_axis_point_leaves_the_skin(cylinder_room):
    """The axis -x from the synthetic cylinder's axis: it leaves the skin (sd = 0) at s = -R_CYL."""
    room = sr.Room(cylinder_room.T, None, None, T, (0.0, 0.0, Z_MID), 0.0, [])
    ex = sr.axis_exit(room, np.array([1.0, 0.0, 0.0]))
    assert ex["surface"] == sr.SKIN_T
    assert abs(ex["s_mm"] + R_CYL) <= VOXEL_TOL / 2


def test_r9_coaxial_runs_give_each_runs_largest_diameter():
    s = [0.0, -2.0, -4.0, -6.0, -8.0, -10.0, -12.0]
    r = [0.0, 3.0, 12.5, 4.0, 0.0, 26.0, 27.0]
    runs = sr.coaxial_runs(s, r)
    assert [x["s_range_mm"] for x in runs] == [[-2.0, -6.0], [-10.0, -12.0]]
    assert [x["max_diameter_mm"] for x in runs] == [25.0, 54.0]
    assert [x["s_at_max_mm"] for x in runs] == [-4.0, -12.0]


@pytest.mark.parametrize("r, exists, blocked, path_min", [
    ([0.0, 0.0, 0.0, 6.0, 5.0, 30.0], True, None, (5.0, -8.0)),       # the ball carries the shaft to s = -4, then r >= 5 to a run >= 25
    ([0.0, 0.0, 0.0, 6.0, 4.5, 30.0], False, -8.0, (4.5, -8.0)),      # r < 5 at s = -8 before r reaches 25
    ([0.0, 0.0, 0.0, 6.0, 6.0, 6.0], False, None, (6.0, -6.0)),       # never reaches 25: no target
])
def test_r9_the_shaft_test_needs_radius_5_from_the_ball_to_a_run_of_25(r, exists, blocked, path_min):
    s = [0.0, -2.0, -4.0, -6.0, -8.0, -10.0]
    R_B = 7.0                                             # sqrt((4 + 0.5)^2 + 5^2) = 6.7 <= 7: the ball holds the shaft to s = -4; at -6, sqrt(6.5^2 + 25) = 8.2 > 7
    res = sr.shaft_test(s, r, R_B)
    assert res["exists"] is exists
    assert res["blocked_at_s_mm"] == blocked
    assert (res["path_min_r_mm"], res["path_min_at_s_mm"]) == path_min      # the least r outside the ball on the way to the target (or the end)


# ---- G-B6: the ball's disc ---------------------------------------------------------------------------------------------------------------

def test_gb6_the_balls_disc_radius_takes_the_disc_thickness_into_account():
    assert sr.ball_disc_radius(29.33, 0.0) == pytest.approx(math.sqrt(29.33 ** 2 - 0.25))
    assert sr.ball_disc_radius(29.33, -4.0) == pytest.approx(math.sqrt(29.33 ** 2 - 4.5 ** 2))
    assert sr.ball_disc_radius(10.0, -12.0) == 0.0


# ---- G-B4 and the summaries, on profiles of known answer -----------------------------------------------------------------------------------

def test_gb4_the_bound_order_check_finds_a_pose_proof_bound_above_the_neutral_one_and_reservations_that_add_room():
    ok = {"N_off": [30.0, 40.0], "N_on": [20.0, 40.0], "S_off": [25.0, 30.0], "S_on": [20.0, 30.0]}
    assert sr.bound_order(ok) == []
    bad = dict(ok, S_off=[31.0, 30.0])
    assert (0, "S_off", "N_off") in sr.bound_order(bad)
    bad = dict(ok, N_on=[20.0, 41.0])
    assert (1, "N_on", "N_off") in sr.bound_order(bad)


def test_runs_and_windows():
    s = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    r = [10.0, 25.0, 31.0, 33.0, 22.0, 5.0]
    assert sr.runs_at_least(s, r, 20.0) == [[2.0, 8.0]]
    assert sr.runs_at_least(s, r, 30.0) == [[4.0, 6.0]]
    assert sr.window_budget(s, r, 2.0) == (31.0, [4.0, 6.0])
    assert sr.window_budget(s, r, 6.0) == (22.0, [2.0, 8.0])


# ---- the committed output ------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def room():
    return json.loads(OUT.read_text(encoding="utf-8"))


def test_the_output_carries_the_banner_keys_and_is_current_with_its_inputs(room):
    assert room["generated_by"] == "analysis/shoulder_room.py"
    assert room["inputs"] == f"sha256:{sr.inputs_hash(ROOT)}"
    raw = OUT.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")


def test_gb1_the_centre_is_the_envelope_sjc_with_the_models_y_and_z_and_u1_is_the_named_unit_vector(room):
    g = room["gates"]["G-B1"]
    assert g["pass"] and g["yz_pass"] and g["lateral"]["pass"]
    assert abs(g["y_difference_mm"]) <= sr.SJC_TOL_MM and abs(g["z_difference_mm"]) <= sr.SJC_TOL_MM
    assert abs(g["lateral"]["skin_from_midline_mm"] - sr.MEMO59_LATERAL_MM) <= VOXEL_TOL
    for role in ("basis", "comparison"):
        a = room["axes"][role]
        u = np.asarray(sr.read_address(ROOT, sr.AXES[role]), float)
        assert a["u1"]["as_read"] == [float(x) for x in u]
        assert abs(np.linalg.norm(a["u1"]["used"]) - 1.0) <= sr.UNIT_TOL and a["u1"]["pass"]
    assert room["axes"]["basis"]["u1"]["address"].endswith("#/basins/1/u1")
    assert room["axes"]["comparison"]["u1"]["address"].endswith("#/basins/0/u1")
    assert room["axes"]["comparison"]["role"] == "comparison, not basis"


def test_gb3_the_oracles_ball_agrees_with_the_skin_distance_from_the_field(room):
    g = room["gates"]["G-B3"]
    assert g["pass"] and abs(g["R_B_oracle_mm"] - g["R_B_field_mm"]) <= VOXEL_TOL


def test_gb4_on_the_committed_profiles_of_both_basins(room):
    for role in ("basis", "comparison"):
        a = room["axes"][role]
        assert sr.bound_order(a["m1"]["r_mm"]) == []
        t = a["r9"]["r_mm"]
        assert all(on <= off for on, off in zip(t["T_on"], t["T_off"]))
        assert room["gates"]["G-B4"][role]["pass"]
    assert room["gates"]["G-B4"]["pass"]


def test_gb6_s_maximum_is_the_balls_disc_within_the_bisection_where_the_ball_binds(room):
    for role in ("basis", "comparison"):
        g = room["gates"]["G-B6"][role]
        if g["binding_at_max"] == sr.BALL:
            assert 0.0 <= g["residual_mm"] <= sr.BISECT_TOL_MM
        assert g["pass"]
    assert room["gates"]["G-B6"]["pass"]


def test_r6_the_unheld_sheet_is_reported(room):
    v = room["unheld_sheet"]
    assert v["within_40_mm_cm3"] > 0 and v["inside_ball_cm3"] <= v["within_40_mm_cm3"]


def test_r9_reports_the_exit_the_runs_and_the_shaft_test_for_both_basins(room):
    for role in ("basis", "comparison"):
        r9 = room["axes"][role]["r9"]
        assert r9["exit"]["s_mm"] < 0
        assert r9["s_mm"][0] == 0.0 and r9["s_mm"][-1] >= r9["exit"]["s_mm"]
        for state in ("off", "on"):
            assert isinstance(r9["shaft_test"][state]["exists"], bool)
            assert all("binding" in run for run in r9["runs"][state])


# ---- G-B5: a fresh build ------------------------------------------------------------------------------------------------------------------

def test_gb5_a_fresh_build_is_byte_identical_to_the_committed_file():
    """The committed file is one build (`python analysis/shoulder_room.py`) and this is a second: equality is G-B5's two builds byte-identical and
    the committed output equal to a fresh build. Memo 70 records two consecutive builds compared byte for byte as well."""
    missing = [p.name for p in CACHE if not p.exists()]
    if missing:
        pytest.skip(f"the envelope cache is absent ({', '.join(missing)}); run `fy envelope build` to rebuild it; the committed file is checked by the tests above")
    assert sr.render(sr.build(ROOT)) == OUT.read_text(encoding="utf-8")
