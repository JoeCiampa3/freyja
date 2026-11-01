"""
Thread T1: the three schemas (docs/schemas/thread-record-2, thread-stamp-1, thread-graph-1). Each accepts one valid example per kind and
rejects one example of each schema-level error. Reference resolution, kinds of referenced records and everything across records is the
library's job (tests/test_thread_validate.py), so the schema accepts any record id in a reference field.

    python -m pytest tests/test_thread_schema.py
"""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

SCHEMAS = Path(__file__).resolve().parents[1] / "docs" / "schemas"


def load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


RECORD = load("thread-record-2.schema.json")
STAMP = load("thread-stamp-1.schema.json")
GRAPH = load("thread-graph-1.schema.json")


def errors(schema, doc):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(doc))


def base(kind, id, **f):
    return {"schema": "thread-record/2", "id": id, "kind": kind, "status": "proposed", "purpose": "Why this exists.", **f}


EXAMPLES = {
    "segment": base("segment", "seg.thigh", body="thigh", sides=["left", "right"]),
    "joint": base("joint", "jnt.hip", hinges=["hip_fe", "hip_aa", "hip_ier"], rom_keys=["hip_flexion", "hip_extension"], sides=["left", "right"]),
    "part": base("part", "part.hip.m2", housed_in="seg.thigh", acts_across="jnt.hip", reacts_into="seg.thigh", harness=["hn.leg-power"],
                 mass={"kg": 1.2, "source": "datasheet", "reserved": False}, category="actuator", catalog="catalog/actuators/akh70.yaml",
                 sides=["left", "right"]),
    "interface": base("interface", "if.hip-m2-thigh", between=["part.hip.m2", "seg.thigh"], carries_cut_of="jnt.hip",
                      mechanical={"status": "open", "notes": "bolt pattern"}, electrical={"status": "defined"}, thermal={"status": "open"}),
    "load_case": base("load_case", "lc.walk-1p4", source={"gait_spec": "walk_treadmill", "condition": "1.4 m/s"}, independent_source_required=False),
    "harness_run": base("harness_run", "hn.leg-power", path=["seg.pelvis", "seg.thigh", "seg.shank"], carries="motor power"),
    "work_item": base("work_item", "work.thigh-cad", of="seg.thigh", mode="assisted", consumes=["snapshot#/thigh_right_mass", "part.hip.m2#/housed_in"],
                      output="cad/exports/thigh.step"),
}


def test_schema_files_are_valid_schemas():
    for s in (RECORD, STAMP, GRAPH):
        jsonschema.Draft202012Validator.check_schema(s)


@pytest.mark.parametrize("kind", sorted(EXAMPLES))
def test_each_kind_accepts_its_valid_example(kind):
    assert errors(RECORD, EXAMPLES[kind]) == []


def test_every_kind_has_an_example():
    assert sorted(EXAMPLES) == ["harness_run", "interface", "joint", "load_case", "part", "segment", "work_item"]


def test_minimal_examples_without_optional_fields_are_valid():
    for kind, drop in (("segment", ["sides"]), ("part", ["acts_across", "reacts_into", "harness", "catalog", "sides"]), ("interface", ["carries_cut_of"]),
                       ("work_item", ["output"])):
        doc = copy.deepcopy(EXAMPLES[kind])
        for k in drop:
            doc.pop(k)
        assert errors(RECORD, doc) == [], kind
    doc = copy.deepcopy(EXAMPLES["load_case"])
    doc["source"] = {"scenario": "stand_static"}
    assert errors(RECORD, doc) == []
    doc = copy.deepcopy(EXAMPLES["segment"])
    doc.update(status="superseded", superseded_by="seg.thigh2", notes="n")
    assert errors(RECORD, doc) == []


def mutate(kind, fn):
    doc = copy.deepcopy(EXAMPLES[kind])
    fn(doc)
    return doc


