"""check.sim.rom_reachable against synthetic summaries (including its mutation test) and against the real
rom_sweep on the committed model."""
import copy
import json

import pytest

import checklib as cl
import sim_checks as sc

SNAP = {"hip_flexion": 130.0, "hip_extension": 20.0, "knee_flexion": 140.0, "knee_extension": 0.0}
TEMPLATE = """
<joint name="hip_fe_right" type="hinge" axis="0 -1 0" limited="true" range="!{-hip_extension} !{hip_flexion}"/>
<joint name="knee_right" type="hinge" axis="0 1 0" limited="true" range="!{-knee_extension} !{knee_flexion}"/>
<joint name="lsj_fe" type="hinge" axis="0 1 0"/>
<joint name="odd" type="hinge" axis="0 1 0" limited="true" range="-5 5"/>
"""


def joint(lo_used, hi_used, lo_lim, hi_lim):
    return {"torque_source": "inverse_dynamics", "torque_peak_nm": 1.0, "torque_rms_nm": 1.0, "speed_peak_rad_s": 1.0,
            "power_peak_w": 1.0, "rom_used_deg": [lo_used, hi_used], "rom_limit_deg": [lo_lim, hi_lim], "limit_hit_fraction": 0.0}


def summary(**joints):
    return {"run_id": "run.20261012-1430-rom_sweep", "scenario": {"name": "rom_sweep"}, "model_sha256": "m" * 64, "joints": joints}


def good():
    return summary(hip_fe_right=joint(-0.99 * 20, 0.99 * 130, -20, 130), knee_right=joint(0.0, 0.99 * 140, 0.0, 140))


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_template_ranges_map_to_snapshot_values_in_degrees():
    lim = sc.sheet_limits(TEMPLATE, SNAP)
    assert lim == {"hip_fe_right": (-20.0, 130.0), "knee_right": (-0.0, 140.0)}  # lsj_fe and the literal range are not sheet-sourced


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_sweep_that_reaches_99_percent_passes():
    checked, short = sc.rom_shortfalls(good(), sc.sheet_limits(TEMPLATE, SNAP))
    assert (checked, short) == (2, [])


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_mutation_a_joint_that_falls_short_of_the_sheet_fails():
    bad = copy.deepcopy(good())
    bad["joints"]["hip_fe_right"]["rom_used_deg"][1] = 0.90 * 130  # the model stops at 90% of the sheet value
    checked, short = sc.rom_shortfalls(bad, sc.sheet_limits(TEMPLATE, SNAP))
    assert len(short) == 1 and "hip_fe_right" in short[0] and "117.000" in short[0]


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_mutation_a_stale_sheet_value_fails_the_same_sweep():
    snap = dict(SNAP, knee_flexion=160.0)  # the sheet now says 160 but the model (and so the sweep) still has 140
    _, short = sc.rom_shortfalls(good(), sc.sheet_limits(TEMPLATE, snap))
    assert any("knee_right" in s for s in short)


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_lower_limit_is_checked_too():
    bad = copy.deepcopy(good())
    bad["joints"]["hip_fe_right"]["rom_used_deg"][0] = -0.5 * 20
    _, short = sc.rom_shortfalls(bad, sc.sheet_limits(TEMPLATE, SNAP))
    assert len(short) == 1 and "hip_fe_right" in short[0]


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_unlimited_joints_are_not_checked_and_a_limit_without_a_sheet_value_is_named():
    s = summary(lsj_fe=joint(0.0, 0.0, 0.0, 0.0), odd=joint(-4.95, 4.95, -5, 5))
    s["joints"]["lsj_fe"]["rom_limit_deg"] = None
    checked, short = sc.rom_shortfalls(s, sc.sheet_limits(TEMPLATE, SNAP))
    assert checked == 0 and len(short) == 1 and "odd" in short[0]


@pytest.mark.check("check.sim.rom_reachable", tier="advisory")
def test_check_skips_without_a_sweep_for_this_model_and_picks_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "RUNS_DIR", tmp_path)
    ctx = type("Ctx", (), {"model_sha256": "m" * 64, "snapshot": SNAP})()
    assert cl.call(cl.REGISTRY["check.sim.rom_reachable"], ctx)[0].status == cl.SKIP
    for run_id, ok in (("run.20261012-1430-rom_sweep", False), ("run.20261013-0900-rom_sweep", True)):
        s = good() if ok else summary(hip_fe_right=joint(0, 1, -20, 130))
        s["run_id"] = run_id
        (tmp_path / run_id.removeprefix("run.")).mkdir()
        (tmp_path / run_id.removeprefix("run.") / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    other = copy.deepcopy(good())
    other.update(run_id="run.20261014-0900-rom_sweep", model_sha256="x" * 64)  # a newer run on a different model
    (tmp_path / "20261014-0900-rom_sweep").mkdir()
    (tmp_path / "20261014-0900-rom_sweep" / "summary.json").write_text(json.dumps(other), encoding="utf-8")
    assert sc.latest_sweep("m" * 64)["run_id"] == "run.20261013-0900-rom_sweep"
