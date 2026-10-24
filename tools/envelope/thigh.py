"""The thigh segment frame (MJC convention: origin at the hip centre, z up the thigh, x anterior), the required stretch and the axial conform."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SegmentFrame:
    origin: np.ndarray       # hip centre, sheet frame, mm
    R: np.ndarray            # columns: segment x (anterior), y (left), z (up the thigh) in the sheet frame

    def to_segment(self, pts):
        return (np.asarray(pts, float) - self.origin) @ self.R

    def to_sheet(self, pts):
        return np.asarray(pts, float) @ self.R.T + self.origin


def segment_frame(hjc, kjc, pelvis_x) -> SegmentFrame:
    """z = HJC - KJC (up the thigh, the knee at (0, 0, -L)); x = the pelvis's anterior axis made perpendicular to z; y = z x x."""
    hjc, kjc = np.asarray(hjc, float), np.asarray(kjc, float)
    z = (hjc - kjc) / np.linalg.norm(hjc - kjc)
    x = np.asarray(pelvis_x, float) - z * (np.asarray(pelvis_x, float) @ z)
    x /= np.linalg.norm(x)
    return SegmentFrame(hjc, np.column_stack([x, np.cross(z, x), z]))


def required_stretch(hjc, kjc, length_sheet) -> float:
    return float(length_sheet / np.linalg.norm(np.asarray(hjc, float) - np.asarray(kjc, float)))


def conform(points_seg, s) -> np.ndarray:
    """Axial stretch by s about the hip plane, in the segment frame. Only z changes: cross-sections are untouched, no uniform scaling."""
    if not s > 0:
        raise ValueError(f"stretch must be positive, got {s}")
    out = np.array(points_seg, float, copy=True)
    out[..., 2] *= s
    return out
