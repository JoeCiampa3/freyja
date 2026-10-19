"""
Thread T1: the three schemas (docs/schemas/thread-record-1, thread-stamp-1, thread-graph-1). Each accepts one valid example per kind and
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


RECORD = load("thread-record-1.schema.json")
STAMP = load("thread-stamp-1.schema.json")
GRAPH = load("thread-graph-1.schema.json")


def errors(schema, doc):
    return list(jsonschema.Draft202012Validator(schema).iter_errors(doc))


def base(kind, id, **f):
    return {"schema": "thread-record/1", "id": id, "kind": kind, "status": "proposed", "purpose": "Why this exists.", **f}


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
    "wrong schema string": ("segment", lambda d: d.update(schema="thread-record/2")),
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
