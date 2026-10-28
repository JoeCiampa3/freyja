"""
Thread T8: the pre-commit hook builds the thread after the roadmap and stages its outputs, in a throwaway repository, as the roadmap's hook
test does.

    python -m pytest tests/test_thread_hook.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from thread_help import REPO, edit_record, make_root

# ---- the hook

SH = shutil.which("sh") or next((p for p in (r"C:\Program Files\Git\bin\sh.exe", r"C:\Program Files\Git\usr\bin\sh.exe") if Path(p).exists()), None)


def git(root, *args, env=None, check=True):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=check, env=env)


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository: its own tools/, the hook, a tiny model and snapshot, valid thread records and a valid roadmap."""
    from rmhelp import leaf, make
    root = tmp_path / "r"
    make_root(root)
    (root / "CONVENTIONS.md").write_text("marker\n")
    shutil.copytree(REPO / "tools", root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "docs" / "schemas", root / "docs" / "schemas")
    (root / "sim" / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "sim" / "scripts" / "pre_processor.py", root / "sim" / "scripts" / "pre_processor.py")
    shutil.copytree(REPO / ".githooks", root / ".githooks")
    shutil.copy(REPO / ".gitignore", root / ".gitignore")
    make(root, {"rm.root": {"title": "Top"}, "rm.a": leaf("rm.root")})
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "core.hooksPath", ".githooks")
    return root


@pytest.mark.skipif(SH is None, reason="no POSIX sh available to run a git hook")
def test_the_hook_builds_the_thread_stages_its_outputs_and_blocks_on_errors(repo):
    env = {**os.environ, "FREYJA_PYTHON": sys.executable}
    git(repo, "add", ".gitignore", "CONVENTIONS.md", "tools", "docs", "sim", ".githooks", "roadmap/nodes", "params", "thread/records", "decisions")
    r = git(repo, "commit", "-q", "-m", "first", env=env, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    tracked = git(repo, "ls-files").stdout.split()
    for want in ("thread/STATUS.md", "thread/graph.json", "thread/derived/seg.thigh.json", "thread/dossiers/seg.thigh.md", "roadmap/state.json"):
        assert want in tracked, want
    assert git(repo, "status", "--porcelain").stdout.strip() == ""
    # a broken record blocks the commit, with the error text, and the generated files are not touched
    before = (repo / "thread" / "STATUS.md").read_bytes()
    edit_record(repo, "part.base.p2", housed_in="seg.nowhere")
    git(repo, "add", "thread/records")
    r = git(repo, "commit", "-q", "-m", "broken", env=env, check=False)
    assert r.returncode != 0 and "ref-unresolved" in r.stdout + r.stderr
    assert (repo / "thread" / "STATUS.md").read_bytes() == before
    assert git(repo, "log", "--oneline").stdout.count("\n") == 1


def test_the_hook_text_builds_the_thread_after_the_roadmap_and_keeps_the_roadmap_lines():
    hook = (REPO / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert hook.index("roadmap build") < hook.index("thread build")
    assert "git add -- roadmap/state.json roadmap/STATUS.md" in hook and "thread/derived" in hook and "\r" not in hook


# ---- fy state

def test_the_state_line_counts_records_work_items_rework_and_errors(tmp_path):
    from thread import fixture
    sys.path.insert(0, str(REPO / "sim" / "scripts"))
    import state
    assert state.thread_line(REPO).startswith("Thread: 27 records | 1 work items | rework 0 | errors 0")
    fixture.generate(tmp_path / "f", 0)
    assert state.thread_line(tmp_path / "f") == "Thread: 46 records | 6 work items | rework 3 | errors 0"
    edit_record(tmp_path / "f", "part.hip.m1", housed_in="seg.nowhere")
    assert state.thread_line(tmp_path / "f") == "Thread: 46 records | 6 work items | rework 0 | errors 1"
    (tmp_path / "e").mkdir()
    assert state.thread_line(tmp_path / "e") == "Thread: no thread/"


def test_the_state_file_has_the_thread_line_right_after_the_roadmap_line():
    sys.path.insert(0, str(REPO / "sim" / "scripts"))
    import state
    text = state.generate(REPO, run=False)
    lines = text.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("Roadmap: "))
    assert lines[i + 1].startswith("Thread: ")
    assert len(lines) <= state.MAX_LINES
