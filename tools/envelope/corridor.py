"""The corridor sweep (volume-extractor brief 8, item 6): the largest circle that a vertical column can have at each station of the trunk, from the lumbosacral joint to the CJC.

In the mesh frame (the trunk bodies' own frame: origin on the hip line, midline y = 0, x anterior), for a vertical axis at x = d, y = 0 and every 2 mm layer of the abdomen (LJC to TJC) and
the thorax (TJC to CJC): the radius of the largest circle centred on the axis that lies inside {skin sd >= t} (t = 5 mm, the design shell): the 2-D distance from the axis to the edge of that
section, 0 when the axis lies outside it. The column's diameter is twice the least such radius over the stations; the best d is the one that maximises it. The sim's stack axis, in the same
x (relative to the right hip joint centre, which is the hip line), is read from `trunk_offsets.json`; the forward shift the best d implies is the best d less that x. Nothing in the sim, the
sheet or the model changes.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import field

D_RANGE_MM = (-60.0, 60.0)
D_STEP_MM = 5.0
STATION_STEP_MM = 10.0                    # the profile that is reported; the minimum is over every 2 mm layer
BODIES = ("abdomen", "thorax")            # LJC to TJC, TJC to CJC


def d_values(lo=D_RANGE_MM[0], hi=D_RANGE_MM[1], step=D_STEP_MM):
    return [float(x) for x in np.arange(lo, hi + step / 2, step)]


def _layer_radius(seg: field.Segment, k: int, t: float, xs: np.ndarray, y0: float = 0.0) -> np.ndarray:
    """Radius (mm) of the largest circle centred at (x, y0) for each x in xs, inside {sd >= t} & region in voxel layer k; 0 where the centre is not inside."""
    m = (seg.sd[:, :, k] >= t) & seg.region[:, :, k]
    if not m.any():
        return np.zeros(len(xs))
    d = ndimage.distance_transform_edt(m, sampling=seg.h) - seg.h / 2
    ix = np.clip(np.floor((xs - seg.o[0]) / seg.h).astype(int), 0, m.shape[0] - 1)
    iy = int(np.clip(np.floor((y0 - seg.o[1]) / seg.h), 0, m.shape[1] - 1))
    r = np.where(m[ix, iy], d[ix, iy], 0.0)
    return np.maximum(r, 0.0)


def profile(segs: dict, t: float = 5.0, ds=None) -> dict:
    """The radius of the corridor at every layer of the given bodies (a dict name -> segment in the order from the LSJ up), for every d. Returns d, the layer's height in the first
    body's frame is not needed: each layer carries its body and its station below that body's top, and its distance above the lowest plane (the LSJ)."""
    ds = np.asarray(d_values() if ds is None else ds, float)
    rows = []
    z_above = 0.0
    for name in segs:                                                           # lowest body first (abdomen, then thorax)
        seg = segs[name]
        zl = seg.centres(2)
        keep = [k for k in range(len(zl)) if seg.z_top - seg.length <= zl[k] <= seg.z_top]
        for k in keep:                                                          # z increases with k: bottom to top
            r = _layer_radius(seg, k, t, ds)
            rows.append({"body": name, "station_mm": float(seg.z_top - zl[k]), "height_above_lsj_mm": float(z_above + (zl[k] - (seg.z_top - seg.length))), "radius_mm": r})
        z_above += seg.length
    return {"d_mm": ds, "rows": rows, "t_mm": t, "heights_total_mm": z_above}


def best(prof: dict) -> dict:
    """Per d the least diameter over the stations and where it is; the d that maximises it."""
    R = np.array([r["radius_mm"] for r in prof["rows"]])               # (layers, d)
    mins = R.min(axis=0)
    arg = R.argmin(axis=0)
    table = [{"d_mm": float(d), "min_diameter_mm": float(2 * mins[i]), "station": {"body": prof["rows"][arg[i]]["body"], "station_mm": prof["rows"][arg[i]]["station_mm"],
                                                                                  "height_above_lsj_mm": prof["rows"][arg[i]]["height_above_lsj_mm"]}} for i, d in enumerate(prof["d_mm"])]
    i = int(np.argmax(mins))
    return {"table": table, "best_d_mm": float(prof["d_mm"][i]), "best_min_diameter_mm": float(2 * mins[i]), "best_station": table[i]["station"]}


def profile_at(prof: dict, d: float, step=STATION_STEP_MM) -> list:
    """The diameter along the column at x = d, every `step` mm of height above the LSJ."""
    i = int(np.argmin(np.abs(prof["d_mm"] - d)))
    out, nxt = [], 0.0
    for r in prof["rows"]:
        if r["height_above_lsj_mm"] + 1e-9 >= nxt:
            out.append({"height_above_lsj_mm": round(r["height_above_lsj_mm"], 1), "body": r["body"], "station_mm": round(r["station_mm"], 1), "diameter_mm": round(float(2 * r["radius_mm"][i]), 2)})
            nxt += step
    return out


def sim_axes(offsets: dict) -> dict:
    """The sim's stack axis x (mm, relative to the right hip joint centre = the hip line) at the LJC, TJC and CJC for the zero pose, the design stance and the stance with the ankle lean,
    from `trunk_offsets.json` (`fy envelope offsets`: poses.<pose>.planes.<plane>.sim.x)."""
    return {pose: {plane.upper(): float(v["sim"]["x"]) for plane, v in d["planes"].items() if plane in ("ljc", "tjc", "cjc")} for pose, d in offsets["poses"].items()}


def forward_shift(best_d: float, axes: dict) -> dict:
    """The best d less the sim's axis x, per pose and plane: how far the column would have to move forward of the sim's stack (positive = anterior)."""
    return {pose: {plane: float(best_d - x) for plane, x in planes.items()} for pose, planes in axes.items()}
