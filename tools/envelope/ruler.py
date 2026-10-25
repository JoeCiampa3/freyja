"""MakeHuman Ruler measures (`data/makehuman/ruler_measures.json`): vertex lists on the body mesh. Lists of two are chords; longer lists are closed
polylines. The lists belong to the subject's left leg; the mesh is left-right symmetric to under 0.5% in section area, so heights and lengths carry to
the right leg and a centroid mirrors by y -> -y."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PATH = "data/makehuman/ruler_measures.json"
KEYS = {"knee": "measure/measure-knee-circ-decr|incr", "ankle": "measure/measure-ankle-circ-decr|incr", "calf": "measure/measure-calf-circ-decr|incr",
        "thigh": "measure/measure-thigh-circ-decr|incr", "upperleg_height": "measure/measure-upperleg-height-decr|incr",
        "lowerleg_height": "measure/measure-lowerleg-height-decr|incr"}


def load(root: Path) -> dict:
    from .sheet import StopAndAsk
    p = root / PATH
    if not p.exists():
        raise StopAndAsk(f"{PATH} is missing (the Ruler.Measures vertex lists)")
    return json.loads(p.read_text(encoding="utf-8"))["measures"]


def loop_stats(V, ids) -> dict:
    """Height (mean z), spread, closed-polyline length, plane-fit tilt from horizontal, and centroid (x, y) of a Ruler loop, from the body vertices V
    (sheet axes, mm, z above the sole)."""
    P = np.asarray(V)[list(ids)]
    c = P.mean(axis=0)
    length = float(np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1).sum())
    n = np.linalg.svd(P - c)[2][2]
    return {"n": len(P), "z_mm": float(c[2]), "z_min_mm": float(P[:, 2].min()), "z_max_mm": float(P[:, 2].max()), "length_mm": length,
            "tilt_deg": float(np.degrees(np.arccos(min(1.0, abs(n[2]))))), "centroid_xy_mm": [float(c[0]), float(c[1])]}


def chord_stats(V, ids) -> dict:
    P = np.asarray(V)[list(ids)]
    return {"top_z_mm": float(P[:, 2].max()), "bottom_z_mm": float(P[:, 2].min()), "length_mm": float(np.linalg.norm(P[0] - P[1]))}


def all_stats(V, measures) -> dict:
    out = {}
    for name in ("knee", "ankle", "calf", "thigh"):
        out[name] = loop_stats(V, measures[KEYS[name]])
    for name in ("upperleg_height", "lowerleg_height"):
        out[name] = chord_stats(V, measures[KEYS[name]])
    return out
