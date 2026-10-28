"""
Stage 3b T9: the `work` done_when type. It passes when thread/graph.json reports the wanted status (default `current`) for the work item; `awaiting` when the work item
exists but is unstamped; `unknown` when the work item is missing or the graph is unreadable; `fail` otherwise. The evaluator reads the graph file and never builds the thread.

    python -m pytest tests/test_roadmap_work_criterion.py
"""
import json
from pathlib import Path

import jsonschema
import pytest
from rmhelp import make

import roadmap
from roadmap import evaluate

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO / "docs" / "schemas" / "roadmap-node-2.schema.json").read_text(encoding="utf-8"))
WORK = "work.upper-arm-cad"


def graph(statuses):
    return json.dumps({"schema": "thread-graph/1", "nodes": [], "edges": [], "work_statuses": statuses})


def ev(tmp_path, done_when, graph_text=None, dirs=("thread",)):
    root = tmp_path / "r"
    make(root, {"rm.root": {"title": "Top"}, "rm.leaf": {"parent": "rm.root", "estimate_days": 1, "done_when": done_when}})
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    if graph_text is not None:
        (root / "thread" / "graph.json").write_text(graph_text, encoding="utf-8")
    rm = roadmap.compute(root)
    assert rm.errors == [], [e.message for e in rm.errors]
    return rm.evaluation("rm.leaf"), rm.status("rm.leaf"), rm


def test_current_passes_by_default(tmp_path):
    e, status, _ = ev(tmp_path, {"type": "work", "work": WORK}, graph({WORK: "current"}))
    assert e.result == "pass" and status == "done" and WORK in e.reason and "current" in e.reason


def test_a_named_status_is_the_one_that_passes(tmp_path):
    dw = {"type": "work", "work": WORK, "status": "stale"}
    assert ev(tmp_path / "a", dw, graph({WORK: "stale"}))[0].result == "pass"
    assert ev(tmp_path / "b", dw, graph({WORK: "current"}))[0].result == "fail"


@pytest.mark.parametrize("actual", ["stale", "drifted", "unknown", "reverified"])
def test_any_other_status_fails_and_says_which(tmp_path, actual):
    e, status, _ = ev(tmp_path, {"type": "work", "work": WORK}, graph({WORK: actual}))
    assert e.result == "fail" and actual in e.reason and status != "done"


def test_an_unstamped_work_item_is_awaiting_not_a_failure(tmp_path):
    e, status, rm = ev(tmp_path, {"type": "work", "work": WORK}, graph({WORK: "unstamped"}))
    assert e.result == "awaiting" and "unstamped" in e.reason
    assert not any(w.code == "criterion-unknown" for w in rm.warnings)       # awaiting is normal for unfinished work: no warning


def test_asking_for_unstamped_and_finding_it_unstamped_passes(tmp_path):
    assert ev(tmp_path, {"type": "work", "work": WORK, "status": "unstamped"}, graph({WORK: "unstamped"}))[0].result == "pass"


def test_a_missing_work_item_is_unknown_and_warns(tmp_path):
    e, _, rm = ev(tmp_path, {"type": "work", "work": WORK}, graph({"work.other": "current"}))
    assert e.result == "unknown" and WORK in e.reason
    assert any(w.code == "criterion-unknown" for w in rm.warnings)


@pytest.mark.parametrize("text", [None, "{not json", "[]", json.dumps({"nodes": []}), json.dumps({"work_statuses": []}), json.dumps({"work_statuses": {WORK: 3}})])
def test_an_unreadable_graph_is_unknown(tmp_path, text):
    e, _, rm = ev(tmp_path, {"type": "work", "work": WORK}, text)
    assert e.result == "unknown"
    assert any(w.code == "criterion-unknown" for w in rm.warnings)


def test_a_missing_thread_directory_is_unknown_too(tmp_path):
    assert ev(tmp_path, {"type": "work", "work": WORK}, None, dirs=())[0].result == "unknown"


def test_the_evaluator_reads_the_graph_and_never_builds_the_thread(tmp_path):
    root = tmp_path / "r"
    e, _, _ = ev(tmp_path, {"type": "work", "work": WORK}, graph({WORK: "current"}))
    assert e.result == "pass"
    assert sorted(p.name for p in (root / "thread").iterdir()) == ["graph.json"]          # nothing was built or written beside it
    assert not (root / "thread" / "records").exists()


def test_the_graph_is_a_referenced_file_of_the_node():
    class N:
        done_when = {"type": "work", "work": WORK}
    assert evaluate.referenced_files(N) == ["thread/graph.json"]


def test_the_node_schema_takes_a_work_criterion_and_rejects_bad_ones():
    def errors(dw):
        node = {"schema": "roadmap-node/2", "id": "rm.x", "title": "t", "parent": "rm.root", "estimate_days": 1, "done_when": dw}
        return list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(node))
    assert errors({"type": "work", "work": WORK}) == []
    assert errors({"type": "work", "work": WORK, "status": "stale"}) == []
    assert errors({"type": "work"})                                                  # work is required
    assert errors({"type": "work", "work": "part.arm.x"})                            # a work id
    assert errors({"type": "work", "work": WORK, "status": "fresh"})                 # one of the thread's work statuses
    assert errors({"type": "work", "work": WORK, "path": "x"})                       # no stray fields


def test_the_criterion_is_shown_in_text_and_the_table_names_it():
    from roadmap import render
    assert render._criterion_text({"type": "work", "work": WORK}) == f"work: {WORK} current"
    assert render._criterion_text({"type": "work", "work": WORK, "status": "stale"}) == f"work: {WORK} stale"
    readme = (REPO / "roadmap" / "README.md").read_text(encoding="utf-8")
    assert "| `work` |" in readme
    assert 'work: dw.work + " " + (dw.status || "current")' in (REPO / "tools" / "roadmap" / "viewer" / "app.js").read_text(encoding="utf-8")
