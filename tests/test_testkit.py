"""
tools/testkit: the input-keyed skip of marked tests, the tree key and the last-full-run record (memo 61).

Every case runs pytest in a throwaway git repository whose conftest registers the real plugin, so nothing here depends on this repo's own
tests or reads its cache. Run from the repo root:
    python -m pytest tests/test_testkit.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import testkit  # noqa: E402

CONFTEST = f"""import sys
sys.path.insert(0, {str(REPO / 'tools')!r})
import testkit.plugin as tk


def pytest_addoption(parser):
    tk.add_options(parser)


def pytest_configure(config):
    tk.register(config)
"""

TEST_FILE = """import pathlib
import pytest

HERE = pathlib.Path(__file__).resolve().parent


@pytest.mark.inputs("src")
def test_marked():
    assert (HERE.parent / "src" / "a.txt").read_text() != "bad"


def test_plain():
    pass
"""


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "r"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "checks").mkdir()
    (root / "docs" / "memos").mkdir(parents=True)
    (root / "pytest.ini").write_text("[pytest]\ntestpaths = tests checks\nmarkers =\n    inputs(*paths): the repo paths the result depends on\n")
    (root / ".gitignore").write_text(".fy-cache/\n__pycache__/\n.pytest_cache/\nignored.bin\n")
    (root / "conftest.py").write_text(CONFTEST)
    (root / "src" / "a.txt").write_text("good")
    (root / "src" / "b.txt").write_text("b")
    (root / "other.txt").write_text("o")
    (root / "docs" / "memos" / "memo1.md").write_text("m\n")
    (root / "tests" / "test_x.py").write_text(TEST_FILE)
    (root / "checks" / "test_c.py").write_text("def test_check():\n    pass\n")
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "core.autocrlf", "false")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def run(root, *args):
    """Run pytest in the throwaway repo; return (counts from the last line, whole output)."""
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    text = out.stdout + out.stderr
    tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    return {k.rstrip("s"): int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|errors|error)", tail)}, text


def store(root):
    return json.loads((root / ".fy-cache" / "inputs.json").read_text(encoding="utf-8"))["passed"]


# ---- the input-keyed skip ---------------------------------------------------------------------------------------------------------

def test_a_marked_test_that_passed_is_skipped_while_its_inputs_are_unchanged_and_says_why(repo):
    first, _ = run(repo)
    assert first == {"passed": 3}
    assert list(store(repo)) == ["tests/test_x.py::test_marked"]  # only the marked test is recorded
    second, text = run(repo)
    assert second == {"passed": 2, "skipped": 1}
    assert "inputs unchanged since this test last passed" in text and "--rerun-cached" in text
    assert re.search(r"inputs sha256:[0-9a-f]{12}", text)
    assert "1 skipped on unchanged inputs" in text


@pytest.mark.parametrize("edit", ["src/a.txt", "src/b.txt", "tests/test_x.py", "new file under src", "pytest.ini"])
def test_any_change_to_a_declared_input_or_to_the_test_file_runs_it_again(repo, edit):
    run(repo)
    if edit == "new file under src":
        (repo / "src" / "c.txt").write_text("new")  # untracked but not ignored: it counts
    elif edit == "tests/test_x.py":
        (repo / edit).write_text(TEST_FILE + "\n# edited\n")
    elif edit == "pytest.ini":
        (repo / edit).write_text((repo / edit).read_text() + "# edited\n")
    else:
        (repo / edit).write_text("changed")
    assert run(repo)[0] == {"passed": 3}
    assert run(repo)[0] == {"passed": 2, "skipped": 1}  # and the new key is recorded


def test_a_change_outside_the_declared_inputs_leaves_it_skipped(repo):
    run(repo)
    (repo / "other.txt").write_text("changed")
    (repo / "src" / "ignored.bin").write_text("gitignored files are not inputs")
    assert run(repo)[0] == {"passed": 2, "skipped": 1}


def test_a_failing_test_is_never_recorded_and_a_recorded_pass_is_forgotten_when_it_fails(repo):
    run(repo)
    (repo / "src" / "a.txt").write_text("bad")
    assert run(repo)[0] == {"passed": 2, "failed": 1}
    assert store(repo) == {}
    assert run(repo)[0] == {"passed": 2, "failed": 1}  # still run, still failing: a failure is never skipped
    (repo / "src" / "a.txt").write_text("good")
    assert run(repo)[0] == {"passed": 3}  # mutation: going back to the first key does not find the old pass


def test_rerun_cached_runs_a_test_whose_inputs_are_unchanged(repo):
    run(repo)
    assert run(repo, "--rerun-cached")[0] == {"passed": 3}


def test_a_marker_whose_path_names_no_file_is_an_error_that_names_the_path(repo):
    p = repo / "tests" / "test_x.py"
    p.write_text(TEST_FILE.replace('inputs("src")', 'inputs("src", "no/such/dir")'))
    counts, text = run(repo)
    assert counts == {"passed": 2, "error": 1}
    assert "no/such/dir" in text and "names no file" in text
    assert not (repo / ".fy-cache" / "inputs.json").exists() or store(repo) == {}


def test_a_marker_without_paths_is_an_error(repo):
    p = repo / "tests" / "test_x.py"
    p.write_text(TEST_FILE.replace('inputs("src")', "inputs()"))
    counts, text = run(repo)
    assert counts == {"passed": 2, "error": 1} and "at least one path" in text


def test_passes_are_recorded_and_skipped_under_xdist(repo):
    pytest.importorskip("xdist")
    assert run(repo, "-n", "2")[0] == {"passed": 3}
    assert list(store(repo)) == ["tests/test_x.py::test_marked"]
    assert run(repo, "-n", "2")[0] == {"passed": 2, "skipped": 1}


def test_a_class_marker_covers_its_methods_and_skips_the_class_setup(repo):
    (repo / "tests" / "test_x.py").write_text(
        "import unittest\nimport pytest\n\n\n@pytest.mark.inputs('src/a.txt')\nclass T(unittest.TestCase):\n"
        "    @classmethod\n    def setUpClass(cls):\n        print('SETUP RAN')\n\n    def test_one(self):\n        pass\n\n    def test_two(self):\n        pass\n")
    counts, text = run(repo, "-s")
    assert counts == {"passed": 3} and "SETUP RAN" in text
    counts, text = run(repo, "-s")
    assert counts == {"passed": 1, "skipped": 2} and "SETUP RAN" not in text


# ---- the tree key -----------------------------------------------------------------------------------------------------------------

def test_the_tree_key_follows_content_and_not_commits(repo):
    k0 = testkit.tree_key(repo)
    assert re.fullmatch(r"[0-9a-f]{64}", k0) and testkit.tree_key(repo) == k0
    (repo / "other.txt").write_text("changed")
    k1 = testkit.tree_key(repo)
    assert k1 != k0
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "edit")
    assert testkit.tree_key(repo) == k1  # committing what was in the working tree changes nothing
    (repo / "stray.txt").write_text("x")
    assert testkit.tree_key(repo) != k1  # an untracked file that git would track counts
    (repo / "stray.txt").unlink()
    (repo / "other.txt").unlink()
    assert testkit.tree_key(repo) not in (k0, k1)  # a deleted tracked file counts


def test_the_tree_key_ignores_memos_the_state_file_and_gitignored_files(repo):
    k0 = testkit.tree_key(repo)
    (repo / "docs" / "memos" / "memo1.md").write_text("edited\n")
    (repo / "docs" / "memos" / "memo2.md").write_text("new\n")
    (repo / "docs" / "STATE.md").write_text("state\n")
    (repo / "ignored.bin").write_text("x")
    assert testkit.tree_key(repo) == k0
    (repo / "docs" / "other.md").write_text("any other file under docs counts\n")
    assert testkit.tree_key(repo) != k0


# ---- the last-full-run record -----------------------------------------------------------------------------------------------------

def test_a_full_run_writes_the_record_with_the_tree_key_and_the_counts(repo):
    assert testkit.last_full(repo) is None
    run(repo)
    rec = testkit.last_full(repo)
    assert rec["schema"] == "fy-last-full/1" and rec["tree_key"] == testkit.tree_key(repo)
    assert rec["tests"] == {"passed": 3, "cached": 0, "failed": 0, "skipped": 0}
    run(repo)
    assert testkit.last_full(repo)["tests"] == {"passed": 2, "cached": 1, "failed": 0, "skipped": 0}


def test_the_record_is_not_offered_once_the_tree_has_changed_and_memos_do_not_change_it(repo):
    run(repo)
    (repo / "docs" / "memos" / "memo2.md").write_text("the memo written after the run\n")
    assert testkit.last_full(repo) is not None
    (repo / "other.txt").write_text("changed")
    assert testkit.last_full(repo) is None
    (repo / "other.txt").write_text("o")
    assert testkit.last_full(repo) is not None  # back to the content the run saw


@pytest.mark.parametrize("args", [("-k", "plain"), ("tests",), ("tests/test_x.py",), ("-m", "inputs"), ("-x",), ("--collect-only",)], ids=" ".join)
def test_a_partial_run_writes_no_record(repo, args):
    if args == ("-x",):
        (repo / "src" / "a.txt").write_text("bad")  # the run stops at the first failure
    run(repo, *args)
    assert not (repo / ".fy-cache" / "last_full.json").exists()


def test_a_full_run_with_failures_is_recorded_with_them(repo):
    (repo / "src" / "a.txt").write_text("bad")
    run(repo)
    assert testkit.last_full(repo)["tests"] == {"passed": 2, "cached": 0, "failed": 1, "skipped": 0}


def test_a_run_during_which_the_tree_changed_writes_no_record_and_says_so(repo):
    (repo / "checks" / "test_c.py").write_text("import pathlib\n\n\ndef test_check():\n    pathlib.Path(__file__).resolve().parents[1].joinpath('left_behind.txt').write_text('x')\n")
    _, text = run(repo)
    assert not (repo / ".fy-cache" / "last_full.json").exists()
    assert "tree changed during the run" in text


def test_the_record_and_the_store_are_deterministic_text(repo):
    run(repo)
    for name in ("inputs.json", "last_full.json"):
        raw = (repo / ".fy-cache" / name).read_bytes()
        assert b"\r" not in raw and raw.endswith(b"\n")
        assert json.dumps(json.loads(raw), indent=1, sort_keys=True).encode() + b"\n" == raw
