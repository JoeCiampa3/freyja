"""
Stage 3b T2: the CAD bridge library without Fusion (tools/cad): units, the name rule, bindings, drift, frames, mass properties, the canonical mesh,
STEP normalisation, parameter checks, the sidecar and the component entry. Every check-like function has a mutation test: a deliberately broken
copy must make its known-answer test fail.

    python -m pytest tests/test_cad_lib.py
"""
import copy
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from cad import binding as cb  # noqa: E402
from cad import component as cc  # noqa: E402
from cad import drift as cd  # noqa: E402
from cad import frames as cf  # noqa: E402
from cad import mesh as cm  # noqa: E402
from cad import names as cn  # noqa: E402
from cad import params as cp  # noqa: E402
from cad import sidecar as cs  # noqa: E402
from cad import step as cstep  # noqa: E402
from cad import units as cu  # noqa: E402
from envelope import registry  # noqa: E402

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from test_cad_schema import BINDING_OK, SIDECAR_OK  # noqa: E402


# ---- units -----------------------------------------------------------------------------------------------------------------------------

def unit_known_answers(u):
    """Failures of the unit module against hand-computed answers; empty when it is right."""
    bad = []
    cases = [
        ("mm to cm", u.mm_to_fusion_length(312.4), 31.24),
        ("cm to mm", u.fusion_length_to_mm(31.24), 312.4),
        ("deg to rad", u.deg_to_fusion_angle(180.0), math.pi),
        ("rad to deg", u.fusion_angle_to_deg(math.pi / 2), 90.0),
        ("kg cm2 to kg mm2", u.fusion_inertia_to_kgmm2(2.5), 250.0),
        ("kg mm2 to kg cm2", u.kgmm2_to_fusion_inertia(250.0), 2.5),
        ("kg/cm3 to kg/m3", u.fusion_density_to_kg_m3(0.0027), 2700.0),
        ("m to mm", u.convert(0.255234699434, "m", "mm"), 255.234699434),
        ("rad to deg conv", u.convert(math.pi / 3, "rad", "deg"), 60.0),
        ("deg to deg", u.convert(62.0, "deg", "deg"), 62.0),
        ("unitless", u.convert(3.0, "unitless", "unitless"), 3.0),
        ("mm to mm", u.convert(7.0, "mm", "mm"), 7.0),
        ("internal length", u.fusion_value_to_unit(31.24, "mm"), 312.4),
        ("internal angle", u.fusion_value_to_unit(math.pi, "deg"), 180.0),
        ("internal unitless", u.fusion_value_to_unit(3.0, "unitless"), 3.0),
        ("mm expression value", u.unit_to_fusion_value(312.4, "mm"), 31.24),
        ("deg expression value", u.unit_to_fusion_value(180.0, "deg"), math.pi),
    ]
    for name, got, want in cases:
        if not math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-15):
            bad.append(f"{name}: {got} != {want}")
    return bad


def test_unit_known_answers_hold():
    assert unit_known_answers(cu) == []


@pytest.mark.parametrize("attr,value", [("CM_PER_MM", 0.01), ("MM_PER_CM", 100.0), ("KGMM2_PER_KGCM2", 10.0), ("KG_M3_PER_KG_CM3", 1e5)])
def test_a_broken_unit_factor_fails_the_known_answers(monkeypatch, attr, value):
    monkeypatch.setattr(cu, attr, value)
    assert unit_known_answers(cu)


def test_unknown_units_are_refused():
    with pytest.raises(ValueError):
        cu.convert(1.0, "m", "deg")
    with pytest.raises(ValueError):
        cu.fusion_value_to_unit(1.0, "furlong")


@pytest.mark.parametrize("value,unit,text", [
    (312.4, "mm", "312.4 mm"), (62.0, "deg", "62 deg"), (3.0, "unitless", "3"), (255.23469943400002, "mm", "255.234699434 mm"),
    (0.0, "mm", "0 mm"), (-12.5, "deg", "-12.5 deg"), (1e-7, "mm", "0.0000001 mm"), (1.5e7, "mm", "15000000 mm"),
])
def test_expressions_carry_an_explicit_unit(value, unit, text):
    assert cu.format_expression(value, unit) == text


