"""
Thread T7: the real store. One segment record per pre_processor segment and one joint record per anatomical joint, active; four proposed
load cases; no part, interface, harness or work records. The generated outputs on disk are what a fresh build gives (the pre-commit hook
keeps them so). The fixture generator reads the real structural records and says so when they are invalid.

    python -m pytest tests/test_thread_real.py
"""
import shutil
import time

import pytest
import yaml
from thread_help import REPO

from thread import build, fixture

JOINTS = {"ankle", "cervicothoracic", "elbow", "hip", "knee", "lumbosacral", "shoulder", "thoracolumbar", "toe", "wrist"}
PROPOSED = set()  # jnt.toe was created proposed by Code (CLAUDE.md rule 2) and activated by Joe (memo 25, Q5)
LOAD_CASES = {"lc.stand-static": {"scenario": "stand_static"},
              "lc.walk-0p5": {"gait_spec": "walk_treadmill", "condition": "0.5 m/s level treadmill walking"},
              "lc.walk-1p4": {"gait_spec": "walk_treadmill", "condition": "1.4 m/s level treadmill walking"},
              "lc.walk-1p6": {"gait_spec": "walk_treadmill", "condition": "1.6 m/s level treadmill walking"},
              "lc.gravity-hold-rom": {"scenario": "rom_sweep"}}


@pytest.fixture(scope="module")
def real():
    return build.build_root(REPO)


def test_the_real_store_has_no_errors_and_no_warnings(real):
    assert real.errors == [], [(i.code, i.message) for i in real.errors]
    assert real.warnings == [], [(i.code, i.message) for i in real.warnings]


def test_one_segment_per_pre_processor_segment_and_one_joint_per_anatomical_joint(real):
    pp = build.pre_processor()
    assert sorted(i for i, r in real.recs.items() if r["kind"] == "segment") == sorted(f"seg.{s}" for s in pp.EXPECTED_SEGMENTS)
    assert sorted(i for i, r in real.recs.items() if r["kind"] == "joint") == sorted(f"jnt.{j}" for j in JOINTS)
    for i, r in real.recs.items():
        if r["kind"] in ("segment", "joint"):
            assert r["status"] == ("proposed" if i in PROPOSED else "active") and r["purpose"].endswith(".") and r["purpose"].count(". ") == 0, i


def test_every_body_and_hinge_is_bound_exactly_once(real):
    model = real.store.model
    assert len(model.bodies) == 18 and len(model.hinges) == 33
    assert sorted(real.body_owner) == sorted(model.bodies) and sorted(real.hinge_owner) == sorted(model.hinges)


def test_the_joint_names_follow_the_answers_to_memo18(real):
    assert real.recs["jnt.thoracolumbar"]["hinges"] == ["tj_fe", "tj_lat", "tj_ax"]
    assert real.recs["jnt.cervicothoracic"]["hinges"] == ["cj_fe", "cj_lat", "cj_ax"]
    assert real.recs["seg.head_neck"]["body"] == "head_and_neck"
    missing = sorted(k for r in real.recs.values() if r["kind"] == "joint" for k in r["rom_keys"] if k not in real.store.snapshot)
    assert missing == []  # the seven values rm.v1-rom-gaps-filled covered, and the toe's two, are in the sheet


def test_the_load_cases_are_proposed_and_do_not_require_an_independent_source(real):
    got = {i: r for i, r in real.recs.items() if r["kind"] == "load_case"}
    assert {i: r["source"] for i, r in got.items()} == LOAD_CASES
    for i, r in got.items():
        assert r["status"] == "proposed" and r["independent_source_required"] is False and r["notes"].strip(), i
    for r in got.values():
        name = r["source"].get("scenario") or r["source"]["gait_spec"]
        assert (REPO / "sim" / "scenarios" / f"{name}.yaml").is_file() or (REPO / "sim" / "scenarios" / "gait" / f"{name}.yaml").is_file(), name


def test_the_acceptance_speed_case_says_what_it_is_and_states_no_verdict_and_no_number(real):
    """Stage 2f D1: lc.walk-0p5 is v1's acceptance speed, not a sizing speed; trust at this speed is carried by the envelope rows' band flags, so the
    record restates neither the band verdict nor any number."""
    r = real.recs["lc.walk-0p5"]
    assert r["status"] == "proposed" and r["independent_source_required"] is False
    assert "acceptance speed" in r["purpose"] and "not a sizing speed" in r["purpose"] and r["purpose"].count(". ") == 0
    notes = r["notes"].lower()
    assert "band flag" in notes and "acceptance speed" in notes and "not a sizing speed" in notes
    assert "no contact solver" in notes and "inverse dynamics" in notes  # the reasons the other walking cases give
    assert not any(ch.isdigit() for ch in r["notes"])  # no number
    for word in ("meets", "misses", "fails", "passes", "outside", "within", "correlation"):
        assert word not in notes, word  # no verdict


def test_no_hardware_records_exist_yet(real):
    assert {r["kind"] for r in real.recs.values()} == {"segment", "joint", "load_case"}
    assert real.work == {}


def test_the_generated_outputs_on_disk_are_what_a_fresh_build_gives(real):
    for rel, data in real.outputs.items():
        assert (REPO / rel).read_bytes() == data, f"{rel} is stale: run `python tools/fy thread build`"
    on_disk = {p.relative_to(REPO).as_posix() for sub in ("derived", "dossiers") for p in (REPO / "thread" / sub).iterdir()}
    assert on_disk == {r for r in real.outputs if "/derived/" in r or "/dossiers/" in r}


def test_a_warm_build_takes_under_two_seconds():
    build.build_root(REPO)
    t = time.perf_counter()
    build.build_root(REPO)
    assert time.perf_counter() - t < 2.0


def test_the_fixture_reads_the_real_structural_records_and_names_an_invalid_real_store(tmp_path, monkeypatch):
    fake = tmp_path / "repo"
    for rel in ("sim/models", "params", "thread/records"):
        shutil.copytree(REPO / rel, fake / rel, ignore=shutil.ignore_patterns("*FAILED*"))
    monkeypatch.setattr(fixture, "REPO", fake)
    fixture.generate(tmp_path / "ok", 0)
    assert (tmp_path / "ok" / "thread" / "records" / "seg.thigh.yaml").read_bytes() == (REPO / "thread" / "records" / "seg.thigh.yaml").read_bytes()
    p = fake / "thread" / "records" / "seg.thigh.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    doc["body"] = "no_such_body"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    for make in (lambda: fixture.generate(tmp_path / "bad1", 0), lambda: fixture.reallocation(tmp_path / "bad2")):
        with pytest.raises(ValueError, match="real thread store.*invalid.*binding-missing"):
            make()


def test_the_gravity_hold_load_case_describes_the_rom_sweep_as_it_is(real):
    r = real.recs["lc.gravity-hold-rom"]
    assert r["status"] == "proposed" and r["independent_source_required"] is False
    assert r["purpose"] == ("Each limited joint swept through its range against gravity, one at a time, with the other joints at the reference pose "
                            "and the pelvis held by the gantry.")
    n = r["notes"]
    assert "ground reaction" not in n and "ground-reaction" not in n  # the gantry holds the body
    assert "6 unlimited" in n and "bare joints" in n and "shoulder adduction limit is a" in n
    assert "near-worst, not a bound" in n and "proximal" in n
    model = real.store.model
    import re
    limited = len(re.findall(r'<joint[^>]*type="hinge"[^>]*\brange=', (REPO / "sim" / "models" / "freyja.xml").read_text(encoding="utf-8")))
    assert len(model.hinges) - limited == 6  # the number the notes state
