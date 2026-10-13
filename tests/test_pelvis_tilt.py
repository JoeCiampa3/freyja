"""
Stage 2d T6 (report only): the marker-defined pelvic tilt and the hip extension relative to it (sim/scripts/pelvis_tilt.py), on synthetic input
with known answers.

Run from the repo root:
    python -m pytest tests/test_pelvis_tilt.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))
sys.path.insert(0, str(REPO / "analysis"))

import pelvis_tilt as pt  # noqa: E402


def _table(tilt_deg, n=300, rate=100.0, nan_at=()):
    """A marker table (lab frame, x right, y up, forward is minus z) of a pelvis tilted anteriorly by tilt_deg (a number or an array over frames)."""
    tilt = np.broadcast_to(np.asarray(tilt_deg, float), (n,))
    th = np.deg2rad(tilt)
    fwd, down = 0.15 * np.cos(th), 0.15 * np.sin(th)
    t = {"Header": np.arange(n) / rate}
    pts = {"R_PSIS": (0.04, 0.95, 0.0), "L_PSIS": (-0.04, 0.95, 0.0)}
    for name, (x, y, z) in pts.items():
        for c, v in zip("xyz", (x, y, z)):
            t[f"{name}_{c}"] = np.full(n, v)
    for name, x in (("R_ASIS", 0.10), ("L_ASIS", -0.10)):
        t[f"{name}_x"] = np.full(n, x)
        t[f"{name}_y"] = 0.95 - down
        t[f"{name}_z"] = -fwd
    for k in nan_at:
        t["R_ASIS_y"] = np.array(t["R_ASIS_y"], float)
        t["R_ASIS_y"][k] = np.nan
    return t


def test_the_tilt_series_over_a_stride_is_the_markers_tilt_at_the_100_phase_points():
    ramp = np.linspace(5.0, 25.0, 300)  # 5 to 25 degrees over 3 s
    t0, T = 0.5, 1.0
    got = pt.tilt_series(_table(ramp), t0, T)
    assert got.shape == (100,)
    want = np.interp(t0 + T * np.arange(100) / 100.0, np.arange(300) / 100.0, ramp)
    assert got == pytest.approx(want, abs=1e-9)


def test_a_few_missing_marker_frames_are_interpolated_over_and_many_are_not():
    tab = _table(12.0, nan_at=[100, 101, 102])
    assert pt.tilt_series(tab, 0.5, 1.0) == pytest.approx(np.full(100, 12.0), abs=1e-9)
    gappy = _table(12.0, nan_at=list(range(60, 160)))  # a third of the stride window is missing
    assert pt.tilt_series(gappy, 0.5, 1.0) is None


def test_the_hip_angle_relative_to_the_marker_pelvis_is_the_thigh_from_the_vertical_plus_the_markers_anterior_tilt():
    hip = np.array([30.0, 0.0, -10.0])  # relative to the IK pelvis
    lst = np.array([-12.0, -12.0, -12.0])  # IK pelvis pitched forward by 12 degrees (list is minus the anterior pitch)
    tilt = np.array([8.0, 8.0, 8.0])  # the marker pelvis is tilted forward by 8
    thigh = hip + lst  # thigh from the vertical, forward positive: 18, -12, -22
    got = pt.hip_relative_to_marker_pelvis(hip, lst, tilt)
    assert got == pytest.approx(thigh + tilt)
    # the marker pelvis equal to the IK pelvis gives back the IK hip angle exactly
    assert pt.hip_relative_to_marker_pelvis(hip, lst, -lst) == pytest.approx(hip)


def test_peak_extension_is_minus_the_smallest_hip_angle_of_either_limb_negative_when_never_extended():
    assert pt.peak_extension(np.array([10.0, -14.0, 3.0]), np.array([8.0, -9.0, 20.0])) == pytest.approx(14.0)
    assert pt.peak_extension(np.array([4.0, 6.0]), np.array([5.0, 9.0])) == pytest.approx(-4.0)


def test_a_constant_shift_of_the_pelvis_frame_shifts_the_extension_by_the_same_amount():
    rng = np.random.default_rng(3)
    hip_r, hip_l, lst = rng.normal(size=(3, 100)) * 8, rng.normal(size=100) * 8, rng.normal(size=100) * 2
    base = pt.peak_extension(pt.hip_relative_to_marker_pelvis(hip_r, lst, 10.0 + np.zeros(100)), pt.hip_relative_to_marker_pelvis(hip_l, lst, 10.0 + np.zeros(100)))
    shifted = pt.peak_extension(pt.hip_relative_to_marker_pelvis(hip_r, lst, 15.0 + np.zeros(100)), pt.hip_relative_to_marker_pelvis(hip_l, lst, 15.0 + np.zeros(100)))
    assert shifted == pytest.approx(base - 5.0)  # tilting the reference pelvis 5 degrees more forward asks the hip for 5 degrees less extension
