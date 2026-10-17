"""
Roadmap T3: evaluation of each done_when type against records inside a root.

Run from the repo root:
    python -m pytest tests/test_roadmap_evaluate.py
"""
import json
from pathlib import Path

import pytest
from rmhelp import make

import roadmap

SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["ok"], "properties": {"ok": {"const": True}}}


def ev(tmp_path, done_when, files=None, signed_off=False, dirs=()):
    root = tmp_path / "r"
    make(root, {"rm.root": {"title": "Top"},
                "rm.leaf": {"parent": "rm.root", "estimate_days": 1, "done_when": done_when, "signed_off": signed_off}})
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    for rel, content in (files or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
    rm = roadmap.compute(root)
    assert rm.errors == [], [e.message for e in rm.errors]
    return rm.evaluation("rm.leaf"), rm.status("rm.leaf")


def test_manual(tmp_path):
    assert ev(tmp_path / "a", {"type": "manual"}, signed_off=True)[0].result == "pass"
    assert ev(tmp_path / "b", {"type": "manual"})[0].result == "fail"


def test_artifact_exists_nonempty_and_schema(tmp_path):
    dw = {"type": "artifact", "path": "records/x.json"}
    assert ev(tmp_path / "a", dw, dirs=["records"])[0].result == "awaiting"  # absent, parent exists
    assert ev(tmp_path / "b", dw, {"records/x.json": ""})[0].result == "fail"  # empty
    e, status = ev(tmp_path / "c", dw, {"records/x.json": "{}"})
    assert e.result == "pass" and status == "done"
    dws = {**dw, "schema": "docs/schemas/s.json"}
    files = {"docs/schemas/s.json": json.dumps(SCHEMA)}
    assert ev(tmp_path / "d", dws, {**files, "records/x.json": '{"ok": true}'})[0].result == "pass"
    bad, _ = ev(tmp_path / "e", dws, {**files, "records/x.json": '{"ok": false}'})
    assert bad.result == "fail" and "ok" in bad.reason
    assert ev(tmp_path / "f", dws, {"records/x.json": '{"ok": true}'})[0].result == "unknown"  # the schema file is missing
    assert ev(tmp_path / "g", dws, {**files, "records/x.json": "{not json"})[0].result == "unknown"


def test_a_path_that_leaves_the_root_is_never_read(tmp_path):
    # the schema forbids '..', but a hand-edited node must not escape either; the library refuses at evaluation too
    from roadmap.evaluate import safe_path
    root = tmp_path
    assert safe_path(root, "a/b.json") == root / "a" / "b.json"
    for bad in ("../x", "/etc/passwd", "a/../../x", "C:/x", "a\\b"):
        assert safe_path(root, bad) is None, bad


def decision(status):
    return f"---\nid: adr-0001\nstatus: {status}\ndate: 2026-10-11\nlinks: []\n---\n## Context\n"


def test_decision_passes_only_when_accepted(tmp_path):
    dw = {"type": "decision", "record": "decisions/0001-x.md"}
    assert ev(tmp_path / "a", dw, dirs=["decisions"])[0].result == "awaiting"
    assert ev(tmp_path / "b", dw, {"decisions/0001-x.md": decision("proposed")})[0].result == "fail"
    assert ev(tmp_path / "c", dw, {"decisions/0001-x.md": decision('"superseded-by: adr-0002"')})[0].result == "fail"
    assert ev(tmp_path / "d", dw, {"decisions/0001-x.md": decision("accepted")})[0].result == "pass"
    assert ev(tmp_path / "e", dw, {"decisions/0001-x.md": "no front matter\n"})[0].result == "unknown"


STATE = """<!-- GENERATED -->

STATE: x

## Tests

passed 1

## Checks

- check.a.one | gate | PASS
- check.a.two | advisory | FAIL
- check.a.three | advisory | WAIVED

## Waivers

none
"""


def test_check_reads_the_recorded_result_from_docs_state(tmp_path):
    def run(name, check, state=STATE):
        return ev(tmp_path / name, {"type": "check", "check": check}, {"docs/STATE.md": state} if state is not None else None)[0]
    assert run("a", "check.a.one").result == "pass"
    assert run("b", "check.a.two").result == "fail"
    w = run("c", "check.a.three")
    assert w.result == "fail" and "WAIVED" in w.reason
    assert run("d", "check.a.absent").result == "unknown"  # not listed at all
    assert run("e", "check.a.one", state=None).result == "unknown"  # no STATE.md to read
    assert run("f", "check.a.one", state="## Checks\n\nnot run (--no-run)\n").result == "awaiting"  # `fy state --no-run`
    nr = STATE.replace("- check.a.three | advisory | WAIVED", "- check.a.nr | gate | NOT_RUN")
    assert run("g", "check.a.nr", state=nr).result == "awaiting"


def metric(op, value, record_value=0.1):
    return {"type": "metric", "record": "records/m.json", "pointer": "/a/0/v", "op": op, "value": value}, {"records/m.json": json.dumps({"a": [{"v": record_value}]})}


@pytest.mark.parametrize("op,value,rec,expect", [
    ("<", 0.2, 0.1, "pass"), ("<", 0.1, 0.1, "fail"), ("<=", 0.1, 0.1, "pass"), (">", 0.1, 0.1, "fail"), (">", 0.0, 0.1, "pass"),
    (">=", 0.1, 0.1, "pass"), (">=", 0.2, 0.1, "fail"), ("==", 0.1, 0.1, "pass"), ("==", 0.2, 0.1, "fail")])
def test_metric_operators_and_the_measured_value(tmp_path, op, value, rec, expect):
    dw, files = metric(op, value, rec)
    e, _ = ev(tmp_path, dw, files)
    assert e.result == expect and e.measured == rec


def test_metric_unknown_when_the_record_or_pointer_is_unusable(tmp_path):
    dw, files = metric("<", 1)
    assert ev(tmp_path / "a", dw)[0].result == "unknown"  # no record and no parent directory
    assert ev(tmp_path / "a2", dw, dirs=["records"])[0].result == "awaiting"  # no record, parent exists
    assert ev(tmp_path / "b", dw, {"records/m.json": "{broken"})[0].result == "unknown"
    assert ev(tmp_path / "c", dw, {"records/m.json": json.dumps({"a": []})})[0].result == "unknown"  # pointer does not resolve
    assert ev(tmp_path / "d", dw, {"records/m.json": json.dumps({"a": [{"v": "high"}]})})[0].result == "unknown"  # not a number
    assert ev(tmp_path / "e", dw, {"records/m.json": json.dumps({"a": [{"v": True}]})})[0].result == "unknown"  # a bool is not a number


def test_json_pointer_escapes_and_array_indices():
    from roadmap.evaluate import resolve_pointer
    doc = {"a/b": {"c~d": [10, 20]}, "": 5}
    assert resolve_pointer(doc, "/a~1b/c~0d/1") == 20
    assert resolve_pointer(doc, "/") == 5
    with pytest.raises(KeyError):
        resolve_pointer(doc, "/a~1b/c~0d/2")
    with pytest.raises(KeyError):
        resolve_pointer(doc, "/a~1b/c~0d/01")


# ---- brief 2 T2: awaiting versus unknown, every row of the table

AWAITING_ROWS = {
    "artifact": ({"type": "artifact", "path": "records/x.json"}, "records"),
    "metric": ({"type": "metric", "record": "records/m.json", "pointer": "/v", "op": "<", "value": 1}, "records"),
    "decision": ({"type": "decision", "record": "decisions/0001-x.md"}, "decisions"),
}


@pytest.mark.parametrize("kind", sorted(AWAITING_ROWS))
def test_an_absent_file_with_an_existing_parent_is_awaiting_and_the_node_stays_ready(tmp_path, kind):
    dw, parent = AWAITING_ROWS[kind]
    e, status = ev(tmp_path, dw, dirs=[parent])
    assert e.result == "awaiting" and status == "ready"


@pytest.mark.parametrize("kind", sorted(AWAITING_ROWS))
def test_an_absent_file_whose_parent_directory_is_missing_is_unknown(tmp_path, kind):
    dw, _ = AWAITING_ROWS[kind]
    assert ev(tmp_path, dw)[0].result == "unknown"


def test_a_nested_parent_must_exist_in_full(tmp_path):
    dw = {"type": "artifact", "path": "records/deep/er/x.json"}
    assert ev(tmp_path / "a", dw, dirs=["records"])[0].result == "unknown"
    assert ev(tmp_path / "b", dw, dirs=["records/deep/er"])[0].result == "awaiting"


def test_an_existing_but_unusable_file_is_unknown_not_awaiting(tmp_path):
    dw, _ = AWAITING_ROWS["metric"]
    assert ev(tmp_path / "a", dw, {"records/m.json": "{broken"})[0].result == "unknown"
    assert ev(tmp_path / "b", dw, {"records/m.json": "{}"})[0].result == "unknown"  # the pointer does not resolve
    dd, _ = AWAITING_ROWS["decision"]
    assert ev(tmp_path / "c", dd, {"decisions/0001-x.md": "---\nid: adr-0001\n---\n"})[0].result == "unknown"  # no status


def test_manual_is_never_awaiting_or_unknown(tmp_path):
    assert ev(tmp_path / "a", {"type": "manual"})[0].result == "fail"
    assert ev(tmp_path / "b", {"type": "manual"}, signed_off=True)[0].result == "pass"


def test_a_state_file_without_a_checks_section_cannot_be_read(tmp_path):
    e, _ = ev(tmp_path, {"type": "check", "check": "check.a.one"}, {"docs/STATE.md": "STATE: x\n"})
    assert e.result == "unknown"
