"""Volume-extractor brief 6, item 2 and 6: the component registry (components/1): schema, round trip, validation, the ISB to segment rotation, the STL reader and the flexible kind."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from envelope import occupancy, registry  # noqa: E402
from envelope.synthetic import box  # noqa: E402

DOC = {
    "schema": "components/1", "segment": "thigh_R",
    "components": [
        {"id": "part.thigh.actuator", "name": "actuator", "status": "designed", "owner": "thigh_R", "primitive": {"type": "cylinder", "diameter": 70, "length": 110},
         "pose": {"tx": 5, "ty": -8, "tz": -170, "rx": 0, "ry": 10, "rz": 0}, "clearance_mm": 3.0, "mass_kg": 0.42, "source": "hand-typed primitive"},
        {"id": "cable.1", "name": "harness", "status": "reserved", "owner": "thigh_R", "kind": "flexible", "polyline": [[0, 0, -20], [0, 0, -100], [30, 0, -140]], "radius_mm": 4.0,
         "bend_radius_mm": 150.0, "source": "routing sketch"},
        {"id": "if.hip.m2", "name": "hip motor", "status": "foreign", "owner": "pelvis", "primitive": {"type": "box", "half": [30, 30, 40]}, "poses_file": "hip_sweep.csv", "source": "pelvis owner"},
        {"id": "x", "name": "pod", "status": "candidate", "owner": "thigh_R", "primitive": {"type": "capsule", "radius": 12, "length": 40}},
    ],
}


def reg_of(doc=DOC, base="."):
    return registry.parse(doc, base)


def test_a_registry_survives_dump_and_load(tmp_path):
    reg = reg_of()
    registry.dump(reg, tmp_path / "thigh_R.yaml")
    back = registry.load(tmp_path / "thigh_R.yaml")
    assert back.to_dict() == reg.to_dict()
    text = (tmp_path / "thigh_R.yaml").read_text()
    assert yaml.safe_load(text)["schema"] == "components/1" and "\r" not in text


def test_defaults_and_the_placed_set():
    reg = reg_of()
    a = reg.by_name("actuator")
    assert a.pose == (5.0, -8.0, -170.0, 0.0, 10.0, 0.0) and reg.by_name("pod").clearance_mm == 0.0 and reg.by_name("pod").pose == (0.0,) * 6
    assert [c.name for c in reg.placed()] == ["actuator", "harness", "hip motor"]        # a candidate takes no space


@pytest.mark.parametrize("edit, fragment", [
    (lambda d: d["components"][0].update(status="planned"), "status"),
    (lambda d: d["components"][0].pop("primitive"), "bounding primitive is required"),
    (lambda d: d["components"][0].update(owner="pelvis"), "use status foreign"),
    (lambda d: d["components"][2].pop("poses_file"), "needs poses_file"),
    (lambda d: d["components"][2].update(owner="thigh_R"), "owned by another segment"),
    (lambda d: d["components"][0].update(colour="red"), "unknown field"),
    (lambda d: d["components"][1].pop("bend_radius_mm"), "needs bend_radius_mm"),
    (lambda d: d["components"][0].update(primitive={"type": "sphere"}), "primitive"),
    (lambda d: d["components"][3].update(name="actuator"), "used twice"),
    (lambda d: d.update(schema="components/2"), "schema"),
])
def test_the_registry_says_what_is_wrong(edit, fragment):
    import copy
    d = copy.deepcopy(DOC)
    edit(d)
    with pytest.raises(registry.RegistryError, match=fragment):
        reg_of(d)


def test_the_isb_frame_maps_onto_the_segment_frame_with_the_hip_at_the_origin_and_the_knee_below():
    L = 398.0
    hjc, kjc = np.array([0.0, 0.0, 0.0]), np.array([0.0, -L, 0.0])            # ISB/CAD thigh frame: x anterior, y up, z right; the knee is L below the hip
    out = registry.isb_to_segment(np.array([hjc, kjc]))
    assert np.allclose(out[0], [0, 0, 0]) and np.allclose(out[1], [0, 0, -L])
    assert np.allclose(registry.isb_to_segment([[1.0, 2.0, 3.0]]), [[1.0, -3.0, 2.0]])           # (a, b, c) -> (a, -c, b)
    assert np.allclose(registry.isb_to_segment([[0, 0, 1.0]]), [[0, -1.0, 0]])                   # right in the CAD frame is -y: y is left in the segment frame
    assert np.isclose(np.linalg.det(registry.ISB_TO_SEGMENT), 1.0)                               # a proper rotation, not a mirror
    with pytest.raises(NotImplementedError):
        registry.isb_to_segment([[0, 0, 0.0]], side="left")


def test_stl_round_trip_binary_and_ascii(tmp_path):
    v, f = box(10, 20, 30)
    registry.write_stl(tmp_path / "b.stl", v, f)
    v2, f2 = registry.read_stl(tmp_path / "b.stl")
    assert len(v2) == 8 and f2.shape == (12, 3) and np.allclose(np.sort(v2, axis=0), np.sort(v, axis=0))
    lines = ["solid t"]
    for tri in v[f]:
        lines += ["facet normal 0 0 0", "outer loop"] + [f"vertex {x} {y} {z}" for x, y, z in tri] + ["endloop", "endfacet"]
    (tmp_path / "a.stl").write_text("\n".join(lines + ["endsolid t"]))
    v3, f3 = registry.read_stl(tmp_path / "a.stl")
    assert len(v3) == 8 and f3.shape == (12, 3)


def test_the_flexible_kind_is_a_capsule_chain_with_a_bend_radius_check():
    reg = reg_of()
    h = reg.by_name("harness")
    sd = occupancy.chain_sdf(h.polyline, h.radius_mm)
    assert sd(np.array([[10.0, 0, -60]]))[0] == pytest.approx(10.0 - 4.0)                       # 10 mm off the first straight run, radius 4
    assert sd(np.array([[0.0, 0, -60]]))[0] == pytest.approx(-4.0)                              # on the axis
    assert sd(np.array([[0.0, 0, 0.0]]))[0] == pytest.approx(20.0 - 4.0)                         # beyond the end: the cap
    body = occupancy.Body(h, reg)
    Q, f = body.placed((0,) * 6)
    assert np.abs(f(Q)).max() < 0.05 and len(Q) > 100                                           # the samples lie on the surface of the chain
    right_angle = [[0, 0, 0], [10, 0, 0], [10, 10, 0]]
    assert occupancy.min_bend_radius(right_angle) == pytest.approx(np.hypot(10, 10) / 2)          # circumradius of a right triangle: half the hypotenuse
    assert occupancy.min_bend_radius([[0, 0, 0], [5, 0, 0], [10, 0, 0]]) == np.inf
    marg = occupancy.component_margins([{"name": "rod", "type": "cylinder", "radius": 5, "length": 40}], [[20, 0, -60, 0, 0, 0]], registry.parse({**DOC, "components": [DOC["components"][1]]}))
    assert marg[0]["margin_mm"] == pytest.approx(20 - 5 - 4, abs=0.6) and marg[0]["bend"]["ok"] is False and marg[0]["bend"]["min_radius_mm"] < 150.0