SCHEMA_ERRORS = {
    "wrong schema string": ("segment", lambda d: d.update(schema="thread-record/3")),
    "unknown kind": ("segment", lambda d: d.update(kind="widget")),
    "id prefix does not match kind": ("segment", lambda d: d.update(id="jnt.thigh")),
    "id with an upper-case letter": ("segment", lambda d: d.update(id="seg.Thigh")),
    "unknown status": ("segment", lambda d: d.update(status="draft")),
    "missing purpose": ("segment", lambda d: d.pop("purpose")),
    "empty purpose": ("segment", lambda d: d.update(purpose="")),
    "unknown field": ("segment", lambda d: d.update(colour="red")),
    "superseded without superseded_by": ("segment", lambda d: d.update(status="superseded")),
    "superseded_by on a live record": ("segment", lambda d: d.update(superseded_by="seg.x")),
    "segment without body": ("segment", lambda d: d.pop("body")),
    "sides not left and right": ("segment", lambda d: d.update(sides=["right"])),
    "joint without hinges": ("joint", lambda d: d.pop("hinges")),
    "joint with no hinge listed": ("joint", lambda d: d.update(hinges=[])),
    "joint without rom_keys": ("joint", lambda d: d.pop("rom_keys")),
    "part without housed_in": ("part", lambda d: d.pop("housed_in")),
    "part without mass": ("part", lambda d: d.pop("mass")),
    "part mass without reserved": ("part", lambda d: d["mass"].pop("reserved")),
    "part mass negative": ("part", lambda d: d["mass"].update(kg=-1)),
    "part mass reserved not a boolean": ("part", lambda d: d["mass"].update(reserved="yes")),
    "part without category": ("part", lambda d: d.pop("category")),
    "acts_across without reacts_into": ("part", lambda d: d.pop("reacts_into")),
    "interface with one end": ("interface", lambda d: d.update(between=["part.hip.m2"])),
    "interface with three ends": ("interface", lambda d: d.update(between=["part.hip.m2", "seg.thigh", "seg.pelvis"])),
    "interface with the same end twice": ("interface", lambda d: d.update(between=["seg.thigh", "seg.thigh"])),
    "interface without electrical": ("interface", lambda d: d.pop("electrical")),
    "interface status not open or defined": ("interface", lambda d: d["mechanical"].update(status="done")),
    "load case source with both keys": ("load_case", lambda d: d["source"].update(scenario="stand_static")),
    "load case source with neither key": ("load_case", lambda d: d.update(source={"condition": "x"})),
    "load case gait source without condition": ("load_case", lambda d: d.update(source={"gait_spec": "walk_treadmill"})),
    "load case without independent_source_required": ("load_case", lambda d: d.pop("independent_source_required")),
    "harness path of one segment": ("harness_run", lambda d: d.update(path=["seg.pelvis"])),
    "work item without of": ("work_item", lambda d: d.pop("of")),
    "work item mode neither assisted nor manual": ("work_item", lambda d: d.update(mode="automatic")),
    "work item consumes not an address": ("work_item", lambda d: d.update(consumes=["no hash sign"])),
    "work item consumes pointer without a slash": ("work_item", lambda d: d.update(consumes=["snapshot#thigh_right_mass"])),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_ERRORS))
def test_each_schema_level_error_is_rejected(name):
    kind, fn = SCHEMA_ERRORS[name]
    assert errors(RECORD, mutate(kind, fn)), name


def test_a_field_of_another_kind_is_rejected():
    assert errors(RECORD, mutate("segment", lambda d: d.update(housed_in="seg.thigh")))


FALL = base("load_case", "lc.fall-hip-lateral", source={"zone": "hip", "direction": "lateral, hip first", "energy_j": 540, "energy_basis": "E_max"},
            zone_in="seg.pelvis", independent_source_required=True, evidence=[{"kind": "decision", "record": "adr-0037", "clause": "D1(b)"}])
ADR, ROW, TEST = {"kind": "decision", "record": "adr-0037", "clause": "D3"}, {"kind": "literature", "file": "data/falls/sources.md", "row": "S1"}, {"kind": "test", "path": "bench/drop.json"}


def fall(fn):
    doc = copy.deepcopy(FALL)
    fn(doc)
    return doc


