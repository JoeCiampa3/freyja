"""
Roadmap T2a/T3: the seeded fixture generator, and the derivation checked against the statuses the generator intended. The generator
builds records and blockers to produce each status and computes its intended statuses from its own intents; it does not import the
derivation, evaluation or validation code, which is what makes the comparison a test.

Run from the repo root:
    python -m pytest tests/test_roadmap_fixture.py
"""
import hashlib
import json
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
    # the only warnings are criterion-unknown, one for each leaf the generator left with missing or unreadable evidence
    assert [w.code for w in rm.warnings] == ["criterion-unknown"] * len(intended(root)["unknown_criteria"]), [w.message for w in rm.warnings[:3]]
    assert sorted(w.ids[0] for w in rm.warnings) == intended(root)["unknown_criteria"] != []
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
