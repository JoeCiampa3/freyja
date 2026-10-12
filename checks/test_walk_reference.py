"""check.sim.walk_reference (advisory) against synthetic baselines, including its mutation tests. No dataset is needed: the
current metrics are replaced by a stub."""
import copy
import json

import pytest

import checklib as cl
import sim_checks as sc

SNAP, MODEL = "s" * 64, "m" * 64
METRICS = {"rigid/A_filtered": {"hip_fe_right": {"corr": 0.95, "rms_pct_ptp": 12.0, "peak_diff": 0.1}}}


def baseline(**kw):
    b = {"schema": "walk-reference/1", "snapshot_sha256": SNAP, "model_sha256": MODEL, "gait_id": "gait.x", "git_commit": "c" * 40,
         "baselined_methods": ["A_filtered"], "not_baselined_methods": ["B"],
         "reproduction": {"subset": {}, "tolerance_rel": 1e-6, "metrics": copy.deepcopy(METRICS)}}
    b.update(kw)
    return b


@pytest.fixture
def env(tmp_path, monkeypatch):
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"snapshot_sha256": SNAP, "model_sha256": MODEL}), encoding="utf-8")
    bf = tmp_path / "walk_reference.json"
    monkeypatch.setattr(sc, "BASELINE_FILE", bf)
    monkeypatch.setattr(sc, "META_FILE", meta)
    monkeypatch.setattr(sc, "dataset_available", lambda: True)
    monkeypatch.setattr(sc, "current_reference_metrics", lambda methods: copy.deepcopy(METRICS))
    ctx = type("Ctx", (), {"model_sha256": MODEL, "snapshot": {}})()
    return bf, meta, ctx


def run(ctx):
    return cl.call(cl.REGISTRY["check.sim.walk_reference"], ctx)[0]


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_it_is_registered_as_advisory():
    assert cl.REGISTRY["check.sim.walk_reference"].tier == cl.ADVISORY


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_without_a_baseline_or_the_dataset_it_skips(env, monkeypatch):
    bf, _, ctx = env
    assert run(ctx).status == cl.SKIP  # no baseline file
    bf.write_text(json.dumps(baseline()), encoding="utf-8")
    assert run(ctx).status == cl.PASS
    monkeypatch.setattr(sc, "dataset_available", lambda: False)
    assert run(ctx).status == cl.SKIP


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_the_same_snapshot_must_reproduce_the_metrics(env):
    bf, _, ctx = env
    bf.write_text(json.dumps(baseline()), encoding="utf-8")
    r = run(ctx)
    assert r.status == cl.PASS and "reproduce" in r.message


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_mutation_a_metric_that_moved_fails_when_the_snapshot_is_the_baselines(env):
    bf, _, ctx = env
    b = baseline()
    b["reproduction"]["metrics"]["rigid/A_filtered"]["hip_fe_right"]["corr"] += 1e-3  # the baseline no longer matches the code
    bf.write_text(json.dumps(b), encoding="utf-8")
    r = run(ctx)
    assert r.status == cl.FAIL and "hip_fe_right/corr" in r.message


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_a_difference_below_1e_6_is_round_off(env):
    bf, _, ctx = env
    b = baseline()
    b["reproduction"]["metrics"]["rigid/A_filtered"]["hip_fe_right"]["corr"] += 1e-8
    bf.write_text(json.dumps(b), encoding="utf-8")
    assert run(ctx).status == cl.PASS


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_a_design_change_supersedes_the_baseline_and_never_fails(env):
    bf, meta, ctx = env
    b = baseline(snapshot_sha256="o" * 64)  # the baseline was taken on another snapshot
    b["reproduction"]["metrics"]["rigid/A_filtered"]["hip_fe_right"]["corr"] = 0.2  # wildly different, and still not a failure
    bf.write_text(json.dumps(b), encoding="utf-8")
    r = run(ctx)
    assert r.status == cl.SKIP and "superseded" in r.message and "hip_fe 0.950" in r.message
    bf.write_text(json.dumps(baseline(model_sha256="p" * 64)), encoding="utf-8")  # a template change with the same snapshot is a design change too
    assert run(ctx).status == cl.SKIP


@pytest.mark.check("check.sim.walk_reference", tier="advisory")
def test_a_context_that_is_not_the_installed_model_skips(env):
    bf, _, _ = env
    bf.write_text(json.dumps(baseline()), encoding="utf-8")
    other = type("Ctx", (), {"model_sha256": "z" * 64, "snapshot": {}})()  # e.g. the candidate model during a build gate
    r = run(other)
    assert r.status == cl.SKIP and "installed" in r.message
