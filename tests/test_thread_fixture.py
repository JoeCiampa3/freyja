"""
Thread T3: the fixture generator. It writes a repo-shaped root from the tracked model and snapshot, with structural records covering every
body and hinge and synthetic records of every other kind. Deterministic for a seed. The intent file records the status each work item was
meant to have; the library's derived status must equal it.

    python -m pytest tests/test_thread_fixture.py
"""
import json
from pathlib import Path

import pytest
import yaml
from thread_help import REPO

from thread import build, cli, fixture


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    out = tmp_path_factory.mktemp("fx") / "root"
    fixture.generate(out, 0)
    return out


@pytest.fixture(scope="module")
def built(fx):
    return build.build_root(fx)


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def records(root):
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (Path(root) / "thread" / "records").glob("*.yaml")}


def test_the_fixture_builds_without_errors(built):
    assert built.errors == [], [(i.code, i.ids, i.message) for i in built.errors]
    assert built.outputs


def test_model_and_snapshot_are_copies_of_the_tracked_files(fx):
    for rel in ("sim/models/freyja.xml", "params/snapshot.csv"):
        assert (fx / rel).read_bytes() == (REPO / rel).read_bytes()


def test_every_body_and_hinge_is_bound_so_nothing_warns_unbound(built):
    assert not [i for i in built.warnings if i.code in ("unbound-body", "unbound-hinge")]
    kinds = {r["kind"] for r in built.recs.values()}
    assert kinds == {"segment", "joint", "part", "interface", "load_case", "harness_run", "work_item"}
    assert sum(r["kind"] == "segment" for r in built.recs.values()) == 10 and sum(r["kind"] == "joint" for r in built.recs.values()) == 10


def test_derived_work_status_equals_the_intent_for_every_item(fx, built):
    intent = json.loads((fx / "fixture-intent.json").read_text(encoding="utf-8"))
    assert intent["seed"] == 0
    assert {w: built.work[w]["status"] for w in built.work} == intent["work"]
    assert set(intent["work"].values()) == {"unstamped", "current", "stale", "drifted", "unknown"}  # every status but reverified


def test_the_required_features_are_present(fx, built):
    recs = built.recs
    assert any("sides" in r for r in recs.values() if r["kind"] == "part")  # a bilateral part
    assert any(doc["pinned"] for lst in built.store.stamps.values() for _, doc in lst)  # a pinned stamp
    adr = [d for d in built.store.decisions if any(x in recs and recs[x]["kind"] == "part" for x in d["links"])]
    assert adr  # a decision whose links name a part
    assert any(r["kind"] == "harness_run" and len(r["path"]) == 3 for r in recs.values())  # a run crossing three segments
    housed = {r["housed_in"] for r in recs.values() if r["kind"] == "part"}
    assert len(housed) >= 4  # parts in at least four segments
    assert any(r["status"] == "superseded" for r in recs.values())


def test_an_older_stamp_is_not_the_baseline(fx, built):
    assert len(built.store.stamps["work.thigh-cad"]) == 2 and built.work["work.thigh-cad"]["stamp"] == "20261001-1000"


def test_the_only_unresolved_address_is_the_unknown_work_items(built):
    # random part statuses can make an active part name a proposed run, which warns active-refs-inactive; nothing else may warn
    assert {i.code for i in built.warnings} <= {"address-unresolved", "active-refs-inactive"}
    assert [(i.code, i.ids) for i in built.warnings if i.code == "address-unresolved"] == [("address-unresolved", ("work.battery-bench",))]


def test_the_same_seed_gives_identical_bytes_and_another_seed_differs(tmp_path, fx):
    fixture.generate(tmp_path / "again", 0)
    assert tree(tmp_path / "again") == tree(fx)
    fixture.generate(tmp_path / "other", 7)
    a, b = tree(tmp_path / "other"), tree(fx)
    assert a != b and sorted(a) == sorted(b)
    other = build.build_root(tmp_path / "other")
    assert other.errors == []
    assert {w: other.work[w]["status"] for w in other.work} == json.loads((tmp_path / "other" / "fixture-intent.json").read_text(encoding="utf-8"))["work"]


def test_outputs_are_deterministic_across_builds(fx, built):
    assert build.build_root(fx).outputs == built.outputs


def test_a_non_empty_output_directory_is_refused_not_overwritten(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        fixture.generate(tmp_path / "x", 0)
    assert (tmp_path / "x" / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_no_masses_overfill_a_budget_in_the_general_fixture(built):
    assert not [i for i in built.warnings if i.code == "budget-over"]


def test_the_fixture_command_writes_the_fixture_and_refuses_twice(tmp_path):
    lines = []
    assert cli.main(["fixture", "--out", str(tmp_path / "o"), "--seed", "3"], say=lines.append) == 0
    assert "seed 3" in lines[0] and (tmp_path / "o" / "fixture-intent.json").is_file()
    assert cli.main(["fixture", "--out", str(tmp_path / "o")], say=lines.append) == 1


def test_fy_dispatches_thread_commands(tmp_path):
    import subprocess
    import sys
    fy = str(REPO / "tools" / "fy")
    r = subprocess.run([sys.executable, fy, "thread", "fixture", "--out", str(tmp_path / "o"), "--scenario", "reallocation"], capture_output=True, text=True)
    assert r.returncode == 0 and "reallocation fixture" in r.stdout
    r = subprocess.run([sys.executable, fy, "thread", "impact", "--root", str(tmp_path / "o"), "part.hip.m2#/housed_in"], capture_output=True, text=True)
    assert r.returncode == 0 and "work.m2-mount" in r.stdout, r.stdout + r.stderr
