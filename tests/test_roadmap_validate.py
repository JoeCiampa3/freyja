"""
Roadmap T3: validation. Each hand-authored invalid fixture under tests/fixtures/roadmap/invalid/ holds exactly one error class and must
yield exactly that error, naming the right ids and file paths. Nothing here depends on how the fixtures were made.

Run from the repo root:
    python -m pytest tests/test_roadmap_validate.py
"""
from pathlib import Path

import pytest
from rmhelp import leaf, make

import roadmap

INVALID = Path(__file__).parent / "fixtures" / "roadmap" / "invalid"

# fixture directory -> [(code, ids)]. no-root is the one class that cannot stand alone: a graph with no root has a node whose parent
# is missing or a parent cycle, so it is reported together with that cause.
EXPECTED = {
    "schema-unknown-field": [("schema", ("rm.ok",))],
    "schema-missing-title": [("schema", ("rm.ok",))],
    "filename-id": [("filename-id", ("rm.other",))],
    "id-format": [("id-format", ("rm.Bad_Id",))],
    "no-root": [("no-root", ()), ("parent-unresolved", ("rm.a",))],
    "multiple-roots": [("multiple-roots", ("rm.root", "rm.second"))],
    "parent-unresolved": [("parent-unresolved", ("rm.x",))],
    "parent-cycle": [("parent-cycle", ("rm.c1", "rm.c2"))],
    "blocker-unresolved": [("blocker-unresolved", ("rm.x",))],
    "blocked-self": [("blocked-relative", ("rm.x",))],
    "blocked-ancestor": [("blocked-relative", ("rm.g1", "rm.grp"))],
    "blocked-descendant": [("blocked-relative", ("rm.g1", "rm.grp"))],
    "blocked-by-superseded": [("blocked-by-superseded", ("rm.x", "rm.old"))],
    "blocking-cycle": [("blocking-cycle", ("rm.p", "rm.q"))],
    "blocking-cycle-interior": [("blocking-cycle", ("rm.g1", "rm.x"))],
    "blocking-cycle-inherited": [("blocking-cycle", ("rm.g1", "rm.x"))],
    "interior-has-stub": [("interior-forbidden", ("rm.grp",))],
    "interior-has-done-when": [("interior-forbidden", ("rm.grp",))],
    "interior-has-estimate": [("interior-forbidden", ("rm.grp",))],
    "leaf-missing-done-when": [("leaf-incomplete", ("rm.x",))],
    "leaf-missing-estimate": [("leaf-incomplete", ("rm.x",))],
    "stub-has-done-when": [("stub-forbidden", ("rm.x",))],
    "stub-has-estimate": [("stub-forbidden", ("rm.x",))],
    "superseded-by-unresolved": [("superseded-by-unresolved", ("rm.old",))],
    "superseded-by-superseded": [("superseded-by-superseded", ("rm.old1", "rm.old2"))],
    "superseded-live-children": [("superseded-live-children", ("rm.child", "rm.old"))],
}


def test_every_fixture_directory_has_an_expectation_and_back():
    assert sorted(p.name for p in INVALID.iterdir()) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_invalid_fixture_yields_exactly_its_error(name):
    rm = roadmap.compute(INVALID / name)
    assert [(e.code, tuple(sorted(e.ids))) for e in rm.errors] == [(c, tuple(sorted(i))) for c, i in EXPECTED[name]], [e.message for e in rm.errors]
    for e in rm.errors:
        assert e.message
        assert all(i in e.message for i in e.ids), (e.code, e.message)  # every message names its ids
        assert all(p in e.message for p in e.paths), (e.code, e.message)  # and its file paths
        assert all(p.startswith("roadmap/nodes/") and "\\" not in p for p in e.paths)  # repo-relative
    if name not in ("no-root", "multiple-roots", "parent-cycle") and not name.startswith("blocking-cycle"):
        assert all(e.paths for e in rm.errors), name


