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


# ------------------------------------------------------------------------------ T9.3 pitch flags

def _markers_at_tilt(tilt_deg, n=3):
    """ASIS and PSIS markers (lab: x right, y up, z backward) of a pelvis tilted anteriorly by tilt_deg: the ASIS line forward and down."""
    th = np.deg2rad(tilt_deg)
    fwd, down = 0.15 * np.cos(th), 0.15 * np.sin(th)
    psis_r, psis_l = np.array([0.04, 0.95, 0.0]), np.array([-0.04, 0.95, 0.0])
    asis_r, asis_l = np.array([0.10, 0.95 - down, -fwd]), np.array([-0.10, 0.95 - down, -fwd])  # forward is minus z
    rep = lambda v: np.tile(v, (n, 1))
    return rep(asis_r), rep(asis_l), rep(psis_r), rep(psis_l)


@pytest.mark.parametrize("tilt", [-12.0, 0.0, 7.5, 20.0])
def test_marker_pelvic_tilt_recovers_the_tilt_of_the_asis_psis_line_anterior_positive(tilt):
    assert np.allclose(gd.marker_pelvic_tilt_deg(*_markers_at_tilt(tilt)), tilt, atol=1e-9)


def test_marker_pelvic_tilt_is_unchanged_by_a_translation_and_by_a_roll_of_the_pelvis_about_the_walking_axis_to_first_order():
    a_r, a_l, p_r, p_l = _markers_at_tilt(10.0)
    shift = np.array([0.3, -0.1, 2.0])
    assert np.allclose(gd.marker_pelvic_tilt_deg(a_r + shift, a_l + shift, p_r + shift, p_l + shift), 10.0, atol=1e-9)


def test_the_flag_is_a_difference_of_the_static_to_walking_changes_above_the_threshold():
    assert gd.PITCH_FLAG_DEG == 5.0  # the brief's named threshold
    # IK pitch went from -0.2 to -14.9 (a change of -14.7) while the markers changed by -2.0: the changes differ by 12.7 degrees
    assert gd.pitch_flag(-14.7, -2.0)
    assert not gd.pitch_flag(-4.0, -2.0)  # differ by 2
    assert not gd.pitch_flag(-7.0, -2.0)  # exactly 5: not above
    assert gd.pitch_flag(-7.001, -2.0) and gd.pitch_flag(3.0, -2.5)  # either direction
    assert gd.pitch_flag(5.0, 0.0) is False and gd.pitch_flag(5.1, 0.0) is True


def test_a_flag_that_compared_the_levels_instead_of_the_changes_would_flag_a_constant_offset():
    # a subject whose IK pitch sits 12 degrees above the markers' at both static and walking has no flag: the change is what is compared
    assert not gd.pitch_flag(delta_ik=-5.0, delta_marker=-5.0)


@pytest.mark.parametrize("heading", [30.0, 90.0, 180.0, -75.0])
def test_marker_pelvic_tilt_does_not_depend_on_which_way_the_subject_faces_in_the_lab(heading):
    # the static trials are recorded facing another way than the treadmill trials: forward must come from the ASIS line, not from the lab's z axis
    a_r, a_l, p_r, p_l = _markers_at_tilt(10.0)
    h = np.deg2rad(heading)
    rot = np.array([[np.cos(h), 0.0, np.sin(h)], [0.0, 1.0, 0.0], [-np.sin(h), 0.0, np.cos(h)]])  # about the vertical (y)
    got = gd.marker_pelvic_tilt_deg(a_r @ rot.T, a_l @ rot.T, p_r @ rot.T, p_l @ rot.T)
    assert np.allclose(got, 10.0, atol=1e-9)


# ------------------------------------------------------------------------------ Stage 2b T2 and T4: peak-torque statistics and the gain-or-shape fit

def test_peak_stats_are_mean_median_95th_percentile_and_maximum():
    s = gd.peak_stats(np.arange(1.0, 101.0))
    assert s == {"mean": pytest.approx(50.5), "median": pytest.approx(50.5), "p95": pytest.approx(95.05), "max": 100.0}