def test_expressions_round_trip_within_the_gate_tolerance():
    for v in (0.0, 1.0, 255.234699434, 312.4, 1e-3, 123456.789012345, 62.0000000001):
        text = cu.format_expression(v, "mm")
        back = float(text.split()[0])
        assert math.isclose(back, v, rel_tol=1e-9, abs_tol=1e-12)


def test_non_finite_values_are_refused_in_expressions():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            cu.format_expression(bad, "mm")


# ---- names -----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("address,name", [
    ("snapshot#/upper_arm_right_length", "in_upper_arm_right_length"),
    ("req.elbow.flex_max#/value", "in_req_elbow_flex_max_value"),
    ("seg.upper_arm#/body", "in_seg_upper_arm_body"),
    ("part.hip.m2#/mass/kg", "in_part_hip_m2_mass_kg"),
    ("if.hip-m2-thigh#/mechanical/bolt-circle", "in_if_hip_m2_thigh_mechanical_bolt_circle"),
    ("data/envelope/arm_bodies.json#/upper_arm_R/length", "in_data_envelope_arm_bodies_json_upper_arm_R_length"),
    ("snapshot#/a/0/b", "in_a_0_b"),
])
def test_the_name_rule_on_every_address_form(address, name):
    assert cn.inherited_name(address) == name


@pytest.mark.parametrize("address", ["snapshot#", "req.x.y#", "nohash", "snapshot#/with space", "snapshot#/ü"])
def test_the_name_rule_refuses_addresses_with_no_valid_name(address):
    with pytest.raises(ValueError):
        cn.inherited_name(address)


def test_two_addresses_mapping_to_one_name_is_an_error():
    with pytest.raises(ValueError, match="in_a_b_c"):
        cn.names_for(["a.b#/c", "a_b#/c"])
    with pytest.raises(ValueError):
        cn.names_for(["a-b#/c", "a.b#/c"])
    assert cn.names_for(["a.b#/c", "a.b#/d"]) == {"a.b#/c": "in_a_b_c", "a.b#/d": "in_a_b_d"}


def test_a_repeated_address_is_not_a_collision():
    assert cn.names_for(["a.b#/c", "a.b#/c"]) == {"a.b#/c": "in_a_b_c"}


# ---- binding ---------------------------------------------------------------------------------------------------------------------------

def good_binding():
    return copy.deepcopy(BINDING_OK)


def test_a_valid_binding_has_no_problems():
    assert cb.check(good_binding()) == []


def test_the_binding_hash_is_stable_and_sensitive():
    a = cb.binding_hash(good_binding())
    assert a == cb.binding_hash(good_binding()) and len(a) == 12
    b = good_binding()
    b["revision"] = "p2"
    assert cb.binding_hash(b) != a
    # key order does not matter
    c = dict(reversed(list(good_binding().items())))
    assert cb.binding_hash(c) == a


BAD_BINDINGS = {
    "left side": lambda b: b.update(side="left"),
    "unprefixed parameter": lambda b: b["parameters"][1].update(name="uam_od"),
    "missing prefix on inherited": lambda b: b["parameters"][0].update(name="upper_arm_right_length"),
    "wrong inherited name": lambda b: b["parameters"][0].update(name="in_length"),
    "duplicate name": lambda b: b["parameters"].append({"name": "dv_uam_od", "class": "dv", "unit": "deg"}),
    "two addresses one name": lambda b: b["parameters"].append(
        {"name": "in_upper_arm_right_length", "class": "in", "address": "snapshot#/upper_arm_right_length", "address_unit": "m", "unit": "mm"}),
    "inherited without address": lambda b: b["parameters"][0].pop("address"),
    "address of the wrong class": lambda b: b["parameters"][1].update(address="snapshot#/x"),
}


@pytest.mark.parametrize("case", sorted(BAD_BINDINGS))
def test_binding_check_reports(case):
    b = good_binding()
    BAD_BINDINGS[case](b)
    assert cb.check(b), case


