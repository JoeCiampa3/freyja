"""Volume-extractor brief 4: sourced reference densities, the Dumas 2015 Table 1 landmark cuts, the raw-ratio share rows, and the region split used for
the volume attribution. Offline."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import cuts, decompose, features, masses  # noqa: E402
from envelope.synthetic import box  # noqa: E402

ENV = REPO / "data" / "envelope"


# ---- the two authored data files ---------------------------------------------------------------------------------------------------

def test_reference_densities_are_the_winter_rows_with_edition_and_page_left_blank():
    d = json.loads((ENV / "reference_densities.json").read_text())
    assert "Winter" in d["source"] and "Table 4.1" in d["source"]
    assert d["edition"] == "" and d["page"] == ""
    r = d["rows"]
    assert (r["thigh"]["mass_fraction"], r["thigh"]["density_kg_per_l"]) == (0.100, 1.05)
    assert (r["leg"]["mass_fraction"], r["leg"]["density_kg_per_l"]) == (0.0465, 1.09)
    assert (r["foot"]["mass_fraction"], r["foot"]["density_kg_per_l"]) == (0.0145, 1.10)
    assert (r["abdomen"]["mass_fraction"], r["abdomen"]["density_kg_per_l"]) == (0.139, None)
    assert (r["pelvis"]["mass_fraction"], r["pelvis"]["density_kg_per_l"]) == (0.142, None)
    assert (r["abdomen_and_pelvis"]["mass_fraction"], r["abdomen_and_pelvis"]["density_kg_per_l"]) == (0.281, 1.01)
    assert (r["thorax"]["mass_fraction"], r["thorax"]["density_kg_per_l"]) == (0.216, 0.92)
    assert (r["trunk"]["mass_fraction"], r["trunk"]["density_kg_per_l"]) == (0.497, 1.03)


def test_loaded_densities_apply_the_combined_abdomen_and_pelvis_value_to_each():
    dens = masses.load_densities(REPO)
    assert dens == {"thigh": 1.05, "shank": 1.09, "foot": 1.10, "abdomen": 1.01, "pelvis": 1.01, "abdomen_and_pelvis": 1.01}


def test_missing_densities_file_stops_and_names_it(tmp_path):
    from envelope.sheet import StopAndAsk
    with pytest.raises(StopAndAsk, match="reference_densities.json"):
        masses.load_densities(tmp_path)


def test_no_recalled_density_constants_remain():
    assert not hasattr(masses, "REFERENCE_DENSITY") and not hasattr(masses, "PELVIS_REFERENCE_DENSITY") and not hasattr(masses, "ABDOMEN_REFERENCE_DENSITY")
    assert "recalled" not in Path(masses.__file__).read_text().lower()


def test_dumas_table1_holds_the_landmarks_and_reference_lengths_of_the_brief():
    t = json.loads((ENV / "dumas2015_table1_female.json").read_text())
    a = t["segments"]["abdomen"]
    assert a["origin"] == "TJC"
    assert a["landmarks"] == {"MSR10": [-53, -1, 0], "RR10": [32, -21, 134], "RI": [17, -75, 153], "RASIS": [72, -172, 119], "LJC": [0, -121, 0]}
    assert t["segments"]["thorax"]["landmarks"]["TJC"] == [0, -313, 0]
    assert t["reference_length_mm"] == {"thorax": 313, "abdomen": 121}
    assert t["source"] and t["page"]


# ---- cut heights ---------------------------------------------------------------------------------------------------------------------

def test_cut_heights_scale_table1_by_the_sheet_abdomen_over_the_reference_length():
    t = masses.load_dumas_table1(REPO)
    h = cuts.dumas_cut_heights(t, abdomen_length_mm=127.092175438, ljc_mesh_mm=972.5)
    s = 127.092175438 / 121.0
    assert h["scale"] == pytest.approx(s)
    assert h["MSR10"] == pytest.approx(972.5 + 120 * s) and h["RR10"] == pytest.approx(972.5 + 100 * s) and h["RI"] == pytest.approx(972.5 + 46 * s)
    assert h["TJC"] == pytest.approx(972.5 + 127.092175438)
    # the brief's expected mesh-frame values, to its own rounding
    assert h["MSR10"] == pytest.approx(1098.5, abs=0.6) and h["RR10"] == pytest.approx(1077.5, abs=0.6) and h["RI"] == pytest.approx(1020.8, abs=0.6)


def test_cut_heights_use_the_snapshot_abdomen_length():
    from envelope import register
    n = register.sheet_nodes(REPO / "params" / "snapshot.csv")
    assert n.abdomen_length_mm == pytest.approx(127.092175438)


# ---- the share rows ------------------------------------------------------------------------------------------------------------------

def _inp(total=10.0):
    V, F = box(50, 50, 50)                                  # 1 l
    sh = SimpleNamespace(total_mass_kg=total, thigh_mass_kg=1.0, shank_mass_kg=0.5, foot_mass_kg=0.2, pelvis_mass_kg=1.0, abdomen_mass_kg=0.3)
    return SimpleNamespace(V=V, F=F, sheet=sh, stature_mesh=100.0)


def _fake(v):
    return SimpleNamespace(seg=SimpleNamespace(volume=lambda t=0.0, s0=0.0, s1=None: v * 1e6))


def _dumas_volumes():
    v = {"thigh_in": 0.2e6, "thigh_out": 0.1e6, "thigh_crotch": 0.15e6, "pelvis_hjc": 0.3e6, "pelvis_crotch": 0.4e6}
    for top in ("ilio", "ilio_lo", "ilio_hi"):
        v[f"pelvis_hjc_{top}"], v[f"pelvis_crotch_{top}"] = 0.35e6, 0.45e6
    v.update({"lumped": 0.9e6, "lumped_lo": 0.8e6, "lumped_hi": 1.0e6})
    v.update({"abdomen": 0.1e6, "abdomen_rr10": 0.08e6, "abdomen_ri_p10": 0.11e6, "abdomen_ri_m10": 0.09e6, "abdomen_msr10_p10": 0.11e6, "abdomen_msr10_m10": 0.09e6})
    for k, x in (("hjc", 0.3e6), ("crotch", 0.4e6)):
        v[f"pelvis_{k}_ri"], v[f"pelvis_{k}_ri_p10"], v[f"pelvis_{k}_ri_m10"] = x, x + 0.01e6, x - 0.01e6
    v.update({"lumped_msr10": 0.95e6, "lumped_msr10_p10": 0.96e6, "lumped_msr10_m10": 0.94e6, "lumped_rr10": 0.93e6})
    return v


def test_dumas_rows_use_the_combined_density_and_report_the_raw_ratio_as_the_primary_number():
    dens = {"thigh": 1.05, "shank": 1.09, "foot": 1.10, "abdomen": 1.01, "pelvis": 1.01, "abdomen_and_pelvis": 1.01}
    out = masses.report(_inp(), {"thigh": _fake(0.2), "shank": _fake(0.1), "foot": _fake(0.02)}, {"body_fat_fraction": 0.2, "v_lung_l": 0.1},
                        {"volumes_mm3": _dumas_volumes(), "s_crotch_mm": 70.0, "ljc_mesh_mm": 900.0}, dens)
    r = out["rows"]
    a = r["abdomen"]
    assert a["volume_l"] == pytest.approx(0.1) and a["mass_kg_sheet"] == 0.3 and a["reference_density_kg_per_l"] == 1.01
    assert a["ratio"] == pytest.approx((0.3 / 10.0) / (0.1 / 1.0))                      # raw: sheet mass share / sculpt volume share, nothing else
    assert a["sheet_mass_per_skin_volume_kg_per_l"] == pytest.approx(3.0)
    assert r["pelvis_hjc_ri"]["mass_kg_sheet"] == 1.0 and r["pelvis_crotch_ri"]["volume_l"] == pytest.approx(0.4)
    assert r["thigh_pelvis_hjc_ri"]["volume_l"] == pytest.approx(2 * 0.2 + 0.3) and r["thigh_pelvis_crotch_ri"]["volume_l"] == pytest.approx(2 * 0.15 + 0.4)
    tp = r["thigh_pelvis_hjc_ri"]
    assert tp["reference_density_kg_per_l"] == pytest.approx((2 * 1.0 * 1.05 + 1.0 * 1.01) / 3.0)
    lm = r["lumped_msr10"]
    assert lm["mass_kg_sheet"] == pytest.approx(0.3 + 1.0 + 2.0) and lm["volume_l"] == pytest.approx(0.95)
    assert lm["reference_density_kg_per_l"] == pytest.approx(((0.3 + 1.0) * 1.01 + 2.0 * 1.05) / 3.3)
    assert {"abdomen_rr10", "abdomen_ri_p10", "abdomen_msr10_m10", "pelvis_hjc_ri_p10", "lumped_msr10_m10", "lumped_rr10"} <= set(r)
    # the raw ratio does not depend on any density, the normalised one does
    c = lm["cases"]["nominal"]
    assert c["normalised_ratio"] == pytest.approx(lm["ratio"] / c["expected_tissue_ratio"])


def test_a_cut_moving_ten_millimetres_is_reported_as_a_volume_change_per_ten_millimetres():
    out = masses.report(_inp(), {"thigh": _fake(0.2), "shank": _fake(0.1), "foot": _fake(0.02)}, {"body_fat_fraction": 0.2, "v_lung_l": 0.1},
                        {"volumes_mm3": _dumas_volumes(), "s_crotch_mm": 70.0, "ljc_mesh_mm": 900.0},
                        {"thigh": 1.05, "shank": 1.09, "foot": 1.10, "abdomen": 1.01, "pelvis": 1.01, "abdomen_and_pelvis": 1.01})
    d = out["cut_diagnostics_per_10mm_l"]
    assert d["abdomen_ri"] == pytest.approx((0.11 - 0.09) / 2.0) and d["abdomen_msr10"] == pytest.approx((0.11 - 0.09) / 2.0)
    assert d["label"] == "diagnostic"


def test_dempster_lumped_share_against_the_sheet_s():
    out = masses.report(_inp(), {"thigh": _fake(0.2), "shank": _fake(0.1), "foot": _fake(0.02)}, {"body_fat_fraction": 0.2, "v_lung_l": 0.1},
                        {"volumes_mm3": _dumas_volumes(), "s_crotch_mm": 70.0, "ljc_mesh_mm": 900.0},
                        {"thigh": 1.05, "shank": 1.09, "foot": 1.10, "abdomen": 1.01, "pelvis": 1.01, "abdomen_and_pelvis": 1.01})
    d = out["dempster_lumped_check"]
    assert d["dempster_share"] == pytest.approx(0.281 + 2 * 0.100)
    assert d["sheet_share"] == pytest.approx((0.3 + 1.0 + 2.0) / 10.0)


# ---- the region split ------------------------------------------------------------------------------------------------------------------

def _gridbox(hx, hy, hz, center, step=20.0):
    """A closed box whose faces carry a vertex grid (about `step` mm), so nearest-vertex labelling means something; shared edge vertices are merged."""
    pts, idx, tris = [], {}, []

    def vid(p):
        key = tuple(np.round(p, 6))
        if key not in idx:
            idx[key] = len(pts)
            pts.append(np.array(p, float))
        return idx[key]

    for axis in range(3):
        u, w = [a for a in range(3) if a != axis]
        h = (hx, hy, hz)
        nu, nw = max(1, int(round(2 * h[u] / step))), max(1, int(round(2 * h[w] / step)))
        for sign in (-1, 1):
            grid = [[None] * (nw + 1) for _ in range(nu + 1)]
            for i in range(nu + 1):
                for j in range(nw + 1):
                    p = np.zeros(3)
                    p[axis], p[u], p[w] = sign * h[axis], -h[u] + 2 * h[u] * i / nu, -h[w] + 2 * h[w] * j / nw
                    grid[i][j] = vid(p + center)
            for i in range(nu):
                for j in range(nw):
                    a, b, c, d = grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]
                    tris += [(a, b, c), (a, c, d)]
    return np.array(pts), np.array(tris)


def _body():
    """Two leg boxes (0-800), a trunk box (800-1600), a neck (1600-1650), a head box (1650-1800), two detached arm boxes beside the trunk."""
    parts = [_gridbox(40, 50, 400, (0, -80, 400)), _gridbox(40, 50, 400, (0, 80, 400)),            # legs: 80 x 100 x 800 each
             _gridbox(100, 150, 400, (0, 0, 1200), step=8.0),                                       # trunk: 200 x 300 x 800
             _gridbox(30, 30, 25, (0, 0, 1625)),                                                    # neck: 60 x 60 x 50
             _gridbox(50, 50, 75, (0, 0, 1725)),                                                    # head: 100 x 100 x 150
             _gridbox(15, 25, 200, (0, -330, 1200), step=8.0), _gridbox(15, 25, 200, (0, 330, 1200), step=8.0)]         # arms: 30 x 50 x 400 each, detached
    V = np.vstack([p[0] for p in parts])
    F, n = [], 0
    for v, f in parts:
        F.append(f + n)
        n += len(v)
    return V, np.vstack(F)


PLANES = {"ajc": 100.0, "kjc": 400.0, "apex": 800.0, "msr10": 1300.0, "neck": 1600.0, "top": 1800.0}


def test_region_volumes_split_a_synthetic_body_into_its_boxes():
    V, F = _body()
    r = features.BodyRaster(V, F, 1810.0, h=2.0)
    prof = decompose.profile(r)
    arm = np.array(decompose.vertex_regions(V, r, PLANES)) == "arms"
    vols = decompose.region_volumes(decompose.labelled_profile(r, V, arm), PLANES)
    leg = 2 * 80 * 100.0
    assert vols["feet"] == pytest.approx(leg * 100.0, rel=0.02)
    assert vols["shanks"] == pytest.approx(leg * 300.0, rel=0.02)
    assert vols["thighs"] == pytest.approx(leg * 400.0, rel=0.02)
    assert vols["abdomen_pelvis"] == pytest.approx(200 * 300.0 * 500.0, rel=0.02)
    assert vols["trunk_above_rib"] == pytest.approx(200 * 300.0 * 300.0 + 60 * 60.0 * 0.0, rel=0.02)        # 1300-1600 is all trunk box
    assert vols["head"] == pytest.approx(60 * 60.0 * 50.0 + 100 * 100.0 * 150.0, rel=0.02)
    assert vols["arms"] == pytest.approx(2 * 30 * 50.0 * 400.0, rel=0.02)
    assert sum(vols.values()) == pytest.approx(decompose.total_volume(prof), rel=1e-9)


def test_a_posed_arm_resting_against_the_trunk_is_still_an_arm():
    V, F = _body()
    r = features.BodyRaster(V, F, 1810.0, h=2.0)
    arm = np.array(decompose.vertex_regions(V, r, PLANES)) == "arms"
    V2 = V.copy()
    V2[arm & (V[:, 1] > 0), 1] -= 154.0                      # the +y arm moves in to 1 mm from the trunk (half-width 150): one raster cell, so the layer no longer separates them
    assert decompose.band(decompose.profile(features.BodyRaster(V2, F, 1810.0, h=2.0)), "arm", 1000.0, 1100.0, 800.0) < 3 * 30 * 50.0 * 100.0   # fused: one fewer piece
    r2 = features.BodyRaster(V2, F, 1810.0, h=2.0)
    vols = decompose.region_volumes(decompose.labelled_profile(r2, V2, arm), PLANES)
    # nearest-vertex labelling blurs the contact face by about a vertex spacing (8 mm here), so the tolerance is that spacing over the arm's 50 mm thickness
    assert vols["arms"] == pytest.approx(2 * 30 * 50.0 * 400.0, rel=0.06)
    assert vols["trunk_above_rib"] == pytest.approx(200 * 300.0 * 300.0, rel=0.03)


def test_band_edges_between_layers_are_weighted_by_the_overlap():
    V, F = box(50, 50, 100)                              # 100 x 100 x 200 mm
    V = V + np.array([0.0, 0.0, 100.0])
    r = features.BodyRaster(V, F, 210.0, h=2.0)
    prof = decompose.profile(r)
    assert decompose.band(prof, "core", 51.3, 98.9) == pytest.approx(100 * 100.0 * 47.6, rel=0.01)


def test_vertices_are_labelled_by_the_piece_they_sit_on():
    V, F = _body()
    r = features.BodyRaster(V, F, 1810.0, h=2.0)
    reg = np.array(decompose.vertex_regions(V, r, {**PLANES, "neck": 1625.0}))
    assert len(reg) == len(V)
    at = lambda x, y, z: reg[int(np.argmin(np.linalg.norm(V - [x, y, z], axis=1)))]
    assert at(0, -80, 0) == "legs" and at(0, 80, 0) == "legs" and at(40, 80, 200) == "legs"
    assert at(100, 0, 1200) == "torso" and at(0, 150, 1000) == "torso"          # the trunk box, below the neck plane
    assert at(0, 0, 1800) == "head"
    assert at(15, -330, 1200) == "arms" and at(0, 330, 1100) == "arms"


def test_neck_plane_is_the_narrowest_core_section_in_the_search_window():
    V, F = _body()
    r = features.BodyRaster(V, F, 1810.0, h=2.0)
    prof = decompose.profile(r)
    z = decompose.neck_height(prof, 1800.0)
    assert 1600.0 <= z <= 1650.0