def test_a_valid_roadmap_has_no_errors_and_no_warnings(tmp_path):
    rm = roadmap.compute(make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.a": leaf("rm.root"), "rm.b": leaf("rm.root", blocked_by=["rm.a"])}))
    assert rm.errors == [] and rm.warnings == []


def test_the_blocking_cycle_message_names_a_cycle_in_order():
    rm = roadmap.compute(INVALID / "blocking-cycle")
    assert "rm.p" in rm.errors[0].message and "rm.q" in rm.errors[0].message and "->" in rm.errors[0].message


def test_a_superseded_node_is_exempt_from_the_leaf_and_interior_rules(tmp_path):
    rm = roadmap.compute(make(tmp_path / "r", {
        "rm.root": {"title": "Top"}, "rm.keep": leaf("rm.root"),
        "rm.old": {"parent": "rm.root", "superseded_by": "rm.keep"}}))  # no done_when and no estimate: allowed once retired
    assert rm.errors == [] and rm.status("rm.old") == "superseded"


def test_a_broken_front_matter_is_a_schema_error_naming_the_file(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.keep": leaf("rm.root")})
    (root / "roadmap" / "nodes" / "rm.bad.md").write_text("no front matter here\n", encoding="utf-8")
    (root / "roadmap" / "nodes" / "rm.bad2.md").write_text("---\nid: [unclosed\n---\n", encoding="utf-8")
    rm = roadmap.compute(root)
    assert sorted((e.code, e.paths) for e in rm.errors) == [("schema", ("roadmap/nodes/rm.bad.md",)), ("schema", ("roadmap/nodes/rm.bad2.md",))]


def test_a_node_whose_children_are_all_superseded_is_a_childless_node(tmp_path):
    rm = roadmap.compute(make(tmp_path / "r", {
        "rm.root": {"title": "Top"}, "rm.keep": leaf("rm.root"),
        "rm.old": {**leaf("rm.root"), "superseded_by": "rm.keep"}}))
    assert rm.errors == []
    rm = roadmap.compute(make(tmp_path / "s", {
        "rm.root": {"title": "Top"}, "rm.a": {"parent": "rm.root"},
        "rm.old": {**leaf("rm.a"), "superseded_by": "rm.a"}}))
    # rm.a has only a retired child, so it is a childless non-stub without a criterion
    assert [(e.code, e.ids) for e in rm.errors] == [("leaf-incomplete", ("rm.a",))]


def test_both_node_schema_versions_load_side_by_side_and_short_reaches_the_node(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top", "short": "Top"}, "rm.a": leaf("rm.root"), "rm.b": leaf("rm.root", short="B")})
    text = {i: (root / "roadmap" / "nodes" / f"{i}.md").read_text(encoding="utf-8") for i in ("rm.root", "rm.a", "rm.b")}
    assert "schema: roadmap-node/2" in text["rm.root"] and "schema: roadmap-node/1" in text["rm.a"]  # the fixtures exercise both forms
    rm = roadmap.compute(root)
    assert rm.errors == [] and [rm.nodes[i].short for i in ("rm.root", "rm.a", "rm.b")] == ["Top", None, "B"]


def test_short_over_16_characters_or_on_a_version_1_file_is_a_schema_error_naming_the_node(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.long": leaf("rm.root", short="x" * 17)})
    nodes = root / "roadmap" / "nodes"
    text = (nodes / "rm.long.md").read_text(encoding="utf-8").replace("rm.long", "rm.old").replace("roadmap-node/2", "roadmap-node/1").replace("x" * 17, "ok")
    (nodes / "rm.old.md").write_text(text, encoding="utf-8", newline="\n")  # a version-1 file that carries `short`
    rm = roadmap.compute(root)
    bad = sorted((e.code, e.ids) for e in rm.errors if e.code == "schema")
    assert bad == [("schema", ("rm.long",)), ("schema", ("rm.old",))], [e.message for e in rm.errors]
    assert any("short" in e.message and "roadmap-node/2" in e.message for e in rm.errors if e.ids == ("rm.old",))  # the message says what to do