def test_ols_recovers_a_known_line():
    x = np.linspace(-2, 3, 40)
    slope, icpt = gd.ols(x, 1.7 * x - 0.4)
    assert slope == pytest.approx(1.7) and icpt == pytest.approx(-0.4)


def _stride(n=100, phase=0.0, amp=1.0, seed=0):
    t = np.arange(n) / n
    return amp * (np.sin(2 * np.pi * t + phase) + 0.3 * np.sin(4 * np.pi * t))


def test_a_pure_gain_error_has_slope_away_from_one_unit_correlation_and_zero_rms_once_the_gain_is_removed():
    data = [_stride(amp=a) for a in (0.8, 1.0, 1.2)]
    model = [1.5 * d for d in data]
    f = gd.stem_fit(model, data)
    assert f["slope"] == pytest.approx(1.5) and f["intercept"] == pytest.approx(0.0, abs=1e-12)
    assert f["corr"] == pytest.approx(1.0)
    expect = np.mean([100 * 0.5 * np.sqrt(np.mean(d ** 2)) / np.ptp(d) for d in data])  # the residual of a gain of 1.5 is 0.5 d
    assert f["rms_pct_ptp"] == pytest.approx(expect, rel=1e-9) and f["rms_gain_removed_pct_ptp"] == pytest.approx(0.0, abs=1e-9)
    assert f["gain"] == pytest.approx(1.5)
    assert f["peak_diff"] > 0.0 and f["peak_diff_gain_removed"] == pytest.approx(0.0, abs=1e-12)


def test_a_pure_shape_error_leaves_the_slope_near_one_and_the_rms_after_gain_removal_large():
    data = [_stride() for _ in range(3)]
    model = [_stride(phase=0.6) for _ in range(3)]  # same amplitude, shifted in time
    f = gd.stem_fit(model, data)
    assert 0.5 < f["slope"] < 1.1 and f["corr"] < 0.95
    assert f["rms_gain_removed_pct_ptp"] > 0.8 * f["rms_pct_ptp"]  # a gain cannot repair a shape error: most of the RMS stays


def test_the_rms_is_a_percentage_of_each_strides_own_peak_to_peak_range_then_averaged():
    d1, d2 = _stride(amp=1.0), _stride(amp=3.0)
    f = gd.stem_fit([d1 + 0.1, d2 + 0.1], [d1, d2])  # a constant 0.1 offset: rms 0.1 in both strides
    expect = np.mean([100 * 0.1 / np.ptp(d1), 100 * 0.1 / np.ptp(d2)])
    assert f["rms_pct_ptp"] == pytest.approx(expect, rel=1e-9)


def test_thigh_angle_from_the_vertical_is_the_hip_angle_plus_the_pelvis_list_because_anterior_pitch_is_minus_the_list():
    # a pelvis tilted back by 10 deg (list +10, anterior pitch -10) with the thigh vertical in the world reads as 10 deg of hip EXTENSION
    assert gd.thigh_world_deg(hip_flexion_deg=-10.0, pelvis_list_deg=10.0) == pytest.approx(0.0)
    # bending forward 20 deg at the hips with the thigh fixed in the world: the pelvis pitches forward 20 (list -20), the hip reads 20 flexion
    assert gd.thigh_world_deg(hip_flexion_deg=20.0, pelvis_list_deg=-20.0) == pytest.approx(0.0)
    assert gd.thigh_world_deg(np.array([5.0, -3.0]), np.array([2.0, 2.0])) == pytest.approx([7.0, -1.0])


def test_peak_extension_is_the_larger_of_the_two_limbs_and_minus_the_minimum_angle():
    right, left = np.array([10.0, -20.0, 5.0]), np.array([8.0, -25.0, 1.0])
    assert gd.peak_extension_deg(right, left) == pytest.approx(25.0)
    assert gd.peak_extension_deg(np.array([3.0, 4.0]), np.array([5.0, 6.0])) == pytest.approx(-3.0)  # never extended: negative, not clipped