@pytest.mark.parametrize("source, flag", [({"scenario": "stand_static"}, False), ({"scenario": "fall_impact"}, True),
                                          ({"gait_spec": "walk_treadmill", "condition": "1.4 m/s"}, False)])
def test_the_scenario_and_gait_forms_accept_either_flag_and_no_zone(source, flag):
    assert errors(RECORD, mutate("load_case", lambda d: d.update(source=source, independent_source_required=flag))) == []


def test_the_energy_form_is_accepted_with_and_without_its_optional_numbers():
    assert errors(RECORD, FALL) == []
    assert errors(RECORD, fall(lambda d: d["source"].update(contact_velocity_m_s=3.0, effective_mass_kg=30.0))) == []


@pytest.mark.parametrize("entry", [ADR, ROW, TEST, {**ADR, "note": "why"}, {**ROW, "note": "cross-check"}, {**TEST, "note": "n"},
                                   {**ADR, "clause": "D3"}, {**ADR, "clause": "D10"}, {**ADR, "clause": "D1(b)"}])
def test_each_evidence_kind_is_accepted(entry):
    assert errors(RECORD, mutate("load_case", lambda d: d.update(evidence=[entry]))) == []


def test_an_empty_evidence_list_is_valid_because_it_is_how_a_what_if_removes_evidence():
    assert errors(RECORD, mutate("load_case", lambda d: d.update(evidence=[]))) == []


EVIDENCE_ERRORS = {
    "unknown evidence kind": lambda d: d.update(evidence=[{"kind": "hearsay", "path": "x.json"}]),
    "decision without clause": lambda d: d.update(evidence=[{"kind": "decision", "record": "adr-0037"}]),
    "clause without a D": lambda d: d.update(evidence=[{**ADR, "clause": "1(b)"}]),
    "clause with two letters": lambda d: d.update(evidence=[{**ADR, "clause": "D1(bc)"}]),
    "clause with an upper-case letter": lambda d: d.update(evidence=[{**ADR, "clause": "D1(B)"}]),
    "clause with a trailing word": lambda d: d.update(evidence=[{**ADR, "clause": "D1 extra"}]),
    "decision record not an adr id": lambda d: d.update(evidence=[{**ADR, "record": "0037"}]),
    "literature without row": lambda d: d.update(evidence=[{"kind": "literature", "file": "x.md"}]),
    "test without path": lambda d: d.update(evidence=[{"kind": "test"}]),
    "a field of another evidence kind": lambda d: d.update(evidence=[{**ADR, "row": "S1"}]),
    "a repeated entry": lambda d: d.update(evidence=[ADR, ADR]),
    "the energy form with the flag false": lambda d: d.update(independent_source_required=False),
    "the energy form without zone_in": lambda d: d.pop("zone_in"),
    "energy_j of 0": lambda d: d["source"].update(energy_j=0),
    "energy_j negative": lambda d: d["source"].update(energy_j=-1),
    "energy form without direction": lambda d: d["source"].pop("direction"),
    "energy form without energy_basis": lambda d: d["source"].pop("energy_basis"),
    "energy form with a zone that is not a slug": lambda d: d["source"].update(zone="hand and arm"),
    "energy form with an unknown key": lambda d: d["source"].update(force_n=1000),
}


@pytest.mark.parametrize("name", sorted(EVIDENCE_ERRORS))
def test_each_evidence_and_energy_error_is_rejected(name):
    assert errors(RECORD, fall(EVIDENCE_ERRORS[name])), name


def test_zone_in_on_the_other_source_forms_is_rejected():
    assert errors(RECORD, mutate("load_case", lambda d: d.update(source={"scenario": "stand_static"}, zone_in="seg.pelvis")))
    assert errors(RECORD, mutate("load_case", lambda d: d.update(zone_in="seg.pelvis")))


def test_evidence_and_zone_in_on_a_record_that_is_not_a_load_case_are_rejected():
    assert errors(RECORD, mutate("part", lambda d: d.update(evidence=[ADR])))
    assert errors(RECORD, mutate("work_item", lambda d: d.update(zone_in="seg.pelvis")))


