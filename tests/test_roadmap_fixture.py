"""
Roadmap T2a/T3: the seeded fixture generator, and the derivation checked against the statuses the generator intended. The generator
builds records and blockers to produce each status and computes its intended statuses from its own intents; it does not import the
derivation, evaluation or validation code, which is what makes the comparison a test.

Run from the repo root:
    python -m pytest tests/test_roadmap_fixture.py
"""
import hashlib
import json
import re
from pathlib import Path

import pytest
from rmhelp import TOOLS  # noqa: F401  (puts tools/ on sys.path)

import roadmap
from roadmap import fixture

ALL_LIVE = {"done", "blocked", "active", "ready", "expandable", "in_progress", "not_started"}


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def intended(root: Path) -> dict:
    return json.loads((root / "fixture-intent.json").read_text(encoding="utf-8"))


def test_the_generator_is_deterministic_and_seeded(tmp_path):
    fixture.generate(80, tmp_path / "a", seed=1)
    fixture.generate(80, tmp_path / "b", seed=1)
    fixture.generate(80, tmp_path / "c", seed=2)
    assert tree_hash(tmp_path / "a") == tree_hash(tmp_path / "b") != tree_hash(tmp_path / "c")


def test_the_generator_does_not_import_the_code_it_tests():
    import ast
    tree = ast.parse(Path(fixture.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and not (node.module or "").startswith("roadmap"), ast.dump(node)
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith("roadmap") for a in node.names), ast.dump(node)


def test_refuses_a_nonempty_output_directory(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("1")
    with pytest.raises(FileExistsError):
        fixture.generate(30, tmp_path / "x")


@pytest.mark.parametrize("size,seed", [(300, 0), (300, 7), (600, 3), (60, 5)])
def test_fixture_is_valid_and_derived_statuses_match_the_intended_ones(tmp_path, size, seed):
    root = tmp_path / "f"
    fixture.generate(size, root, seed=seed)
    rm = roadmap.compute(root)
    assert rm.errors == [], [e.message for e in rm.errors[:3]]
    # the only warnings are criterion-unknown, and they name exactly the leaves the generator left with unreadable or unexpectable evidence;
    # the leaves whose evidence is merely not there yet are awaiting and draw nothing
    want_unknown, want_awaiting = intended(root)["unknown_criteria"], intended(root)["awaiting_criteria"]
    assert [w.code for w in rm.warnings] == ["criterion-unknown"] * len(want_unknown), [w.message for w in rm.warnings[:3]]
    assert sorted(w.ids[0] for w in rm.warnings) == want_unknown != []
    assert want_awaiting != [] and not set(want_awaiting) & set(want_unknown)
    assert {i: rm.evaluation(i).result for i in want_awaiting} == {i: "awaiting" for i in want_awaiting}
    assert {i: rm.evaluation(i).result for i in want_unknown} == {i: "unknown" for i in want_unknown}
    got = {i for i in rm.nodes if rm.evaluation(i) is not None and rm.evaluation(i).result in ("awaiting", "unknown")}
    assert got == set(want_awaiting) | set(want_unknown)  # and no other leaf evaluates to either
    want = intended(root)["statuses"]
    assert len(want) == size and sorted(rm.nodes) == sorted(want)
    wrong = {i: (want[i], rm.status(i)) for i in want if rm.status(i) != want[i]}
    assert wrong == {}


@pytest.mark.parametrize("seed", [0, 7])
def test_the_300_node_fixture_covers_the_brief(tmp_path, seed):
    root = tmp_path / "f"
    fixture.generate(300, root, seed=seed)
    rm = roadmap.compute(root)
    statuses = {rm.status(i) for i in rm.nodes}
    assert statuses >= ALL_LIVE | {"superseded"}, ALL_LIVE | {"superseded"} - statuses
    depth = {}
    for i in sorted(rm.nodes, key=lambda i: len(rm.graph.ancestors(i))):
        depth[i] = len(rm.graph.ancestors(i))
    assert 6 <= max(depth.values()) <= 8
    kids = [len(rm.graph.all_children[i]) for i in rm.nodes if rm.graph.all_children[i]]
    assert max(kids) - min(kids) >= 3  # uneven branching
    assert any(rm.nodes[i].stub for i in rm.nodes)
    # a blocking edge between nodes in different branches (neither an ancestor of the other, different parents)
    cross = [(i, b) for i in rm.nodes for b in rm.nodes[i].blocked_by if rm.nodes[i].parent != rm.nodes[b].parent]
    assert len(cross) >= 20
    types = {rm.nodes[i].done_when["type"] for i in rm.nodes if rm.nodes[i].done_when}
    assert types == {"artifact", "decision", "check", "metric", "manual"}
    assert (root / "decisions").is_dir() and list((root / "records" / "metrics").glob("*.json")) and list((root / "log").glob("*"))
    assert (root / "docs" / "STATE.md").exists()


def test_the_fixture_has_references_to_search_for(tmp_path):
    from roadmap import refs
    root = tmp_path / "f"
    fixture.generate(120, root, seed=4)
    rm = roadmap.compute(root)
    assert sum(1 for i in rm.nodes if refs.file_references(root, i)) >= 10


# ---- brief 2 T3: the root has 5 to 10 first-layer branches of uneven size

def first_layer(rm):
    return [i for i in rm.nodes if rm.nodes[i].parent == "rm.n000-root"]


def subtree_size(rm, i):
    return 1 + sum(subtree_size(rm, c) for c in rm.graph.all_children[i])


@pytest.mark.parametrize("seed", [0, 3, 7, 11, 12])
def test_the_root_has_five_to_ten_uneven_first_layer_branches_with_distinct_titles(tmp_path, seed):
    root = tmp_path / "f"
    fixture.generate(300, root, seed=seed)
    rm = roadmap.compute(root)
    layer = first_layer(rm)
    assert 5 <= len(layer) <= 10, len(layer)
    titles = [rm.nodes[i].title for i in layer]
    assert len(set(titles)) == len(titles)
    assert len({i.split("-", 1)[1] for i in layer}) == len(layer)  # the nouns differ too, so a branch is recognisable at a glance
    sizes = sorted(subtree_size(rm, i) for i in layer)
    assert sizes[-1] >= 2 * sizes[0], sizes  # uneven
    assert sizes[-1] < 0.8 * (len(rm.nodes) - 1), sizes  # and no branch holds almost everything, which was the old shape


@pytest.mark.parametrize("size,seed", [(300, 0), (300, 7), (600, 3)])
def test_the_depth_and_coverage_guarantees_survive_the_new_shape(tmp_path, size, seed):
    root = tmp_path / "f"
    fixture.generate(size, root, seed=seed)
    rm = roadmap.compute(root)
    assert {rm.status(i) for i in rm.nodes} >= ALL_LIVE | {"superseded"}
    assert 6 <= max(len(rm.graph.ancestors(i)) for i in rm.nodes) <= 8


@pytest.mark.parametrize("n", [1, 3, 5, 12, 20])
def test_first_layer_overrides_the_branch_count(tmp_path, n):
    root = tmp_path / "f"
    fixture.generate(300, root, seed=0, first_layer=n)
    rm = roadmap.compute(root)
    assert rm.errors == [] and len(first_layer(rm)) == n


def test_first_layer_that_cannot_fit_is_refused(tmp_path):
    with pytest.raises(ValueError):
        fixture.generate(10, tmp_path / "a", first_layer=9)  # 10 nodes, 1 retired: 9 live, so at most 8 below the root
    with pytest.raises(ValueError):
        fixture.generate(60, tmp_path / "b", first_layer=0)


@pytest.mark.parametrize("seed", [0, 3, 7])
def test_intended_statuses_hold_for_an_overridden_first_layer(tmp_path, seed):
    root = tmp_path / "f"
    fixture.generate(300, root, seed=seed, first_layer=12)
    rm = roadmap.compute(root)
    want = intended(root)["statuses"]
    assert {i: (want[i], rm.status(i)) for i in want if rm.status(i) != want[i]} == {}


@pytest.mark.parametrize("seed", [0, 3, 7])
def test_the_fixture_exercises_both_node_schema_versions_and_shorts_the_first_layer(tmp_path, seed):
    """Brief 3 T1: every first-layer branch has a short label, some deeper nodes do, and the rest are version-1 files without one."""
    root = tmp_path / "f"
    fixture.generate(300, root, seed=seed)
    rm = roadmap.compute(root)
    assert rm.errors == []
    layer = [i for i in first_layer(rm) if not rm.nodes[i].superseded]
    assert all(rm.nodes[i].short and len(rm.nodes[i].short) <= 16 for i in layer)
    shorts = [n for n in rm.nodes.values() if n.short]
    assert len(layer) < len(shorts) < len(rm.nodes) - 20  # a mix, not all or only the heads
    own = re.compile(r"^schema: (\S+)$", re.M)  # the node's own line, not a done_when schema path
    versions = {i: own.search((root / "roadmap" / "nodes" / f"{i}.md").read_text(encoding="utf-8")).group(1) for i in rm.nodes}
    assert {v for i, v in versions.items() if rm.nodes[i].short} == {"roadmap-node/2"}
    assert "roadmap-node/1" in set(versions.values())
