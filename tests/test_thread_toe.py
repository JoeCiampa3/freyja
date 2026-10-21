"""
Stage 2g T5: the toe in the thread. A segment record may own further bodies (`also_bodies`), so `seg.foot` binds `foot_right`, `foot_left`, `toe_right` and `toe_left`, and
`jnt.toe` binds the two toe hinges and the toe's range-of-motion keys. The tracked records carry both since Part B. These tests copy the real records with the toe
records taken out again, to exercise the mechanism (what an unbound toe looks like, what binds it) on the fixture model of tests/foot_help.py in a temporary root.

Run from the repo root:
    python -m pytest tests/test_thread_toe.py
"""
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "checks"))

import foot_help as fh  # noqa: E402
import thread_help  # noqa: E402,F401  (puts tools/ on the path)
import thread_checks as tc  # noqa: E402
from thread import build  # noqa: E402

JNT_TOE = {"schema": "thread-record/1", "id": "jnt.toe", "kind": "joint", "status": "proposed", "hinges": ["toe"], "rom_keys": ["toe_extension", "toe_flexion"], "sides": ["left", "right"],
           "purpose": "The metatarsophalangeal joint, between the foot and the toe, a passive hinge with a spring, a damper and stops."}


@pytest.fixture()
def root(tmp_path):
    shutil.copytree(REPO / "thread" / "records", tmp_path / "thread" / "records")
    (tmp_path / "sim" / "models").mkdir(parents=True)
    shutil.copy(fh.fixture_model_path(), tmp_path / "sim" / "models" / "freyja.xml")
    (tmp_path / "params").mkdir()
    shutil.copy(REPO / "params" / "snapshot.csv", tmp_path / "params" / "snapshot.csv")
    (records(tmp_path) / "jnt.toe.yaml").unlink()  # the tracked records carry the toe; the tests below add it back
    p = records(tmp_path) / "seg.foot.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    del doc["also_bodies"]
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    (tmp_path / "decisions").mkdir()
    return tmp_path


def records(root):
    return root / "thread" / "records"


def add_toe(root, also=True):
    (records(root) / "jnt.toe.yaml").write_text(yaml.safe_dump(JNT_TOE, sort_keys=True), encoding="utf-8")
    if also:
        p = records(root) / "seg.foot.yaml"
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        doc["also_bodies"] = ["toe"]
        p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")


def test_without_the_records_the_toe_is_unbound_in_the_coverage_check(root):
    xml = (root / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    problems = tc.coverage_problems(xml, records(root))
    assert any("toe_right has no segment record" in p for p in problems) and any("toe_left has no joint record" in p for p in problems)


def test_the_toe_records_cover_the_model_and_the_thread_builds_without_error(root):
    add_toe(root)
    xml = (root / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    assert tc.coverage_problems(xml, records(root)) == []
    b = build.build_root(root)
    assert [i.message for i in b.errors] == []
    model = b.store.model
    assert len(model.bodies) == 18 and len(model.hinges) == 33
    assert b.body_owner["toe_right"] == b.body_owner["foot_right"] == "seg.foot" and b.body_owner["toe_left"] == "seg.foot"
    assert b.hinge_owner["toe_left"] == b.hinge_owner["toe_right"] == "jnt.toe"
    assert b.recs["jnt.toe"]["status"] == "proposed"  # created proposed, Joe activates it


def test_a_toe_body_without_also_bodies_is_still_unbound_and_a_doubly_bound_one_is_an_error(root):
    add_toe(root, also=False)
    xml = (root / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")
    assert any("toe_right has no segment record" in p for p in tc.coverage_problems(xml, records(root)))
    p = records(root) / "seg.shank.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["also_bodies"] = ["foot"]  # the shank claims the foot as well
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    b = build.build_root(root)
    assert any(i.code == "binding-duplicate" and "foot_right" in i.message for i in b.errors)
    assert any("foot_right is bound by 2 segment records" in q for q in tc.coverage_problems(xml, records(root)))


def test_also_bodies_names_must_exist_in_the_model(root):
    add_toe(root, also=False)
    p = records(root) / "seg.foot.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["also_bodies"] = ["toenail"]
    p.write_text(yaml.safe_dump(doc, sort_keys=True), encoding="utf-8")
    assert any(i.code == "binding-missing" and "toenail" in i.message for i in build.build_root(root).errors)
