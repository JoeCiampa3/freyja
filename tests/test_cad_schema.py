"""
Stage 3b T1: the two CAD bridge schemas (docs/schemas/cad-binding-1, cad-sidecar-1). Each accepts one valid example and rejects one example of
each schema-level error. What a schema cannot say (two parameters with one name, an address that does not resolve, a name that does not follow
from its address) is the library's job (tests/test_cad_binding.py).

    python -m pytest tests/test_cad_schema.py
"""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

SCHEMAS = Path(__file__).resolve().parents[1] / "docs" / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


BINDING = load("cad-binding-1.schema.json")
SIDECAR = load("cad-sidecar-1.schema.json")


def errors(schema, doc):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(doc))


BINDING_OK = {
    "schema": "cad-binding/1",
    "part": "part.arm.upper_member",
    "revision": "p1",
    "document": {"name": "freyja-bridge-fixture", "id": "urn:adsk.wipprod:dm.lineage:abc"},
    "side": "right",
    "chord_tolerance_mm": 0.05,
    "clearance_mm": 2.0,
    "parameters": [
        {"name": "in_upper_arm_right_length", "class": "in", "address": "snapshot#/upper_arm_right_length", "address_unit": "m", "unit": "mm"},
        {"name": "dv_uam_od", "class": "dv", "unit": "mm"},
        {"name": "dv_uam_wall", "class": "dv", "unit": "mm"},
        {"name": "dr_uam_id", "class": "dr", "unit": "mm"},
        {"name": "dv_uam_angle", "class": "dv", "unit": "deg"},
        {"name": "dv_uam_count", "class": "dv", "unit": "unitless"},
    ],
}

SIDECAR_OK = {
    "schema": "cad-sidecar/1",
    "generated_by": "tools/cad pull",
    "inputs": "sha256:0123456789ab",
    "identity": {"part": "part.arm.upper_member", "revision": "p1", "side": "right", "binding_sha256": "0123456789ab"},
    "document": {"name": "freyja-bridge-fixture", "id": "urn:adsk.wipprod:dm.lineage:abc", "version": 7, "unsaved_changes": False},
    "parameters": [
        {"name": "in_upper_arm_right_length", "class": "in", "expression": "255.234699434 mm", "value": 255.234699434, "unit": "mm",
         "address": "snapshot#/upper_arm_right_length", "address_hash": "0123456789ab"},
        {"name": "dv_uam_od", "class": "dv", "expression": "30 mm", "value": 30.0, "unit": "mm"},
        {"name": "dr_uam_id", "class": "dr", "expression": "dv_uam_od - 2 * dv_uam_wall", "value": 26.0, "unit": "mm"},
    ],
    "drift": [],
    "timeline": {"healthy": True, "failed_features": []},
    "mass_properties": {
        "material": {"name": "Aluminum 6061", "density_kg_m3": 2700.0},
        "mass_kg": 0.1,
        "com_mm": [0.0, 0.0, -127.6],
        "inertia_kgmm2": {"ixx": 1.0, "iyy": 1.0, "izz": 0.1, "ixy": 0.0, "ixz": 0.0, "iyz": 0.0},
        "accuracy": "VeryHigh",
    },
    "exports": {
        "stl": {"path": "cad/exports/part.arm.upper_member.stl", "sha256": "0" * 64, "chord_tolerance_mm": 0.05, "normal_deviation_deg": 9.36, "chord_bound_mm": 0.0499,
                "chord_guarantee": True, "triangles": 1200},
        "step": {"path": "cad/exports/part.arm.upper_member.step", "sha256": "1" * 64},
    },
    "component": {
        "id": "part.arm.upper_member", "revision": "p1", "name": "upper arm member", "status": "designed", "clearance_mm": 2.0,
        "mass_kg": 0.1, "sha256": "0" * 64, "parameter_inputs": "0123456789ab",
        "primitive": {"type": "box", "size_mm": [30.0, 30.0, 255.2], "offset_mm": [0.0, 0.0, -127.6]},
        "mesh": "cad/exports/part.arm.upper_member.stl",
    },
    "consumes": [{"address": "snapshot#/upper_arm_right_length", "hash": "0123456789ab"}],
}


