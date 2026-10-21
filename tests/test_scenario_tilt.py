"""
Stage 2g Part B (decision Q3 of memo 24): stand_static and hold_pose stand in the design stance. Their `pose` block stays {com_x_rel_ankle_m: 0.0}; the pelvic tilt
(hips flexed, lumbosacral joint extended by it) comes from the snapshot's stand_pelvis_tilt_deg as a default, so no number is typed in the yaml, and a scenario that
sets pelvic_tilt_deg or lsj_fe_deg itself keeps its own value.

Run from the repo root:
    python -m pytest tests/test_scenario_tilt.py
"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import gait  # noqa: E402
import leanpose  # noqa: E402
import simrun  # noqa: E402

TILT = gait.snapshot_stand_tilt_deg()


def snapshot(tmp_path, tilt):
    p = tmp_path / "s.csv"
    rows = "placeholder,value,sheet_source\n" + (f"stand_pelvis_tilt_deg,{tilt},x\n" if tilt is not None else "target_mass,60,x\n")
    p.write_text(rows, encoding="utf-8", newline="\n")
    return p


def test_the_tracked_snapshot_has_a_tilt_and_the_scenarios_type_none():
    assert TILT > 5.0
    for name in ("stand_static", "hold_pose"):
        text = (REPO / "sim" / "scenarios" / f"{name}.yaml").read_text(encoding="utf-8")
        pose = yaml.safe_load(text)["pose"]
        assert pose == {"com_x_rel_ankle_m": 0.0}, name


def test_the_default_fills_the_hip_and_lumbosacral_offsets_from_the_snapshot_and_an_explicit_value_wins(tmp_path):
    p = simrun.pose_with_design_tilt({"com_x_rel_ankle_m": 0.0}, snapshot(tmp_path, 12.5))
    assert p == {"com_x_rel_ankle_m": 0.0, "pelvic_tilt_deg": 12.5, "lsj_fe_deg": -12.5}
    p = simrun.pose_with_design_tilt({"com_x_rel_ankle_m": 0.0, "pelvic_tilt_deg": 3.0}, snapshot(tmp_path, 12.5))
    assert p["pelvic_tilt_deg"] == 3.0 and p["lsj_fe_deg"] == -12.5
    p = simrun.pose_with_design_tilt({"com_x_rel_ankle_m": 0.0, "pelvic_tilt_deg": 0.0, "lsj_fe_deg": 0.0}, snapshot(tmp_path, 12.5))
    assert p["pelvic_tilt_deg"] == 0.0 and p["lsj_fe_deg"] == 0.0  # zero is a value, not an absence
    assert simrun.pose_with_design_tilt({"com_x_rel_ankle_m": 0.0}, snapshot(tmp_path, None)) == {"com_x_rel_ankle_m": 0.0}  # no key: the old pose
    assert simrun.pose_with_design_tilt({"com_x_rel_ankle_m": 0.0}, tmp_path / "absent.csv") == {"com_x_rel_ankle_m": 0.0}


def test_the_applied_pose_is_the_design_stance_of_the_model():
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    data = mujoco.MjData(model)
    lean = simrun._apply_pose(mujoco, model, data, {"com_x_rel_ankle_m": 0.0})
    want = leanpose.design_stance(model, TILT, gait.STANDING_FEET)
    assert np.allclose(data.qpos, want.qpos, atol=1e-12) and lean.lean_rad == pytest.approx(want.lean_rad, abs=1e-12)
    for n in ("hip_fe_right", "hip_fe_left"):  # the hips are flexed by the tilt, the lumbosacral joint extended by it
        assert abs(abs(np.degrees(data.qpos[model.jnt_qposadr[model.joint(n).id]])) - TILT) < 1e-9
    assert abs(abs(np.degrees(data.qpos[model.jnt_qposadr[model.joint("lsj_fe").id]])) - TILT) < 1e-9


def test_stand_static_records_the_tilt_and_the_lean_of_the_design_stance():
    scn = simrun.load_scenario("stand_static")
    with tempfile.TemporaryDirectory() as d:
        rec = simrun.run_scenario(scn, runs_dir=d, now=datetime(2026, 10, 21, 12, 0)).record
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    lean = leanpose.design_stance(model, TILT, gait.STANDING_FEET)
    assert rec["diagnostics"]["stand_pelvis_tilt_deg"] == pytest.approx(TILT)
    assert rec["diagnostics"]["lean_angle_deg"] == pytest.approx(np.degrees(lean.lean_rad), abs=1e-9)
    assert rec["scenario"]["params"]["pose"] == {"com_x_rel_ankle_m": 0.0}  # the record shows what the yaml says; the default is a diagnostic


def test_a_ground_run_starts_with_every_sole_corner_in_contact():
    """The solved pose puts the soles on the floor to round-off (heel corners at +7e-18 m and toe corners at -7e-18 m is what the Stage 2g model gave), and MuJoCo makes a contact
    only below zero, so a hold started there had contact at the toes alone, tipped forward and fell in 0.07 s. The ground run starts SETTLE_M lower."""
    scn = simrun.load_scenario("hold_pose")
    model = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))
    data = mujoco.MjData(model)
    simrun._apply_pose(mujoco, model, data, scn["pose"])
    simrun._settle_on_floor(data, model)
    mujoco.mj_forward(model, data)
    feet = {model.body(n).id for n in ("foot_right", "foot_left", "toe_right", "toe_left")}
    geoms = {int(c.geom2) for c in data.contact[:data.ncon] if int(c.geom1) == 0}
    assert {g for g in range(model.ngeom) if model.geom_bodyid[g] in feet and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX} == geoms  # all four sole boxes touch
    assert data.ncon == 16  # four corners on each of four boxes
    assert simrun.SETTLE_M <= 1e-5  # a few micrometres, far below anything a result depends on


class FakeData:
    """Just what _diverged reads: no warnings, finite state, and a clock that MuJoCo advances by adding the timestep each step."""
    class _W:
        number = 0
    def __init__(self, t):
        self.warning = [self._W() for _ in range(32)]
        self.qpos, self.qvel, self.time = np.zeros(3), np.zeros(3), t


def test_a_clock_that_drifts_by_rounding_is_not_a_divergence():
    """hold_pose at a timestep of 1e-4 s was reported 'diverged' at 6.1526 s with the state at rest: the accumulated clock (61 526 additions of 1e-4) fell 1e-12 s short of
    (k + 1) * dt. A step that did not advance the clock at all (a real stop) is still a divergence."""
    dt, t = 1e-4, 0.0
    for k in range(80000):  # the 8 s of hold_pose
        t += dt
        assert not simrun._diverged(mujoco, FakeData(t), (k + 1) * dt), k
    assert simrun._diverged(mujoco, FakeData(t - dt), 80000 * dt)  # one step short
