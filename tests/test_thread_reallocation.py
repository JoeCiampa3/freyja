"""
Thread T4: the reallocation acceptance test. Moving an actuator from the thigh to the pelvis is an edit to one record; every consequence
(which dossiers change, which budgets move, which work is stale) is computed, and nothing unrelated changes by a byte.

The fixture: M1 housed in the pelvis, M2 in the thigh (both acting across the hip), a harness run pelvis to thigh to shank, an M3 in the
shank, and work items that consume the thigh's and the pelvis's `houses`, M2's `housed_in`, the pelvis mass budget (pinned), the hip's
`acted_on_by` and only shank facts. The masses make the move overfill the pelvis.

    python -m pytest tests/test_thread_reallocation.py
"""
import json
import time
from pathlib import Path

import pytest
from thread_help import edit_record

from thread import build, cli, fixture, store

EDIT_HOUSED = "part.hip.m2#/housed_in=seg.pelvis"
EDIT_REACTS = "part.hip.m2#/reacts_into=seg.pelvis"

WORK = ["work.thigh-houses", "work.pelvis-houses", "work.m2-mount", "work.pelvis-mass", "work.hip-actuation", "work.shank-only"]

# The generated files that must change when M2 moves, each with its reason. Everything else must be byte-identical, the shank's among it.
EXPECTED_CHANGED = {
    # M2 itself: its housed_in and reacts_into are authored fields of its record
    "part.hip.m2": "its housed_in and reacts_into changed",
    # the thigh loses M2 from `houses`, `reacted_by` and its mass claim
    "seg.thigh": "houses, reacted_by and the mass budget lose M2",
    # the pelvis gains M2 and its budget goes over
    "seg.pelvis": "houses, reacted_by and the mass budget gain M2",
    # the four work items whose consumed values moved change status (current -> stale, the pinned one -> drifted) and show their diffs
    "work.thigh-houses": "stale: the thigh's houses lost M2",
    "work.pelvis-houses": "stale: the pelvis's houses gained M2",
    "work.m2-mount": "stale: M2's housed_in moved",
    "work.pelvis-mass": "drifted: the pelvis mass budget moved (pinned baseline)",
}
EXPECTED_FILES = sorted([f"thread/derived/{i}.json" for i in EXPECTED_CHANGED] + [f"thread/dossiers/{i}.md" for i in EXPECTED_CHANGED]
                        + ["thread/graph.json", "thread/STATUS.md"])


@pytest.fixture
def root(tmp_path):
    out = tmp_path / "root"
    info = fixture.reallocation(out)
    assert info["m1_kg"] > 0 and info["m2_kg"] > 0
    return out


def stamp_all(root):
    b = build.build_root(root)
    assert b.errors == [], [(i.code, i.message) for i in b.errors]
    for w in WORK:
        build.write_stamp(root, b, w, stamp="20261001-1000", by="test", pinned=(w == "work.pelvis-mass"))
    return build.build_root(root)


