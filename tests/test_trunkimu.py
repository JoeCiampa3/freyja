"""
Stage 2 T3c.2: is the trunk counter-rotating? The arithmetic that compares the trunk IMU with the pelvis motion, on synthetic
signals with known answers.

Run from the repo root:
    python -m pytest tests/test_trunkimu.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim" / "scripts"))

import trunkimu  # noqa: E402

N = 100
PH = np.arange(N) / N


def rot(axis, a):
    c, s = np.cos(a), np.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]), "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def test_alignment_recovers_a_known_sensor_orientation():
    r_true = rot("z", 0.9) @ rot("x", -0.4) @ rot("y", 1.3)
    f_p = np.stack([2.0 * np.sin(2 * np.pi * PH), 9.81 + 1.5 * np.cos(4 * np.pi * PH + 0.3), 1.2 * np.sin(2 * np.pi * PH + 1.0)], axis=1)
    a_s = (f_p @ r_true) / 9.81  # f_p = R a_s * 9.81  <=>  a_s = R^T f_p / 9.81 ; rows: (R^T f)^T = f^T R
    r, quality = trunkimu.align_sensor_to_pelvis(a_s, f_p)
    assert np.abs(r - r_true).max() < 1e-9
    assert quality.min() > 0.999999


def test_alignment_is_wrong_by_a_half_turn_when_the_sensor_is_flipped_about_the_vertical():
    """Mutation: a sensor turned 180 degrees about the vertical is a different alignment, and the function must not return the first."""
    f_p = np.stack([2.0 * np.sin(2 * np.pi * PH), 9.81 + 0.5 * np.cos(4 * np.pi * PH), 1.2 * np.sin(2 * np.pi * PH + 1.0)], axis=1)
    r0, _ = trunkimu.align_sensor_to_pelvis(f_p / 9.81, f_p)
    flip = rot("y", np.pi)
    r1, _ = trunkimu.align_sensor_to_pelvis((f_p @ flip) / 9.81, f_p)
    assert np.abs(r0 - np.eye(3)).max() < 1e-9 and np.abs(r1 - flip.T).max() < 1e-9 and np.abs(r1 - r0).max() > 1.9


def test_pelvis_body_omega_for_a_yaw_oscillation():
    a, T = np.deg2rad(5.0), 1.0
    ang = np.zeros((N, 3))  # tilt (ground z, the roll), list (ground x, the pitch), rotation (about the pelvis's own y, the yaw)
    ang[:, 2] = np.pi / 2 + a * np.sin(2 * np.pi * PH)
    w = trunkimu.pelvis_body_omega(ang, T)
    assert w[:, 1] == pytest.approx(a * 2 * np.pi / T * np.cos(2 * np.pi * PH), abs=2e-4)  # about the pelvis's vertical axis y
    assert np.abs(w[:, [0, 2]]).max() < 1e-4


def test_angle_from_rate_recovers_a_sinusoid_up_to_its_mean():
    T = 1.2
    w = np.stack([0.3 * np.cos(2 * np.pi * PH) * 2 * np.pi / T, np.zeros(N), np.zeros(N)], axis=1)
    th = trunkimu.angle_from_rate(w, T)
    assert th[:, 0] == pytest.approx(0.3 * np.sin(2 * np.pi * PH) - (0.3 * np.sin(2 * np.pi * PH)).mean(), abs=2e-3)
    assert abs(th[:, 0].mean()) < 1e-12


def test_harmonic_ratio_gives_amplitude_lag_and_the_cancelled_fraction():
    pel = 4.0 * np.sin(2 * np.pi * PH)
    for ratio, lag in ((1.0, 0.0), (0.3, 20.0), (0.0, 0.0), (0.5, -35.0)):
        trunk = ratio * 4.0 * np.sin(2 * np.pi * PH - np.deg2rad(lag))
        h = trunkimu.harmonic_ratio(trunk, pel)
        assert h["amplitude_ratio"] == pytest.approx(ratio, abs=1e-12)
        if ratio > 0:
            assert h["phase_lag_deg"] == pytest.approx(lag, abs=1e-9)
        assert h["cancelled_fraction"] == pytest.approx(1.0 - ratio * np.cos(np.deg2rad(lag)), abs=1e-12)
    # a trunk that rolls opposite to the pelvis cancels more than all of it, and the sign says so
    assert trunkimu.harmonic_ratio(-0.2 * pel, pel)["cancelled_fraction"] == pytest.approx(1.2)
