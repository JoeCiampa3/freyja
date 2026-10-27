"""Where the sim's trunk stack stands against the mesh trunk centre line (volume-extractor brief 7, item 2). A report; nothing in the sim or the model changes.

The sim side is the MuJoCo model's own forward kinematics: the lumbosacral joint (pelvis origin), the TJC (abdomen origin), the CJC (thorax origin) and the SJC (upper-arm origin) relative to the
right hip joint centre, in the zero pose (`qpos0`) and in the design stance (ADR 0004: the pelvis tilted forward by `stand_pelvis_tilt_deg`, the hips flexed by it, the lumbosacral joint extended by
it; `leanpose.design_stance(..., upright=True)`, so no lean about the ankle: the lean is a rigid rotation of the whole body and not part of the stance's geometry). The mesh side is the area centroid
of the built body's cross-section at the height of the plane, in the oracle's frame, whose origin is on the mesh hip line (the vertical through the hip joint centre) and the mesh midline. Both
are therefore relative to the hip line, and the offset is sim minus mesh: positive x means the sim's stack is ahead of the mesh's centre line. `skin_margin_at_stack_mm` is the skin's signed distance at the sim's stack point on that section
(positive: the stack axis is inside the skin).

A plane is the boundary of two bodies, so in the zero pose both are reported (the section EDGE_MM inside each). In the design stance the stack stands higher (the tilt raises the lumbosacral joint) and
the plane's height is interior to one body. The mesh is not moved: its section is taken at the stance plane's height above the hip centre.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from . import field, foreign

EDGE_MM = 1.0                      # a plane on the boundary of two bodies is sampled this far inside each
FEET = {"foot_right": "ankle_pdflex_right", "foot_left": "ankle_pdflex_left"}     # as sim/scripts/gait.py STANDING_FEET
BODY_ORDER = ("pelvis", "abdomen", "thorax", "head_neck")
SIM_BODIES = {"ljc": "pelvis", "tjc": "abdomen", "cjc": "thorax", "sjc": "upper_arm_right"}      # the model body whose origin is the joint centre
ROUND = 3


def load_model(path=None):
    return foreign.load_model(path)


def zero_qpos(model) -> np.ndarray:
    return np.array(model.qpos0, float)


def _leanpose():
    d = str(foreign.REPO / "sim" / "scripts")
    if d not in sys.path:
        sys.path.insert(0, d)
    import leanpose
    return leanpose


def stance_qpos(model, tilt_deg: float, lean: bool = False) -> np.ndarray:
    """The design stance: the pelvis tilted, the hips flexed and the lumbosacral joint extended by `tilt_deg`, soles flat; without the lean (the default) or with the rigid lean about the ankle
    that puts the whole-body centre of mass over it, as `stand_static` does."""
    return np.array(_leanpose().design_stance(model, float(tilt_deg), FEET, com_x_rel_ankle_m=0.0, upright=not lean).qpos, float)


def sim_stack(model, qpos) -> dict:
    """The joint centres of the trunk stack relative to the right hip joint centre, mm, world axes (x anterior, y left, z up). y is taken from the pelvis origin (the midline).
    `sjc` carries the thorax axis at the SJC's height (on the line through the TJC and CJC origins) as x, y and the shoulder joint centre's own x as `point_x`."""
    import mujoco
    d = mujoco.MjData(model)
    d.qpos[:] = qpos
    mujoco.mj_forward(model, d)
    pos = lambda n: d.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)] * 1000.0      # noqa: E731
    hjc, mid = pos("thigh_right"), pos("pelvis")
    out = {}
    for k, body in SIM_BODIES.items():
        p = pos(body)
        out[k] = {"x": p[0] - hjc[0], "y": p[1] - mid[1], "z": p[2] - hjc[2]}
    f = (out["sjc"]["z"] - out["tjc"]["z"]) / (out["cjc"]["z"] - out["tjc"]["z"])                  # the thorax axis (through the TJC and CJC origins) at the SJC's height
    out["sjc"] = {"x": out["tjc"]["x"] + f * (out["cjc"]["x"] - out["tjc"]["x"]), "y": out["tjc"]["y"] + f * (out["cjc"]["y"] - out["tjc"]["y"]), "z": out["sjc"]["z"],
                  "point_x": pos("upper_arm_right")[0] - hjc[0]}
    return out


def section_centroid(seg: field.Segment, station_mm: float) -> dict:
    """Area centroid (x, y, segment frame) of the skin's cross-section {sd >= 0} inside the segment region at a station."""
    sec = seg.section(station_mm)
    m = sec.mask(0.0)
    X, Y = np.meshgrid(sec.x, sec.y, indexing="ij")
    return {"x": float(X[m].mean()), "y": float(Y[m].mean()), "area_mm2": float(m.sum() * field.SECTION_MM ** 2)}


def _bodies(cache: Path) -> dict:
    out = {}
    for n in BODY_ORDER:
        seg = field.Segment.load(Path(cache) / f"{n}.npz")
        if "mesh_hip_line_x_mm" not in seg.meta:
            raise RuntimeError(f"the built {n} has no model frame: rebuild with `fy envelope build`")
        z_top = float(seg.meta["origin_xyz"][2])
        out[n] = {"seg": seg, "z_top": z_top, "z_bottom": z_top - seg.length}
    return out


