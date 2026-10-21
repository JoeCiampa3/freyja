"""
Stage 2g Part B (T7, T8): sim/scripts/limit_frames_diag.py, the report-only scan of the retargeted frames against every model limit and of the toe's angle. The pure functions on
synthetic input with known answers.

Run from the repo root:
    python -m pytest tests/test_limit_frames_diag.py
"""
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import limit_frames_diag as lf  # noqa: E402

MODEL = mujoco.MjModel.from_xml_path(str(REPO / "sim" / "models" / "freyja.xml"))


def frames(n=10):
    return np.tile(MODEL.qpos0, (n, 1))


def test_frames_inside_every_range_give_no_exceedance_and_a_joint_on_its_stop_is_not_outside():
    out = lf.outside(MODEL, frames())
    assert set(out) >= {"hip_fe_right", "toe_right", "lsj_fe", "shoulder_aa_right"}
    assert all(v["below"] == 0 and v["above"] == 0 for v in out.values())  # the arms hang on the zero-width adduction stop: at it, not beyond it


def test_counts_and_worst_excess_in_degrees_on_each_side():
    q = frames(10)
    a = int(MODEL.jnt_qposadr[MODEL.joint("toe_right").id])
    h = int(MODEL.jnt_qposadr[MODEL.joint("hip_fe_left").id])
    q[2:5, a] = np.radians(-1.7)           # three frames 1.7 degrees below the flat stop
    q[7, a] = np.radians(80 + 3.0)         # one frame 3 degrees past the extension stop
    q[:, h] = np.radians(-31 - 0.5)        # every frame half a degree past the hip extension stop (-31 degrees)
    out = lf.outside(MODEL, q)
    assert (out["toe_right"]["below"], out["toe_right"]["above"]) == (3, 1)
    assert out["toe_right"]["below_max_deg"] == pytest.approx(1.7) and out["toe_right"]["above_max_deg"] == pytest.approx(3.0)
    assert out["hip_fe_left"]["below"] == 10 and out["hip_fe_left"]["below_max_deg"] == pytest.approx(0.5)
    assert out["toe_left"]["below"] == 0


def test_mutation_a_frame_one_micro_degree_inside_a_limit_is_not_counted_and_one_outside_is():
    q = frames(2)
    a = int(MODEL.jnt_qposadr[MODEL.joint("lsj_fe").id])
    q[0, a] = np.radians(69.9 - 1e-6)
    q[1, a] = np.radians(69.9 + 1e-6)
    out = lf.outside(MODEL, q)["lsj_fe"]
    assert out["above"] == 1 and out["below"] == 0


def test_toe_summary_gives_peak_and_time_at_each_stop_over_all_frames_and_over_stance():
    q = frames(10)
    a = int(MODEL.jnt_qposadr[MODEL.joint("toe_left").id])
    q[:, a] = np.radians([0, 0, 0, 10, 30, 80, 80, 20, 0, 0])
    stance = np.zeros((2, 10), bool)
    stance[1, 3:8] = True  # the left foot's stance frames
    s = lf.toe_summary(MODEL, q, stance)["left"]
    assert s["peak_deg"] == pytest.approx(80.0)
    assert s["at_flexion_stop"] == pytest.approx(0.5) and s["at_extension_stop"] == pytest.approx(0.2)
    assert s["stance_at_flexion_stop"] == 0.0 and s["stance_at_extension_stop"] == pytest.approx(0.4)
    assert s["stance_peak_deg"] == pytest.approx(80.0)


def test_frames_beyond_a_limit_by_more_than_the_reporting_tolerance_are_counted_separately():
    """A filtered signal rings a hair past a stop it sits on; the count that matters beside the strict one is the frames past the stop by more than TOL_DEG."""
    q = frames(6)
    a = int(MODEL.jnt_qposadr[MODEL.joint("toe_right").id])
    q[:, a] = np.radians([-1e-9, -0.05, -0.1001, -0.5, -2.0, 0.0])
    o = lf.outside(MODEL, q)["toe_right"]
    assert o["below"] == 5 and o["below_gt_tol"] == 3 and lf.TOL_DEG == 0.1
