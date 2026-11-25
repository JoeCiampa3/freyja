"""Where the shoulder gimbal's fixed axis points (docs/briefs/ariadne/shoulder-axis-search-brief.md).

A three-axis gimbal with intersecting axes: axis 1 fixed in the thorax along u1, axis 2 perpendicular to axis 1 and axis 3, axis 3 along the
humerus. It is singular where the humerus is parallel to the line +/-u1. This script finds the u1 whose singular line lies farthest from every
humeral direction Freyja must reach. Directions and kinematics only: no model change, no collision, no actuator, no load.

Frame: the thorax body frame of sim/models/freyja.xml (x anterior, y left, z up). The humeral direction d is the unit vector from the shoulder
joint centre to the elbow joint centre. Angles in degrees at the interface, radians inside.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

INPUTS = "data/shoulder/inputs/axis_search.yaml"
OUT = "data/shoulder/axis_search.json"
SIDES = ("right", "left")
ROM_ADDRESSES = ("snapshot#/shoulder_flexion", "snapshot#/shoulder_extension", "snapshot#/shoulder_abduction")


def read_rom(root: Path = ROOT) -> dict:
    """The three ROM ends, read through the thread's address resolution (never typed). Raises naming the address that does not resolve."""
    from thread import build as tb
    b = tb.build_root(Path(root))
    out = {}
    for a in ROM_ADDRESSES:
        ok, v = b.resolve(a)
        if not ok:
            raise ValueError(f"{a} does not resolve")
        out[a] = float(v)
    return out


# ---- vectors ------------------------------------------------------------------------------------------------------------------------

def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def rot(axis, angle: float) -> np.ndarray:
    """Rotation matrix about a unit axis by `angle` radians (Rodrigues)."""
    k = np.asarray(axis, dtype=float)
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)


def mirror(v) -> np.ndarray:
    """The y-mirror (sagittal plane) of a vector or an array of vectors."""
    return np.asarray(v, dtype=float) * np.array([1.0, -1.0, 1.0])


# ---- the humeral direction, ISB humerothoracic Y-X-Y (Wu et al. 2005) -------------------------------------------------------------

def d_of(phi_deg, theta_deg, side: str = "right") -> np.ndarray:
    """d(phi, theta) = (sin t sin p, -sin t cos p, -cos t) for the right arm; the left arm is its y-mirror. theta is elevation from straight
    down; phi = 0 is abduction in the frontal plane, +90 forward flexion, negative behind the frontal plane. Broadcasts."""
    p, t = np.radians(np.asarray(phi_deg, float)), np.radians(np.asarray(theta_deg, float))
    d = np.stack([np.sin(t) * np.sin(p), -np.sin(t) * np.cos(p), -np.cos(t)], axis=-1)
    return d if side == "right" else mirror(d)


def phi_theta(d, side: str = "right"):
    """(phi, theta) in degrees of a unit direction; phi in (-180, 180]. phi is undefined at theta = 0 or 180 and returned as 0 there."""
    d = np.asarray(d, float)
    if side != "right":
        d = mirror(d)
    theta = np.degrees(np.arccos(np.clip(-d[..., 2], -1.0, 1.0)))
    phi = np.degrees(np.arctan2(d[..., 0], -d[..., 1]))
    if np.ndim(phi) == 0:
        return float(phi), float(theta)
    return phi, theta


# ---- the gimbal ---------------------------------------------------------------------------------------------------------------------

def gimbal_frame(u1):
    """(d0, u2): d0 the unit projection of straight down onto the plane perpendicular to u1 (the zero pose), u2 = u1 x d0 (axis 2 at q1 = 0)."""
    u1 = np.asarray(u1, float)
    down = np.array([0.0, 0.0, -1.0])
    p = down - (down @ u1) * u1
    n = np.linalg.norm(p)
    if n < 1e-12:
        raise ValueError("u1 is vertical: the zero pose d0 is undefined")
    d0 = p / n
    return d0, np.cross(u1, d0)


def gimbal_fk(u1, q1: float, q2: float) -> np.ndarray:
    """d = R(u1, q1) R(u2, q2) d0. Since u2 x d0 = -u1, R(u2, q2) d0 = cos q2 d0 - sin q2 u1: positive q2 tilts the arm toward -u1."""
    d0, u2 = gimbal_frame(u1)
    return rot(u1, q1) @ (rot(u2, q2) @ d0)


def gimbal_ik(u1, d):
    """(q1, q2) in radians on the branch q2 in [-pi/2, pi/2]: q2 = -asin(d . u1), q1 = atan2(d . u2, d . d0). Undefined (q1 arbitrary) when d
    is parallel to u1."""
    u1, d = np.asarray(u1, float), np.asarray(d, float)
    d0, u2 = gimbal_frame(u1)
    q2 = -math.asin(max(-1.0, min(1.0, float(d @ u1))))
    q1 = math.atan2(float(d @ u2), float(d @ d0))
    return q1, q2


def axis_matrix(u1, q1: float, q2: float) -> np.ndarray:
    """The orientation Jacobian of the three intersecting revolute axes: the unit axes in the thorax frame as columns [u1, u2(q1), d]."""
    _, u2 = gimbal_frame(u1)
    return np.column_stack([np.asarray(u1, float), rot(u1, q1) @ u2, gimbal_fk(u1, q1, q2)])


def sigma_min(u1, d):
    """sqrt(1 - |u1 . d|): the least singular value of [u1, u2, d] (the others are 1 and sqrt(1 + |u1 . d|)). Broadcasts over d."""
    c = np.abs(np.asarray(d, float) @ np.asarray(u1, float))
    return np.sqrt(np.clip(1.0 - c, 0.0, None))


def main(argv) -> int:
    print("analysis/shoulder_axis_search.py: the search is not written yet (brief T2)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
