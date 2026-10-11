"""
Stage 2 T3c.2: is the trunk counter-rotating? The dataset has no shoulder or trunk markers, only a trunk IMU (accelerometer in g,
gyroscope), so the trunk's roll and yaw are estimated from the IMU and compared with the pelvis's from the inverse kinematics.

  1. The IMU's axes are unknown. Its orientation relative to the pelvis frame is found from the accelerations: both are on the same
     walking body, so the specific force at the sensor is (nearly) the pelvis's: R maps the sensor frame onto the pelvis frame such
     that R (9.81 a_sensor) = R_pelvis^T (a_pelvis + g). The vertical comes from the means, the heading about the vertical from the
     dynamic horizontal parts. The trunk's own tilt relative to the pelvis is a few degrees and is the error of this step.
  2. The trunk's angular velocity in the pelvis axes is R times the gyroscope; the pelvis's own comes from the kinematics. Both are
     integrated over the stride (drift removed) to roll, pitch and yaw angles about the pelvis axes x forward, y up, z right.
  3. The first harmonic of each compares them: the trunk-to-pelvis amplitude ratio, the phase lag, and the fraction of the pelvis's
     motion that the trunk does not follow (1 minus the real part of the complex ratio): 0 is a rigid trunk, 1 a trunk upright in the world.
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline

import retarget

VERSION = "1"
G = 9.81  # m/s2


def _rodrigues(a, b):
    """Minimal rotation taking unit vector a to unit vector b."""
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3) if c > 0 else -np.eye(3) + 2 * np.outer(a, a)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1.0 + c)


def align_sensor_to_pelvis(accel_g, f_pelvis):
    """(R, quality). accel_g (N, 3) the IMU's accelerometer in g; f_pelvis (N, 3) the pelvis's specific force (a + g) in the pelvis frame,
    m/s2. R is the rotation with R (9.81 accel) approximately f_pelvis; quality is the correlation of the two per pelvis axis."""
    a = np.asarray(accel_g, float) * G
    f = np.asarray(f_pelvis, float)
    ms, mp = a.mean(axis=0), f.mean(axis=0)
    us, up = ms / np.linalg.norm(ms), mp / np.linalg.norm(mp)
    r1 = _rodrigues(us, up)
    ds, dp = (a - ms) @ r1.T, f - mp
    ds, dp = ds - np.outer(ds @ up, up), dp - np.outer(dp @ up, up)  # horizontal parts
    psi = np.arctan2(np.sum(np.cross(ds, dp) @ up), np.sum(ds * dp))
    k = np.array([[0, -up[2], up[1]], [up[2], 0, -up[0]], [-up[1], up[0], 0]])
    r2 = np.eye(3) + np.sin(psi) * k + (1 - np.cos(psi)) * (k @ k)
    r = r2 @ r1
    aligned = a @ r.T
    quality = np.array([np.corrcoef(aligned[:, i], f[:, i])[0, 1] for i in range(3)])
    return r, quality


def _periodic_spline(x, T):
    n = len(x)
    t = np.arange(n + 1) * T / n
    return CubicSpline(t, np.vstack([x, x[:1]]), bc_type="periodic"), t


def pelvis_body_omega(angles_rad, T):
    """Pelvis angular velocity in the pelvis (OpenSim: x forward, y up, z right) axes, rad/s, from periodic unique samples of the
    dataset's tilt, list and rotation angles (Rz Rx Ry) over a stride of duration T."""
    spl, t = _periodic_spline(np.asarray(angles_rad, float), T)
    out = np.zeros((len(angles_rad), 3))
    for k in range(len(angles_rad)):
        a, ad = spl(t[k]), spl(t[k], 1)
        E, dE, _ = retarget.euler_zxy(a, ad, np.zeros(3))
        out[k] = retarget._vee(E.T @ dE)
    return out


def pelvis_specific_force(position_lab, angles_rad, T):
    """(N, 3) the pelvis's specific force in the pelvis axes, m/s2: R_pelvis^T (a + (0, 9.81, 0)), from periodic unique samples of the
    pelvis position in the lab (x right, y up, z backward) and its angles."""
    ps, t = _periodic_spline(np.asarray(position_lab, float), T)
    spl, _ = _periodic_spline(np.asarray(angles_rad, float), T)
    out = np.zeros((len(position_lab), 3))
    for k in range(len(position_lab)):
        E, _, _ = retarget.euler_zxy(spl(t[k]), np.zeros(3), np.zeros(3))
        out[k] = E.T @ (ps(t[k], 2) + np.array([0.0, G, 0.0]))
    return out


def angle_from_rate(omega, T):
    """Integrate a periodic rate (N, 3) over the stride (trapezoid), remove the drift that a periodic signal cannot have, and the mean."""
    w = np.asarray(omega, float)
    n = len(w)
    dt = T / n
    wc = np.vstack([w, w[:1]])
    th = np.vstack([np.zeros((1, w.shape[1])), np.cumsum(0.5 * (wc[:-1] + wc[1:]) * dt, axis=0)])
    drift = th[-1]
    th = th[:-1] - np.outer(np.arange(n) / n, drift)
    return th - th.mean(axis=0)


def first_harmonic(x):
    x = np.asarray(x, float)
    n = len(x)
    return 2.0 / n * np.sum(x * np.exp(-2j * np.pi * np.arange(n) / n))


def harmonic_ratio(trunk, pelvis):
    """First-harmonic comparison of the trunk's angle with the pelvis's. phase_lag_deg is how much later the trunk follows (positive)."""
    ratio = first_harmonic(trunk) / first_harmonic(pelvis)
    return {"amplitude_ratio": float(abs(ratio)), "phase_lag_deg": float(-np.degrees(np.angle(ratio))), "cancelled_fraction": float(1.0 - ratio.real)}
