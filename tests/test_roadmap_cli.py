"""
Roadmap T4/T5: the `fy roadmap` commands (tools/roadmap/cli.py behind tools/fy), the pre-commit hook, install-hooks and the `fy state` line.

Run from the repo root:
    python -m pytest tests/test_roadmap_cli.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from rmhelp import REPO, leaf, make

import roadmap
from roadmap import cli, fixture

INVALID = Path(__file__).parent / "fixtures" / "roadmap" / "invalid"
FY = REPO / "tools" / "fy"


def run(args, root=None, env=None):
    out = []
    opened = []
    code = cli.main(list(args) + (["--root", str(root)] if root else []), say=out.append, opener=lambda p: opened.append(p))
    return code, "\n".join(out), opened


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    root = tmp_path_factory.mktemp("fx") / "f"
    fixture.generate(300, root, seed=0)
    return root


def test_validate_exit_codes_and_output(fx):
    code, out, _ = run(["validate"], fx)
    n_unknown = len(json.loads((fx / "fixture-intent.json").read_text(encoding="utf-8"))["unknown_criteria"])  # awaiting ones draw none
    assert code == 0 and f"0 errors, {n_unknown} warnings" in out and n_unknown > 0  # the fixture's unreadable-evidence leaves
    code, out, _ = run(["validate"], INVALID / "parent-unresolved")
    assert code == 1 and "parent-unresolved" in out and "rm.x" in out and "rm.ghost" in out
    code, out, _ = run(["validate", "--json"], INVALID / "parent-unresolved")
    data = json.loads(out)
    assert code == 1 and [e["code"] for e in data["errors"]] == ["parent-unresolved"] and data["warnings"] == []


def test_validate_on_an_empty_roadmap_says_no_nodes(tmp_path):
    code, out, _ = run(["validate"], make(tmp_path / "e", {}))
    assert code == 0 and "no nodes" in out


def test_build_writes_the_two_files_only_when_valid(tmp_path, fx):
    root = tmp_path / "f"
    shutil.copytree(fx, root)
    code, out, _ = run(["build"], root)
    assert code == 0 and (root / "roadmap" / "state.json").exists() and (root / "roadmap" / "STATUS.md").exists()
    bad = tmp_path / "bad"
    shutil.copytree(INVALID / "blocking-cycle", bad)
    code, out, _ = run(["build"], bad)
    assert code == 1 and "blocking-cycle" in out and not (bad / "roadmap" / "state.json").exists()


def pick(rm, kind, deep=False):
    cands = [i for i in sorted(rm.nodes) if rm.kind(i) == kind and rm.status(i) != "superseded"]
    return max(cands, key=lambda i: len(rm.graph.ancestors(i))) if deep else cands[0]


def test_show_a_deep_leaf_an_interior_node_and_a_stub(fx):
    rm = roadmap.compute(fx)
    leaf_id, interior_id, stub_id = pick(rm, "leaf", deep=True), pick(rm, "interior", deep=True), pick(rm, "stub")
    code, out, _ = run(["show", leaf_id], fx)
    assert code == 0
    assert f"{rm.nodes[leaf_id].parent}" in out.splitlines()[0] and out.splitlines()[0].rstrip().endswith(leaf_id)  # breadcrumb, root to node
    assert out.splitlines()[0].startswith("rm.n000-root")
    assert rm.status(leaf_id) in out and "done_when" in out and rm.nodes[leaf_id].title in out
    code, out, _ = run(["show", interior_id], fx)
    assert "children" in out and all(c in out for c in rm.children(interior_id))
    code, out, _ = run(["show", stub_id], fx)
    assert "stub" in out and "done_when" not in out.replace("done_when: none", "")
    code, out, _ = run(["show", leaf_id, "--json"], fx)
    data = json.loads(out)
    assert data["id"] == leaf_id and data["status"] == rm.status(leaf_id) and data["breadcrumb"][0] == "rm.n000-root"
    assert set(data) >= {"fields", "evaluation", "children", "uncleared_blockers", "dependents", "references", "reason"}


def test_show_resolves_queries_and_reports_candidates(fx):
    rm = roadmap.compute(fx)
    some = pick(rm, "leaf")
    code, out, _ = run(["show", some[3:]], fx)  # without the rm. prefix
    assert code == 0 and some in out
    code, out, _ = run(["show", "-"], fx)  # ambiguous
    assert code == 1 and out.count("rm.n") <= 10 + 1
    code, out, _ = run(["show", "zzzzzz"], fx)
    assert code == 1 and "no node matches" in out


def test_frontier_lists_ready_leaves_and_expandable_stubs(fx):
    rm = roadmap.compute(fx)
    code, out, _ = run(["frontier"], fx)
    assert code == 0 and all(i in out for i in rm.frontier)
    code, out, _ = run(["frontier", "--json"], fx)
    data = json.loads(out)
    assert [d["id"] for d in data] == rm.frontier
    assert {"id", "kind", "title", "done_when", "estimate_days"} <= set(data[0])


def test_refs_lists_references(fx):
    rm = roadmap.compute(fx)
    from roadmap import refs
    target = next(i for i in sorted(rm.nodes) if refs.file_references(fx, i))
    code, out, _ = run(["refs", target], fx)
    assert code == 0 and "log/events.log" in out
    code, out, _ = run(["refs", target, "--json"], fx)
    assert json.loads(out)["files"]


def test_open_uses_the_editor_resolution(fx):
    rm = roadmap.compute(fx)
    some = pick(rm, "leaf")
    code, out, opened = run(["open", some], fx)
    assert code == 0 and opened == [fx / "roadmap" / "nodes" / f"{some}.md"]


def test_fixture_command(tmp_path):
    code, out, _ = run(["fixture", "--size", "40", "--out", str(tmp_path / "x"), "--seed", "3"])
    assert code == 0 and len(list((tmp_path / "x" / "roadmap" / "nodes").glob("*.md"))) == 40
    code, out, _ = run(["fixture", "--size", "40", "--out", str(tmp_path / "x")])
    assert code == 1 and "not empty" in out


def test_fy_dispatches_roadmap(fx):
    p = subprocess.run([sys.executable, str(FY), "roadmap", "validate", "--root", str(fx)], capture_output=True, text=True, cwd=REPO)
    assert p.returncode == 0 and "0 errors" in p.stdout, p.stderr
    p = subprocess.run([sys.executable, str(FY), "roadmap", "validate", "--root", str(INVALID / "parent-cycle")], capture_output=True, text=True, cwd=REPO)
    assert p.returncode == 1 and "parent-cycle" in p.stdout


def test_the_repo_itself_validates_as_an_empty_roadmap():
    p = subprocess.run([sys.executable, str(FY), "roadmap", "validate"], capture_output=True, text=True, cwd=REPO)
    assert p.returncode == 0 and "no nodes" in p.stdout, p.stdout + p.stderr


# ---- the hook ---------------------------------------------------------------------------------

SH = shutil.which("sh") or next((p for p in (r"C:\Program Files\Git\bin\sh.exe", r"C:\Program Files\Git\usr\bin\sh.exe") if Path(p).exists()), None)


def git(root, *args, check=True, env=None):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=check, env=env)


@pytest.fixture()
def repo(tmp_path):
    """A throwaway repository with its own copy of tools/ and the hook, and a valid roadmap."""
    root = tmp_path / "r"
    root.mkdir()
    (root / "CONVENTIONS.md").write_text("marker\n")
    shutil.copytree(REPO / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "docs" / "schemas", root / "docs" / "schemas")
    shutil.copytree(REPO / ".githooks", root / ".githooks")
    shutil.copy(REPO / ".gitignore", root / ".gitignore")
    make(root, {"rm.root": {"title": "Top"}, "rm.a": leaf("rm.root")})
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "core.autocrlf", "false")
    return root


@pytest.mark.skipif(SH is None, reason="no POSIX sh available to run a git hook")
def test_the_hook_builds_stages_exactly_two_files_and_blocks_on_errors(repo):
    env = {**os.environ, "FREYJA_PYTHON": sys.executable}
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "add", ".gitignore", "CONVENTIONS.md", "tools", "docs", ".githooks", "roadmap/nodes")
    (repo / "unrelated.txt").write_text("not staged\n")
    r = git(repo, "commit", "-q", "-m", "first", env=env, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    tracked = git(repo, "ls-files").stdout.split()
    assert "roadmap/state.json" in tracked and "roadmap/STATUS.md" in tracked and "unrelated.txt" not in tracked
    assert git(repo, "status", "--porcelain").stdout.strip() == "?? unrelated.txt"
    # a broken node blocks the commit and the generated files are not touched
    make(repo, {"rm.b": leaf("rm.ghost")})
    before = (repo / "roadmap" / "state.json").read_bytes()
    git(repo, "add", "roadmap/nodes")
    r = git(repo, "commit", "-q", "-m", "broken", env=env, check=False)
    assert r.returncode != 0 and "parent-unresolved" in r.stdout + r.stderr
    assert (repo / "roadmap" / "state.json").read_bytes() == before
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


@pytest.mark.skipif(SH is None, reason="no POSIX sh available to run a git hook")
def test_the_hook_prefers_the_repo_venv(repo):
    hook = (REPO / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert ".venv" in hook and "roadmap build" in hook and "git add -- roadmap/state.json roadmap/STATUS.md" in hook
    assert "\r" not in hook and hook.startswith("#!/bin/sh")


def test_the_hook_is_tracked_with_the_executable_bit():
    out = subprocess.run(["git", "ls-files", "--stage", ".githooks/pre-commit"], cwd=REPO, capture_output=True, text=True).stdout
    assert out.startswith("100755 "), out or "pre-commit is not in the index yet"


def test_install_hooks_sets_hookspath_and_stops_on_existing_hooks(repo):
    code, out, _ = run(["install-hooks"], repo)
    assert code == 0 and git(repo, "config", "core.hooksPath").stdout.strip() == ".githooks"
    code, out, _ = run(["install-hooks"], repo)
    assert code == 0 and "already" in out
    git(repo, "config", "--unset", "core.hooksPath")
    git(repo, "config", "core.hooksPath", "elsewhere")
    code, out, _ = run(["install-hooks"], repo)
    assert code == 1 and "elsewhere" in out and git(repo, "config", "core.hooksPath").stdout.strip() == "elsewhere"
    git(repo, "config", "--unset", "core.hooksPath")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\n")
    code, out, _ = run(["install-hooks"], repo)
    assert code == 1 and "pre-push" in out and git(repo, "config", "core.hooksPath", check=False).stdout.strip() == ""


def test_the_state_line(tmp_path):
    sys.path.insert(0, str(REPO / "sim" / "scripts"))
    import state
    assert state.roadmap_line(REPO).startswith("Roadmap: ")
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.a": leaf("rm.root"), "rm.b": leaf("rm.root", done=True)})
    assert state.roadmap_line(root) == "Roadmap: 3 nodes | frontier 1 | errors 0"
    assert state.roadmap_line(make(tmp_path / "e", {})) == "Roadmap: no nodes | frontier 0 | errors 0"


def test_open_exits_nonzero_with_the_underlying_error(fx):
    some = pick(roadmap.compute(fx), "leaf")

    def bad(path):
        raise OSError("WinError 2: cannot find the file")
    out = []
    code = cli.main(["open", some, "--root", str(fx)], say=out.append, opener=bad)
    assert code == 1 and "WinError 2" in "\n".join(out)


def test_open_passes_an_absolute_path(fx):
    some = pick(roadmap.compute(fx), "leaf")
    _, _, opened = run(["open", some], fx)
    assert Path(opened[0]).is_absolute()


def test_fixture_command_takes_first_layer(tmp_path):
    code, out, _ = run(["fixture", "--size", "80", "--out", str(tmp_path / "x"), "--first-layer", "4"])
    assert code == 0
    rm = roadmap.compute(tmp_path / "x")
    assert sum(1 for n in rm.nodes.values() if n.parent == "rm.n000-root") == 4
    code, out, _ = run(["fixture", "--size", "80", "--out", str(tmp_path / "y"), "--first-layer", "0"])
    assert code == 1 and "first-layer" in out
