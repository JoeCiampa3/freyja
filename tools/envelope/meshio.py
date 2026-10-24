"""MakeHuman OBJ reading, the topology check against the reference mesh, and the MakeHuman -> sheet frame map."""
from __future__ import annotations

from pathlib import Path

import numpy as np

BODY_VERTICES = 13380
DM_TO_MM = 100.0
# MakeHuman: x = subject's left, y = up, z = anterior. Sheet (MuJoCo): x anterior, y left, z up. (x, y, z)_mh -> (z, x, y)_mh.
MH_TO_SHEET = np.array([[0.0, 0.0, 1.0],
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0]])
assert np.isclose(np.linalg.det(MH_TO_SHEET), 1.0)


def read_obj(path):
    """(vertices (n, 3) float in file units, polygons: list of 0-based vertex-id tuples)."""
    v, polys = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("v "):
                p = line.split()
                v.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("f "):
                polys.append(tuple(int(t.split("/")[0]) - 1 for t in line.split()[1:]))
    return np.array(v, dtype=float), polys


def topology_difference(path, reference) -> str | None:
    """None when `path` has the reference's vertex count and identical faces; else a sentence naming the first difference."""
    v, f = read_obj(path)
    rv, rf = read_obj(reference)
    if len(v) != len(rv):
        return f"{len(v)} vertices, reference has {len(rv)}"
    for i, (a, b) in enumerate(zip(f, rf)):
        if a != b:
            return f"face {i}: {a} vs reference {b}"
    if len(f) != len(rf):
        return f"{len(f)} faces, reference has {len(rf)}"
    return None


def to_sheet_mm(points_dm_mh):
    """Points in MakeHuman axes and decimeters -> sheet (MuJoCo) axes and millimeters."""
    return np.asarray(points_dm_mh, dtype=float) @ MH_TO_SHEET.T * DM_TO_MM