def test_the_binding_check_catches_a_missing_prefix_but_not_when_the_check_is_broken(monkeypatch):
    b = good_binding()
    b["parameters"][1]["name"] = "uam_od"
    assert cb.check(b)
    monkeypatch.setattr(cb, "PREFIXES", {"in": "", "dv": "", "dr": ""})  # mutation: prefix rule removed
    # the schema still catches an unprefixed name, so the mutation only counts if the library check alone would have let it through
    assert cb.check_names(b) == []


def test_load_binding_refuses_with_the_problems_listed(tmp_path):
    b = good_binding()
    b["side"] = "left"
    p = tmp_path / "part.arm.upper_member.yaml"
    p.write_text(yaml.safe_dump(b), encoding="utf-8")
    with pytest.raises(cb.BindingError, match="side"):
        cb.load(p)
    p.write_text(yaml.safe_dump(good_binding()), encoding="utf-8")
    assert cb.load(p)["part"] == "part.arm.upper_member"


def test_the_filename_stem_must_equal_the_part_id(tmp_path):
    p = tmp_path / "part.arm.other.yaml"
    p.write_text(yaml.safe_dump(good_binding()), encoding="utf-8")
    with pytest.raises(cb.BindingError, match="stem"):
        cb.load(p)


def resolver_for(values):
    return lambda a: (True, values[a]) if a in values else (False, None)


def test_inherited_parameters_resolve_through_addresses_into_fusion_units():
    rows = cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": 0.255234699434}))
    assert len(rows) == 1
    r = rows[0]
    assert r["name"] == "in_upper_arm_right_length" and r["unit"] == "mm"
    assert math.isclose(r["value"], 255.234699434, rel_tol=1e-12)
    assert r["expression"] == "255.234699434 mm"
    assert len(r["address_hash"]) == 12


def test_the_snapshots_numeric_text_is_a_number_and_hashes_as_the_text():
    from thread import addr
    rows = cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": "0.255234699434"}))
    assert rows[0]["value"] == pytest.approx(255.234699434) and rows[0]["address_hash"] == addr.hash_value("0.255234699434")


def test_an_unresolved_or_non_numeric_address_is_refused():
    with pytest.raises(cb.BindingError, match="does not resolve"):
        cb.resolve_inherited(good_binding(), resolver_for({}))
    with pytest.raises(cb.BindingError, match="number"):
        cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": "long"}))
    with pytest.raises(cb.BindingError, match="number"):
        cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": True}))


def test_consumes_lists_the_inherited_addresses_sorted_with_their_hashes():
    b = good_binding()
    b["parameters"].append({"name": "in_a_x", "class": "in", "address": "a#/x", "address_unit": "mm", "unit": "mm"})
    got = cb.consumes(b, resolver_for({"snapshot#/upper_arm_right_length": 0.25, "a#/x": 5.0}))
    assert [c["address"] for c in got] == ["a#/x", "snapshot#/upper_arm_right_length"]
    assert all(len(c["hash"]) == 12 for c in got)


# ---- parameters of the bound document --------------------------------------------------------------------------------------------------

def raw_params():
    """What the Fusion-side read_params returns: the expression and the evaluated value in Fusion's internal units."""
    return [
        {"name": "in_upper_arm_right_length", "expression": "255.234699434 mm", "value": 25.5234699434},
        {"name": "dv_uam_od", "expression": "30 mm", "value": 3.0},
        {"name": "dv_uam_wall", "expression": "2 mm", "value": 0.2},
        {"name": "dr_uam_id", "expression": "dv_uam_od - 2 * dv_uam_wall", "value": 2.6},
        {"name": "dv_uam_angle", "expression": "62 deg", "value": math.radians(62)},
        {"name": "dv_uam_count", "expression": "4", "value": 4.0},
    ]


def test_matching_document_parameters_have_no_problems():
    assert cp.check_document(good_binding(), raw_params()) == []


