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
