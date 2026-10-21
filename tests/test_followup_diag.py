"""
Memo 26 carry-forward items (sim/scripts/followup_diag.py, report only): the position of a stride within its trial, the twist of an oblique-axis rotation about the foot's long axis,
and the table of where a profiled stride spends its time. Pure functions on synthetic input.

Run from the repo root:
    python -m pytest tests/test_followup_diag.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import followup_diag as fu  # noqa: E402


def test_trial_position_says_whether_a_stride_is_the_first_of_its_trial_in_time():
    t0 = np.array([30.0, 10.0, 12.0, 50.0, 52.0])
    trial = np.array([1, 1, 1, 2, 2])
    p = fu.trial_position(t0, trial, 1)
    assert p["first_in_trial"] and p["rank"] == 0 and p["strides_in_trial"] == 3 and p["s_since_first_stride"] == 0.0
    p = fu.trial_position(t0, trial, 0)
    assert not p["first_in_trial"] and p["rank"] == 2 and p["s_since_first_stride"] == pytest.approx(20.0)
    assert fu.trial_position(t0, trial, 4)["rank"] == 1 and fu.trial_position(t0, trial, 3)["first_in_trial"]


def test_the_twist_about_the_long_axis_of_a_rotation_about_an_oblique_axis():
    assert fu.twist_about_x_deg((1, 0, 0), 20.0) == pytest.approx(20.0)
    assert fu.twist_about_x_deg((0, 1, 0), 20.0) == pytest.approx(0.0, abs=1e-12)
    a = np.array([0.78717961, 0.60474746, -0.12094949])
    assert fu.twist_about_x_deg(a, 1.0) == pytest.approx(a[0] / np.linalg.norm(a), rel=1e-3)  # small angles: the x component of the unit axis
    assert fu.twist_about_x_deg(a, -10.0) == pytest.approx(-fu.twist_about_x_deg(a, 10.0))
    assert abs(fu.twist_about_x_deg(a, 30.0)) < 30.0


def test_the_stage_table_sums_the_cumulative_time_of_the_named_functions():
    stats = {("/x/retarget.py", 10, "__init__"): (1, 1, 0.1, 2.0, {}), ("/x/retarget.py", 20, "grid"): (1, 1, 0.1, 1.0, {}),
             ("/x/dynamics.py", 30, "inverse_frame"): (100, 100, 0.5, 4.0, {}), ("/x/dynamics.py", 40, "solve_frame"): (50, 50, 0.5, 6.0, {}),
             ("/x/dynamics.py", 50, "solve_given"): (50, 50, 0.5, 3.0, {}), ("/x/other.py", 1, "noise"): (1, 1, 99.0, 99.0, {})}
    t = fu.stage_table(stats)
    assert t["retargeting"] == 3.0 and t["inverse dynamics"] == 4.0 and t["B: solve_frame"] == 6.0 and t["A and H: solve_given"] == 3.0
    assert "noise" not in " ".join(t)
