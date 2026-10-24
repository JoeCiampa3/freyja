"""Pelvis frame (ISB/Dumas), the scale k and the joint centres, from landmarks in the sheet (MuJoCo) frame, mm."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Frame:
    X: np.ndarray    # anterior
    Y: np.ndarray    # up (Z x X)
    Z: np.ndarray    # to the subject's right (ASIS_L -> ASIS_R)

    @property
    def R(self):
        return np.column_stack([self.X, self.Y, self.Z])


def _unit(v):
    return v / np.linalg.norm(v)


def pelvis_frame(asis_r, asis_l, sacral) -> Frame:
    """Z = ASIS_L -> ASIS_R; X anterior, perpendicular to Z, in the plane of the ASISs and the sacral point; Y = Z x X."""
    asis_r, asis_l, sacral = (np.asarray(p, float) for p in (asis_r, asis_l, sacral))
    Z = _unit(asis_r - asis_l)
    v = (asis_r + asis_l) / 2 - sacral
    X = _unit(v - Z * (v @ Z))
    return Frame(X, np.cross(Z, X), Z)


def _rows(b1):
    return b1["rows"] if "rows" in b1 else b1


def scale_from_asis(asis_r, asis_l, b1) -> float:
    """k = mesh inter-ASIS distance over the sheet's (RASIS - LASIS) distance."""
    rows = _rows(b1)
    ref = np.linalg.norm(np.array(rows["RASIS"], float) - np.array(rows["LASIS"], float))
    return float(np.linalg.norm(np.asarray(asis_r, float) - np.asarray(asis_l, float)) / ref)


def lumbosacral_joint_centre(asis_r, asis_l, sacral, b1, k):
    """LJC = ASIS midpoint - R . (x, y, 0)_RASIS . k  (the ASIS midpoint sits at the RASIS x, y and z = 0 in the ISB frame)."""
    rows = _rows(b1)
    f = pelvis_frame(asis_r, asis_l, sacral)
    mid = (np.asarray(asis_r, float) + np.asarray(asis_l, float)) / 2
    rx, ry, _ = rows["RASIS"]
    return mid - f.R @ np.array([rx, ry, 0.0]) * k


def hip_joint_centre(asis_r, asis_l, sacral, b1, k):
    """Right hip joint centre: LJC + R . HJC(Dumas) . k."""
    rows = _rows(b1)
    f = pelvis_frame(asis_r, asis_l, sacral)
    return lumbosacral_joint_centre(asis_r, asis_l, sacral, b1, k) + f.R @ (np.array(rows["HJC (Dumas)"], float) * k)