def test_a_record_in_the_old_schema_is_rejected():
    assert errors(RECORD, mutate("segment", lambda d: d.update(schema="thread-record/1")))


def test_the_old_schema_file_stays_as_history():
    assert load("thread-record-1.schema.json")["$id"] == "thread-record/1"


def test_every_real_record_is_on_the_new_schema():
    records = sorted((SCHEMAS.parents[1] / "thread" / "records").glob("*.yaml"))
    assert records and [p.name for p in records if "\nschema: thread-record/2\n" not in "\n" + p.read_text(encoding="utf-8")] == []


STAMP_OK = {
    "schema": "thread-stamp/1", "work": "work.thigh-cad", "stamp": "20261018-1430",
    "consumes": [{"address": "snapshot#/thigh_right_mass", "hash": "0123456789ab", "value": "6.4"},
                 {"address": "thread/derived/seg.thigh.json#/houses", "hash": "ba9876543210", "value": None}],
    "note": "CAD model v3 checked", "pinned": False, "by": "joe",
}


def test_stamp_accepts_a_valid_example():
    assert errors(STAMP, STAMP_OK) == []


@pytest.mark.parametrize("name, fn", [
    ("wrong schema", lambda d: d.update(schema="thread-stamp/2")),
    ("work not a work id", lambda d: d.update(work="seg.thigh")),
    ("stamp id malformed", lambda d: d.update(stamp="2026-10-18")),
    ("missing pinned", lambda d: d.pop("pinned")),
    ("pinned not a boolean", lambda d: d.update(pinned="no")),
    ("missing by", lambda d: d.pop("by")),
    ("missing note", lambda d: d.pop("note")),
    ("hash not 12 hex", lambda d: d["consumes"][0].update(hash="xyz")),
    ("consumes entry without value key", lambda d: d["consumes"][0].pop("value")),
    ("address malformed", lambda d: d["consumes"][0].update(address="snapshot")),
    ("unknown field", lambda d: d.update(timestamp="now")),
])
def test_stamp_rejects_each_schema_level_error(name, fn):
    doc = copy.deepcopy(STAMP_OK)
    fn(doc)
    assert errors(STAMP, doc), name


GRAPH_OK = {
    "schema": "thread-graph/1", "generated_by": "tools/thread", "inputs": "sha256:0123456789ab",
    "nodes": [{"id": "seg.thigh", "kind": "segment", "status": "active"}, {"id": "work.thigh-cad", "kind": "work_item", "status": "proposed"}],
    "edges": [{"type": "housed_in", "from": "part.hip.m2", "to": "seg.thigh"}],
    "edge_types": [{"name": "housed_in", "from_kinds": ["part"], "to_kinds": ["segment"], "origin": "authored", "doc": "The segment a part sits in."}],
    "work_statuses": {"work.thigh-cad": "current"},
    "budgets": {"mass": {"body": {"target_kg": 65.0, "claimed_kg": 1.0, "over": False}, "segments": {"seg.thigh": {"target_kg": 6.0, "claimed_kg": 1.0, "over": False}}}},
}


def test_graph_accepts_a_valid_example():
    assert errors(GRAPH, GRAPH_OK) == []


@pytest.mark.parametrize("name, fn", [
    ("wrong schema", lambda d: d.update(schema="thread-graph/2")),
    ("missing inputs banner", lambda d: d.pop("inputs")),
    ("node with an unknown kind", lambda d: d["nodes"][0].update(kind="widget")),
    ("edge without type", lambda d: d["edges"][0].pop("type")),
    ("edge type origin neither authored nor derived", lambda d: d["edge_types"][0].update(origin="both")),
    ("edge type without doc", lambda d: d["edge_types"][0].pop("doc")),
    ("work status outside the six", lambda d: d["work_statuses"].update({"work.x": "done"})),
    ("unknown field", lambda d: d.update(extra=1)),
])
def test_graph_rejects_each_schema_level_error(name, fn):
    doc = copy.deepcopy(GRAPH_OK)
    fn(doc)
    assert errors(GRAPH, doc), name
