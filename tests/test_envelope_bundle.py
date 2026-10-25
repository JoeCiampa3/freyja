"""Volume-extractor brief 2, item 7: the inspect bundle's geometry (marching tetrahedra, frame conversion, OBJ writer) and the masses module."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import bundle, field, masses, meshio  # noqa: E402

OBJ = REPO / "data" / "makehuman" / "freyja-body-v1.obj"


def sphere_values(r=20.0, h=1.0, n=48):
    ax = (np.arange(n) - n / 2 + 0.5) * h
    X, Y, Z = np.meshgrid(ax, ax, ax, indexing="ij")
    return r - np.sqrt(X ** 2 + Y ** 2 + Z ** 2), np.array([ax[0]] * 3), h        # positive inside, like sd


def test_marching_tetrahedra_surface_of_a_sphere_has_the_right_area_volume_and_orientation():
    vals, origin, h = sphere_values()
    V, F = bundle.marching_tetrahedra(vals, origin, h, 0.0)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2
    vol = np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6
    assert abs(area - 4 * np.pi * 400) / (4 * np.pi * 400) < 0.02
    assert vol > 0 and abs(vol - 4 / 3 * np.pi * 8000) / (4 / 3 * np.pi * 8000) < 0.02     # positive: normals point outward
    assert field.watertight(F)["boundary_edges"] == 0 and field.watertight(F)["nonmanifold_edges"] == 0


def test_marching_tetrahedra_on_an_iso_level_other_than_zero():
    vals, origin, h = sphere_values()
    V, F = bundle.marching_tetrahedra(vals, origin, h, 5.0)                 # sd >= 5: a sphere of radius 15
    r = np.linalg.norm(V, axis=1)
    assert abs(r.mean() - 15.0) < 0.2 and r.std() < 0.2


def test_empty_field_gives_an_empty_mesh():
    V, F = bundle.marching_tetrahedra(np.full((5, 5, 5), -1.0), np.zeros(3), 1.0, 0.0)
    assert len(V) == 0 and len(F) == 0


def test_to_mh_dm_inverts_the_loading_transform():
    v, _ = meshio.read_obj(OBJ)
    V = meshio.to_sheet_mm(v)
    z0, ymid = float(V[:, 2].min()), 0.0
    inp = SimpleNamespace(y_mid=ymid, z_sole_mm=z0)
    back = bundle.to_mh_dm(V - np.array([0.0, ymid, z0]), inp)
    assert np.allclose(back, v, atol=1e-9)


def test_direction_conversion_matches_the_axis_map():
    assert np.allclose(bundle.dir_to_mh([1, 0, 0]), [0, 0, 1])      # sheet anterior -> OBJ z
    assert np.allclose(bundle.dir_to_mh([0, 1, 0]), [1, 0, 0])      # sheet left -> OBJ x
    assert np.allclose(bundle.dir_to_mh([0, 0, 1]), [0, 1, 0])      # sheet up -> OBJ y


def test_write_obj_round_trips_vertices_faces_and_groups(tmp_path):
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1.0]])
    F = [[0, 1, 2], [0, 1, 3]]
    p = tmp_path / "a.obj"
    bundle.write_obj(p, V, F, [("one", 0), ("two", 1)])
    text = p.read_text()
    assert "g one" in text and "g two" in text and "\r" not in text
    v, polys = meshio.read_obj(p)
    assert np.allclose(v, V, atol=1e-5) and polys == [(0, 1, 2), (0, 1, 3)]


# ---- masses ------------------------------------------------------------------------------------------------------------------------

def test_siri_density_at_the_bracket_ends():
    assert masses.body_density(0.15) == pytest.approx(4.95 / 4.65)
    assert masses.body_density(0.35) == pytest.approx(4.95 / 4.85)


def test_mesh_volume_of_a_unit_cube_in_millimetres():
    from envelope.synthetic import box
    V, F = box(5, 5, 5)
    assert masses.mesh_volume_l(V, F) == pytest.approx(1e3 / 1e6)


def test_the_body_mesh_volume_matches_joes_blender_figure_within_half_a_percent():
    v, polys = meshio.read_obj(OBJ)
    from envelope import trial
    V = meshio.to_sheet_mm(v)
    vol = masses.mesh_volume_l(V, trial.triangulate(polys))
    blender = masses.load_constants(REPO)["blender_volume_m3"] * 1000.0
    assert abs(vol - blender) / blender < masses.BLENDER_TOLERANCE


def test_missing_constants_file_stops_and_names_it(tmp_path):
    from envelope.sheet import StopAndAsk
    with pytest.raises(StopAndAsk, match="body_density.json"):
        masses.load_constants(tmp_path)


def test_sheet_masses_sum_to_the_target_within_a_fraction_of_a_percent():
    from envelope import register
    n = register.sheet_nodes(REPO / "params" / "snapshot.csv")
    assert abs(n.total_mass_kg - n.target_mass_kg) / n.target_mass_kg < 0.005


# ---- cuts and the share tables -----------------------------------------------------------------------------------------------------

def test_stretched_volume_integrates_the_area_profile_with_the_height_map():
    from envelope import cuts, register
    sh = register.sheet_nodes(REPO / "params" / "snapshot.csv")
    reg = register.make_registration(sh, {"ajc": 60.0, "kjc": 480.0, "hjc": 880.0}, {n: (0.0, -100.0) for n in ("ajc", "kjc", "hjc")}, {n: 1.0 for n in ("ajc", "kjc", "hjc")})
    z = np.arange(0.0, 1100.0, 2.0)
    area = np.full_like(z, 10000.0)
    s = reg.axial.stretches()["thigh"]
    # between the knee and the hip node the height map has slope s; above the hip node slope 1
    assert cuts.stretched_volume(z, area, 480.0, 880.0, reg) == pytest.approx(10000.0 * 400.0 * s, rel=1e-3)
    assert cuts.stretched_volume(z, area, 880.0, 980.0, reg) == pytest.approx(10000.0 * 100.0, rel=1e-3)
    assert cuts.stretched_volume(z, area, 800.0, 900.0, reg) == pytest.approx(10000.0 * (80.0 * s + 20.0), rel=2e-3)


def test_core_area_profile_ignores_a_detached_arm():
    from envelope import cuts, features
    from envelope.synthetic import box
    torso, tf = box(100, 150, 200, center=(0, 0, 200))
    arm, af = box(30, 30, 100, center=(0, 300, 200))
    V = np.vstack([torso, arm])
    F = np.vstack([tf, af + len(torso)])
    r = features.BodyRaster(V, F, 380.0)
    z, a = cuts.core_area_profile(r, 100.0, 300.0)
    assert np.allclose(a, 200 * 300, rtol=0.03)            # the torso's 200 x 300 mm section, not plus the arm's 60 x 60


def test_share_ratio_arithmetic_with_stand_in_segments():
    from envelope import masses
    from envelope.synthetic import box
    V, F = box(50, 50, 50)                                  # 100 mm cube = 1 l
    sh = SimpleNamespace(total_mass_kg=10.0, thigh_mass_kg=1.0, shank_mass_kg=0.5, foot_mass_kg=0.2, pelvis_mass_kg=1.0)
    inp = SimpleNamespace(V=V, F=F, sheet=sh, stature_mesh=100.0)
    fake = lambda v: SimpleNamespace(seg=SimpleNamespace(volume=lambda t=0.0, s0=0.0, s1=None: v * 1e6))
    consts = {"body_fat_fraction": 0.2, "v_lung_l": 0.1, "blender_volume_m3": 0.001}
    out = masses.report(inp, {"thigh": fake(0.2), "shank": fake(0.1), "foot": fake(0.02)}, consts)
    D = 4.95 / 4.7
    assert out["cases"]["nominal"]["mesh_mass_kg"] == pytest.approx(D * 0.9)
    r = out["rows"]["thigh"]
    assert r["mass_share"] == pytest.approx(0.1) and r["volume_share"] == pytest.approx(0.2) and r["ratio"] == pytest.approx(0.5)
    mean = D * 0.9 / 1.0
    c = r["cases"]["nominal"]
    assert c["expected_tissue_ratio"] == pytest.approx(1.05 / mean) and c["normalised_ratio"] == pytest.approx(0.5 / (1.05 / mean))
    assert c["implied_density_kg_per_l"] == pytest.approx(0.1 * D * 0.9 / 0.2)
    assert out["blender_within_tolerance"] is True


# ---- brief 3: pelvis tops at the iliocristale, the lumped region to the tenth rib ----------------------------------------------------

def _ansur_stub():
    return {"landmarks": {"iliocristale": {"ratio": {"mean": 0.6, "sd": 0.01}}, "tenth_rib": {"ratio": {"mean": 0.65, "sd": 0.02}}}}


def test_landmark_heights_are_ansur_ratio_times_the_mesh_stature_with_a_one_sd_band():
    from envelope import cuts
    h = cuts.landmark_heights(_ansur_stub(), 1700.0)
    assert h["iliocristale"] == pytest.approx({"mean": 1020.0, "lo": 1003.0, "hi": 1037.0, "sd": 17.0})
    assert h["tenth_rib"] == pytest.approx({"mean": 1105.0, "lo": 1071.0, "hi": 1139.0, "sd": 34.0})


def test_lumped_volume_is_the_slab_from_the_crotch_apex_plus_two_thighs_and_does_not_see_the_pelvis_cuts():
    from envelope import cuts, register
    sh = register.sheet_nodes(REPO / "params" / "snapshot.csv")
    reg = register.make_registration(sh, {"ajc": 60.0, "kjc": 480.0, "hjc": 880.0}, {n: (0.0, -100.0) for n in ("ajc", "kjc", "hjc")}, {n: 1.0 for n in ("ajc", "kjc", "hjc")})
    z = np.arange(0.0, 1200.0, 2.0)
    area = np.full_like(z, 10000.0)
    s = reg.axial.stretches()["thigh"]
    v = cuts.lumped_volume(z, area, 800.0, 1100.0, reg, thigh_below_apex_mm3=3.0e6)
    assert v == pytest.approx(10000.0 * (80.0 * s + 220.0) + 2 * 3.0e6, rel=2e-3)


def test_mass_rows_for_the_new_cuts_carry_sheet_mass_per_skin_volume():
    from envelope import masses
    from envelope.synthetic import box
    V, F = box(50, 50, 50)                                  # 1 l
    sh = SimpleNamespace(total_mass_kg=10.0, thigh_mass_kg=1.0, shank_mass_kg=0.5, foot_mass_kg=0.2, pelvis_mass_kg=1.0, abdomen_mass_kg=0.3)
    inp = SimpleNamespace(V=V, F=F, sheet=sh, stature_mesh=100.0)
    fake = lambda v: SimpleNamespace(seg=SimpleNamespace(volume=lambda t=0.0, s0=0.0, s1=None: v * 1e6))
    vols = {"thigh_in": 0.2e6, "thigh_out": 0.1e6, "thigh_crotch": 0.15e6, "pelvis_hjc": 0.3e6, "pelvis_crotch": 0.4e6}
    for top in ("ilio", "ilio_lo", "ilio_hi"):
        vols[f"pelvis_hjc_{top}"], vols[f"pelvis_crotch_{top}"] = 0.35e6, 0.45e6
    vols.update({"lumped": 0.9e6, "lumped_lo": 0.8e6, "lumped_hi": 1.0e6})
    cuts = {"volumes_mm3": vols, "s_crotch_mm": 70.0, "ljc_mesh_mm": 900.0}
    out = masses.report(inp, {"thigh": fake(0.2), "shank": fake(0.1), "foot": fake(0.02)}, {"body_fat_fraction": 0.2, "v_lung_l": 0.1}, cuts)
    r = out["rows"]
    assert r["pelvis_hjc_ilio"]["volume_l"] == pytest.approx(0.35) and r["pelvis_hjc_ilio"]["mass_kg_sheet"] == 1.0
    assert r["pelvis_hjc_ilio"]["sheet_mass_per_skin_volume_kg_per_l"] == pytest.approx(1.0 / 0.35)
    assert r["thigh_pelvis_hjc_ilio"]["volume_l"] == pytest.approx(2 * 0.2 + 0.35) and r["thigh_pelvis_hjc_ilio"]["mass_kg_sheet"] == pytest.approx(3.0)
    assert r["lumped"]["mass_kg_sheet"] == pytest.approx(0.3 + 1.0 + 2 * 1.0) and r["lumped"]["volume_l"] == pytest.approx(0.9)
    assert r["lumped"]["reference_density_kg_per_l"] == pytest.approx((0.3 * masses.ABDOMEN_REFERENCE_DENSITY + 1.0 * masses.PELVIS_REFERENCE_DENSITY + 2 * 1.05) / 3.3)
    assert r["shank"]["sheet_mass_per_skin_volume_kg_per_l"] == pytest.approx(0.5 / 0.1) and r["foot"]["sheet_mass_per_skin_volume_kg_per_l"] == pytest.approx(0.2 / 0.02)
    assert {"lumped_lo", "lumped_hi", "pelvis_crotch_ilio_hi", "thigh_pelvis_crotch_ilio_lo"} <= set(r)
    assert r["pelvis_hjc"]["volume_l"] == pytest.approx(0.3)           # the lumbosacral-top rows are untouched
