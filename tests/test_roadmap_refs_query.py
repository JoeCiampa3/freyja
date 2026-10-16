"""
Roadmap T2/T4: reference search, query resolution and editor resolution.

Run from the repo root:
    python -m pytest tests/test_roadmap_refs_query.py
"""
import subprocess

import pytest
from rmhelp import leaf, make

import roadmap
from roadmap import editor, query, refs


def test_token_boundaries():
    rx = refs.token_re("rm.foo")
    for text, hit in [("see rm.foo for", True), ("rm.foo", True), ("(rm.foo)", True), ("`rm.foo`,", True), ("done rm.foo.", True),
                      ("rm.foo-bar", False), ("rm.foobar", False), ("xrm.foo", False), ("rm.foo_x", False), ("rm.foo.bar", False),
                      ("my-rm.foo", False), ("rm.foo2", False), ("[rm.foo]", True), ("rm.fo", False)]:
        assert bool(rx.search(text)) is hit, text


def test_file_references_report_file_and_line_in_the_three_directories(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.foo": leaf("rm.root"), "rm.foo-bar": leaf("rm.root")})
    for rel, text in {"log/events.log": "a\nstarted rm.foo today\n", "docs/memos/m1.md": "rm.foo-bar only\n",
                      "notebook/2026-10-16-x.md": "x rm.foo.\nrm.foo\n", "docs/other/ignored.md": "rm.foo\n", "log/binary.bin": ""}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (root / "log" / "binary.bin").write_bytes(b"\xff\xfe\x00rm.foo")
    hits = refs.file_references(root, "rm.foo")
    assert [(h.path, h.line) for h in hits] == [("log/events.log", 2), ("notebook/2026-10-16-x.md", 1), ("notebook/2026-10-16-x.md", 2)]
    assert hits[0].text == "started rm.foo today"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def test_commit_references_use_git_log_and_only_inside_a_git_root(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}})
    assert refs.commit_references(root, "rm.foo") == []  # not a git repository: no search
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "start rm.foo")
    (root / "x.txt").write_text("x")
    git(root, "add", "x.txt")
    git(root, "commit", "-q", "-m", "other work", "-m", "body mentions rm.foo-bar only")
    (root / "y.txt").write_text("y")
    git(root, "add", "y.txt")
    git(root, "commit", "-q", "-m", "third", "-m", "body says rm.foo here")
    got = refs.commit_references(root, "rm.foo")
    assert [s for _, s in got] == ["third", "start rm.foo"]
    assert all(len(h) >= 7 for h, _ in got)


def test_references_for_a_node_combine_both(tmp_path):
    root = make(tmp_path / "r", {"rm.root": {"title": "Top"}, "rm.foo": leaf("rm.root")})
    (root / "log").mkdir()
    (root / "log" / "e.log").write_text("rm.foo\n")
    r = refs.references(root, "rm.foo")
    assert len(r["files"]) == 1 and r["commits"] == []


NODES = {"rm.root": {"title": "Top"}, "rm.elbow-actuator": {**leaf("rm.root"), "title": "Elbow actuator selected"},
         "rm.wrist-actuator": {**leaf("rm.root"), "title": "Wrist actuator selected"}, "rm.wrist": {**leaf("rm.root"), "title": "Wrist tested"}}


def resolve(tmp_path, q):
    rm = roadmap.compute(make(tmp_path / "r", NODES))
    return query.resolve(rm, q)


def test_query_exact_id_then_rm_prefix_then_unique_substring(tmp_path):
    assert resolve(tmp_path, "rm.wrist") == ("ok", "rm.wrist")  # exact beats the longer substring matches
    assert resolve(tmp_path, "elbow-actuator") == ("ok", "rm.elbow-actuator")  # with the rm. prefix added
    assert resolve(tmp_path, "ELBOW") == ("ok", "rm.elbow-actuator")  # unique case-insensitive substring of id
    assert resolve(tmp_path, "tested") == ("ok", "rm.wrist")  # ... or of the title
    assert resolve(tmp_path, "actuator")[0] == "ambiguous"
    assert resolve(tmp_path, "actuator")[1] == ["rm.elbow-actuator", "rm.wrist-actuator"]
    assert resolve(tmp_path, "zzz")[0] == "none"


def test_query_candidates_are_capped_at_ten_and_sorted(tmp_path):
    nodes = {"rm.root": {"title": "Top"}, **{f"rm.item-{i:02d}": leaf("rm.root") for i in range(15)}}
    rm = roadmap.compute(make(tmp_path / "r", nodes))
    status, cands = query.resolve(rm, "item")
    assert status == "ambiguous" and cands == [f"rm.item-{i:02d}" for i in range(10)]


def test_editor_resolution_order():
    path = "/x/rm.a.md"
    on_path = {"code"}
    which = lambda name: f"/bin/{name}" if name in on_path else None  # noqa: E731
    # 1. FREYJA_EDITOR with {path}
    assert editor.resolve({"FREYJA_EDITOR": "myed --goto {path}", "VISUAL": "v", "EDITOR": "e"}, path, which) == ["myed", "--goto", path]
    # 2. VISUAL then EDITOR
    assert editor.resolve({"VISUAL": "vim", "EDITOR": "nano"}, path, which) == ["vim", path]
    assert editor.resolve({"EDITOR": "nano -w"}, path, which) == ["nano", "-w", path]
    # 3. code -g
    assert editor.resolve({}, path, which) == ["code", "-g", path]
    # 4. startfile
    assert editor.resolve({}, path, lambda n: None) == ["startfile", path]
    # a FREYJA_EDITOR without {path} is not used as given: it is ignored in favour of the next
    assert editor.resolve({"FREYJA_EDITOR": "myed", "EDITOR": "nano"}, path, which) == ["nano", path]


def test_open_in_editor_runs_the_resolved_command(tmp_path):
    calls = []
    editor.open_file(tmp_path / "f.md", env={"EDITOR": "ed"}, which=lambda n: None, popen=lambda argv: calls.append(argv), startfile=lambda p: calls.append(("sf", p)))
    assert calls == [["ed", str(tmp_path / "f.md")]]
    editor.open_file(tmp_path / "f.md", env={}, which=lambda n: None, popen=lambda argv: calls.append(argv), startfile=lambda p: calls.append(("sf", p)))
    assert calls[-1] == ("sf", str(tmp_path / "f.md"))
