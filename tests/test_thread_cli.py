"""
Thread T6: the `fy thread` commands on the fixture, including every refusal of `stamp`, and the pre-commit hook in a throwaway repository.

    python -m pytest tests/test_thread_cli.py
"""
import json
from pathlib import Path

import pytest
from thread_help import FIXTURES, REPO, edit_record, make_root

from thread import build, cli, fixture, query


def run(args, root):
    lines = []
    code = cli.main([*args, "--root", str(root)], say=lines.append)
    return code, "\n".join(lines)


@pytest.fixture
def fx(tmp_path):
    out = tmp_path / "root"
    fixture.generate(out, 0)
    return out


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


# ---- validate

def test_validate_a_clean_thread_prints_the_summary_and_exits_0(fx):
    code, out = run(["validate"], fx)
    assert code == 0 and "errors 0" in out and "work items" in out
    assert "address-unresolved" in out  # the fixture's unknown item warns


def test_validate_exits_1_on_errors_and_names_them(tmp_path):
    root = make_root(tmp_path / "r", FIXTURES / "invalid" / "ref-kind")
    code, out = run(["validate"], root)
    assert code == 1 and "ref-kind" in out and "part.bad.kind" in out


def test_validate_json(fx):
    code, out = run(["validate", "--json"], fx)
    doc = json.loads(out)
    assert code == 0 and doc["errors"] == [] and any(w["code"] == "address-unresolved" for w in doc["warnings"])


# ---- build

def test_build_writes_the_outputs_and_a_second_build_changes_nothing(fx):
    code, out = run(["build"], fx)
    assert code == 0 and (fx / "thread" / "STATUS.md").is_file() and (fx / "thread" / "graph.json").is_file()
    assert "wrote" in out and "changed" in out
    before = tree(fx)
    code, out = run(["build"], fx)
    assert code == 0 and tree(fx) == before and "0 changed" in out


def test_build_on_errors_writes_nothing_and_exits_1(tmp_path):
    root = make_root(tmp_path / "r", FIXTURES / "invalid" / "ref-unresolved")
    before = tree(root)
    code, out = run(["build"], root)
    assert code == 1 and "ref-unresolved" in out and tree(root) == before


def test_build_removes_the_outputs_of_nothing_it_does_not_own(fx):
    run(["build"], fx)
    (fx / "thread" / "derived" / "stray.json").write_text("{}", encoding="utf-8")
    (fx / "thread" / "records" / "notes.txt").write_text("keep", encoding="utf-8")
    run(["build"], fx)
    assert not (fx / "thread" / "derived" / "stray.json").exists() and (fx / "thread" / "records" / "notes.txt").exists()


def test_build_in_a_root_without_a_thread_directory_is_a_quiet_success(tmp_path):
    (tmp_path / "x").mkdir()
    code, out = run(["build"], tmp_path / "x")
    assert code == 0 and "no thread/" in out and not (tmp_path / "x" / "thread").exists()


# ---- show and the query rules

def test_show_prints_one_record_with_its_derived_view(fx):
    code, out = run(["show", "seg.thigh"], fx)
    assert code == 0 and "seg.thigh" in out and "thigh_right_mass" in out and "houses" in out and "Mass: target" in out
    assert "GENERATED" not in out and "## References" not in out and "mermaid" not in out


def test_query_rules_exact_prefix_substring_ambiguous_none(fx):
    b = build.build_root(fx)
    assert query.resolve(b, "seg.thigh") == ("ok", "seg.thigh")
    assert query.resolve(b, "thigh") == ("ok", "seg.thigh")  # the id with one kind prefix added, when exactly one record has it
    assert query.resolve(b, "hip") == ("ok", "jnt.hip")
    assert query.resolve(b, "hip-fea") == ("ok", "work.hip-fea")  # a unique substring
    assert query.resolve(b, "WALK-1P4") == ("ok", "lc.walk-1p4")  # case-insensitively
    st, ids = query.resolve(b, "m2")
    assert st == "ambiguous" and "part.hip.m2" in ids and "if.hip-m2-thigh" in ids and ids == sorted(ids)
    st, close = query.resolve(b, "seg.thihg")
    assert st == "none" and "seg.thigh" in close


def test_show_reports_ambiguous_and_unknown_queries(fx):
    code, out = run(["show", "m2"], fx)
    assert code == 2 and "ambiguous" in out and "part.hip.m2" in out
    code, out = run(["show", "zzzz"], fx)
    assert code == 2 and "no record" in out


# ---- why

def test_why_shows_stamped_against_current_for_each_moved_address(fx):
    code, out = run(["why", "work.hip-fea"], fx)
    assert code == 0 and "stale" in out and "part.hip.m2#/mass" in out and "stamped" in out and "current" in out and "an earlier estimate" in out
    code, out = run(["why", "work.ankle-print"], fx)
    assert "drifted" in out and "pinned" in out and "99.0" in out
    code, out = run(["why", "work.battery-bench"], fx)
    assert "unknown" in out and "snapshot#/retired_key" in out and "does not resolve" in out
    code, out = run(["why", "work.pelvis-cad"], fx)
    assert "unstamped" in out
    code, out = run(["why", "work.thigh-cad"], fx)
    assert "current" in out and "20261001-1000" in out
    code, out = run(["why", "seg.thigh"], fx)
    assert code == 2 and "not a work item" in out


