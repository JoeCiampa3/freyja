"""
rm.v1-fall-cases-recorded: the seven fall load cases of the real store (adr-0037 D1(a), adr-0044 D1; docs/briefs/ariadne/fall-cases-brief.md).

Zone, direction, housing segment and evidence are asserted against the brief's table. The energies are not restated here: a typed copy of a
decision's number would be a second home for it, so they are compared with the decisions in the memo (gate G5).

    python -m pytest tests/test_fall_cases.py
"""
import json

import pytest
import yaml
from thread_help import REPO

from thread import build

CASES = {
    "lc.fall-hip-lateral": ("hip", "lateral, hip first", "seg.pelvis", [("adr-0037", "D1(b)")]),
    "lc.fall-shoulder-lateral": ("shoulder", "lateral, shoulder first", "seg.thorax", [("adr-0037", "D1(b)")]),
    "lc.fall-buttock-backward": ("buttock", "backward, buttock first", "seg.pelvis", [("adr-0037", "D1(b)")]),
    "lc.fall-back-backward": ("back", "backward, back first", "seg.thorax", [("adr-0037", "D1(b)")]),
    "lc.fall-chest-forward": ("chest", "forward, chest first, with the arm not arresting", "seg.thorax",
                              [("adr-0037", "D1(b)"), ("adr-0044", "D1")]),
    "lc.fall-knee-forward": ("knee", "forward collapse onto one knee", "seg.thigh", [("adr-0037", "D1(c)"), ("adr-0037", "D3")]),
    "lc.fall-hand-arm": ("hand-arm", "arrest on one arm, forward or sideways; no sharing", "seg.upper_arm",
                         [("adr-0037", "D3"), ("adr-0008", "D5")]),
}
FALL_CASES_BY_SEGMENT = {"seg.thorax": ["lc.fall-back-backward", "lc.fall-chest-forward", "lc.fall-shoulder-lateral"],
                         "seg.pelvis": ["lc.fall-buttock-backward", "lc.fall-hip-lateral"],
                         "seg.thigh": ["lc.fall-knee-forward"],
                         "seg.upper_arm": ["lc.fall-hand-arm"]}


@pytest.fixture(scope="module")
def real():
    return build.build_root(REPO)


def record(id):
    return yaml.safe_load((REPO / "thread" / "records" / f"{id}.yaml").read_text(encoding="utf-8"))


def derived(id):
    return json.loads((REPO / "thread" / "derived" / f"{id}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("id", sorted(CASES))
def test_the_record_is_the_proposed_flagged_energy_case_of_the_table(id):
    zone, direction, zone_in, evidence = CASES[id]
    r = record(id)
    assert r["kind"] == "load_case" and r["status"] == "proposed" and r["independent_source_required"] is True
    assert r["source"]["zone"] == zone and r["source"]["direction"] == direction and r["zone_in"] == zone_in
    assert [(e["record"], e["clause"]) for e in r["evidence"]] == evidence and all(e["kind"] == "decision" for e in r["evidence"])
    assert r["purpose"].endswith(".") and r["purpose"].count(". ") == 0 and r["notes"].strip()
    # a case carries an energy and never a force, a cap or a stroke
    assert set(r["source"]) <= {"zone", "direction", "energy_j", "energy_basis"} and "energy_j" in r["source"]


@pytest.mark.parametrize("id", sorted(CASES))
def test_the_derived_document_says_sourced_with_every_entry_resolved_and_admissible(id):
    d = derived(id)
    assert d["sourcing"] == "sourced"
    assert len(d["evidence"]) == len(CASES[id][3])
    assert all(e["resolved"] and e["admissible"] for e in d["evidence"])


def test_each_housing_segment_lists_exactly_its_fall_cases_and_no_other_record_is_one(real):
    for seg, want in FALL_CASES_BY_SEGMENT.items():
        assert sorted(derived(seg)["fall_cases"]) == want, seg
    others = [i for i, r in real.recs.items() if r["kind"] == "segment" and i not in FALL_CASES_BY_SEGMENT]
    assert others and all(derived(i)["fall_cases"] == [] for i in others)
    assert sorted(i for i, r in real.recs.items() if r["kind"] == "load_case" and "zone_in" in r) == sorted(CASES)


def test_the_real_store_builds_clean_with_the_seven_cases(real):
    assert real.errors == [] and not [i for i in real.warnings if i.code == "unsourced-consumption"]
