"""
Roadmap T3: status derivation, hand-built cases, one per rule of docs/briefs/architecture/roadmap-brief1.md.

Run from the repo root:
    python -m pytest tests/test_roadmap_derive.py
"""
from rmhelp import leaf, make

import roadmap


def derive(tmp_path, nodes):
    rm = roadmap.compute(make(tmp_path / "r", nodes))
    assert rm.errors == [], [e.message for e in rm.errors]
    return rm


ROOT = {"rm.root": {"title": "Everything works"}}


def test_leaf_ready_active_done_and_blocked(tmp_path):
    rm = derive(tmp_path, {**ROOT,
        "rm.a": leaf("rm.root", done=True),
        "rm.b": leaf("rm.root"),
        "rm.c": leaf("rm.root", active=True),
        "rm.d": leaf("rm.root", blocked_by=["rm.b"]),
        "rm.e": leaf("rm.root", blocked_by=["rm.a"]),
        "rm.f": leaf("rm.root", active=True, blocked_by=["rm.b"])})
    got = {i: rm.status(f"rm.{i}") for i in "abcdef"}
    # d waits on an unfinished leaf; e's only blocker is done; an active leaf that is blocked reads blocked
    assert got == {"a": "done", "b": "ready", "c": "active", "d": "blocked", "e": "ready", "f": "blocked"}
    assert "rm.b" in rm.reason("rm.d")


def test_a_done_leaf_with_an_uncleared_blocker_is_done_with_a_warning(tmp_path):
    rm = derive(tmp_path, {**ROOT, "rm.a": leaf("rm.root"), "rm.b": leaf("rm.root", done=True, blocked_by=["rm.a"])})
    assert rm.status("rm.b") == "done"
    assert [w.code for w in rm.warnings] == ["done-out-of-order"] and rm.warnings[0].ids == ("rm.b", "rm.a")  # the node, then the blocker it ran ahead of


def test_active_on_a_done_leaf_and_signed_off_on_other_criteria_warn(tmp_path):
    rm = derive(tmp_path, {**ROOT,
        "rm.a": leaf("rm.root", done=True, active=True),
        "rm.b": {**leaf("rm.root"), "done_when": {"type": "artifact", "path": "x.json"}, "signed_off": True}})
    assert sorted((w.code, w.ids) for w in rm.warnings) == [("active-on-done", ("rm.a",)), ("signed-off-not-manual", ("rm.b",))]


def test_the_estimate_cap_warns_above_three_days(tmp_path):
    assert roadmap.ESTIMATE_CAP_DAYS == 3.0
    rm = derive(tmp_path, {**ROOT, "rm.a": leaf("rm.root", estimate_days=3.0), "rm.b": leaf("rm.root", estimate_days=3.5)})
    assert [(w.code, w.ids) for w in rm.warnings] == [("estimate-over-cap", ("rm.b",))]


def test_stub_is_expandable_or_blocked(tmp_path):
    rm = derive(tmp_path, {**ROOT,
        "rm.a": leaf("rm.root"),
        "rm.s": {"parent": "rm.root", "stub": True},
        "rm.t": {"parent": "rm.root", "stub": True, "blocked_by": ["rm.a"]}})
    assert rm.status("rm.s") == "expandable" and rm.status("rm.t") == "blocked"
    assert rm.kind("rm.s") == "stub"


def test_interior_done_blocked_in_progress_not_started(tmp_path):
    rm = derive(tmp_path, {
        "rm.root": {"title": "Top"},
        "rm.i-done": {"parent": "rm.root"}, "rm.i-done-1": leaf("rm.i-done", done=True), "rm.i-done-2": leaf("rm.i-done", done=True),
        "rm.i-prog": {"parent": "rm.root"}, "rm.i-prog-1": leaf("rm.i-prog", done=True), "rm.i-prog-2": leaf("rm.i-prog"),
        "rm.i-act": {"parent": "rm.root"}, "rm.i-act-1": leaf("rm.i-act", active=True),
        "rm.i-none": {"parent": "rm.root"}, "rm.i-none-1": leaf("rm.i-none"), "rm.i-none-2": {"parent": "rm.i-none", "stub": True},
        "rm.i-blk": {"parent": "rm.root", "blocked_by": ["rm.i-none-1"]}, "rm.i-blk-1": leaf("rm.i-blk")})
    got = {i: rm.status(f"rm.{i}") for i in ("i-done", "i-prog", "i-act", "i-none", "i-blk", "root")}
    assert got == {"i-done": "done", "i-prog": "in_progress", "i-act": "in_progress", "i-none": "not_started", "i-blk": "blocked", "root": "in_progress"}
    assert rm.kind("rm.i-done") == "interior" and rm.kind("rm.i-done-1") == "leaf"


