"""Volume-extractor brief 6, items 3, 4 and 6: margin to the registry's components against analytic cases, overlapping, outside-the-skin and swept components, the exact mesh distance,
and the free field."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import field, ledger, occupancy, oracle, registry  # noqa: E402
from envelope.synthetic import box, frustum  # noqa: E402

R_ENV, H = 45.0, 300.0


@pytest.fixture(scope="module")
def seg():
    v, f = frustum(R_ENV, R_ENV, 60, -H - 60)
    return field.build_segment(v, f, length=H, voxel=2.0, z_top=0.0, margin=40.0)


def cyl(radius, length, name="shape"):
    return {"name": name, "type": "cylinder", "radius": radius, "length": length}


def comp(name, primitive, pose=(0, 0, -150, 0, 0, 0), status="designed", clearance=0.0, **kw):
    d = {"id": f"id.{name}", "name": name, "status": status, "owner": "thigh_R", "primitive": primitive, "pose": dict(zip(registry.POSE_KEYS, pose)), "clearance_mm": clearance}
    d.update(kw)
    return d


def reg_of(*components, base="."):
    return registry.parse({"schema": "components/1", "segment": "thigh_R", "components": list(components)}, base)


# ---- margin to a component ----------------------------------------------------------------------------------------------------------------

def test_margin_to_a_component_against_the_analytic_two_cylinder_case():
    reg = reg_of(comp("actuator", {"type": "cylinder", "radius": 10, "length": 100}, pose=(-20, 0, -150, 0, 0, 0), clearance=2.0))
    cand = [cyl(8, 80)]
    out = occupancy.component_margins(cand, [[10, 0, -150, 0, 0, 0]], reg)[0]          # axes 30 apart, radii 10 and 8: surfaces 12 apart, less the 2 mm clearance
    assert out["distance_mm"] == pytest.approx(12.0, abs=0.6) and out["margin_mm"] == pytest.approx(10.0, abs=0.6)
    assert out["shape"] == "shape" and out["pose_index"] == 0 and out["status"] == "designed" and out["clearance_mm"] == 2.0
    hit = occupancy.component_margins(cand, [[-5, 0, -150, 0, 0, 0]], reg)[0]          # axes 15 apart: the cylinders overlap by 3 mm
    assert hit["distance_mm"] == pytest.approx(-3.0, abs=0.6) and hit["margin_mm"] == pytest.approx(-5.0, abs=0.6)


def test_a_candidate_that_swallows_a_component_is_caught_from_the_components_side():
    reg = reg_of(comp("actuator", {"type": "cylinder", "radius": 10, "length": 60}))
    out = occupancy.component_margins([cyl(30, 120)], [[0, 0, -150, 0, 0, 0]], reg)[0]
    assert out["margin_mm"] == pytest.approx(-30.0, abs=0.6)                                # the deepest point of the component, the centre of an end cap, sits 30 mm inside the candidate


def test_the_binding_pose_is_the_closest_and_the_station_is_below_the_origin():
    reg = reg_of(comp("actuator", {"type": "cylinder", "radius": 10, "length": 100}, pose=(-20, 0, -150, 0, 0, 0)))
    poses = [[10, 0, -150, 0, 0, 0], [0, 0, -150, 0, 0, 0], [20, 0, -150, 0, 0, 0]]
    out = occupancy.component_margins([cyl(8, 80)], poses, reg)[0]
    assert out["pose_index"] == 1 and out["margin_mm"] == pytest.approx(2.0, abs=0.6) and 100 <= out["station_mm"] <= 200


def test_a_rotated_component_pose_uses_the_oracles_extrinsic_xyz_convention():
    prim = {"type": "box", "half": [5, 5, 50]}
    reg = reg_of(comp("bar", prim, pose=(0, 0, -150, 0, 90, 0)))                           # a ry of 90 degrees lays the bar along x
    out = occupancy.component_margins([cyl(5, 20)], [[70, 0, -150, 0, 0, 0]], reg)[0]     # past the bar's end at x = 50: 70 - 5 - 50 (laid along y or z it would be 60)
    assert out["distance_mm"] == pytest.approx(15.0, abs=0.7)
    out = occupancy.component_margins([cyl(5, 20)], [[0, 40, -150, 0, 0, 0]], reg)[0]     # beside the bar: 40 - 5 - 5
    assert out["distance_mm"] == pytest.approx(30.0, abs=0.7)
    out = occupancy.component_margins([cyl(5, 20)], [[30, 0, -150, 0, 0, 0]], reg)[0]     # through the bar: the deepest point is on the axis, 5 mm from the bar's top and bottom faces
    assert out["distance_mm"] == pytest.approx(-5.0, abs=0.7)


def test_a_swept_component_is_checked_at_every_pose_of_its_sweep(tmp_path):
    (tmp_path / "sweep.csv").write_text("tx,ty,tz\n-20,-30,-150\n-20,-15,-150\n-20,0,-150\n-20,15,-150\n-20,30,-150\n")
    reg = reg_of(comp("arm", {"type": "cylinder", "radius": 10, "length": 100}, poses_file="sweep.csv"), base=tmp_path)
    out = occupancy.component_margins([cyl(8, 80)], [[10, 0, -150, 0, 0, 0]], reg)[0]
    assert out["sweep_poses"] == 5 and out["component_pose_index"] == 2                      # it passes the candidate in the middle of the sweep: 12 mm between the surfaces
    assert out["distance_mm"] == pytest.approx(12.0, abs=0.6)
    static = reg_of(comp("arm", {"type": "cylinder", "radius": 10, "length": 100}, pose=(-20, -30, -150, 0, 0, 0)))
    assert occupancy.component_margins([cyl(8, 80)], [[10, 0, -150, 0, 0, 0]], static)[0]["distance_mm"] > 20       # the static pose at the sweep's end: 42.4 between the axes, less 18


def test_a_candidate_is_not_an_obstacle():
    reg = reg_of(comp("pod", {"type": "cylinder", "radius": 10, "length": 100}, status="candidate"))
    assert occupancy.component_margins([cyl(8, 80)], [[0, 0, -150, 0, 0, 0]], reg) == []


# ---- exact distance between meshes ------------------------------------------------------------------------------------------------------------

def test_triangle_distance_is_exact_for_a_vertex_an_edge_and_a_face_case():
    A = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], float)
    assert occupancy.triangle_distance(A, A + [0, 0, 2.0])[0] == pytest.approx(2.0)                                   # parallel, one above the other
    skew = np.array([[[0.5, -1, 1], [0.5, 1, 1], [3, 0, 1.0]]])
    assert occupancy.triangle_distance(A, skew)[0] == pytest.approx(1.0)                                              # edge against edge
    far = np.array([[[4, 4, 0], [5, 4, 0], [4, 5, 0.0]]])
    assert occupancy.triangle_distance(A, far)[0] == pytest.approx(np.hypot(3.5, 3.5))                                 # the far corner against the middle of the hypotenuse


def test_mesh_distance_of_two_boxes_and_the_binding_pair_of_a_mesh_component(tmp_path):
    v, f = box(10, 10, 30)
    registry.write_stl(tmp_path / "bar.stl", v, f)
    reg = reg_of(comp("bar", {"type": "box", "half": [10, 10, 30]}, pose=(0, 0, -150, 0, 0, 0), clearance=1.0, mesh="bar.stl"), base=tmp_path)
    cand = [{"name": "post", "type": "cylinder", "radius": 8, "length": 40}]
    out = occupancy.component_margins(cand, [[30, 0, -150, 0, 0, 0]], reg)[0]                # face to face: 30 - 10 - 8 = 12 mm
    assert out["distance_mm"] == pytest.approx(12.0, abs=1.3) and out["margin_mm"] == pytest.approx(11.0, abs=1.3)       # the 1 mm voxel field of the mesh
    ex = occupancy.exact_binding_distance(out)
    assert ex["exact_mm"] == pytest.approx(12.0, abs=0.01) and ex["interpenetrating"] is False
    corner = occupancy.component_margins(cand, [[10 + 8 + 6, 10 + 8 + 6, -150, 0, 0, 0]], reg)[0]      # diagonal: the box's vertical edge against the cylinder's wall
    assert occupancy.exact_binding_distance(corner)["exact_mm"] == pytest.approx(np.hypot(14, 14) - 8, abs=0.05)
    over = occupancy.component_margins(cand, [[15, 0, -150, 0, 0, 0]], reg)[0]
    assert occupancy.exact_binding_distance(over) == {"exact_mm": None, "interpenetrating": True}


def test_an_analytic_component_has_no_mesh_pair_to_be_exact_about():
    reg = reg_of(comp("a", {"type": "cylinder", "radius": 10, "length": 60}))
    assert occupancy.exact_binding_distance(occupancy.component_margins([cyl(8, 40)], [[30, 0, -150, 0, 0, 0]], reg)[0]) is None


def test_the_shape_triangles_are_the_shape():
    for shape in ({"type": "box", "half": [5, 6, 7]}, {"type": "cylinder", "radius": 6, "length": 30}, {"type": "capsule", "radius": 6, "length": 30}):
        V, F = occupancy.shape_mesh(shape, [1, 2, 3, 0, 0, 0])
        sd = occupancy.shape_sdf(shape, [1, 2, 3, 0, 0, 0])(V)
        assert np.abs(sd).max() < 0.03 * 6                                                  # the vertices lie on the surface (the facets are inscribed)
        vol = abs(np.einsum("ij,ij->i", V[F][:, 0], np.cross(V[F][:, 1], V[F][:, 2])).sum()) / 6
        expect = {"box": 10 * 12 * 14, "cylinder": np.pi * 36 * 30, "capsule": np.pi * 36 * 30 + 4 / 3 * np.pi * 216}[shape["type"]]
        assert vol == pytest.approx(expect, rel=0.01)


# ---- the free field ---------------------------------------------------------------------------------------------------------------------

def test_without_components_the_free_field_is_the_skin_and_the_largest_sphere_is_the_inscribed_one(seg):
    virt, rep = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(), (0, 0, 0))])
    assert rep["free_volume_l"] == pytest.approx(rep["skin_volume_l"]) and rep["occupied_volume_l"] == pytest.approx(0.0, abs=1e-12)
    assert rep["largest_free_sphere"]["diameter_mm"] == pytest.approx(2 * R_ENV, abs=2.0)           # not cut by the slab planes: the sphere's distance is to the skin only
    assert rep["skin_volume_l"] == pytest.approx(np.pi * R_ENV ** 2 * H / 1e6, rel=0.01)


def test_overlapping_components_occupy_their_union_not_their_sum(seg):
    a = comp("a", {"type": "cylinder", "radius": 10, "length": 100}, pose=(-5, 0, -150, 0, 0, 0))
    b = comp("b", {"type": "cylinder", "radius": 10, "length": 100}, pose=(5, 0, -150, 0, 0, 0))
    _, rep = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(a, b), (0, 0, 0))])
    d, r = 10.0, 10.0
    lens = 2 * r * r * np.arccos(d / (2 * r)) - d / 2 * np.sqrt(4 * r * r - d * d)
    union = (2 * np.pi * r * r - lens) * 100.0 / 1e6
    assert rep["occupied_volume_l"] == pytest.approx(union, rel=0.03)
    assert rep["occupied_volume_l"] < 2 * np.pi * r * r * 100.0 / 1e6 * 0.9
    assert rep["free_volume_l"] + rep["occupied_volume_l"] == pytest.approx(rep["skin_volume_l"])


def test_a_clearance_dilates_a_component_and_a_component_outside_the_skin_takes_nothing(seg):
    plain = comp("a", {"type": "cylinder", "radius": 10, "length": 100}, pose=(0, 0, -150, 0, 0, 0))
    padded = comp("a", {"type": "cylinder", "radius": 10, "length": 100}, pose=(0, 0, -150, 0, 0, 0), clearance=5.0)
    _, r0 = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(plain), (0, 0, 0))])
    _, r5 = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(padded), (0, 0, 0))])
    assert r5["occupied_volume_l"] == pytest.approx(np.pi * 15 ** 2 * 110 / 1e6 * (1 + 0.0), rel=0.12)       # a radius-15 cylinder 110 long (the caps are rounded, the field is a distance dilation)
    assert r5["occupied_volume_l"] > 1.9 * r0["occupied_volume_l"]
    outside = comp("far", {"type": "cylinder", "radius": 10, "length": 100}, pose=(90, 0, -150, 0, 0, 0))
    _, ro = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(outside), (0, 0, 0))])
    assert ro["occupied_volume_l"] == pytest.approx(0.0, abs=1e-9) and ro["free_volume_l"] == pytest.approx(ro["skin_volume_l"])


def test_a_swept_component_occupies_everything_it_passes_through(seg, tmp_path):
    (tmp_path / "s.csv").write_text("tx,ty,tz\n-20,0,-150\n0,0,-150\n20,0,-150\n")
    swept = reg_of(comp("a", {"type": "cylinder", "radius": 6, "length": 60}, poses_file="s.csv"), base=tmp_path)
    still = reg_of(comp("a", {"type": "cylinder", "radius": 6, "length": 60}, pose=(0, 0, -150, 0, 0, 0)))
    _, rs = occupancy.free_field([(seg, (0, 0, 0))], [(swept, (0, 0, 0))])
    _, r1 = occupancy.free_field([(seg, (0, 0, 0))], [(still, (0, 0, 0))])
    assert rs["occupied_volume_l"] == pytest.approx(r1["occupied_volume_l"] * 3, rel=0.03)          # the poses are the sweep: three separate placements, no interpolation between rows
    assert rs["components"][0]["poses"] == 3


def test_a_candidate_component_does_not_take_free_space(seg):
    _, rep = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(comp("pod", {"type": "cylinder", "radius": 20, "length": 100}, pose=(0, 0, -150, 0, 0, 0), status="candidate")), (0, 0, 0))])
    assert rep["occupied_volume_l"] == 0.0 and rep["components"] == []


def test_the_largest_free_sphere_is_found_in_the_gap_a_component_leaves(seg):
    big = comp("core", {"type": "cylinder", "radius": 30, "length": 300}, pose=(0, 0, -150, 0, 0, 0), clearance=0.0)       # leaves an annulus 15 mm wide
    virt, rep = occupancy.free_field([(seg, (0, 0, 0))], [(reg_of(big), (0, 0, 0))])
    s = rep["largest_free_sphere"]
    assert s["diameter_mm"] == pytest.approx(15.0, abs=2.0) and np.hypot(s["centre_mm"][0], s["centre_mm"][1]) == pytest.approx(37.5, abs=2.0)
    rows = ledger.rows_for(virt, "trunk")                                                     # the free ledger: the existing schema, computed on the free field
    mid = next(r for r in rows if r["s_mm"] == 150.0)
    assert mid["cheb_r_mm"] == pytest.approx(7.5, abs=1.2) and mid["area_mm2"] == pytest.approx(np.pi * (45 ** 2 - 30 ** 2), rel=0.03)


def test_the_union_of_two_bodies_frees_the_space_across_their_shared_plane():
    v, f = frustum(R_ENV, R_ENV, 60, -300 - 60)
    upper = field.build_segment(v, f, length=100.0, voxel=2.0, z_top=0.0, margin=40.0)
    lower = field.build_segment(v + np.array([0.0, 0.0, 100.0]), f, length=200.0, voxel=2.0, z_top=0.0, margin=40.0)
    parts = [(upper, (0, 0, 0)), (lower, (0, 0, -100))]
    across = comp("rod", {"type": "cylinder", "radius": 10, "length": 150}, pose=(0, 0, -100, 0, 0, 0))
    virt, rep = occupancy.free_field(parts, [(reg_of(across), (0, 0, 0))])
    assert virt.length == pytest.approx(300.0) and virt.z_top == 0.0
    assert rep["skin_volume_l"] == pytest.approx(np.pi * R_ENV ** 2 * 300 / 1e6, rel=0.02)
    assert rep["occupied_volume_l"] == pytest.approx(np.pi * 100 * 150 / 1e6, rel=0.06)       # the whole rod counts: it crosses the plane but both bodies hold it
    one, rep1 = occupancy.free_field([(upper, (0, 0, 0))], [(reg_of(across), (0, 0, 0))])
    assert rep1["occupied_volume_l"] < rep["occupied_volume_l"]


def test_the_free_ledger_hash_changes_with_the_registry_and_nothing_else_moves_it():
    r1 = reg_of(comp("a", {"type": "cylinder", "radius": 10, "length": 60}))
    r2 = reg_of(comp("a", {"type": "cylinder", "radius": 11, "length": 60}))
    h = lambda r, t=0.0: occupancy.inputs_hash({"thigh_R": "abc"}, [(r, (0, 0, 0))], t, [])
    assert h(r1) == h(r1) and h(r1) != h(r2) and h(r1) != h(r1, 3.0)
