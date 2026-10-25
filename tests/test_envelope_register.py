"""Volume-extractor brief 1 (revised Phase B): sheet nodes from the snapshot, ANSUR ratios, mesh features, the piecewise axial stretch plus
horizontal shear, and the Monte Carlo over the mesh node heights."""
import csv
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import anthro, features, field, register  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402
from envelope.synthetic import box, frustum, tube  # noqa: E402

SNAP = REPO / "params" / "snapshot.csv"


# ---- sheet nodes -------------------------------------------------------------------------------------------------------------------

def test_sheet_nodes_chain_up_from_the_scaled_ankle_height_and_agree_with_the_models_own_hip_height():
    n = register.sheet_nodes(SNAP)
    assert abs(n.ajc - 62.7 * 1700 / 1628.5) < 1e-6                         # ADR 0038: the malleolus scales with stature
    assert abs(n.kjc - n.ajc - n.shank_length) < 1e-9 and abs(n.hjc - n.kjc - n.thigh_length) < 1e-9
    assert abs(n.checks["hjc_height_chain_minus_model_mm"]) < 0.01          # pelvis origin + thigh offset in the snapshot gives the same hip height
    assert abs(n.k_pelvis - 1.0504) < 0.0005                                # ADR 0038's factor
    assert n.lateral_y < 0 and abs(n.lateral_y + 92.43) < 0.01              # right side, 88 mm x k from the midplane
    assert abs(n.checks["lateral_y_minus_dumas_times_k_mm"]) < 0.01


def test_a_changed_source_landmark_stops_and_names_the_key(tmp_path):
    rows = list(csv.DictReader(open(SNAP, newline="")))
    for r in rows:
        if r["placeholder"] == "source_landmark_hjc_dumas_isb_z":
            r["value"] = "0.089"
    p = tmp_path / "s.csv"
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["placeholder", "value", "sheet_source"])
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(StopAndAsk, match="source_landmark_hjc_dumas_isb_z"):
        register.sheet_nodes(p)