def test_document_parameter_problems():
    b = good_binding()
    extra = raw_params() + [{"name": "stray", "expression": "1 mm", "value": 0.1}]
    assert any("stray" in p and "prefix" in p for p in cp.check_document(b, extra))
    extra2 = raw_params() + [{"name": "dv_other", "expression": "1 mm", "value": 0.1}]
    assert any("dv_other" in p and "not in the binding" in p for p in cp.check_document(b, extra2))
    missing = [r for r in raw_params() if r["name"] != "in_upper_arm_right_length"]
    assert any("in_upper_arm_right_length" in p and "missing" in p for p in cp.check_document(b, missing))
    dup = raw_params() + [raw_params()[1]]
    assert any("twice" in p for p in cp.check_document(b, dup))


def test_the_unprefixed_check_fails_when_the_prefix_test_is_removed(monkeypatch):
    extra = raw_params() + [{"name": "stray", "expression": "1 mm", "value": 0.1}]
    assert any("prefix" in p for p in cp.check_document(good_binding(), extra))
    monkeypatch.setattr(cp, "PREFIXES", ("",))  # mutation: every name "has" the prefix
    assert not any("prefix" in p for p in cp.check_document(good_binding(), extra))


def test_sidecar_parameters_convert_internal_values_to_the_binding_units():
    resolved = cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": 0.255234699434}))
    rows = cp.sidecar_parameters(good_binding(), raw_params(), resolved)
    by = {r["name"]: r for r in rows}
    assert by["dv_uam_od"]["value"] == pytest.approx(30.0) and by["dv_uam_od"]["unit"] == "mm"
    assert by["dv_uam_angle"]["value"] == pytest.approx(62.0) and by["dv_uam_angle"]["unit"] == "deg"
    assert by["dv_uam_count"]["value"] == 4.0 and by["dv_uam_count"]["unit"] == "unitless"
    assert by["in_upper_arm_right_length"]["address"] == "snapshot#/upper_arm_right_length"
    assert by["in_upper_arm_right_length"]["address_hash"] == resolved[0]["address_hash"]
    assert "address" not in by["dv_uam_od"]
    assert [r["name"] for r in rows] == sorted(by)


# ---- drift -----------------------------------------------------------------------------------------------------------------------------

def expected_rows():
    return cb.resolve_inherited(good_binding(), resolver_for({"snapshot#/upper_arm_right_length": 0.255234699434}))


def test_drift_is_empty_when_fusion_holds_the_address_value():
    assert cd.compare(expected_rows(), {"in_upper_arm_right_length": 255.234699434}) == []
    assert cd.compare(expected_rows(), {"in_upper_arm_right_length": 255.234699434 * (1 + 5e-10)}) == []


def test_drift_reports_a_changed_inherited_parameter():
    got = cd.compare(expected_rows(), {"in_upper_arm_right_length": 260.0})
    assert got == [{"name": "in_upper_arm_right_length", "address": "snapshot#/upper_arm_right_length", "fusion_value": 260.0,
                    "address_value": pytest.approx(255.234699434)}]
    assert cd.compare(expected_rows(), {"in_upper_arm_right_length": 255.234699434 * (1 + 2e-9)})


def test_drift_tolerance_is_a_named_constant_and_a_loosened_one_hides_drift(monkeypatch):
    assert cd.REL_TOL == 1e-9
    assert cd.compare(expected_rows(), {"in_upper_arm_right_length": 255.3})
    monkeypatch.setattr(cd, "REL_TOL", 1.0)
    assert cd.compare(expected_rows(), {"in_upper_arm_right_length": 255.3}) == []  # mutation: the check no longer fails


def test_an_inherited_parameter_missing_from_fusion_is_an_error_not_clean():
    with pytest.raises(cd.DriftError, match="in_upper_arm_right_length"):
        cd.compare(expected_rows(), {})


# ---- frames and mass properties ---------------------------------------------------------------------------------------------------------

def test_the_isb_marker_lands_on_the_model_axis_g7():
    L = 255.234699434
    got = cf.points_to_model([[0.0, -L, 0.0]], "right")
    assert np.allclose(got, [[0.0, 0.0, -L]], atol=1e-9)
    assert np.allclose(cf.points_to_model([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]), [[1, 0, 0], [0, 0, 1], [0, -1, 0]])


