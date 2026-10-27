"""Frames and mass properties (CONVENTIONS section 3, CAD frame). CAD is modelled in the right-side ISB segment frame; the bridge converts to the owner's
model body frame through `envelope.registry.isb_to_segment`, the one copy of that rotation.

Inertia is the tensor [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]] (matrix entries, as MuJoCo's fullinertia), in kg mm^2 with lengths in mm."""
from __future__ import annotations

import numpy as np

from envelope import registry

KEYS = ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")


def rotation(side: str = "right") -> np.ndarray:
    """R with p_model = R @ p_isb, read from the registry's function so the rotation exists once."""
    return registry.isb_to_segment(np.eye(3), side).T


def points_to_model(points, side: str = "right") -> np.ndarray:
    return registry.isb_to_segment(points, side)


def to_matrix(d: dict) -> np.ndarray:
    return np.array([[d["ixx"], d["ixy"], d["ixz"]], [d["ixy"], d["iyy"], d["iyz"]], [d["ixz"], d["iyz"], d["izz"]]], float)


def from_matrix(m) -> dict:
    return {"ixx": float(m[0][0]), "iyy": float(m[1][1]), "izz": float(m[2][2]), "ixy": float(m[0][1]), "ixz": float(m[0][2]), "iyz": float(m[1][2])}


def mass_to_model(com_isb, inertia_isb: dict, side: str = "right"):
    """(com in the model frame, inertia about the com in the model frame as a dict). The inertia must already be about the centre of mass."""
    R = rotation(side)
    com = points_to_model([com_isb], side)[0]
    I = R @ to_matrix(inertia_isb) @ R.T
    return com, from_matrix(I)


def shift_inertia_to_com(I_origin, mass: float, com) -> np.ndarray:
    """Parallel-axis theorem: the tensor about the origin to the tensor about the centre of mass."""
    c = np.asarray(com, float)
    return np.asarray(I_origin, float) - mass * (c @ c * np.eye(3) - np.outer(c, c))


def shift_inertia_to_origin(I_com, mass: float, com) -> np.ndarray:
    c = np.asarray(com, float)
    return np.asarray(I_com, float) + mass * (c @ c * np.eye(3) - np.outer(c, c))


def principal_moments(I) -> np.ndarray:
    return np.linalg.eigvalsh(np.asarray(I, float))