def test_a_missing_snapshot_key_stops_and_names_it(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("placeholder,value,sheet_source\nthigh_right_mass,9.0,x\n")
    with pytest.raises(StopAndAsk, match="shank_right_length|thigh_right_length"):
        register.sheet_nodes(p)


# ---- ANSUR -------------------------------------------------------------------------------------------------------------------------

def test_ansur_summary_ratios_on_a_tiny_csv(tmp_path):
    girths = ["thighcircumference", "lowerthighcircumference", "calfcircumference", "anklecircumference"]
    cols = ["stature"] + list(anthro.COLUMNS.values()) + girths
    p = tmp_path / "a.csv"
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for stature in (1600.0, 1700.0):
            w.writerow([stature] + [stature * 0.5 + i for i in range(len(anthro.COLUMNS))] + [400.0, 300.0, 350.0, 200.0])
    s = anthro.summarise(p)
    assert s["n"] == 2 and abs(s["stature_mm"]["mean"] - 1650) < 1e-9
    r = s["landmarks"]["crotch"]["ratio"]
    assert abs(r["mean"] - 0.5) < 1e-3
    assert abs(s["trochanterion_minus_crotch_ratio"]["mean"] - (1 / 1650)) < 1e-4       # one millimetre apart in the fixture
    assert s["circumferences_mm"]["calf_maximum"]["mean"] == 350.0


def test_the_tracked_ratios_match_the_published_female_means():
    s = anthro.load_summary(REPO)
    assert s["n"] == 1986 and abs(s["stature_mm"]["mean"] - 1628.5) < 0.1
    assert abs(s["landmarks"]["lateral_malleolus"]["height_mm"]["mean"] - 62.7) < 0.1      # ANSUR II female mean, ADR 0038


# ---- features ----------------------------------------------------------------------------------------------------------------------

def two_flaring_legs():
    """Two cones 100 mm apart (y = -50 and +50) whose radius grows 0.1 mm per mm of height from 20 mm: the gap 60 - 0.2 z closes below 5 mm at z = 275."""
    V, F, off = [], [], 0
    for s in (-1, 1):
        v, f = frustum(20.0, 70.0, 0.0, 500.0)
        v = v.copy()
        v[:, 1] += s * 50.0
        V.append(v), F.append(f + off)
        off += len(v)
    return np.vstack(V), np.vstack(F)


def test_crotch_apex_is_where_the_gap_between_the_legs_closes():
    V, F = two_flaring_legs()
    z, zs, gaps = features.crotch_apex(features.Cuts(V, F), 0.0, 100.0, 450.0)
    assert abs(z - 275.0) < 1.0


def test_knee_level_needs_a_peak_that_stands_out_and_is_not_on_the_band_edge():
    zs = np.arange(400.0, 600.0, 2.0)
    peak = 100 + 8 * np.exp(-((zs - 480) / 15) ** 2)
    k = features.knee_level(zs, peak, 480.0)
    assert k["is_feature"] and abs(k["z_mm"] - 480) < 3
    ramp = 100 + 0.05 * (zs - 400)                    # breadth still rising at the band edge: no feature
    k = features.knee_level(zs, ramp, 480.0)
    assert k["on_band_edge"] and not k["is_feature"]
    flat = np.full_like(zs, 100.0)
    assert not features.knee_level(zs, flat, 480.0)["is_feature"]


def test_sole_plane_and_midline_on_a_symmetric_pair_of_feet():
    V = np.array([[0, -150, 0.0], [10, -120, 2.0], [0, 150, 0.0], [10, 120, 1.0], [0, 0, 900.0]])
    sp = features.sole_plane(V)
    assert sp["z_mm"] == 0.0 and sp["left_foot_lowest_mm"] == 0.0
    assert features.midline_y(V, 0.0) == 0.0


def test_right_section_centroid_of_a_box():
    V, F = box(30, 20, 100, center=(10, -80, 100))
    r = features.BodyRaster(V, F, 150.0)
    area, c, _ = r.right_section(100.0, 0.0)
    assert abs(area - 60 * 40) < 4 * 2 * 2 * 100 / 10 and abs(c[0] - 10) < 2 and abs(c[1] + 80) < 2


# ---- registration ------------------------------------------------------------------------------------------------------------------

def nodes(ajc=60.0, kjc=480.0, hjc=880.0):
    return {"ajc": ajc, "kjc": kjc, "hjc": hjc}


def make_reg(mesh=None, centroids=None, sigmas=None):
    sh = register.sheet_nodes(SNAP)
    cent = centroids or {"ajc": (-30.0, -178.0), "kjc": (-20.0, -134.0), "hjc": (-45.0, -73.0)}
    return register.make_registration(sh, mesh or nodes(), cent, sigmas or {"ajc": 5.0, "kjc": 17.0, "hjc": 17.0})


def test_axial_map_hits_the_nodes_is_invertible_and_has_slope_one_outside():
    reg = make_reg()
    a = reg.axial
    sh = reg.sheet
    assert np.allclose(a.forward([0.0, 60.0, 480.0, 880.0]), [0.0, sh.ajc, sh.kjc, sh.hjc])
    z = np.array([-10.0, 20.0, 300.0, 700.0, 880.0, 950.0])
    assert np.allclose(a.inverse(a.forward(z)), z)
    assert np.isclose(a.forward(950.0) - a.forward(900.0), 50.0) and np.isclose(a.forward(-10.0), -10.0)
    st = a.stretches()
    assert np.isclose(st["thigh"], sh.thigh_length / 400.0) and np.isclose(st["shank"], sh.shank_length / 420.0)


def test_shear_puts_the_three_section_centres_on_one_vertical_line_at_the_sheets_lateral_offset():
    reg = make_reg()
    sh = reg.sheet
    for n, z in nodes().items():
        dx, dy = reg.shear.at(z)
        cx, cy = reg.centroids[n]
        assert np.isclose(cx + dx, reg.target_xy[0]) and np.isclose(cy + dy, sh.lateral_y)
    assert np.isclose(reg.target_xy[0], reg.centroids["kjc"][0])           # the knee keeps its AP position


def test_conform_changes_no_cross_section_a_slanted_cylinder_keeps_its_horizontal_area_and_ends_up_upright():
    R, H = 40.0, 300.0
    v, f = tube(R, 0.0, H + 60, 43)                      # sole-referenced heights 0 to 360, a ring every 8.6 mm
    v = v.copy()
    v[:, 1] += -0.2 * v[:, 2]                            # lean the cylinder sideways: a slanted leg
    mesh = {"ajc": 50.0, "kjc": 200.0, "hjc": 350.0}
    sh = register.sheet_nodes(SNAP)
    reg = register.make_registration(sh, mesh, {n: (0.0, -0.2 * z) for n, z in mesh.items()}, {n: 1.0 for n in mesh})
    w = reg.apply(v)
    lo, hi = float(reg.axial.forward(100.0)), float(reg.axial.forward(350.0))
    a = field.build_segment(v, f, length=250.0, voxel=2.0, z_top=350.0, margin=20.0)
    b = field.build_segment(w, f, length=hi - lo, voxel=2.0, z_top=hi, margin=20.0)
    ar = a.section(350.0 - 275.0).area()
    br = b.section(hi - float(reg.axial.forward(275.0))).area()
    assert abs(br - ar) / ar < 0.01                       # an ellipse of area pi R^2 / cos(theta), unchanged by the conform
    for z in (200.0, 275.0, 350.0):                       # the section centre is on the sheet's lateral line from the knee to the hip
        sec = b.section(hi - float(reg.axial.forward(z)))
        yy = np.broadcast_to(sec.y[None, :], sec.mask().shape)[sec.mask()]      # the centroid: the ellipse has no unique Chebyshev centre
        assert abs(yy.mean() - sh.lateral_y) < 3.0


def test_apply_moves_x_and_y_only_by_the_shear_and_z_only_by_the_axial_map():
    reg = make_reg()
    V = np.array([[5.0, -100.0, 300.0], [0.0, 0.0, 700.0]])
    W = reg.apply(V)
    dx, dy = reg.shear.at(V[:, 2])
    assert np.allclose(W[:, 0], V[:, 0] + dx) and np.allclose(W[:, 1], V[:, 1] + dy)
    assert np.allclose(W[:, 2], reg.axial.forward(V[:, 2]))


# ---- Monte Carlo -------------------------------------------------------------------------------------------------------------------

def profile_of_a_cone(z0=0.0, z1=1000.0):
    z = np.arange(z0, z1, 2.0)
    r = 30.0 + 0.05 * z                                      # radius grows 0.05 mm per mm of height
    return {"z": z, "area": {0.0: np.pi * r * r, 5.0: np.pi * (r - 5) ** 2}, "radius": {0.0: r, 5.0: r - 5}}


def test_monte_carlo_with_no_uncertainty_returns_the_nominal_everywhere():
    reg = make_reg(sigmas={"ajc": 0.0, "kjc": 0.0, "hjc": 0.0})
    mc = register.monte_carlo(profile_of_a_cone(), reg, "thigh", n=20, shells=(0.0, 5.0))
    sp = mc["spread"]["rmin_t0"]
    assert sp["sd"] < 1e-9 and abs(sp["p5"] - mc["nominal"]["rmin_t0"]) < 1e-9
    assert mc["spread"]["volume_t0"]["sd"] < 1e-6


def test_monte_carlo_minimum_radius_sits_at_the_distal_end_and_the_5th_percentile_is_below_nominal():
    reg = make_reg()
    mc = register.monte_carlo(profile_of_a_cone(), reg, "thigh", n=200, shells=(0.0, 5.0))
    nom = mc["nominal"]
    assert nom["rmin_station_t0"] == pytest.approx(reg.sheet.thigh_length, abs=10.0)       # the smallest section is the knee end
    assert mc["spread"]["rmin_t0"]["p5"] < nom["rmin_t0"] and abs(nom["rmin_t5"] - (nom["rmin_t0"] - 5)) < 1e-6
    # volume of a cone slab, scaled by the thigh stretch: analytic check
    z0, z1 = reg.mesh_nodes["kjc"], reg.mesh_nodes["hjc"]
    zz = np.linspace(z0, z1, 4001)
    analytic = reg.axial.stretches()["thigh"] * np.trapezoid(np.pi * (30 + 0.05 * zz) ** 2, zz)
    assert abs(nom["volume_t0"] - analytic) / analytic < 1e-3


def test_monte_carlo_is_reproducible_for_a_seed():
    reg = make_reg()
    a = register.monte_carlo(profile_of_a_cone(), reg, "thigh", n=30, seed=3, shells=(0.0,))
    b = register.monte_carlo(profile_of_a_cone(), reg, "thigh", n=30, seed=3, shells=(0.0,))
    assert a["spread"]["volume_t0"] == b["spread"]["volume_t0"]