def mesh_at(bodies: dict, z_conf: float) -> list:
    """The cross-section centroids of every body that contains the height `z_conf` (conformed mesh frame), each sampled at least EDGE_MM inside its own ends."""
    out = []
    for n in BODY_ORDER:
        b = bodies[n]
        if b["z_bottom"] - 1e-6 <= z_conf <= b["z_top"] + 1e-6:
            z = float(np.clip(z_conf, b["z_bottom"] + EDGE_MM, b["z_top"] - EDGE_MM))
            c = section_centroid(b["seg"], b["z_top"] - z)
            out.append({"body": n, "station_mm": b["z_top"] - z, "centroid_x_mm": c["x"], "centroid_y_mm": c["y"], "area_mm2": c["area_mm2"]})
    return out


def _pose(model, bodies, qpos, hjc_z) -> dict:
    stack = sim_stack(model, qpos)
    planes = {}
    for k, s in stack.items():
        z_conf = hjc_z + s["z"]
        mesh = mesh_at(bodies, z_conf)
        for e in mesh:
            e["offset_x_mm"] = s["x"] - e["centroid_x_mm"]
            e["offset_y_mm"] = s["y"] - e["centroid_y_mm"]
            e["skin_margin_at_stack_mm"] = float(bodies[e["body"]]["seg"].signed_distance([[s["x"], s["y"], -e["station_mm"]]])[0])      # inside the skin if positive, at the stack axis
        planes[k] = {"sim": {kk: float(v) for kk, v in s.items()}, "height_above_hjc_mm": float(s["z"]), "mesh": mesh}
    return {"planes": planes}


def _round(o):
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v) for v in o]
    return round(float(o), ROUND) if isinstance(o, (float, np.floating)) else o


def report(root, cache, tilt_deg=None, model_path=None) -> dict:
    """The offsets in the zero pose and in the design stance. `tilt_deg` defaults to the snapshot's stand_pelvis_tilt_deg."""
    from . import sheet
    root = Path(root)
    snap = sheet.read_snapshot(root / "params/snapshot.csv")
    tilt = float(snap["stand_pelvis_tilt_deg"] if tilt_deg is None else tilt_deg)
    model = load_model(model_path)
    bodies = _bodies(cache)
    pel = bodies["pelvis"]["seg"].meta
    hjc_z = bodies["pelvis"]["z_bottom"]                                  # the pelvis stands on the hip-centre plane
    zero = _pose(model, bodies, zero_qpos(model), hjc_z)
    stance = _pose(model, bodies, stance_qpos(model, tilt), hjc_z)
    stance["tilt_deg"] = tilt
    stance["rise_mm"] = stance["planes"]["ljc"]["sim"]["z"] - zero["planes"]["ljc"]["sim"]["z"]
    lean = _pose(model, bodies, stance_qpos(model, tilt, lean=True), hjc_z)                  # a sensitivity: the stance as stand_static holds it, the whole body leaned about the ankle
    lean["tilt_deg"] = tilt
    lean["rise_mm"] = lean["planes"]["ljc"]["sim"]["z"] - zero["planes"]["ljc"]["sim"]["z"]
    rep = {"schema": "trunk-offsets/1", "mesh_hip_line_x_mm": pel["mesh_hip_line_x_mm"], "model_hjc_x_mm": pel["model_hjc_x_mm"], "poses": {"zero": zero, "stance": stance, "stance_lean": lean},
           "definition": "offset = sim - mesh, mm, relative to the hip line (x anterior) and the midline (y left); sim = MuJoCo forward kinematics of the lumbosacral joint, TJC, CJC and the SJC "
                         "(the thorax stack axis at the SJC's height; sjc.point_x is the joint itself); mesh = area centroid of the built body's section at that height"}
    return _round(rep)


def format_report(rep: dict) -> str:
    lines = [f"mesh hip line x {rep['mesh_hip_line_x_mm']:.3f} mm, model HJC x {rep['model_hjc_x_mm']:.3f} mm (offset = sim - mesh, mm; x anterior, y left, both from the hip line / midline)"]
    for pose in ("zero", "stance", "stance_lean"):
        p = rep["poses"][pose]
        head = {"zero": "zero pose", "stance": "design stance", "stance_lean": "design stance with the lean about the ankle (sensitivity; world axes)"}[pose]
        if pose != "zero":
            head += f" (pelvis tilt {p['tilt_deg']:g} deg, lumbosacral extension {p['tilt_deg']:g} deg; the lumbosacral joint stands {p['rise_mm']:.2f} mm higher)"
        lines.append(f"{head}:")
        lines.append(f"  {'plane':5s} {'z':>8s} {'sim x':>8s} {'body':10s} {'mesh x':>8s} {'dx':>8s} {'mesh y':>8s} {'dy':>8s} {'skin@stack':>10s}")
        for k, pl in p["planes"].items():
            for e in pl["mesh"]:
                lines.append(f"  {k:5s} {pl['height_above_hjc_mm']:8.2f} {pl['sim']['x']:8.2f} {e['body']:10s} {e['centroid_x_mm']:8.2f} {e['offset_x_mm']:8.2f} {e['centroid_y_mm']:8.2f} {e['offset_y_mm']:8.2f} {e['skin_margin_at_stack_mm']:8.2f}")
    return "\n".join(lines)
