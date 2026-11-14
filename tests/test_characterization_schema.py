"""
The characterization schemas (docs/briefs/ariadne/upper-arm-characterization-brief.md, T4; gate G-S7): segment-characterization/1 (adr-0045
D2) and characterization-inputs/1 (T5). A hand-written minimal fixture of each validates, and each mutation the gate names fails.

    python -m pytest tests/test_characterization_schema.py
"""
import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
SCHEMAS = REPO / "docs" / "schemas"
FIXTURES = Path(__file__).parent / "fixtures" / "characterization"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


CHAR = load("segment-characterization-1.schema.json")
INPUTS = load("characterization-inputs-1.schema.json")
MINIMAL = json.loads((FIXTURES / "minimal.json").read_text(encoding="utf-8"))
MINIMAL_INPUTS = json.loads(json.dumps(yaml.safe_load((FIXTURES / "minimal_inputs.yaml").read_text(encoding="utf-8"))))


def errors(schema, doc):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(doc))


def mutate(doc, fn):
    d = copy.deepcopy(doc)
    fn(d)
    return d


def test_both_schemas_are_valid_draft_2020_12():
    for s in (CHAR, INPUTS):
        jsonschema.Draft202012Validator.check_schema(s)
    assert CHAR["$id"] == "segment-characterization/1" and INPUTS["$id"] == "characterization-inputs/1"


def test_the_minimal_fixtures_validate():
    assert errors(CHAR, MINIMAL) == []
    assert errors(INPUTS, MINIMAL_INPUTS) == []


def _no_additional(node, path="#"):
    """Every object schema closes its properties (additionalProperties false, or a schema for them)."""
    bad = []
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node and "additionalProperties" not in node:
            bad.append(path)
        for k, v in node.items():
            bad += _no_additional(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            bad += _no_additional(v, f"{path}/{i}")
    return bad


@pytest.mark.parametrize("schema", [CHAR, INPUTS], ids=["characterization", "inputs"])
def test_every_object_closes_its_properties(schema):
    assert _no_additional(schema) == []


CHAR_ERRORS = {
    "missing generated_by": lambda d: d.pop("generated_by"),
    "missing inputs": lambda d: d.pop("inputs"),
    "an inputs banner that is not a hash": lambda d: d.update(inputs="2026-11-14T10:00"),
    "an unknown top-level key": lambda d: d.update(notes="x"),
    "an actuator key": lambda d: d.update(actuator={"peak_torque_nm": 10}),
    "a timestamp key": lambda d: d.update(generated_at="2026-11-14"),
    "the left side": lambda d: d.update(side="left"),
    "no frame statement": lambda d: d["frame"].pop("statement"),
    "an anchor position without its bar": lambda d: d["anchors"]["elbow"]["position"].pop("bar"),
    "an interface origin without its bar": lambda d: d["interfaces"]["elbow"]["frame"]["origin"].pop("bar"),
    "a contact position without its bar": lambda d: d["load_cases"]["fall"][0]["contact"]["position"].pop("bar"),
    "an SJC bar of 0": lambda d: d["anchors"]["shoulder"]["position"]["bar"].update(value_mm=0),
    "an SJC bar of a string other than unstated": lambda d: d["anchors"]["shoulder"]["position"]["bar"].update(value_mm="zero"),
    "a bar without its source": lambda d: d["anchors"]["elbow"]["position"]["bar"].pop("source"),
    "a fall case without a flag": lambda d: d["load_cases"]["fall"][0].pop("flag"),
    "a fall case without its basis": lambda d: d["load_cases"]["fall"][0].pop("basis"),
    "a fall case with an empty basis": lambda d: d["load_cases"]["fall"][0].update(basis=[]),
    "a fall case with an unknown flag": lambda d: d["load_cases"]["fall"][0].update(flag="cosmetic"),
    "a fall case without energy": lambda d: d["load_cases"]["fall"][0].pop("energy_j"),
    "a fall case without its contact": lambda d: d["load_cases"]["fall"][0].pop("contact"),
    "a fall case reaching by another relation": lambda d: d["load_cases"]["fall"][0].update(reaches_by=["zone_in"]),
    "an interface without sections": lambda d: d["interfaces"]["elbow"].pop("sections"),
    "an interface with three bracketing rows": lambda d: d["interfaces"]["elbow"]["sections"].append(d["interfaces"]["elbow"]["sections"][0]),
    "a ray with an unknown label": lambda d: d["interfaces"]["elbow"]["sections"][0]["rays"]["r_ant_mm"].update(label="bone"),
    "no ROM loaded arc": lambda d: d["rom"].pop("loaded_arc"),
    "no flexion clearance": lambda d: d["rom"].pop("flexion_clearance"),
    "no volume": lambda d: d.pop("volume"),
    "load cases without the inertial split": lambda d: d["load_cases"].pop("inertial"),
    "a load-case split of another name": lambda d: d["load_cases"].update(actuator_peak=[]),
    "a bolt circle on an interface": lambda d: d["interfaces"]["elbow"].update(bolt_circle_mm=40),
    # Joe's answer 2 to memo 62: an interface holds only the governing wrench per case and component; the sweeps live in load_cases.
    "an interface wrench that does not name the component it governs": lambda d: d["interfaces"]["elbow"]["wrenches"][0].pop("governs"),
    "an interface wrench governing an unknown component": lambda d: d["interfaces"]["elbow"]["wrenches"][0].update(governs="force_sum"),
    "an interface wrench carrying a sweep": lambda d: d["interfaces"]["elbow"]["wrenches"][0].update(angles_deg=[0, 1]),
}


@pytest.mark.parametrize("name", sorted(CHAR_ERRORS))
def test_each_characterization_mutation_fails(name):
    assert errors(CHAR, mutate(MINIMAL, CHAR_ERRORS[name])), name


INPUT_ERRORS = {
    "an entry without its source": lambda d: d["shell"].pop("source"),
    "an entry with an empty source": lambda d: d["shell"].update(source=[]),
    "an entry citing a clause that is not D<n>": lambda d: d["shell"].update(source=[{"record": "adr-0007", "clause": "4"}]),
    "an entry without its unit": lambda d: d["shell"].pop("unit"),
    "a null value without source_needed": lambda d: d["rom"]["loaded_arc"].pop("source_needed"),
    "source_needed on a value": lambda d: d["shell"].update(source_needed=True),
    "a bar of 0": lambda d: d["anchor_bars"]["shoulder"].update(value=0),
    "a bar in another unit": lambda d: d["anchor_bars"]["elbow"].update(unit="cm"),
    "a flag that is not structural or clearance": lambda d: d["fall_flags"]["lc.fall-x"].update(value="cosmetic"),
    "a flag without provisional": lambda d: d["fall_flags"]["lc.fall-x"].pop("provisional"),
    "an unknown top-level key": lambda d: d.update(actuator={"value": 1, "unit": "N m", "source": []}),
    "the left side": lambda d: d.update(side="left"),
    "no flags": lambda d: d.pop("fall_flags"),
    "a swing row without its duration": lambda d: d["swing_rows"]["S1"].pop("duration"),
}


@pytest.mark.parametrize("name", sorted(INPUT_ERRORS))
def test_each_inputs_mutation_fails(name):
    assert errors(INPUTS, mutate(MINIMAL_INPUTS, INPUT_ERRORS[name])), name
