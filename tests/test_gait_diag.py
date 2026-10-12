"""Stage 2 T9 diagnostics: the pure arithmetic of the report subcommands, on synthetic input with known answers. The subcommands themselves
print numbers to the memo and write nothing; they are reproduced by running them, not by a test."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import gait_diag as gd  # noqa: E402


def test_joint_metrics_of_a_sinusoid_have_known_peaks():
    t = np.arange(100) / 100.0
    ang = np.deg2rad(8.0) * np.sin(2 * np.pi * t)
    w = np.deg2rad(8.0) * 2 * np.pi * np.cos(2 * np.pi * t)
    tau = 30.0 * np.cos(2 * np.pi * t)
    m = gd.joint_metrics(ang, w, tau)
    assert m["peak_angle_deg"] == pytest.approx(8.0, rel=1e-3)
    assert m["peak_speed_rad_s"] == pytest.approx(np.deg2rad(8.0) * 2 * np.pi, rel=1e-3)
    assert m["peak_torque_nm"] == pytest.approx(30.0, rel=1e-3)
    p = tau * w
    assert m["peak_power_pos_w"] == pytest.approx(p.max()) and m["peak_regen_w"] == pytest.approx(-p.min())  # regeneration is the magnitude of the most negative power
    assert m["peak_regen_w"] >= 0.0


def test_distribution_is_median_95th_percentile_and_maximum():
    d = gd.distribution(np.arange(1.0, 101.0))
    assert d == {"median": pytest.approx(50.5), "p95": pytest.approx(95.05), "max": 100.0}


def test_harmonic_gain_is_the_modulus_of_one_minus_the_complex_ratio():
    # the joint must rotate by |1 - r e^(-i phi)| times the pelvis's first-harmonic amplitude (brief T9.1)
    assert gd.joint_over_pelvis(0.0, 0.0) == pytest.approx(1.0)  # a counter-rotating trunk: the joint carries the whole pelvis harmonic
    assert gd.joint_over_pelvis(1.0, 0.0) == pytest.approx(0.0)  # a rigid trunk: nothing
    assert gd.joint_over_pelvis(1.0, 180.0) == pytest.approx(2.0)  # trunk in antiphase: twice
    assert gd.joint_over_pelvis(0.57, 101.0) == pytest.approx(1.2416, abs=1e-3)
    assert gd.joint_over_pelvis(0.57, 101.0) == pytest.approx(gd.joint_over_pelvis(0.57, -101.0))  # the modulus does not depend on the lag's sign


def test_the_four_quartile_corners_pair_each_gain_quartile_with_each_lag_quartile():
    d = {"median": (0.6, 100.0), "q1": (0.4, 50.0), "q3": (0.8, 120.0)}
    corners = gd.quartile_corners(d)
    assert sorted(corners) == [(0.4, 50.0), (0.4, 120.0), (0.8, 50.0), (0.8, 120.0)]