def mutated(doc, path, value=None, delete=False):
    d = copy.deepcopy(doc)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    if delete:
        del cur[path[-1]]
    else:
        cur[path[-1]] = value
    return d


def test_the_valid_examples_are_accepted():
    assert errors(BINDING, BINDING_OK) == []
    assert errors(SIDECAR, SIDECAR_OK) == []


def test_the_schemas_are_themselves_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(BINDING)
    jsonschema.Draft202012Validator.check_schema(SIDECAR)


BINDING_BAD = {
    "side left": mutated(BINDING_OK, ["side"], "left"),
    "side missing": mutated(BINDING_OK, ["side"], delete=True),
    "unknown side": mutated(BINDING_OK, ["side"], "both"),
    "wrong schema const": mutated(BINDING_OK, ["schema"], "cad-binding/2"),
    "part id not a part": mutated(BINDING_OK, ["part"], "seg.upper_arm"),
    "revision empty": mutated(BINDING_OK, ["revision"], ""),
    "revision not a string": mutated(BINDING_OK, ["revision"], 1),
    "document id missing": mutated(BINDING_OK, ["document", "id"], delete=True),
    "chord tolerance zero": mutated(BINDING_OK, ["chord_tolerance_mm"], 0),
    "negative clearance": mutated(BINDING_OK, ["clearance_mm"], -1),
    "extra top-level key": mutated(BINDING_OK, ["notes"], "x"),
    "unprefixed parameter": mutated(BINDING_OK, ["parameters", 1, "name"], "uam_od"),
    "prefix disagrees with class": mutated(BINDING_OK, ["parameters", 1, "name"], "dr_uam_od"),
    "inherited without address": mutated(BINDING_OK, ["parameters", 0, "address"], delete=True),
    "inherited without address unit": mutated(BINDING_OK, ["parameters", 0, "address_unit"], delete=True),
    "inherited not prefixed in_": mutated(BINDING_OK, ["parameters", 0, "name"], "dv_upper_arm_right_length"),
    "design with an address": mutated(BINDING_OK, ["parameters", 1, "address"], "snapshot#/x"),
    "unknown class": mutated(BINDING_OK, ["parameters", 1, "class"], "xx"),
    "unit suffix style unit": mutated(BINDING_OK, ["parameters", 1, "unit"], "cm"),
    "parameter missing unit": mutated(BINDING_OK, ["parameters", 1, "unit"], delete=True),
    "identical duplicate parameter": mutated(BINDING_OK, ["parameters"], BINDING_OK["parameters"] + [BINDING_OK["parameters"][1]]),
    "no parameters key": mutated(BINDING_OK, ["parameters"], delete=True),
}


@pytest.mark.parametrize("case", sorted(BINDING_BAD))
def test_the_binding_schema_rejects(case):
    assert errors(BINDING, BINDING_BAD[case]), case


