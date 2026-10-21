"""check.thread.coverage (advisory) on the committed thread records and the committed model, and its mutation tests: removing a record, or
adding a body or a hinge to a copy of the model, or binding a body twice, makes it fail."""
import shutil
from pathlib import Path

import pytest

import checklib as cl
import thread_checks as tc

REPO = Path(__file__).resolve().parents[1]
XML = (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
RECORDS = REPO / "thread" / "records"


@pytest.fixture
def records(tmp_path):
    d = tmp_path / "records"
    shutil.copytree(RECORDS, d)
    return d


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_the_committed_records_cover_the_committed_model():
    assert tc.coverage_problems(XML, RECORDS) == []


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_the_check_is_registered_advisory_and_passes_on_the_real_context(ctx):
    assert cl.REGISTRY["check.thread.coverage"].tier == "advisory"
    [r] = cl.call(cl.REGISTRY["check.thread.coverage"], ctx)
    assert r.status == cl.PASS and "18 bodies" in r.message and "33 hinges" in r.message


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_mutation_removing_a_segment_record_fails(records):
    (records / "seg.thigh.yaml").unlink()
    problems = tc.coverage_problems(XML, records)
    assert any("thigh_right" in p and "no segment record" in p for p in problems) and any("thigh_left" in p for p in problems)


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_mutation_removing_a_joint_record_fails(records):
    (records / "jnt.knee.yaml").unlink()
    assert any("knee_right" in p and "no joint record" in p for p in tc.coverage_problems(XML, records))


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_mutation_a_body_added_to_the_model_fails():
    bad = XML.replace('<body name="abdomen"', '<body name="extra_body"/>\n<body name="abdomen"', 1)
    assert bad != XML
    assert any("extra_body" in p and "no segment record" in p for p in tc.coverage_problems(bad, RECORDS))


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_mutation_a_hinge_added_to_the_model_fails():
    bad = XML.replace('<joint name="lsj_fe"', '<joint name="lsj_extra" type="hinge" axis="1 0 0"/>\n<joint name="lsj_fe"', 1)
    assert bad != XML
    assert any("lsj_extra" in p and "no joint record" in p for p in tc.coverage_problems(bad, RECORDS))


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_mutation_a_body_bound_by_two_records_fails(records):
    p = records / "seg.hand.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("body: hand", "body: forearm"), encoding="utf-8")
    problems = tc.coverage_problems(XML, records)
    assert any("forearm_right" in x and "2 segment records" in x for x in problems) and any("hand_right" in x and "no segment record" in x for x in problems)


@pytest.mark.check("check.thread.coverage", tier="advisory")
def test_without_a_records_directory_the_check_skips_and_says_why(tmp_path, monkeypatch):
    monkeypatch.setattr(tc, "RECORDS_DIR", tmp_path / "none")
    r = tc.coverage(type("C", (), {"xml_text": XML})())
    assert r.status == cl.SKIP and "thread/records" in r.message