def test_the_left_side_is_refused():
    with pytest.raises((NotImplementedError, ValueError)):
        cf.points_to_model([[0, 0, 0]], "left")


def test_the_frame_conversion_uses_the_registry_rotation(monkeypatch):
    monkeypatch.setattr(registry, "ISB_TO_SEGMENT", np.eye(3))  # mutation: a swapped-axis fix would show up here
    assert np.allclose(cf.rotation("right"), np.eye(3))


def tube_inertia_about_com(m, ro, ri, L):
    """Closed form, tube axis along z: kg, mm."""
    izz = m * (ro**2 + ri**2) / 2
    ixx = m * (3 * (ro**2 + ri**2) + L**2) / 12
    return np.diag([ixx, ixx, izz])


def test_mass_properties_rotate_and_translate_to_the_model_frame():
    m, ro, ri, L = 0.3, 15.0, 13.0, 250.0
    # ISB: tube axis along -y from the origin; the centre of mass at (0, -L/2, 0)
    Iy = tube_inertia_about_com(m, ro, ri, L)  # axis z; move the axis to y by swapping z and y
    P = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)
    I_isb = P @ Iy @ P.T
    com, inertia = cf.mass_to_model((0.0, -L / 2, 0.0), _as_dict(I_isb), "right")
    assert np.allclose(com, (0.0, 0.0, -L / 2))
    got = _as_matrix(inertia)
    assert np.allclose(got, Iy, rtol=1e-12, atol=1e-9)  # the axis is now z, the model's up


def test_a_swapped_axis_fails_the_mass_property_check(monkeypatch):
    m, ro, ri, L = 0.3, 15.0, 13.0, 250.0
    P = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)
    I_isb = P @ tube_inertia_about_com(m, ro, ri, L) @ P.T
    monkeypatch.setattr(registry, "ISB_TO_SEGMENT", np.array([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]))  # mutation: no rotation
    com, inertia = cf.mass_to_model((0.0, -L / 2, 0.0), _as_dict(I_isb), "right")
    assert not np.allclose(com, (0.0, 0.0, -L / 2))


def _as_dict(M):
    return {"ixx": M[0, 0], "iyy": M[1, 1], "izz": M[2, 2], "ixy": M[0, 1], "ixz": M[0, 2], "iyz": M[1, 2]}


def _as_matrix(d):
    return np.array([[d["ixx"], d["ixy"], d["ixz"]], [d["ixy"], d["iyy"], d["iyz"]], [d["ixz"], d["iyz"], d["izz"]]])


def test_inertia_about_the_com_follows_the_parallel_axis_theorem():
    m = 0.3
    I_com = tube_inertia_about_com(m, 15.0, 13.0, 250.0)
    com = np.array([12.0, -40.0, 7.0])
    I_origin = I_com + m * (com @ com * np.eye(3) - np.outer(com, com))
    got = cf.shift_inertia_to_com(I_origin, m, com)
    assert np.allclose(got, I_com, rtol=1e-12, atol=1e-9)
    assert np.allclose(cf.shift_inertia_to_origin(I_com, m, com), I_origin)


def test_a_rotated_offset_tube_matches_the_parallel_axis_theorem_end_to_end():
    rng = np.random.default_rng(3)
    m = 0.42
    I_com = tube_inertia_about_com(m, 20.0, 17.0, 180.0)
    Rot = np.linalg.qr(rng.normal(size=(3, 3)))[0]
    if np.linalg.det(Rot) < 0:
        Rot[:, 0] *= -1
    I_rot = Rot @ I_com @ Rot.T
    com = np.array([30.0, -90.0, 15.0])
    I_origin = I_rot + m * (com @ com * np.eye(3) - np.outer(com, com))
    I_back = cf.shift_inertia_to_com(I_origin, m, com)
    assert np.allclose(I_back, I_rot, atol=1e-8)
    assert np.allclose(np.sort(np.linalg.eigvalsh(I_back)), np.sort(np.diag(I_com)), rtol=1e-12)
    assert np.allclose(cf.principal_moments(I_back), np.sort(np.diag(I_com)), rtol=1e-12)


