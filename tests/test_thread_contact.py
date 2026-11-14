"""
adr-0045 D5: a fall case's optional `contact_in` (the segment whose skin is struck) and the derived `fall_contacts` on each segment
(docs/briefs/ariadne/upper-arm-characterization-brief.md, T1; gates G-S1, G-S2, G-S4). `fall_cases` stays keyed on `zone_in`; contact
defaults to `zone_in` when `contact_in` is absent.

    python -m pytest tests/test_thread_contact.py
"""
import copy
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml
from thread_help import REPO, codes, edit_record, make_root, write_record

from thread import build, edges, impact, store

SCHEMA = json.loads((REPO / "docs" / "schemas" / "thread-record-2.schema.json").read_text(encoding="utf-8"))
SOURCE = {"zone": "shoulder", "direction": "lateral, shoulder first", "energy_j": 540, "energy_basis": "E_max"}


def schema_errors(doc):
    return list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc))


def fall_doc(**f):
    return {"schema": "thread-record/2", "id": "lc.fall", "kind": "load_case", "status": "proposed", "purpose": "p",
            "source": dict(SOURCE), "independent_source_required": True, "zone_in": "seg.abdomen", **f}


def energy(root, id="lc.fall", zone_in="seg.abdomen", **f):
    write_record(root, id=id, kind="load_case", zone_in=zone_in, independent_source_required=True, source=dict(SOURCE), **f)


def built(root):
    b = build.build_root(root)
    assert b.errors == [], [(i.code, i.message) for i in b.errors]
    return b


# ---- schema --------------------------------------------------------------------------------


def test_contact_in_is_accepted_on_the_energy_form():
    assert schema_errors(fall_doc(contact_in="seg.pelvis")) == []
    assert schema_errors(fall_doc()) == []  # optional


@pytest.mark.parametrize("source", [{"scenario": "fall_impact"}, {"gait_spec": "walk_treadmill", "condition": "1.4 m/s"}])
def test_contact_in_on_a_gait_or_scenario_case_is_rejected(source):
    doc = fall_doc(contact_in="seg.pelvis", source=source)
    doc.pop("zone_in")
    assert schema_errors(doc)


def test_contact_in_on_a_record_that_is_not_a_load_case_is_rejected():
    doc = {"schema": "thread-record/2", "id": "part.a.b", "kind": "part", "status": "proposed", "purpose": "p", "housed_in": "seg.pelvis",
           "mass": {"kg": 1.0, "source": "s", "reserved": True}, "category": "c", "contact_in": "seg.pelvis"}
    assert schema_errors(doc)


def test_contact_in_that_is_not_a_record_id_is_rejected():
    assert schema_errors(fall_doc(contact_in="upper arm"))


# ---- G-S4: the build ------------------------------------------------------------------------


@pytest.mark.parametrize("target, code", [("jnt.hip", "ref-kind"), ("part.base.p1", "ref-kind"), ("hn.base", "ref-kind"),
                                          ("seg.nowhere", "ref-unresolved")])
def test_contact_in_naming_a_non_segment_fails_the_build(tmp_path, target, code):
    root = make_root(tmp_path / "r")
    energy(root, contact_in=target)
    b = build.build_root(root)
    assert code in codes(b.errors) and any("contact_in" in i.message for i in b.errors)
    assert b.outputs == {}


def test_contact_in_on_a_scenario_case_fails_the_build(tmp_path):
    root = make_root(tmp_path / "r")
    write_record(root, id="lc.x", kind="load_case", source={"scenario": "fall_impact"}, independent_source_required=True, contact_in="seg.pelvis")
    assert "schema" in codes(build.build_root(root).errors)


# ---- the derived relation -----------------------------------------------------------------------


def test_without_contact_in_the_contact_is_the_zone(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root)
    b = built(root)
    assert b.docs["seg.abdomen"]["fall_contacts"] == ["lc.fall"] and b.docs["seg.abdomen"]["fall_cases"] == ["lc.fall"]
    assert all(b.docs[s]["fall_contacts"] == [] for s in ("seg.pelvis", "seg.thigh", "seg.shank"))


def test_with_contact_in_the_contact_moves_and_the_housing_stays(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root, contact_in="seg.pelvis")
    b = built(root)
    assert b.docs["seg.pelvis"]["fall_contacts"] == ["lc.fall"] and b.docs["seg.pelvis"]["fall_cases"] == []
    assert b.docs["seg.abdomen"]["fall_contacts"] == [] and b.docs["seg.abdomen"]["fall_cases"] == ["lc.fall"]


def test_contact_in_equal_to_zone_in_reads_as_absent(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root, contact_in="seg.abdomen")
    b = built(root)
    assert b.docs["seg.abdomen"]["fall_contacts"] == ["lc.fall"] and b.docs["seg.abdomen"]["fall_cases"] == ["lc.fall"]


def test_non_energy_cases_are_in_neither_relation(tmp_path):
    root = make_root(tmp_path / "r")
    write_record(root, id="lc.walk", kind="load_case", source={"gait_spec": "walk_treadmill", "condition": "1.4 m/s"}, independent_source_required=False)
    b = built(root)
    assert all(d.get("fall_contacts") == [] and d.get("fall_cases") == [] for d in b.docs.values() if d["kind"] == "segment")


