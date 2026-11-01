"""
Thread sources T4: the `sources` fixture and the gates that run on it. G1, every case derives the sourcing the brief's table gives; G2, every stamp is
written or refused as the table says, through `fy thread stamp`; G3, evidence lost after a stamp; G4, addresses into a derived file; G5, the what-if;
G8, determinism. The intended outcomes are the generator's, typed from the brief, and compared here with what the library derives.

    python -m pytest tests/test_thread_sources.py
"""
import json
import re
import shutil

import pytest
from thread_help import REPO  # noqa: F401  (sets sys.path for the library)

from thread import build, cli, fixture

SOURCING = {"lc.src-none": "unsourced", "lc.src-adr": "sourced", "lc.src-adr-proposed": "unsourced", "lc.src-adr-superseded": "unsourced", "lc.src-row": "sourced",
            "lc.src-row-qualified": "sourced", "lc.src-row-unverified": "unsourced", "lc.src-test": "unsourced", "lc.src-mixed": "sourced", "lc.src-post": "sourced",
            "lc.src-plain": "not_required", "lc.src-plain-cited": "not_required", "lc.fall-sample": "sourced"}


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    out = tmp_path_factory.mktemp("sources") / "root"
    fixture.sources(out)
    return out


@pytest.fixture
def root(made, tmp_path):
    return shutil.copytree(made, tmp_path / "r")


def intent(root):
    return json.loads((root / "fixture-intent.json").read_text(encoding="utf-8"))


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def run(root, *args):
    lines = []
    code = cli.main([*args, "--root", str(root)], say=lines.append)
    return code, "\n".join(lines)


def unsourced(b):
    return {i.ids[0]: i for i in b.warnings if i.code == "unsourced-consumption"}


def supersede(root, name="0904-post.md"):
    p = root / "decisions" / name
    p.write_text(p.read_text(encoding="utf-8").replace("status: accepted", 'status: "superseded-by: adr-0901"'), encoding="utf-8")


def test_the_fixture_builds_with_no_errors(made):
    assert build.build_root(made).errors == []


def test_the_intent_is_the_brief_table(made):
    assert intent(made)["sourcing"] == SOURCING


def test_g1_every_case_derives_its_intended_sourcing(made):
    b = build.build_root(made)
    assert {i: s["sourcing"] for i, s in b.sourcing.items()} == intent(made)["sourcing"]
    assert {i: b.docs[i]["sourcing"] for i in SOURCING} == SOURCING


def test_the_fixture_covers_every_work_item_of_the_brief(made):
    flagged = [c for c in SOURCING if c not in ("lc.src-plain", "lc.src-plain-cited")]
    assert sorted(intent(made)["stamps"]) == sorted([f"work.a-{c.split('.', 1)[1]}" for c in flagged] + ["work.p-none", "work.a-derived-none", "work.a-two", "work.a-snapshot", "work.a-plain"])


def test_g2_every_stamp_is_written_or_refused_as_the_table_says(root):
    want = intent(root)
    for work, outcome in sorted(want["stamps"].items()):
        before = tree(root)
        code, out = run(root, "stamp", work, "--by", "t")
        if outcome == "refused":
            assert code == 1 and "refused" in out, work
            assert tree(root) == before, work  # byte-identical
            assert sorted(set(re.findall(r"\blc\.[a-z0-9-]+", out))) == want["refusal_names"][work], out
        else:
            assert code == 0, (work, out)
            assert len(list((root / "thread" / "stamps" / work).glob("*.json"))) == 1, work


def test_g2_the_proposed_item_is_written_and_the_warning_printed(root):
    code, out = run(root, "stamp", "work.p-none", "--by", "t")
    assert code == 0 and "warning unsourced-consumption" in out and "lc.src-none" in out


def test_g2_each_refusal_is_of_active_work_and_every_consumer_of_an_unsourced_case_warns(made):
    b = build.build_root(made)
    want = {w for w, o in intent(made)["stamps"].items() if o == "refused"} | {"work.p-none"}
    assert set(unsourced(b)) == want and {i.code for i in b.warnings} == {"unsourced-consumption"}


def test_g3_superseding_the_sole_source_after_a_stamp_warns_and_leaves_the_status_current(root):
    assert run(root, "stamp", "work.a-src-post", "--by", "t")[0] == 0
    assert "work.a-src-post" not in unsourced(build.build_root(root))
    supersede(root)
    b = build.build_root(root)
    w = unsourced(b)["work.a-src-post"]
    assert "lc.src-post" in w.message and "active" in w.message and "baseline stamp" in w.message
    assert b.work["work.a-src-post"]["status"] == "current" and b.errors == []
    assert "lc.src-post" in b.outputs["thread/STATUS.md"].decode().split("## Unsourced load cases")[1].split("## Proposed")[0]


def test_g3_the_lost_source_refuses_the_next_stamp(root):
    supersede(root)
    code, out = run(root, "stamp", "work.a-src-post", "--by", "t")
    assert code == 1 and "lc.src-post" in out and "superseded-by" in out


def test_g4_a_derived_file_address_is_treated_as_consuming_the_case(root):
    b = build.build_root(root)
    assert b.unsourced_of("work.a-derived-none") == ["lc.src-none"]
    assert "work.a-derived-none" in b.docs["lc.src-none"]["consumed_by"]
    code, out = run(root, "stamp", "work.a-derived-none", "--by", "t")
    assert code == 1 and "lc.src-none" in out


def test_g5_the_what_if_reports_the_new_warning_and_writes_nothing(root):
    assert run(root, "stamp", "work.a-src-adr", "--by", "t")[0] == 0
    before = tree(root)
    code, out = run(root, "impact", "--edit", "lc.src-adr#/evidence=[]")
    assert code == 0 and "new warning unsourced-consumption" in out and "work.a-src-adr" in out and "lc.src-adr" in out
    assert "work status changes (0)" in out
    assert tree(root) == before


def test_g8_two_builds_are_byte_identical(made):
    assert build.build_root(made).outputs == build.build_root(made).outputs


def test_g8_the_generator_is_deterministic(tmp_path):
    fixture.sources(tmp_path / "a")
    fixture.sources(tmp_path / "b")
    assert tree(tmp_path / "a") == tree(tmp_path / "b")


def test_the_cli_writes_the_scenario(tmp_path):
    code, out = run(tmp_path, "fixture", "--out", str(tmp_path / "x"), "--scenario", "sources")
    assert code == 0 and (tmp_path / "x" / "fixture-intent.json").is_file()


def test_the_fall_sample_carries_its_energy_and_its_segment(made):
    b = build.build_root(made)
    assert b.resolve("lc.fall-sample#/source/energy_j") == (True, 540) and b.docs["seg.pelvis"]["fall_cases"] == ["lc.fall-sample"]


def test_a_row_in_a_table_that_does_not_qualify_is_not_a_duplicate(made):
    text = (made / "data" / "falls" / "sources.md").read_text(encoding="utf-8")
    assert text.count("| X1 |") == 2 and build.build_root(made).errors == []


def test_every_link_in_the_evidence_sections_resolves(made):
    b = build.build_root(made)
    links = [t for i in SOURCING for t in re.findall(r"\]\(([^)]+)\)", b.outputs[f"thread/dossiers/{i}.md"].decode().split("## Evidence")[1].split("## Budgets")[0])]
    assert links and all(((made / "thread" / "dossiers") / t).resolve().is_file() for t in links)