SIDECAR_BAD = {
    "side left": mutated(SIDECAR_OK, ["identity", "side"], "left"),
    "wrong schema const": mutated(SIDECAR_OK, ["schema"], "cad-sidecar/2"),
    "banner generated_by missing": mutated(SIDECAR_OK, ["generated_by"], delete=True),
    "banner inputs missing": mutated(SIDECAR_OK, ["inputs"], delete=True),
    "binding hash not 12 hex": mutated(SIDECAR_OK, ["identity", "binding_sha256"], "xyz"),
    "document version not an integer": mutated(SIDECAR_OK, ["document", "version"], "7"),
    "unsaved_changes missing": mutated(SIDECAR_OK, ["document", "unsaved_changes"], delete=True),
    "unsaved_changes not a boolean": mutated(SIDECAR_OK, ["document", "unsaved_changes"], "no"),
    "unprefixed parameter": mutated(SIDECAR_OK, ["parameters", 1, "name"], "od"),
    "inherited without address": mutated(SIDECAR_OK, ["parameters", 0, "address"], delete=True),
    "inherited without address hash": mutated(SIDECAR_OK, ["parameters", 0, "address_hash"], delete=True),
    "parameter without expression": mutated(SIDECAR_OK, ["parameters", 1, "expression"], delete=True),
    "parameter value not a number": mutated(SIDECAR_OK, ["parameters", 1, "value"], "30"),
    "drift entry missing address": mutated(SIDECAR_OK, ["drift"], [{"name": "in_x", "fusion_value": 1.0, "address_value": 2.0}]),
    "timeline healthy missing": mutated(SIDECAR_OK, ["timeline", "healthy"], delete=True),
    "com with two entries": mutated(SIDECAR_OK, ["mass_properties", "com_mm"], [0.0, 0.0]),
    "inertia component missing": mutated(SIDECAR_OK, ["mass_properties", "inertia_kgmm2", "iyz"], delete=True),
    "negative mass": mutated(SIDECAR_OK, ["mass_properties", "mass_kg"], -0.1),
    "accuracy missing": mutated(SIDECAR_OK, ["mass_properties", "accuracy"], delete=True),
    "stl hash not 64 hex": mutated(SIDECAR_OK, ["exports", "stl", "sha256"], "abc"),
    "stl triangles zero": mutated(SIDECAR_OK, ["exports", "stl", "triangles"], 0),
    "stl chord bound missing": mutated(SIDECAR_OK, ["exports", "stl", "chord_bound_mm"], delete=True),
    "stl chord bound negative": mutated(SIDECAR_OK, ["exports", "stl", "chord_bound_mm"], -0.01),
    "stl chord guarantee missing": mutated(SIDECAR_OK, ["exports", "stl", "chord_guarantee"], delete=True),
    "stl chord guarantee not a boolean": mutated(SIDECAR_OK, ["exports", "stl", "chord_guarantee"], "yes"),
    "stl normal deviation missing": mutated(SIDECAR_OK, ["exports", "stl", "normal_deviation_deg"], delete=True),
    "stl normal deviation zero": mutated(SIDECAR_OK, ["exports", "stl", "normal_deviation_deg"], 0),
    "stl path absolute": mutated(SIDECAR_OK, ["exports", "stl", "path"], "C:/x/y.stl"),
    "component id not a part": mutated(SIDECAR_OK, ["component", "id"], "thigh"),
    "component without primitive": mutated(SIDECAR_OK, ["component", "primitive"], delete=True),
    "consumes hash not 12 hex": mutated(SIDECAR_OK, ["consumes", 0, "hash"], "1"),
    "timestamp key": mutated(SIDECAR_OK, ["created"], "2026-10-27"),
}


@pytest.mark.parametrize("case", sorted(SIDECAR_BAD))
def test_the_sidecar_schema_rejects(case):
    assert errors(SIDECAR, SIDECAR_BAD[case]), case


def test_the_thread_record_schema_accepts_the_address_form_of_a_part_mass_and_still_the_typed_form():
    rec = load("thread-record-1.schema.json")
    base = {"schema": "thread-record/1", "id": "part.arm.upper_member", "kind": "part", "status": "proposed", "purpose": "Bridge test article.",
            "housed_in": "seg.upper_arm", "category": "structure", "sides": ["left", "right"]}
    typed = {**base, "mass": {"kg": 1.2, "source": "datasheet", "reserved": False}}
    addr = {**base, "mass": {"address": "cad/sidecars/part.arm.upper_member.json#/mass_properties/mass_kg", "source": "CAD sidecar"}}
    assert errors(rec, typed) == []
    assert errors(rec, addr) == []
    assert errors(rec, {**base, "mass": {"address": "x#/y", "source": "s", "kg": 1.0}})  # both forms at once
    assert errors(rec, {**base, "mass": {"address": "x#/y"}})  # source is required
    assert errors(rec, {**base, "mass": {"source": "s"}})  # neither form