def test_why_json(fx):
    code, out = run(["why", "--json", "work.hip-fea"], fx)
    assert json.loads(out)["status"] == "stale"


# ---- stamp

def test_stamp_writes_a_stamp_prints_what_it_consumed_and_makes_the_item_current(fx):
    code, out = run(["stamp", "work.hip-fea", "--note", "rechecked", "--by", "joe", "--pin"], fx)
    assert code == 0 and "part.hip.m2#/mass" in out and "snapshot#/hip_flexion" in out
    stamps = sorted((fx / "thread" / "stamps" / "work.hip-fea").glob("*.json"))
    assert len(stamps) == 2
    doc = json.loads(stamps[-1].read_text(encoding="utf-8"))
    assert doc["note"] == "rechecked" and doc["by"] == "joe" and doc["pinned"] is True
    assert build.build_root(fx).work["work.hip-fea"]["status"] == "current"


def test_stamp_refuses_an_unknown_work_item_and_a_non_work_record(fx):
    before = tree(fx)
    for target in ("work.nope", "seg.thigh", "zzzz"):
        code, out = run(["stamp", target, "--by", "t"], fx)
        assert code == 1 and "refus" in out.lower(), (target, out)
    assert tree(fx) == before


def test_stamp_refuses_when_an_address_does_not_resolve(fx):
    before = tree(fx)
    code, out = run(["stamp", "work.battery-bench", "--by", "t"], fx)
    assert code == 1 and "snapshot#/retired_key" in out and "refus" in out.lower()
    assert tree(fx) == before


def test_stamp_refuses_when_the_thread_has_errors(fx):
    edit_record(fx, "part.hip.m1", housed_in="seg.nowhere")
    before = tree(fx)
    code, out = run(["stamp", "work.hip-fea", "--by", "t"], fx)
    assert code == 1 and "ref-unresolved" in out
    assert tree(fx) == before


def test_stamp_refuses_to_overwrite_a_stamp_made_in_the_same_minute(fx, monkeypatch):
    import datetime as dt

    class Fixed(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 1, 9, 30)

    monkeypatch.setattr(build, "datetime", Fixed)
    assert run(["stamp", "work.hip-fea", "--by", "t"], fx)[0] == 0
    code, out = run(["stamp", "work.hip-fea", "--by", "t"], fx)
    assert code == 1 and "already exists" in out
    assert (fx / "thread" / "stamps" / "work.hip-fea" / "20261101-0930.json").is_file()


def test_stamp_by_defaults_to_a_name_and_the_stamp_validates(fx):
    assert run(["stamp", "work.thigh-cad"], fx)[0] == 0
    assert build.build_root(fx).errors == []


# ---- refs

def test_refs_lists_prose_mentions_uncapped_newest_file_first(fx):
    import os
    for d, name, body in (("docs/memos", "memo1.md", "a seg.thigh here\nand seg.thigh2 not\n"), ("notebook", "n.md", "seg.thigh\n"), ("log", "e.log", "x seg.thigh\n")):
        (fx / d).mkdir(parents=True, exist_ok=True)
        (fx / d / name).write_text(body, encoding="utf-8")
    for n, f in enumerate(("docs/memos/memo1.md", "notebook/n.md", "log/e.log")):
        os.utime(fx / f, (1_700_000_000 + n * 100, 1_700_000_000 + n * 100))  # the log is newest
    for i in range(30):
        (fx / "notebook" / f"b{i:02d}.md").write_text("seg.thigh\n", encoding="utf-8")
        os.utime(fx / "notebook" / f"b{i:02d}.md", (1_600_000_000 + i, 1_600_000_000 + i))
    code, out = run(["refs", "seg.thigh"], fx)
    lines = [ln.strip() for ln in out.splitlines()[1:]]
    assert code == 0 and "33 mention(s)" in out.splitlines()[0]  # not capped
    assert [ln.split(" ")[0] for ln in lines[:3]] == ["log/e.log:1", "notebook/n.md:1", "docs/memos/memo1.md:1"]
    assert lines[3].startswith("notebook/b29.md") and "thigh2" not in out
    code, out = run(["refs", "--json", "thigh"], fx)
    assert code == 0 and len(json.loads(out)["references"]) == 33


def test_refs_does_not_write_and_reports_unknown_queries(fx):
    before = tree(fx)
    assert run(["refs", "seg.thigh"], fx)[0] == 0 and tree(fx) == before
    code, out = run(["refs", "zzzz"], fx)
    assert code == 2 and "no record" in out
