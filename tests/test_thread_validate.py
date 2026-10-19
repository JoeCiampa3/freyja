"""
Thread T2: validation. Each hand-authored invalid fixture under tests/fixtures/thread/invalid/<name>/ is an overlay on tests/fixtures/thread/base/
(a tiny model, a tiny snapshot and valid records) and holds exactly one error class; the base itself has neither errors nor warnings.
The warning fixtures under tests/fixtures/thread/warnings/ are valid and must yield exactly their warning. Nothing here depends on how the
fixtures were made.

    python -m pytest tests/test_thread_validate.py
"""
from pathlib import Path

import pytest
from thread_help import FIXTURES, codes, edit_record, make_root

from thread import build

# fixture directory -> [(code, ids)]
ERRORS = {
    "filename-id": [("filename-id", ("part.bad.other",))],
    "duplicate-id": [("duplicate-id", ("part.base.p2",))],
    "schema": [("schema", ("part.bad.nocat",))],
    "ref-unresolved": [("ref-unresolved", ("part.bad.ref",))],
    "ref-kind": [("ref-kind", ("part.bad.kind",))],
    "superseded-by-unresolved": [("superseded-by", ("part.bad.old",))],
    "superseded-by-superseded": [("superseded-by", ("part.bad.old1",))],
    "binding-body": [("binding-missing", ("seg.thorax",))],
    "binding-hinge": [("binding-missing", ("jnt.wrist",))],
    "body-twice": [("binding-duplicate", ("seg.head_neck", "seg.pelvis"))],
    "hinge-twice": [("binding-duplicate", ("jnt.lumbosacral", "jnt.other"))],
    "key-twice": [("key-duplicate", ("jnt.hip", "jnt.lumbosacral"))],
    "sides-missing": [("sides", ("seg.thigh",))],
    "sides-extra": [("sides", ("seg.pelvis",))],
    "sides-joint": [("sides", ("jnt.knee",))],
    "sides-part": [("sides", ("part.base.p1",))],
    "reaction-path": [("reaction-path", ("part.bad.react",))],
    "stamp-unknown-work": [("stamp-unknown-work", ("work.ghost",))],
    "stamp-schema": [("stamp-schema", ("work.base",))],
}
WARNINGS = {
    "unbound-hinge": [("unbound-hinge", ("lsj_lat",))],
    "unbound-body": [("unbound-body", ("forearm_right",))],
    "address-unresolved": [("address-unresolved", ("work.base",))],
    "consumes-changed": [("consumes-changed", ("work.base",))],
    "budget-over": [("budget-over", ("seg.pelvis",))],
    "active-refs-proposed": [("active-refs-inactive", ("work.active", "part.base.p1"))],
}


def got(issues):
    return sorted((i.code, tuple(i.ids)) for i in issues)


def test_every_fixture_directory_is_listed_here():
    assert sorted(p.name for p in (FIXTURES / "invalid").iterdir()) == sorted(ERRORS)
    assert sorted(p.name for p in (FIXTURES / "warnings").iterdir()) == sorted(WARNINGS)


def test_the_base_root_is_clean(tmp_path):
    b = build.build_root(make_root(tmp_path / "r"))
    assert b.errors == [] and b.warnings == []
    assert b.outputs  # a clean thread produces its outputs


@pytest.mark.parametrize("name", sorted(ERRORS))
def test_each_invalid_fixture_yields_exactly_its_error(name, tmp_path):
    b = build.build_root(make_root(tmp_path / "r", FIXTURES / "invalid" / name))
    assert got(b.errors) == sorted(ERRORS[name]), [(i.code, i.ids, i.message) for i in b.issues]
    assert b.warnings == [], [(i.code, i.ids) for i in b.warnings]
    assert b.outputs == {}  # errors stop generation


@pytest.mark.parametrize("name", sorted(WARNINGS))
def test_each_warning_fixture_yields_exactly_its_warning(name, tmp_path):
    b = build.build_root(make_root(tmp_path / "r", FIXTURES / "warnings" / name))
    assert b.errors == [], [(i.code, i.ids, i.message) for i in b.errors]
    assert got(b.warnings) == sorted(WARNINGS[name]), [(i.code, i.ids, i.message) for i in b.warnings]
    assert b.outputs  # warnings are listed in the outputs, not blocking
    assert any(i.code in b.outputs["thread/STATUS.md"].decode() for i in b.warnings)


def test_an_unresolved_address_in_the_baseline_is_unknown_and_warns(tmp_path):
    root = make_root(tmp_path / "r")
    b0 = build.build_root(root)
    build.write_stamp(root, b0, "work.base", stamp="20261001-1000", by="test")
    edit_record(root, "work.base", consumes=["snapshot#/pelvis_mass", "part.base.p2#/housed_in"])
    # remove a part: the stamped address `part.base.p2#/housed_in` stops resolving
    (root / "thread" / "records" / "part.base.p2.yaml").unlink()
    b = build.build_root(root)
    assert b.errors == []
    assert b.work["work.base"]["status"] == "unknown"
    assert ("address-unresolved", ("work.base",)) in got(b.warnings)


def test_a_missing_snapshot_is_reported_not_raised(tmp_path):
    root = make_root(tmp_path / "r")
    (root / "params" / "snapshot.csv").unlink()
    b = build.build_root(root)
    assert any(i.code == "input-missing" for i in b.errors)


def test_a_missing_model_is_reported_not_raised(tmp_path):
    root = make_root(tmp_path / "r")
    (root / "sim" / "models" / "freyja.xml").unlink()
    b = build.build_root(root)
    assert any(i.code == "input-missing" for i in b.errors)


def test_a_root_with_no_records_directory_builds_empty(tmp_path):
    root = make_root(tmp_path / "r")
    import shutil
    shutil.rmtree(root / "thread")
    b = build.build_root(root)
    assert b.errors == []
    assert sorted(i.code for i in b.warnings) == ["unbound-body"] * 6 + ["unbound-hinge"] * 5
    assert "thread/STATUS.md" in b.outputs


def test_the_library_does_not_import_mujoco():
    import subprocess
    import sys
    code = ("import sys; sys.path[:0] = [r'%s', r'%s']; import thread.build, thread.impact, thread.store; "
            "sys.exit(1 if 'mujoco' in sys.modules else 0)") % (str(Path(__file__).resolve().parents[1] / "tools"), str(Path(__file__).resolve().parents[1] / "sim" / "scripts"))
    assert subprocess.run([sys.executable, "-I", "-c", code]).returncode == 0


def test_segment_names_and_bilaterality_come_from_pre_processor_not_a_copy(tmp_path, monkeypatch):
    pp = build.pre_processor()
    monkeypatch.setattr(pp, "BILATERAL", list(pp.BILATERAL) + ["pelvis"])
    b = build.build_root(make_root(tmp_path / "r"))
    assert ("sides", ("seg.pelvis",)) in got(b.errors)