def test_contact_in_leaves_houses_and_budgets_alone(tmp_path):
    a, c = make_root(tmp_path / "a"), make_root(tmp_path / "c")
    energy(a)
    energy(c, contact_in="seg.pelvis")
    ba, bc = built(a), built(c)
    for s in ("seg.abdomen", "seg.pelvis"):
        assert ba.docs[s]["budgets"] == bc.docs[s]["budgets"] and ba.docs[s]["houses"] == bc.docs[s]["houses"]
    assert ba.budgets == bc.budgets


def test_both_edges_are_in_the_registry_and_the_graph(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root, contact_in="seg.pelvis")
    g = built(root).graph_final
    e = edges.BY_NAME
    assert (e["contact_in"].from_kinds, e["contact_in"].to_kinds, e["contact_in"].origin) == (("load_case",), ("segment",), "authored")
    assert (e["fall_contacts"].from_kinds, e["fall_contacts"].to_kinds, e["fall_contacts"].origin) == (("segment",), ("load_case",), "derived")
    assert {"type": "contact_in", "from": "lc.fall", "to": "seg.pelvis"} in g["edges"]
    assert {"type": "fall_contacts", "from": "seg.pelvis", "to": "lc.fall"} in g["edges"]
    assert {"type": "fall_cases", "from": "seg.abdomen", "to": "lc.fall"} in g["edges"]


def test_dossiers_show_the_field_and_the_relation(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root, contact_in="seg.pelvis")
    out = built(root).outputs
    assert "- contact_in: [seg.pelvis](seg.pelvis.md)" in out["thread/dossiers/lc.fall.md"].decode()
    assert "- fall_contacts: [lc.fall](lc.fall.md)" in out["thread/dossiers/seg.pelvis.md"].decode()


def test_setting_contact_in_restamps_both_segments_inputs(tmp_path):
    """The old contact and the new one both change content, so both banners' inputs hashes must move (staleness is a hash mismatch)."""
    root = make_root(tmp_path / "r")
    energy(root)
    before = built(root).input_hashes
    edit_record(root, "lc.fall", contact_in="seg.pelvis")
    after = built(root).input_hashes
    for s in ("seg.abdomen", "seg.pelvis"):
        assert before[f"thread/derived/{s}.json"] != after[f"thread/derived/{s}.json"], s
    assert before["thread/derived/seg.thigh.json"] == after["thread/derived/seg.thigh.json"]


def test_impact_of_contact_in_reaches_the_contact_segment(tmp_path):
    root = make_root(tmp_path / "r")
    energy(root, contact_in="seg.pelvis")
    outs = impact.impact(store.load(root), "lc.fall#/contact_in")["outputs"]
    assert "thread/derived/seg.pelvis.json" in outs and "thread/derived/seg.thigh.json" not in outs


# ---- G-S1, G-S2 on the real store --------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    return build.build_root(REPO)


def test_gs1_every_real_record_validates_under_the_amended_schema(real):
    v = jsonschema.Draft202012Validator(SCHEMA)
    files = sorted((REPO / "thread" / "records").glob("*.yaml"))
    assert files and all(not list(v.iter_errors(yaml.safe_load(p.read_text(encoding="utf-8")))) for p in files)
    assert real.errors == [] and len(real.recs) == len(files)


def test_gs2_fall_cases_do_not_depend_on_contact_in(real, tmp_path):
    """Every segment's fall_cases is the same with every contact_in removed: the housing relation does not read the new field."""
    root = tmp_path / "r"
    for sub in ("thread/records", "thread/stamps", "decisions", "params", "sim/models", "data/falls", "roadmap/nodes", "cad/sidecars"):
        if (REPO / sub).is_dir():
            shutil.copytree(REPO / sub, root / sub)
    for p in (root / "thread" / "records").glob("lc.*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        if doc.pop("contact_in", None) is not None:
            p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8", newline="\n")
    stripped = build.build_root(root)
    assert stripped.errors == []
    segs = sorted(i for i, d in real.docs.items() if d["kind"] == "segment")
    assert segs and all(json.dumps(real.docs[s]["fall_cases"]) == json.dumps(stripped.docs[s]["fall_cases"]) for s in segs)


def test_gs3_the_shoulder_lateral_case_strikes_the_upper_arm_and_stays_housed_in_the_thorax(real):
    """T2, adr-0045 D5(d) and gate G3: lc.fall-shoulder-lateral's contact is seg.upper_arm (memo 59, finding 7)."""
    assert real.recs["lc.fall-shoulder-lateral"]["contact_in"] == "seg.upper_arm"
    assert real.docs["seg.upper_arm"]["fall_contacts"] == ["lc.fall-hand-arm", "lc.fall-shoulder-lateral"]
    assert real.docs["seg.upper_arm"]["fall_cases"] == ["lc.fall-hand-arm"]
    assert "lc.fall-shoulder-lateral" not in real.docs["seg.thorax"]["fall_contacts"]
    assert "lc.fall-shoulder-lateral" in real.docs["seg.thorax"]["fall_cases"]
    assert sorted(i for i, r in real.recs.items() if "contact_in" in r) == ["lc.fall-shoulder-lateral"]


def test_every_real_fall_case_reaches_exactly_one_contact_segment(real):
    cases = sorted(i for i, r in real.recs.items() if r["kind"] == "load_case" and "zone_in" in r)
    hits = sorted(c for d in real.docs.values() if d["kind"] == "segment" for c in d["fall_contacts"])
    assert cases and hits == cases