def test_blockers_are_inherited_from_ancestors(tmp_path):
    rm = derive(tmp_path, {
        "rm.root": {"title": "Top"},
        "rm.gate": leaf("rm.root"),
        "rm.a": {"parent": "rm.root", "blocked_by": ["rm.gate"]},
        "rm.b": {"parent": "rm.a"}, "rm.b1": leaf("rm.b"), "rm.b2": {"parent": "rm.b", "stub": True}})
    assert rm.status("rm.b1") == "blocked" and rm.status("rm.b2") == "blocked" and rm.status("rm.b") == "blocked" and rm.status("rm.a") == "blocked"
    assert rm.effective_blockers("rm.b1") == ["rm.gate"]
    assert rm.dependents("rm.gate") == ["rm.a", "rm.b", "rm.b1", "rm.b2"]
    assert "rm.gate" in rm.reason("rm.b1")


def test_an_interior_blocker_clears_only_when_all_its_children_are_done(tmp_path):
    base = {"rm.root": {"title": "Top"}, "rm.lib": {"parent": "rm.root"}, "rm.lib-1": leaf("rm.lib", done=True),
            "rm.user": leaf("rm.root", blocked_by=["rm.lib"])}
    rm = derive(tmp_path / "x", {**base, "rm.lib-2": leaf("rm.lib")})
    assert rm.status("rm.user") == "blocked" and rm.uncleared("rm.user") == ["rm.lib"]
    rm = derive(tmp_path / "y", {**base, "rm.lib-2": leaf("rm.lib", done=True)})
    assert rm.status("rm.lib") == "done" and rm.status("rm.user") == "ready"


def test_superseded_nodes_are_excluded_from_derivation_and_counts(tmp_path):
    rm = derive(tmp_path, {
        "rm.root": {"title": "Top"},
        "rm.ok": leaf("rm.root", done=True),
        "rm.old": {**leaf("rm.root"), "superseded_by": "rm.ok"}})
    assert rm.status("rm.old") == "superseded"
    assert rm.status("rm.root") == "done"  # the retired, unfinished leaf does not hold the parent back
    assert rm.counts == {"done": 2} and rm.superseded_count == 1 and rm.node_count == 2
    assert rm.children("rm.root") == ["rm.ok"]


def test_the_frontier_is_ready_leaves_and_expandable_stubs_sorted_by_id(tmp_path):
    rm = derive(tmp_path, {**ROOT,
        "rm.z": leaf("rm.root"), "rm.a": leaf("rm.root"), "rm.m": {"parent": "rm.root", "stub": True},
        "rm.act": leaf("rm.root", active=True), "rm.dn": leaf("rm.root", done=True), "rm.bl": leaf("rm.root", blocked_by=["rm.z"]),
        "rm.bs": {"parent": "rm.root", "stub": True, "blocked_by": ["rm.z"]}})
    assert rm.frontier == ["rm.a", "rm.m", "rm.z"]


def test_stale_is_reserved_and_never_emitted(tmp_path):
    rm = derive(tmp_path, {**ROOT, "rm.a": leaf("rm.root", done=True), "rm.b": leaf("rm.root")})
    assert "stale" not in {rm.status(i) for i in rm.nodes} and "stale" in roadmap.STATUSES


def test_an_empty_roadmap_is_valid(tmp_path):
    rm = roadmap.compute(make(tmp_path / "e", {}))
    assert rm.errors == [] and rm.nodes == {} and rm.frontier == [] and rm.node_count == 0
    assert "no nodes" in rm.summary_line()
    rm = roadmap.compute(tmp_path / "nonexistent")
    assert rm.errors == [] and rm.nodes == {}


def test_errors_leave_unresolvable_statuses_unknown_but_derive_the_rest(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.a": leaf("rm.root", done=True),
                                 "rm.x": leaf("rm.root", blocked_by=["rm.ghost"]), "rm.y": leaf("rm.root")})
    rm = roadmap.compute(root)
    assert [e.code for e in rm.errors] == ["blocker-unresolved"]
    assert rm.status("rm.a") == "done" and rm.status("rm.y") == "ready"
    assert rm.status("rm.x") == "blocked"  # an unresolvable blocker can never be cleared


def test_a_criterion_whose_evidence_is_missing_or_unreadable_warns(tmp_path):
    """Joe's decision 2 on memo13: an `unknown` evaluation stays ready (the brief) but is no longer silent."""
    metric = {"type": "metric", "record": "sim/none.json", "pointer": "/x", "op": "<", "value": 1}
    rm = derive(tmp_path, {**ROOT, "rm.a": {**leaf("rm.root"), "done_when": metric}, "rm.b": leaf("rm.root")})
    assert rm.status("rm.a") == "ready" and rm.status("rm.b") == "ready"
    got = [w for w in rm.warnings if w.code == "criterion-unknown"]
    assert [w.ids for w in got] == [("rm.a",)] and "sim/none.json" in got[0].message and "roadmap/nodes/rm.a.md" in got[0].message


def test_a_failing_criterion_is_not_a_criterion_unknown_warning(tmp_path):
    art = {"type": "artifact", "path": "sim/none.json"}  # a missing artifact is a fail, not unknown
    rm = derive(tmp_path, {**ROOT, "rm.a": {**leaf("rm.root"), "done_when": art}})
    assert rm.evaluation("rm.a").result == "fail" and rm.warnings == []
