"""The clearance oracle: do rigid shapes, posed in a segment frame, fit inside the segment's skin, and where do they bind.

Shapes are sampled surfaces (capsule, cylinder, box; local frame centred, axis along z). Margin is the minimum signed distance to the skin
over the sampled surface, positive when inside; it is not a distance to a cut plane. The slab ends are reported apart as `slab_overrun_mm`.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial.transform import Rotation

from . import field

SAMPLE_MM = 1.0        # surface sampling of the shapes: a margin is conservative to about this much on curved surfaces
POSE_COLUMNS = ("tx", "ty", "tz", "rx", "ry", "rz")   # translation mm; rotation deg, extrinsic x-y-z about the segment axes (omitted: 0)


def _ring(r, z, n=None):
    n = n or max(8, int(np.ceil(2 * np.pi * r / SAMPLE_MM)))
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack([r * np.cos(a), r * np.sin(a), np.full(n, z)])


def _disc(r, z):
    pts = [[0.0, 0.0, z]]
    for rr in np.arange(SAMPLE_MM, r + 1e-9, SAMPLE_MM):
        pts.extend(_ring(rr, z))
    pts.extend(_ring(r, z))
    return np.array(pts)


def sample_shape(shape: dict) -> np.ndarray:
    """Surface points (n, 3) of one shape in its own frame, with its optional `offset` [x, y, z] and `rpy_deg` applied."""
    kind = shape.get("type")
    if kind in ("cylinder", "capsule"):
        r = float(shape["radius"]) if "radius" in shape else float(shape["diameter"]) / 2
        half = float(shape["length"]) / 2
        zs = np.linspace(-half, half, max(2, int(np.ceil(2 * half / SAMPLE_MM)) + 1))
        parts = [np.vstack([_ring(r, z) for z in zs])]
        if kind == "cylinder":
            parts += [_disc(r, -half), _disc(r, half)]
        else:
            for sign in (-1, 1):
                for ang in np.linspace(0, np.pi / 2, max(2, int(np.ceil(np.pi / 2 * r / SAMPLE_MM)) + 1))[1:]:
                    rr, dz = r * np.cos(ang), r * np.sin(ang)
                    parts.append(_ring(rr, sign * (half + dz)) if rr > 1e-9 else np.array([[0.0, 0.0, sign * (half + dz)]]))
        pts = np.vstack(parts)
    elif kind == "box":
        hx, hy, hz = (float(x) for x in shape["half"])
        gx, gy, gz = (np.linspace(-h, h, max(2, int(np.ceil(2 * h / SAMPLE_MM)) + 1)) for h in (hx, hy, hz))
        faces = []
        for sgn in (-1, 1):
            X, Y = np.meshgrid(gx, gy, indexing="ij"); faces.append(np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, sgn * hz)]))
            X, Z = np.meshgrid(gx, gz, indexing="ij"); faces.append(np.column_stack([X.ravel(), np.full(X.size, sgn * hy), Z.ravel()]))
            Y, Z = np.meshgrid(gy, gz, indexing="ij"); faces.append(np.column_stack([np.full(Y.size, sgn * hx), Y.ravel(), Z.ravel()]))
        pts = np.vstack(faces)
    else:
        raise ValueError(f"unknown shape type {kind!r} (capsule, cylinder, box)")
    if "rpy_deg" in shape:
        pts = pts @ Rotation.from_euler("xyz", shape["rpy_deg"], degrees=True).as_matrix().T
    if "offset" in shape:
        pts = pts + np.asarray(shape["offset"], float)
    return pts


def read_shapes(path) -> list:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    shapes = doc["shapes"] if isinstance(doc, dict) else doc
    for i, s in enumerate(shapes):
        s.setdefault("name", f"shape{i}")
    return shapes


def read_poses(path) -> np.ndarray:
    """(n, 6) array of tx, ty, tz, rx, ry, rz from a CSV with a header; tx, ty, tz are required, the rotations default to 0."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(line for line in fh if not line.startswith("#"))]
    if not rows or not all(c in rows[0] for c in POSE_COLUMNS[:3]):
        raise ValueError(f"{path}: poses need the columns tx, ty, tz (and optionally rx, ry, rz); got {list(rows[0]) if rows else 'no rows'}")
    return np.array([[float(r.get(c, 0) or 0) for c in POSE_COLUMNS] for r in rows])


def pose_points(pts, pose) -> np.ndarray:
    R = Rotation.from_euler("xyz", pose[3:], degrees=True).as_matrix()
    return pts @ R.T + pose[:3]


def clearance(seg: field.Segment, shapes, poses, required_mm: float = 0.0) -> dict:
    """Margin of the shapes at every pose. Returns margin_mm (the minimum over poses and shapes), pose_index, shape, station_mm and
    point_mm (segment frame) where it binds, margins_mm per pose, slab_overrun_mm (the largest protrusion beyond the slab planes over all
    poses) and feasible (margin >= required_mm and no slab overrun)."""
    poses = np.atleast_2d(np.asarray(poses, float))
    if poses.shape[1] == 3:
        poses = np.hstack([poses, np.zeros((len(poses), 3))])
    samples = [(s.get("name", f"shape{i}"), sample_shape(s)) for i, s in enumerate(shapes)]
    best = None
    margins, overruns = [], []
    z_top, z_bot = seg.z_top, seg.z_top - seg.length
    for pi, pose in enumerate(poses):
        pm = np.inf
        over = 0.0
        for name, pts in samples:
            P = pose_points(pts, pose)
            sd = seg.signed_distance(P)
            j = int(np.argmin(sd))
            over = max(over, float(P[:, 2].max() - z_top), float(z_bot - P[:, 2].min()))
            pm = min(pm, float(sd[j]))
            if best is None or sd[j] < best["margin_mm"]:
                best = {"margin_mm": float(sd[j]), "pose_index": pi, "shape": name, "station_mm": float(z_top - P[j, 2]), "point_mm": [float(x) for x in P[j]]}
        margins.append(pm)
        overruns.append(max(over, 0.0))
    best["margins_mm"] = margins
    best["slab_overrun_mm"] = max(overruns)
    best["slab_overruns_mm"] = overruns
    best["required_mm"] = required_mm
    best["feasible"] = bool(best["margin_mm"] >= required_mm and best["slab_overrun_mm"] <= 1e-9)
    return best