def test_the_parallel_axis_check_fails_when_the_shift_is_wrong(monkeypatch):
    m = 0.3
    I_com = tube_inertia_about_com(m, 15.0, 13.0, 250.0)
    com = np.array([12.0, -40.0, 7.0])
    I_origin = I_com + m * (com @ com * np.eye(3) - np.outer(com, com))
    bad = cf.shift_inertia_to_com(I_origin, m * 1.01, com)  # a wrong mass is what a bad unit factor would look like
    assert not np.allclose(bad, I_com, rtol=1e-6)


# ---- canonical mesh --------------------------------------------------------------------------------------------------------------------

def cube_mesh(size=10.0, shift=(0.0, 0.0, 0.0)):
    v = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float) * size + shift
    f = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    return v, f


def test_the_same_mesh_in_two_vertex_and_face_orders_hashes_the_same():
    v, f = cube_mesh()
    rng = np.random.default_rng(1)
    perm = rng.permutation(len(v))
    inv = np.argsort(perm)
    v2, f2 = v[perm], inv[f][rng.permutation(len(f))]
    f2 = np.array([np.roll(t, int(rng.integers(0, 3))) for t in f2])  # a cyclic start is the same triangle
    assert cm.mesh_hash(v, f) == cm.mesh_hash(v2, f2)


def test_the_hash_ignores_noise_below_the_rounding_and_sees_a_real_change():
    v, f = cube_mesh()
    assert cm.mesh_hash(v, f) == cm.mesh_hash(v + 2e-6, f)
    assert cm.mesh_hash(v, f) != cm.mesh_hash(v + [0.001, 0, 0], f)
    f_flipped = f[:, ::-1]
    assert cm.mesh_hash(v, f) != cm.mesh_hash(v, f_flipped)  # winding is part of the geometry


def test_the_written_stl_is_deterministic_and_its_file_hash_equals_the_mesh_hash(tmp_path):
    v, f = cube_mesh(12.5, (1.0, -2.0, 3.0))
    a, b = tmp_path / "a.stl", tmp_path / "b.stl"
    h1 = cm.write_canonical_stl(a, v, f)
    perm = np.random.default_rng(2).permutation(len(v))
    h2 = cm.write_canonical_stl(b, v[perm], np.argsort(perm)[f])
    assert h1 == h2 == cm.hash_stl_file(a) == cm.hash_stl_file(b)
    assert a.read_bytes() == b.read_bytes()
    raw = a.read_bytes()
    assert raw[:80] == cm.HEADER and len(raw) == 84 + 50 * 12 and struct.unpack("<I", raw[80:84])[0] == 12


def test_the_written_stl_reads_back_through_the_registry_reader(tmp_path):
    v, f = cube_mesh(10.0)
    p = tmp_path / "c.stl"
    cm.write_canonical_stl(p, v, f)
    rv, rf = registry.read_stl(p)
    assert rv.shape == (8, 3) and rf.shape == (12, 3)
    assert np.allclose(rv.min(0), 0) and np.allclose(rv.max(0), 10)


def test_the_bounding_box_is_axis_aligned_in_the_given_frame():
    v, f = cube_mesh(10.0, (1.0, -2.0, 3.0))
    lo, hi = cm.bounds(v)
    assert np.allclose(lo, (1, -2, 3)) and np.allclose(hi, (11, 8, 13))


def test_a_mesh_in_the_isb_frame_is_written_in_the_model_frame(tmp_path):
    v = np.array([[0, 0, 0], [30, 0, 0], [0, -250, 0], [0, 0, 30]], float)
    f = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]])
    vm = cf.points_to_model(v, "right")
    assert np.allclose(vm[2], (0, 0, -250)) and np.allclose(vm[3], (0, -30, 0))
    assert np.linalg.det(cf.rotation("right")) == pytest.approx(1.0)  # a proper rotation: winding is kept


# ---- STEP ------------------------------------------------------------------------------------------------------------------------------

