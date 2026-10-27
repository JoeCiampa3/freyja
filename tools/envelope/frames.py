"""Model body frames for the oracle and the registry (volume-extractor brief 7, item 1).

Every segment is addressed in the frame of the MuJoCo model's body of that name: the pelvis origin is the lumbosacral joint (LSJ), the abdomen's is the TJC, the thorax's and the head and
neck's the CJC, the legs' the hip, knee and ankle joint centres (as before). All axes are parallel to the world at q = 0 (x anterior, y left, z up), and the bodies hang below their origin,
except the head and neck, which stands on the CJC.

The oracle's built trunk bodies keep their own frame (origin on the mesh hip line, at the body's upper plane: the hip line is the vertical through the knee section, which the shear makes
the vertical through the hip joint centre too). The model's trunk stack stands on the vertical through its pelvis origin, `thigh_right_pos_x` behind the hip joint centre. So, for a trunk body,

    oracle position = model position + (-hjc_x, 0, 0)        [+ (0, 0, -length) for the head and neck, whose oracle origin is the vertex]

where hjc_x is the model's HJC x relative to the pelvis origin, read from the snapshot. In the mesh frame the model's trunk axis is at the mesh hip line x less hjc_x: the mesh-to-model
trunk shift (`mesh_to_model_trunk_shift_mm`), a computed quantity, never typed. It is applied inside the oracle (`oracle.clearance(..., frame_offset_mm=...)`) and printed in every trunk result.
"""
from __future__ import annotations

import numpy as np

from .sheet import StopAndAsk, read_snapshot

TRUNK_BODIES = ("pelvis", "abdomen", "thorax", "head_neck")
LEG_BODIES = ("thigh_R", "shank_R", "foot_R", "thigh_L", "shank_L", "foot_L")
KEY = "model_to_segment_mm"
MODEL_ORIGIN = {"pelvis": "the lumbosacral joint", "abdomen": "the TJC", "thorax": "the CJC", "head_neck": "the CJC"}


def hjc_x_in_pelvis_mm(snapshot_path, side="right") -> float:
    """The model's hip joint centre ahead of its pelvis origin, mm: the snapshot's thigh_<side>_pos_x."""
    snap = read_snapshot(snapshot_path)
    k = f"thigh_{side}_pos_x"
    if k not in snap:
        raise StopAndAsk(f"snapshot key {k} is missing")
    return snap[k] * 1000.0


def model_to_segment_mm(name: str, hjc_x_mm: float, length_mm: float) -> tuple:
    """Translation from a point in the model body frame of segment `name` to the same point in the oracle's segment frame (the frames are parallel)."""
    if name in LEG_BODIES:
        return (0.0, 0.0, 0.0)
    if name in ("pelvis", "abdomen", "thorax"):
        return (-float(hjc_x_mm), 0.0, 0.0)
    if name == "head_neck":
        return (-float(hjc_x_mm), 0.0, -float(length_mm))
    raise ValueError(f"no model frame for segment {name!r} (trunk bodies {TRUNK_BODIES}, legs {LEG_BODIES})")


def mesh_to_model_trunk_shift_mm(mesh_hip_line_x_mm: float, hjc_x_mm: float) -> float:
    """The mesh x of the model's trunk axis (the pelvis origin's vertical), in the frame the mesh hip line is quoted in: the hip line less the model's HJC x."""
    return float(mesh_hip_line_x_mm) - float(hjc_x_mm)


def meta(name: str, mesh_hip_line_x_mm: float, hjc_x_mm: float, length_mm: float) -> dict:
    """What a built trunk body records about its model frame (in the cache's meta)."""
    if not np.isfinite(hjc_x_mm):
        raise StopAndAsk("the model's HJC x (snapshot thigh_right_pos_x) is not available; the trunk bodies cannot be put in the model frame")
    return {KEY: [float(v) for v in model_to_segment_mm(name, hjc_x_mm, length_mm)], "mesh_hip_line_x_mm": float(mesh_hip_line_x_mm), "model_hjc_x_mm": float(hjc_x_mm),
            "mesh_to_model_trunk_shift_mm": mesh_to_model_trunk_shift_mm(mesh_hip_line_x_mm, hjc_x_mm)}


def segment_offset_mm(name: str, seg_meta: dict) -> tuple:
    """The model-to-oracle translation of a built segment. A leg is in its model frame already (zero); a trunk body must carry it from its build, else this stops (a cache older than brief 7)."""
    if KEY in seg_meta:
        return tuple(float(v) for v in seg_meta[KEY])
    if name in TRUNK_BODIES:
        raise StopAndAsk(f"the built {name} has no model frame (it was built before brief 7): rebuild with `fy envelope build`")
    return (0.0, 0.0, 0.0)


def is_trunk(name: str) -> bool:
    return name in TRUNK_BODIES


def describe(name: str, seg_meta: dict) -> str | None:
    """The line every trunk result prints: the frame, the shift applied and where the model's trunk axis sits in the mesh. None for a leg (its frame is the oracle's)."""
    if not is_trunk(name):
        return None
    off = segment_offset_mm(name, seg_meta)
    hip, hjc = seg_meta["mesh_hip_line_x_mm"], seg_meta["model_hjc_x_mm"]
    return (f"frame: model body frame of {name} (origin at {MODEL_ORIGIN[name]}); oracle = model + ({off[0]:.3f}, {off[1]:.3f}, {off[2]:.3f}) mm "
            f"[model HJC x {hjc:.3f} mm; mesh hip line x {hip:.3f} mm; mesh-to-model trunk shift {mesh_to_model_trunk_shift_mm(hip, hjc):.3f} mm]")


def model_to_mesh(seg_meta: dict, name: str, points) -> np.ndarray:
    """Points in the model body frame of `name` -> the conformed mesh frame (mm, x anterior, y from the mesh midline's conformed position, z above the sole)."""
    p = np.asarray(points, float)
    return p + np.asarray(segment_offset_mm(name, seg_meta), float) + np.asarray(seg_meta["origin_xyz"], float)
