"""
Thread T2: validation. Each hand-authored invalid fixture under tests/fixtures/thread/invalid/<name>/ is an overlay on tests/fixtures/thread/base/
(a tiny model, a tiny snapshot and valid records) and holds exactly one error class; the base itself has neither errors nor warnings.
The warning fixtures under tests/fixtures/thread/warnings/ are valid and must yield exactly their warning. Nothing here depends on how the
fixtures were made.

    python -m pytest tests/test_thread_validate.py
"""
from pathlib import Path

import pytest
from thread_help import FIXTURES, codes, edit_record, make_root, write_record

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
    "evidence-unresolved-decision": [("evidence-unresolved", ("lc.bad-adr",))],
    "evidence-unresolved-file": [("evidence-unresolved", ("lc.bad-file",))],
    "evidence-unresolved-row": [("evidence-unresolved", ("lc.bad-row",))],
    "evidence-unresolved-test": [("evidence-unresolved", ("lc.bad-test",))],
    "evidence-ambiguous": [("evidence-ambiguous", ("lc.bad-twice",))],
    "evidence-clause": [("evidence-clause", ("lc.bad-clause",))],
    "zone-in-joint": [("ref-kind", ("lc.bad-zone",))],
    "zone-in-unresolved": [("ref-unresolved", ("lc.bad-ghost",))],
    "decision-unclosed": [("decision-front-matter", ("0902-unclosed",))],
    "decision-unquoted-status": [("decision-front-matter", ("0903-unquoted",))],
    "decision-no-id": [("decision-front-matter", ("0904-no-id",))],
    "decision-id-number": [("decision-front-matter", ("0905-wrong-number",))],
    "decision-status": [("decision-front-matter", ("0907-bad-status",))],
    "decision-duplicate-id": [("decision-front-matter", ("0001-zcopy",))],
}
WARNINGS = {
    "unbound-hinge": [("unbound-hinge", ("lsj_lat",))],
    "unbound-body": [("unbound-body", ("forearm_right",))],
    "address-unresolved": [("address-unresolved", ("work.base",))],
    "consumes-changed": [("consumes-changed", ("work.base",))],
    "budget-over": [("budget-over", ("seg.pelvis",))],
    "active-refs-proposed": [("active-refs-inactive", ("work.active", "part.base.p1"))],
    "unsourced-consumption": [("unsourced-consumption", ("work.uses-none", "lc.none"))],
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


# ---- decision front matter ---------------------------------------------------------------

DECISION_REASONS = {
    "decision-unclosed": ("0902-unclosed.md", "unclosed", "adr-0902"),
    "decision-unquoted-status": ("0903-unquoted.md", "quote", "adr-0903"),
    "decision-no-id": ("0904-no-id.md", "no string id", None),
    "decision-id-number": ("0905-wrong-number.md", "adr-0905", "adr-0906"),
    "decision-status": ("0907-bad-status.md", "approved", "adr-0907"),
    "decision-duplicate-id": ("0001-zcopy.md", "0001-test.md", None),
}


def decision_file(root, name, text):
    p = Path(root) / "decisions" / name
    p.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return p


GOOD = "---\nid: adr-0910\nstatus: accepted\nlinks: []\n---\n## Decision\n"


@pytest.mark.parametrize("name", sorted(DECISION_REASONS))
def test_a_decision_failure_names_the_file_and_the_reason_and_stays_out_of_the_store(name, tmp_path):
    b = build.build_root(make_root(tmp_path / "r", FIXTURES / "invalid" / name))
    file, reason, kept_out = DECISION_REASONS[name]
    message = b.errors[0].message
    assert f"decisions/{file}" in message and reason in message
    assert file not in [Path(d["path"]).name for d in b.store.decisions]
    if kept_out:
        assert kept_out not in b.store.decision_bodies
    assert [d["id"] for d in b.store.decisions] == ["adr-0001"]  # the base's record alone, and for a duplicate the first file keeps the id
    assert b.store.decisions[0]["path"] == "decisions/0001-test.md"


@pytest.mark.parametrize("text, reason", [
    ("## Decision\nNo front matter at all.\n", "no front matter"),
    ("---- \nid: adr-0910\n---\n", "no front matter"),
    ("---\n---\n", "not a mapping"),
    ("---\n- id: adr-0910\n---\n", "not a mapping"),
    ("---\nid: 910\nstatus: accepted\n---\n", "no string id"),
    ("---\nid: [unclosed\n---\n", "not readable YAML"),
    ("---\nid: adr-0910\nstatus: accepted\ndate: 2026-13-45\n---\n", "not readable YAML"),  # a bad date is a ValueError from the loader, not a YAMLError
    ("---\nid: adr-0910\ndate: 2026-01-01\n---\n", "status"),
    ("---\nid: adr-0910\nstatus: true\n---\n", "status"),
    ("---\nid: adr-0910\nstatus: \"superseded-by: 0001\"\n---\n", "status"),
    ("---\nid: adr-0910\nstatus: \"superseded-by: adr-0001\\n\"\n---\n", "status"),
    ("---\nid: \"adr-0910\\n\"\nstatus: accepted\n---\n", "adr-0910"),
])
def test_the_other_decision_failures(text, reason, tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-x.md", text)
    b = build.build_root(root)
    assert got(b.errors) == [("decision-front-matter", ("0910-x",))]
    assert "decisions/0910-x.md" in b.errors[0].message and reason in b.errors[0].message
    assert [d["id"] for d in b.store.decisions] == ["adr-0001"]


def test_a_file_that_is_not_utf8_is_the_error_not_a_crash(tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-x.md", b"---\nid: adr-0910\xff\n---\n")
    assert got(build.build_root(root).errors) == [("decision-front-matter", ("0910-x",))]


def test_only_a_failure_in_the_yaml_of_an_unquoted_superseded_status_says_to_quote(tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-x.md", "---\nid: adr-0910\nstatus: \"superseded-by: adr-0001\"\nlinks: [\n---\n")
    b = build.build_root(root)
    assert got(b.errors) == [("decision-front-matter", ("0910-x",))] and "quote" not in b.errors[0].message


@pytest.mark.parametrize("status", ["proposed", "accepted", '"superseded-by: adr-0001"', "'superseded-by: adr-0001'"])
def test_the_allowed_statuses_load(status, tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-x.md", GOOD.replace("accepted", status))
    b = build.build_root(root)
    assert b.errors == [] and "adr-0910" in b.store.decision_bodies


def test_the_body_may_carry_rules_and_tables_and_the_crlf_form_loads(tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-x.md", (GOOD + "\n---\n\n| a |\n|---|\n\n**D1 One.** Text.\n").replace("\n", "\r\n"))
    b = build.build_root(root)
    assert b.errors == [] and "**D1 One.**" in b.store.decision_bodies["adr-0910"]


def test_a_decision_that_fails_on_status_still_holds_its_id_against_a_later_file(tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, "0910-a.md", GOOD.replace("accepted", "approved"))
    decision_file(root, "0910-b.md", GOOD)
    b = build.build_root(root)
    assert got(b.errors) == [("decision-front-matter", ("0910-a",)), ("decision-front-matter", ("0910-b",))]
    assert "adr-0910" not in b.store.decision_bodies


@pytest.mark.parametrize("name", ["README.md", "notes.md", "091-short.md", "09100-long.md", "0910.md", "0910_x.md"])
def test_a_file_not_named_nnnn_dash_anything_is_ignored_whatever_it_holds(name, tmp_path):
    root = make_root(tmp_path / "r")
    decision_file(root, name, "---\nstatus: nonsense: [\n")
    decision_file(root, name.replace(".md", "2.md"), GOOD)
    b = build.build_root(root)
    assert b.errors == [] and [d["id"] for d in b.store.decisions] == ["adr-0001"]


def test_a_citing_case_gets_the_loud_error_beside_evidence_unresolved(tmp_path):
    """Memo 57 finding 3: before, the only trace of the lost record was `evidence-unresolved` on the case."""
    root = make_root(tmp_path / "r", FIXTURES / "invalid" / "decision-unquoted-status")
    write_record(root, id="lc.cites", kind="load_case", source={"scenario": "stand_static"}, independent_source_required=True,
                 evidence=[{"kind": "decision", "record": "adr-0903", "clause": "D1"}])
    assert got(build.build_root(root).errors) == [("decision-front-matter", ("0903-unquoted",)), ("evidence-unresolved", ("lc.cites",))]


def test_the_real_decisions_pass_the_front_matter_rules():
    b = build.build_root(Path(__file__).resolve().parents[1])
    assert [i for i in b.issues if i.code == "decision-front-matter"] == []
    assert len(b.store.decisions) == 10


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


def test_a_record_in_the_old_schema_is_a_schema_error_that_says_to_migrate(tmp_path):
    root = make_root(tmp_path / "r")
    write_record(root, schema="thread-record/1", id="part.bad.old", kind="part", housed_in="seg.pelvis", mass={"kg": 1, "source": "s", "reserved": False}, category="c")
    b = build.build_root(root)
    assert got(b.errors) == [("schema", ("part.bad.old",))]
    assert "migrate" in b.errors[0].message and "thread-record/2" in b.errors[0].message


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