STEP_A = ("ISO-10303-21;\r\nHEADER;\r\nFILE_DESCRIPTION(('x'),'2;1');\r\n"
          "FILE_NAME('part.step','2026-10-27T10:11:12-05:00',('Joe'),('Autodesk'),'Fusion','Fusion 2705','');\r\nENDSEC;\r\nDATA;\r\n#1=CARTESIAN_POINT('',(0.,0.,0.));\r\nENDSEC;\r\nEND-ISO-10303-21;\r\n")
STEP_B = STEP_A.replace("2026-10-27T10:11:12-05:00", "2026-10-28T22:00:00+00:00")


def test_step_headers_that_differ_only_in_the_timestamp_hash_the_same():
    assert cstep.step_hash(STEP_A.encode()) == cstep.step_hash(STEP_B.encode())
    assert b"2026" not in cstep.normalise(STEP_A.encode())
    assert b"\r" not in cstep.normalise(STEP_A.encode())


FUSION_STEP = ("ISO-10303-21;\nHEADER;\n/* Generated by software containing ST-Developer */\n\nFILE_DESCRIPTION(\n/* description */ (''),\n/* implementation_level */ '2;1');\n\n"
               "FILE_NAME(\n/* name */ 'part.step',\n/* time_stamp */ '2026-10-27T21:48:48-04:00',\n/* author */ (''),\n/* organization */ (''),\n"
               "/* preprocessor_version */ 'ST-DEVELOPER v20.2',\n/* originating_system */ 'Autodesk Translation Framework v15.15.0.0',\n/* authorisation */ '');\n\n"
               "ENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\nEND-ISO-10303-21;\n")


def test_fusions_own_step_header_with_comments_between_the_fields_is_normalised():
    later = FUSION_STEP.replace("2026-10-27T21:48:48-04:00", "2027-01-01T00:00:00+01:00")
    assert cstep.step_hash(FUSION_STEP.encode()) == cstep.step_hash(later.encode())
    assert b"2026" not in cstep.normalise(FUSION_STEP.encode()) and b"'part.step'" in cstep.normalise(FUSION_STEP.encode())
    # the name field is not the timestamp: a different file name is a different file
    assert cstep.step_hash(FUSION_STEP.encode()) != cstep.step_hash(FUSION_STEP.replace("part.step", "other.step").encode())


def test_a_step_body_change_changes_the_hash():
    changed = STEP_A.replace("(0.,0.,0.)", "(0.,0.,1.)")
    assert cstep.step_hash(STEP_A.encode()) != cstep.step_hash(changed.encode())


