"""Volume-extractor brief 5, items 2 to 5: the trunk map, the axilla from the layer topology, the accounting of cells (planes, overlap split, shoulder planes, zones, arm
clean-up), pinch stations, design numbers and closure, on synthetic bodies with known answers. Offline."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import bodies, field, ledger, register  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402
from envelope.synthetic import frustum  # noqa: E402


# ---- the map -----------------------------------------------------------------------------------------------------------------------

def make_map():
    axial = register.AxialMap(mesh=(10.0, 20.0, 50.0), sheet=(10.0, 21.0, 52.0))        # identity-like legs: stretches 1.1, 1.0333.., 1.0667
    shear = register.Shear(z=(10.0, 20.0, 50.0), dx=(1.0, 1.0, 1.0), dy=(2.0, 2.0, 2.0))
    reg = SimpleNamespace(axial=axial, shear=shear, mesh_nodes={"ajc": 10.0, "kjc": 20.0, "hjc": 50.0})
    return bodies.TrunkMap(reg, mesh=(50.0, 150.0, 300.0, 400.0), sheet=(52.0, 152.0, 332.0, 422.0))


def test_the_map_is_continuous_at_the_hip_invertible_and_slope_one_in_the_pelvis_and_abdomen():
    tm = make_map()
    z = np.array([5.0, 10.0, 35.0, 50.0, 100.0, 150.0, 220.0, 300.0, 350.0, 400.0, 450.0])
    assert np.allclose(tm.inverse(tm.forward(z)), z)
    assert tm.forward(50.0) == pytest.approx(52.0) and tm.forward(50.0 + 1e-9) == pytest.approx(52.0)
    assert tm.forward(150.0) == pytest.approx(152.0) and tm.forward(100.0) == pytest.approx(102.0)      # slope 1 from the HJC to the TJC
    assert tm.forward(300.0) == pytest.approx(332.0) and tm.forward(400.0) == pytest.approx(422.0)
    assert tm.forward(450.0) == pytest.approx(472.0)                                                        # slope 1 above the vertex


def test_the_slope_is_the_stretch_of_each_stretch_of_the_body():
    tm = make_map()
    assert tm.slope(100.0) == pytest.approx(1.0) and tm.slope(220.0) == pytest.approx(180.0 / 150.0) and tm.slope(350.0) == pytest.approx(0.9)
    assert tm.slope(35.0) == pytest.approx(31.0 / 30.0)                                    # the legs' own thigh stretch
    assert tm.slope(420.0) == 1.0


def test_apply_moves_x_and_y_by_the_legs_shear_and_z_by_the_map():
    tm = make_map()
    out = tm.apply(np.array([[0.0, 0.0, 220.0], [5.0, -7.0, 100.0]]))
    assert np.allclose(out[0], [1.0, 2.0, tm.forward(220.0)]) and np.allclose(out[1], [6.0, -5.0, 102.0])
    assert tm.shear_hjc == (1.0, 2.0)


# ---- the axilla --------------------------------------------------------------------------------------------------------------------

def profile(n=100, h=2.0, arms=(10, 60), gap=None, right=True, left=True, left_top=None):
    layers = []
    for k in range(n):
        pieces = [(40000.0, 0.0, True)]
        if arms[0] <= k < arms[1] and right and k != gap:
            pieces.append((3000.0, -200.0, False))
        if arms[0] <= k < (left_top or arms[1]) and left:
            pieces.append((3000.0, 200.0, False))
        pieces.append((80.0, 150.0, False))             # a fingertip sliver: below the minimum, ignored
        layers.append(pieces)
    return {"h": h, "z0": h * np.arange(n), "layers": layers}


def test_the_axilla_is_the_top_of_the_highest_layer_with_a_separate_arm_piece_on_each_side():
    a = bodies.axilla(profile(), apex_mm=0.0)
    assert a["right"]["top_mm"] == pytest.approx(120.0) and a["left"]["top_mm"] == pytest.approx(120.0) and a["level_mm"] == pytest.approx(120.0)
    assert a["merged_below_axilla"] is False and a["right"]["first_layer_mm"] == pytest.approx(20.0)
    b = bodies.axilla(profile(left_top=55), apex_mm=0.0)
    assert b["level_mm"] == pytest.approx(120.0) and b["right_minus_left_mm"] == pytest.approx(10.0)


def test_an_arm_vanishing_below_the_axilla_is_reported_as_a_merge():
    a = bodies.axilla(profile(gap=30), apex_mm=0.0)
    assert a["merged_below_axilla"] is True and a["right"]["layers_missing_between"] == 1


def test_no_arm_piece_on_a_side_stops_and_asks():
    with pytest.raises(StopAndAsk, match="axilla"):
        bodies.axilla(profile(left=False), apex_mm=0.0)
    with pytest.raises(StopAndAsk, match="axilla"):
        bodies.axilla(profile(), apex_mm=300.0)         # nothing above the apex


# ---- the accounting ---------------------------------------------------------------------------------------------------------------

H = 2.0
SHEET = {"ajc": 10.0, "kjc": 20.0, "hjc": 50.0, "ljc": 101.0, "tjc": 150.0, "cjc": 330.0, "vertex": 420.0}


def synthetic_body():
    """Core x 10..50, y -30..30, z 0..400 (mm, cells of 2 mm); two arm bars y +-(60..80), x 20..40, z 0..200; a shoulder bridge z 200..240, y 30..80 (right and left), x 20..40.
    The raster origin is (0, -100, 0). Arm vertices sit on the bars' lower half only, so the bars' upper half is a leak for the nearest-vertex rule."""
    o = np.array([0.0, -100.0, 0.0])
    inside = np.zeros((30, 100, 210), bool)
    cell = lambda x0, x1, y0, y1, z0, z1: (slice(int(x0 / H), int(x1 / H)), slice(int((y0 + 100) / H), int((y1 + 100) / H)), slice(int(z0 / H), int(z1 / H)))
    inside[cell(10, 50, -30, 30, 0, 400)] = True
    for s in (1, -1):
        y0, y1 = (60, 80) if s > 0 else (-80, -60)
        inside[cell(20, 40, y0, y1, 0, 200)] = True
        b0, b1 = (30, 80) if s > 0 else (-80, -30)
        inside[cell(20, 40, b0, b1, 200, 240)] = True
    raster = SimpleNamespace(inside=inside, h=H, o=o)
    pts = lambda x0, x1, y0, y1, z0, z1: np.array([[x, y, z] for x in np.arange(x0 + 1, x1, 6.0) for y in np.arange(y0 + 1, y1, 6.0) for z in np.arange(z0 + 1, z1, 6.0)], float)
    arm_v = np.vstack([pts(20, 40, 60, 80, 0, 100), pts(20, 40, -80, -60, 0, 100)])
    core_v = np.vstack([pts(10, 50, -30, 30, 0, 400), pts(20, 40, 30, 80, 200, 240), pts(20, 40, -80, -30, 200, 240)])
    V = np.vstack([arm_v, core_v])
    arm_mask = np.r_[np.ones(len(arm_v), bool), np.zeros(len(core_v), bool)]
    return raster, V, arm_mask


@pytest.fixture(scope="module")
def acc():
    raster, V, arm = synthetic_body()
    tm = make_map()
    tm = bodies.TrunkMap(tm.reg, mesh=(50.0, 150.0, 300.0, 400.0), sheet=(52.0, 152.0, 332.0, 422.0))
    sheet = {**SHEET, "hjc": 52.0, "ljc": 103.0, "tjc": 152.0, "cjc": 332.0, "vertex": 422.0}
    return bodies.classify(raster, V, arm, tm, sheet, apex_mm=0.0, axilla_mm=200.0, lateral_mm=50.0, sjc_below_mm=88.0, h_zone=25.0), raster


def test_the_class_volumes_add_up_to_the_raster_and_split_by_overlap_where_a_plane_falls_inside_a_cell(acc):
    a, raster = acc
    U = a["volume_unconformed_l"]
    assert sum(U.values()) == pytest.approx(raster.inside.sum() * H ** 3 / 1e6, rel=1e-12)
    assert a["raster_total_l"] == pytest.approx(sum(U.values()), rel=1e-12)
    # the LJC plane is at 103 (conformed), 101 in the mesh: the pelvis is the core between 50 and 101 (51 mm of 2400 mm2), the cell layer 100-102 is split by overlap
    assert U["pelvis"] == pytest.approx(2400.0 * 51.0 / 1e6, rel=1e-9)
    assert U["abdomen"] == pytest.approx(2400.0 * 49.0 / 1e6, rel=1e-9)               # 101 to 150
    assert a["volume_l"]["pelvis"] == pytest.approx(2400.0 * 51.0 / 1e6, rel=1e-9)    # slope 1 below the TJC


def test_the_thorax_is_conformed_by_its_stretch_and_the_shoulder_beyond_the_plane_is_not_the_thorax(acc):
    a, _ = acc
    s = 180.0 / 150.0
    bridge_in = 2 * (50 - 30) * 20 * 40 / 1e6          # y 30..50 of the bridge, both sides, x 20 deep, z 200..240
    bridge_out = 2 * (80 - 50) * 20 * 40 / 1e6
    assert a["volume_unconformed_l"]["thorax"] == pytest.approx((2400.0 * 150.0 + bridge_in * 1e6) / 1e6, rel=1e-9)
    assert a["volume_l"]["thorax"] == pytest.approx(a["volume_unconformed_l"]["thorax"] * s, rel=1e-9)
    assert a["volume_unconformed_l"]["shoulder_R"] == pytest.approx(bridge_out / 2, rel=1e-9) and a["volume_unconformed_l"]["shoulder_L"] == pytest.approx(bridge_out / 2, rel=1e-9)
    assert a["volume_l"]["head_neck"] == pytest.approx(2400.0 * 100.0 / 1e6 * 0.9, rel=1e-9)


def test_arm_cells_are_the_bars_including_the_leaked_half_the_vertex_rule_labelled_as_core(acc):
    a, _ = acc
    assert a["volume_unconformed_l"]["arms"] == pytest.approx(2 * 20 * 20 * 200 / 1e6, rel=1e-9)
    assert 0.02 < a["leaked_arm_cells_reclassified_l"] < 0.16        # the bars above the reach of their own vertices, found by being separate pieces


def test_joint_zones_hold_the_slab_below_and_above_a_plane_and_the_ownership_is_the_body_above(acc):
    a, _ = acc
    z = a["zones"]["tjc"]                                   # the TJC plane at 152: 127..152 abdomen (core 2400), 152..177 thorax (core 2400 x 1.2)
    assert z["below"]["abdomen"] == pytest.approx(2400.0 * 25.0 / 1e6, rel=1e-9) and "thorax" not in z["below"]
    assert z["above"]["thorax"] == pytest.approx(2400.0 * 25.0 / 1e6, rel=1e-9) and "abdomen" not in z["above"]
    t = bodies.zone_table(a)
    assert t["abdomen"]["without_all_l"] == pytest.approx(t["abdomen"]["with_zones_l"] - sum(t["abdomen"]["slab_l"].values()))
    assert t["thorax"]["without_all_and_spheres_l"] <= t["thorax"]["without_all_l"] and t["ownership"].startswith("a cell on a joint-centre plane belongs to the body above")


# ---- design numbers ---------------------------------------------------------------------------------------------------------------

def test_pinch_stations_are_interior_local_minima_that_stand_out():
    s = np.arange(0.0, 200.0, 10.0)
    r = np.where(s < 100, 60.0 - 0.1 * s, 40.0 + 0.2 * (s - 100)) - np.exp(-((s - 100) / 20.0) ** 2) * 15.0
    rows = [{"s_mm": float(a), "cheb_r_mm": float(b)} for a, b in zip(s, r)]
    p = bodies.pinch_stations(rows)
    assert [x["station_mm"] for x in p] == [100.0] and p[0]["prominence_mm"] > bodies.PINCH_PROMINENCE_MM
    assert bodies.pinch_stations([{"s_mm": float(a), "cheb_r_mm": 50.0 - 0.1 * a} for a in s]) == []         # a monotonic radius has no pinch


def cylinder_result(name, mass, R=45.0, L=200.0):
    v, f = frustum(R, R, 60.0, -L - 60.0)
    seg = field.build_segment(v, f, length=L, voxel=2.0, z_top=0.0, margin=40.0)
    return SimpleNamespace(name=name, seg=seg, mass_kg=mass)


def test_design_numbers_of_a_cylinder_are_its_volume_density_and_radius():
    res = cylinder_result("pelvis", 10.0)
    rows = ledger.rows_for(res.seg, "trunk")
    d = bodies.design_numbers(res, rows)
    v = np.pi * 45.0 ** 2 * 200.0 / 1e6
    assert d["skin_volume_l"] == pytest.approx(v, rel=0.01) and d["required_density_skin_kg_per_l"] == pytest.approx(10.0 / d["skin_volume_l"])
    assert d["inner_volume_l"]["t5"] == pytest.approx(np.pi * 40.0 ** 2 * 200.0 / 1e6, rel=0.01)
    assert d["required_density_inner_kg_per_l"]["t5"] > d["required_density_inner_kg_per_l"]["t3"] > d["required_density_skin_kg_per_l"]
    assert d["min_inscribed_radius"]["r_mm"] == pytest.approx(45.0, abs=1.0) and d["pinch_stations"] == []


def test_the_pair_is_one_budget_over_the_summed_volumes():
    a = {"skin_volume_l": 4.0, "inner_volume_l": {"t5": 3.0}, "sheet_mass_kg": 2.0}
    b = {"skin_volume_l": 5.0, "inner_volume_l": {"t5": 4.0}, "sheet_mass_kg": 9.0}
    p = bodies.pair_numbers(a, b)
    assert p["skin_volume_l"] == 9.0 and p["sheet_mass_kg"] == 11.0 and p["required_density_skin_kg_per_l"] == pytest.approx(11.0 / 9.0)
    assert p["required_density_inner_kg_per_l"]["t5"] == pytest.approx(11.0 / 7.0)


def test_the_head_and_necks_minimum_radius_skips_the_crown_cap():
    v, f = frustum(10.0, 60.0, 60.0, -260.0)           # narrow at the top (the "crown", station 0), widening downwards: the crown would win without the rule
    seg = field.build_segment(v, f, length=200.0, voxel=2.0, z_top=0.0, margin=40.0)
    res = SimpleNamespace(name="head_neck", seg=seg, mass_kg=4.0)
    d = bodies.design_numbers(res, ledger.rows_for(seg, "trunk"))
    assert d["min_inscribed_radius"]["from_station_mm"] == bodies.FREE_END_MM and d["min_inscribed_radius"]["station_mm"] >= bodies.FREE_END_MM


# ---- closure ----------------------------------------------------------------------------------------------------------------------

def test_closure_sums_the_built_bodies_and_the_remainder_and_the_shares_add_to_one():
    zero = {c: 0.0 for c in bodies.CLASSES}
    acc = {"volume_unconformed_l": {**zero, "arms": 3.0, "shoulder_R": 0.3, "shoulder_L": 0.3, "pelvis": 5.0}, "volume_l": {**zero, "arms": 3.0, "shoulder_R": 0.3, "shoulder_L": 0.3, "pelvis": 4.9},
           "raster_total_l": 52.0}
    built = {"pelvis": 4.9, "thighs": 40.0}
    c = bodies.closure(built, acc, 52.0)
    assert c["sum_l"] == pytest.approx(4.9 + 40.0 + 3.6) and c["relative_difference"] == pytest.approx((48.5 - 52.0) / 52.0)
    assert c["within_tolerance"] is False and bodies.closure({"pelvis": 4.9, "thighs": 43.6}, acc, 52.0)["within_tolerance"] is True
    assert sum(c["shares"].values()) == pytest.approx(1.0) and c["share_denominator_l"] == c["sum_l"]
    assert c["conform_effect_l"] == pytest.approx(-0.1) and c["remainder_l"] == {"arms": 3.0, "shoulder_R": 0.3, "shoulder_L": 0.3}


# ---- the trunk ledger --------------------------------------------------------------------------------------------------------------

def test_the_trunk_ledger_uses_left_and_right_not_medial_and_lateral():
    assert ledger.direction_names("trunk") == {0: "ant", 45: "ant_left", 90: "left", 135: "post_left", 180: "post", 225: "post_right", 270: "right", 315: "ant_right"}
    res = cylinder_result("abdomen", 3.0, L=60.0)
    rows = ledger.rows_for(res.seg, "trunk")
    r = rows[2]
    assert {"hw_ant_mm", "hw_post_mm", "hw_left_mm", "hw_right_mm", "r_left_mm", "r_ant_right_mm"} <= set(r) and "hw_med_mm" not in r
    assert r["hw_left_mm"] == pytest.approx(45.0, abs=0.7) and r["hw_right_mm"] == pytest.approx(45.0, abs=0.7)
    assert set(ledger.rows_for(res.seg, "right")[0]) >= {"hw_med_mm", "hw_lat_mm"}              # the legs' schema is unchanged


# ---- the shoulder joint centre from the sheet (brief 6, item 0b) ----------------------------------------------------------------------

def test_the_sjc_is_the_sheets_upper_arm_origin_and_the_dumas_2015_one_is_a_cross_check_only():
    from envelope import masses
    table = masses.load_dumas_table1(REPO)
    sh = SimpleNamespace(thorax_length_mm=328.759098448, sjc_mm=(13.8136749663, -192.328859146, -77.5690978875))
    s = bodies.sjc(table, sh)
    assert s["lateral_mm"] == pytest.approx(192.328859146) and s["below_cjc_mm"] == pytest.approx(77.5690978875) and s["ahead_of_cjc_mm"] == pytest.approx(13.8136749663)
    d = s["dumas2015"]                                                      # 178 and 84 mm of Table 1, scaled by 328.76 / 313
    assert d["lateral_mm"] == pytest.approx(178.0 * 328.759098448 / 313.0) and d["below_cjc_mm"] == pytest.approx(84.0 * 328.759098448 / 313.0)
    assert s["sheet_minus_dumas_mm"]["lateral"] == pytest.approx(5.3, abs=0.1) and s["sheet_minus_dumas_mm"]["z"] == pytest.approx(10.6, abs=0.1)
    with pytest.raises(StopAndAsk):
        bodies.sjc(table, SimpleNamespace(thorax_length_mm=328.759098448, sjc_mm=(float("nan"),) * 3))


def test_the_sphere_centre_is_the_thorax_centre_line_at_the_cjc_plus_the_sheets_x_offset():
    raster, V, arm = synthetic_body()
    tm = make_map()
    tm = bodies.TrunkMap(tm.reg, mesh=(50.0, 150.0, 300.0, 400.0), sheet=(52.0, 152.0, 332.0, 422.0))
    sheet = {**SHEET, "hjc": 52.0, "ljc": 103.0, "tjc": 152.0, "cjc": 332.0, "vertex": 422.0}
    a = bodies.classify(raster, V, arm, tm, sheet, apex_mm=0.0, axilla_mm=200.0, lateral_mm=50.0, sjc_below_mm=88.0, h_zone=25.0, sjc_ahead_mm=10.0)["spheres"]
    assert a["cjc_x_mesh_mm"] == pytest.approx(30.0, abs=1.0) and a["centre_x_mesh_mm"] == pytest.approx(a["cjc_x_mesh_mm"] + 10.0)
    b = bodies.classify(raster, V, arm, tm, sheet, apex_mm=0.0, axilla_mm=200.0, lateral_mm=50.0, sjc_below_mm=88.0, h_zone=25.0)["spheres"]
    assert b["centre_x_mesh_mm"] == pytest.approx(b["centre_x_thorax_mean_mesh_mm"])      # without an offset: the previous rule (the thorax's mean x at the sphere height)