def snapshot_of(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def outputs_changed(a, b):
    return sorted(p for p in set(a) | set(b) if a.get(p) != b.get(p))


def test_the_fixture_is_clean_and_set_up_as_the_brief_says(root):
    b = build.build_root(root)
    assert b.errors == [] and b.warnings == []
    d = b.docs
    assert d["part.hip.m1"]["housed_in"] == "seg.pelvis" and d["part.hip.m1"]["acts_across"] == "jnt.hip" and d["part.hip.m1"]["reacts_into"] == "seg.pelvis"
    assert d["part.hip.m2"]["housed_in"] == "seg.thigh" and d["part.hip.m2"]["acts_across"] == "jnt.hip" and d["part.hip.m2"]["reacts_into"] == "seg.thigh"
    assert d["hn.leg-power"]["path"] == ["seg.pelvis", "seg.thigh", "seg.shank"]
    assert d["seg.pelvis"]["budgets"]["mass"]["over"] is False
    assert {w: b.work[w]["status"] for w in WORK} == {w: "unstamped" for w in WORK}


def test_moving_m2_changes_exactly_the_expected_files_and_statuses(root):
    first = stamp_all(root)
    assert {w: first.work[w]["status"] for w in WORK} == {w: "current" for w in WORK}
    before = first.outputs
    assert first.work["work.pelvis-mass"]["pinned"] is True
    m2 = first.docs["part.hip.m2"]["mass"]["kg"]
    thigh0 = first.docs["seg.thigh"]["budgets"]["mass"]["claimed_kg"]
    pelvis0 = first.docs["seg.pelvis"]["budgets"]["mass"]["claimed_kg"]

    edit_record(root, "part.hip.m2", housed_in="seg.pelvis", reacts_into="seg.pelvis")
    after = build.build_root(root)
    assert after.errors == []

    # the set of generated files that changed is exactly the expected set; the shank's are byte-identical
    assert outputs_changed(before, after.outputs) == EXPECTED_FILES
    for p in ("thread/derived/seg.shank.json", "thread/dossiers/seg.shank.md", "thread/derived/part.leg.m3.json", "thread/derived/hn.leg-power.json",
              "thread/derived/jnt.hip.json", "thread/dossiers/jnt.hip.md", "thread/derived/work.shank-only.json", "thread/derived/work.hip-actuation.json",
              "thread/derived/if.m2-thigh.json"):
        assert after.outputs[p] == before[p], p

    # work items consuming the moved facts are stale with their diffs; the pinned one is drifted; the shank-only and the hip item stay current
    w = after.work
    assert [w[x]["status"] for x in WORK] == ["stale", "stale", "stale", "drifted", "current", "current"]
    assert w["work.pelvis-mass"]["pinned"] is True
    moved = {m["address"]: m for m in w["work.m2-mount"]["moved"]}
    assert moved["part.hip.m2#/housed_in"]["stamped"] == "seg.thigh" and moved["part.hip.m2#/housed_in"]["current"] == "seg.pelvis"
    th = w["work.thigh-houses"]["moved"][0]
    assert th["address"] == "thread/derived/seg.thigh.json#/houses" and th["stamped"] == ["part.hip.m2"] and th["current"] == []
    pv = w["work.pelvis-houses"]["moved"][0]
    assert pv["stamped"] == ["part.hip.m1"] and pv["current"] == ["part.hip.m1", "part.hip.m2"]
    pm = w["work.pelvis-mass"]["moved"][0]
    assert pm["address"] == "thread/derived/seg.pelvis.json#/budgets/mass" and pm["stamped"]["over"] is False and pm["current"]["over"] is True
    assert w["work.shank-only"]["moved"] == [] and w["work.hip-actuation"]["moved"] == []

    # the budgets: the thigh's claim falls by M2's mass, the pelvis's rises by it, and budget-over fires for the pelvis
    thigh1 = after.docs["seg.thigh"]["budgets"]["mass"]["claimed_kg"]
    pelvis1 = after.docs["seg.pelvis"]["budgets"]["mass"]["claimed_kg"]
    assert thigh0 - thigh1 == pytest.approx(m2, abs=1e-6)
    assert pelvis1 - pelvis0 == pytest.approx(2 * m2, abs=1e-6)  # M2 is a bilateral part in a unilateral segment: it claims on each side
    assert after.docs["seg.pelvis"]["budgets"]["mass"]["over"] is True and first.docs["seg.pelvis"]["budgets"]["mass"]["over"] is False
    assert [(i.code, i.ids) for i in after.warnings] == [("budget-over", ("seg.pelvis",))]
    assert "budget-over" not in [i.code for i in first.warnings]
    # the arithmetic is shown for the bilateral claim
    claims = {c["part"]: c["arithmetic"] for c in after.docs["seg.pelvis"]["budgets"]["mass"]["claims"]}
    assert claims["part.hip.m2"] == f"2 x {m2} kg, part.hip.m2 left and right"
    assert f"2 x {m2} kg, part.hip.m2 left and right" in after.outputs["thread/STATUS.md"].decode()
    # the dossiers say so
    assert "**OVER**" in after.outputs["thread/dossiers/seg.pelvis.md"].decode()
    assert "drifted" in after.outputs["thread/STATUS.md"].decode()


def test_the_what_if_reports_the_same_as_the_real_edit_and_leaves_the_root_byte_identical(root, capsys):
    first = stamp_all(root)
    before_tree = snapshot_of(root)
    lines = []
    t = time.perf_counter()
    rc = cli.main(["impact", "--root", str(root), "--edit", EDIT_HOUSED, "--edit", EDIT_REACTS], say=lines.append)
    elapsed = time.perf_counter() - t
    assert rc == 0
    assert snapshot_of(root) == before_tree  # nothing written
    assert elapsed < 3.0  # performance: an impact what-if on this fixture takes under 3 s
    text = "\n".join(lines)

    res = store_whatif(root)
    edit_record(root, "part.hip.m2", housed_in="seg.pelvis", reacts_into="seg.pelvis")
    after = build.build_root(root)
    real_changed = outputs_changed(first.outputs, after.outputs)
    real_status = {w: {"from": first.work[w]["status"], "to": after.work[w]["status"]} for w in after.work if first.work[w]["status"] != after.work[w]["status"]}
    assert res["outputs_changed"] == real_changed == EXPECTED_FILES
    assert res["status_changes"] == real_status
    assert res["errors"] == []
    for p in real_changed:
        assert p in text
    for w, v in real_status.items():
        assert f"{w}: {v['from']} -> {v['to']}" in text
    assert "new warning budget-over" in text


def store_whatif(root):
    from thread import impact
    return impact.whatif(store.load(root), [EDIT_HOUSED, EDIT_REACTS])


def test_the_what_if_with_only_one_of_the_two_edits_is_still_a_valid_report(root):
    from thread import impact
    stamp_all(root)
    one = impact.whatif(store.load(root), [EDIT_HOUSED])
    assert one["errors"] == []
    assert "thread/derived/seg.pelvis.json" in one["outputs_changed"] and "thread/derived/seg.shank.json" not in one["outputs_changed"]


def test_reverting_the_edit_restores_every_status_and_every_byte(root):
    first = stamp_all(root)
    edit_record(root, "part.hip.m2", housed_in="seg.pelvis", reacts_into="seg.pelvis")
    assert [build.build_root(root).work[x]["status"] for x in WORK] != ["current"] * 6
    edit_record(root, "part.hip.m2", housed_in="seg.thigh", reacts_into="seg.thigh")
    again = build.build_root(root)
    assert [again.work[x]["status"] for x in WORK] == ["current"] * 6
    assert again.outputs == first.outputs  # byte-identical to the first build


def test_two_builds_from_the_same_inputs_are_byte_identical(root):
    stamp_all(root)
    assert build.build_root(root).outputs == build.build_root(root).outputs


def test_written_outputs_equal_the_in_memory_build_and_a_second_write_changes_nothing(root):
    b = stamp_all(root)
    written = build.write_outputs(root, b)
    assert sorted(written) == sorted(b.outputs)
    for rel, data in b.outputs.items():
        assert (root / rel).read_bytes() == data
    assert build.write_outputs(root, build.build_root(root)) == []
    # an address into a generated output resolves against the in-memory build, not the file on disk
    f = root / "thread" / "derived" / "seg.thigh.json"
    f.write_text(json.dumps({"houses": ["tampered"]}), encoding="utf-8")
    assert build.build_root(root).resolve("thread/derived/seg.thigh.json#/houses") == (True, ["part.hip.m2"])


def test_impact_of_an_address_lists_the_work_that_consumes_it(root):
    lines = []
    assert cli.main(["impact", "part.hip.m2#/housed_in", "--root", str(root)], say=lines.append) == 0
    text = "\n".join(lines)
    assert "work.m2-mount" in text and "thread/derived/seg.thigh.json" in text
    assert cli.main(["impact", "--root", str(root)], say=lines.append) == 2


def test_impact_cli_json_and_error_output(root):
    lines = []
    assert cli.main(["impact", "--json", "--root", str(root), "--edit", "part.hip.m2#/housed_in=seg.nowhere"], say=lines.append) == 0
    doc = json.loads("\n".join(lines))
    assert [e["code"] for e in doc["whatif"]["errors"]] == ["ref-unresolved"]
    lines.clear()
    assert cli.main(["impact", "--root", str(root), "--edit", "part.hip.m2#/housed_in=seg.nowhere"], say=lines.append) == 1
    assert cli.main(["impact", "--root", str(root), "--edit", "no equals sign"], say=lines.append) == 2