def test_a_step_without_a_file_name_header_is_refused():
    with pytest.raises(ValueError):
        cstep.normalise(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")


# ---- sidecar and component -------------------------------------------------------------------------------------------------------------

def sidecar_pieces():
    d = copy.deepcopy(SIDECAR_OK)
    for k in ("schema", "generated_by", "inputs"):
        d.pop(k)
    return d


def test_the_assembled_sidecar_validates_and_carries_the_banner_and_no_timestamps():
    doc = cs.assemble(**sidecar_pieces())
    assert doc["schema"] == "cad-sidecar/1" and doc["generated_by"] == "tools/cad pull"
    assert doc["inputs"].startswith("sha256:") and len(doc["inputs"]) == len("sha256:") + 12
    assert cs.problems(doc) == []
    text = cs.dumps(doc)
    assert text.endswith("\n") and "\r" not in text and text == cs.dumps(json.loads(text))
    assert json.loads(text) == doc


def test_the_sidecar_inputs_hash_changes_with_the_content_and_not_with_key_order():
    a = cs.assemble(**sidecar_pieces())
    b_pieces = sidecar_pieces()
    b_pieces["mass_properties"]["mass_kg"] = 0.2
    assert cs.assemble(**b_pieces)["inputs"] != a["inputs"]
    c_pieces = dict(reversed(list(sidecar_pieces().items())))
    assert cs.assemble(**c_pieces)["inputs"] == a["inputs"]


def test_an_invalid_sidecar_is_not_written(tmp_path):
    pieces = sidecar_pieces()
    pieces["timeline"] = {"healthy": True}
    with pytest.raises(ValueError, match="failed_features"):
        cs.assemble(**pieces)
    doc = cs.assemble(**sidecar_pieces())
    p = tmp_path / "x.json"
    cs.write(p, doc)
    assert p.read_bytes() == cs.dumps(doc).encode("utf-8")


def test_the_sidecar_refuses_an_unhealthy_timeline_for_a_pull():
    pieces = sidecar_pieces()
    pieces["timeline"] = {"healthy": False, "failed_features": ["Extrude1"]}
    with pytest.raises(ValueError, match="Extrude1"):
        cs.assemble(**pieces, require_healthy=True)


def test_the_component_entry_is_a_box_around_the_model_frame_mesh_with_the_binding_clearance():
    v = np.array([[-15, -15, -250], [15, -15, -250], [15, 15, 0], [-15, 15, 0]], float)
    entry = cc.component_entry(good_binding(), segment="upper_arm_R", vertices_model=v, mesh_hash="a" * 64, mass_kg=0.25,
                               consumes=[{"address": "snapshot#/upper_arm_right_length", "hash": "0123456789ab"}],
                               mesh_path="cad/exports/part.arm.upper_member.stl")
    assert entry["id"] == "part.arm.upper_member" and entry["revision"] == "p1" and entry["status"] == "designed"
    assert entry["primitive"] == {"type": "box", "half": [15.0, 15.0, 125.0], "offset": [0.0, 0.0, -125.0]}
    assert entry["clearance_mm"] == 2.0 and entry["mass_kg"] == 0.25 and entry["sha256"] == "a" * 64
    assert entry["owner"] == "upper_arm_R" and entry["mesh"] == "cad/exports/part.arm.upper_member.stl"
    assert len(entry["parameter_inputs"]) == 12
    assert entry["parameter_inputs"] == cc.parameter_inputs([{"address": "snapshot#/upper_arm_right_length", "hash": "0123456789ab"}])


def test_the_box_carries_no_float_noise():
    v = np.array([[-14.979992, -14.989993, -255.2346994], [14.979991999999, 14.989993, 0.0]], float)
    e = cc.component_entry(good_binding(), segment="upper_arm_R", vertices_model=v, mesh_hash="a" * 64, mass_kg=0.1, consumes=[], mesh_path="x.stl")
    assert e["primitive"]["half"] == [14.98, 14.99, 127.6173] and e["primitive"]["offset"] == [0.0, 0.0, -127.6173]


def test_the_parameter_inputs_hash_follows_the_consumed_hashes():
    a = cc.parameter_inputs([{"address": "x#/a", "hash": "0" * 12}])
    assert a != cc.parameter_inputs([{"address": "x#/a", "hash": "1" * 12}])
    assert a == cc.parameter_inputs([{"hash": "0" * 12, "address": "x#/a"}])


def test_the_entry_passes_the_registry_loader_as_a_component(tmp_path):
    v = np.array([[-15, -15, -250], [15, 15, 0]], float)
    entry = cc.component_entry(good_binding(), segment="upper_arm_R", vertices_model=v, mesh_hash="b" * 64, mass_kg=0.25, consumes=[],
                               mesh_path="cad/exports/part.arm.upper_member.stl")
    comp = {k: entry[k] for k in ("id", "name", "status", "owner", "primitive", "clearance_mm", "mass_kg")}
    reg = registry.parse({"schema": "components/1", "segment": "upper_arm_R", "components": [comp]})
    assert len(reg.components) == 1 and reg.components[0].id == "part.arm.upper_member"


def test_the_library_imports_neither_mujoco_nor_adsk():
    import re
    for p in sorted((REPO / "tools" / "cad").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(mujoco|adsk)\b", text, re.M), p.name


def test_no_unit_factor_appears_outside_the_conversion_module():
    import ast
    factors = {10, 100, 1000, 0.1, 0.01, 0.001, 180, 1e6, 1e-6, 1e3}
    for p in sorted((REPO / "tools" / "cad").glob("*.py")):
        if p.name == "units.py":
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        found = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)} & factors
        assert not found, (p.name, found)
        assert "math.pi" not in p.read_text(encoding="utf-8").replace('"""', ""), p.name
