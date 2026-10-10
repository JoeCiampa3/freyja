"""
Run metrics (CONVENTIONS section 6, docs/schemas/run-summary-1.schema.json): pure functions from time
series to the numbers a run summary carries. No MuJoCo, no files, so every definition is testable
against hand-computed arrays (tests/test_metrics.py).

Window handling is the caller's job: pass only the steps inside the measurement window.
"""
from __future__ import annotations

import math

import numpy as np

LIMIT_TOL_DEG = 0.1  # deg. A step within this of either joint limit counts as a limit hit (the brief's definition).
LOADED_N = 1.0  # N. Below this normal force the tangential/normal ratio is noise, so the step is ignored.
COLLINEAR_M2 = 1e-12  # m^2. Twice the triangle area below which three contact points count as collinear
#                       (a 1 um sliver on a 0.1 m foot); the hull is then a segment and the margin cannot be positive.


def _series(name, values, n=None):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or a.size == 0:
        raise ValueError(f"{name}: need a non-empty 1-D series")
    if n is not None and a.size != n:
        raise ValueError(f"{name}: length {a.size} differs from {n}")
    return a


def joint_metrics(angle_rad, vel_rad_s, torque_nm, torque_source, limit_rad=None) -> dict:
    """One joint over the window, in the model's own sign convention. limit_rad is (lower, upper) or None
    for an unlimited joint. Returns the `joints.<name>` object of run-summary/1."""
    q = _series("angle", angle_rad)
    qd = _series("velocity", vel_rad_s, q.size)
    tau = _series("torque", torque_nm, q.size)
    if limit_rad is None:
        rom_limit, hit = None, None
    else:
        lo, hi = float(limit_rad[0]), float(limit_rad[1])
        tol = math.radians(LIMIT_TOL_DEG)
        rom_limit = [math.degrees(lo), math.degrees(hi)]
        hit = float(np.mean((q <= lo + tol) | (q >= hi - tol)))
    return {
        "torque_source": torque_source,
        "torque_peak_nm": float(np.max(np.abs(tau))),
        "torque_rms_nm": float(np.sqrt(np.mean(tau ** 2))),
        "speed_peak_rad_s": float(np.max(np.abs(qd))),
        "power_peak_w": float(np.max(np.abs(tau * qd))),
        "rom_used_deg": [float(np.degrees(q.min())), float(np.degrees(q.max()))],
        "rom_limit_deg": rom_limit,
        "limit_hit_fraction": hit,
    }


def foot_metrics(normal_n, tangential_n) -> dict:
    """One foot over the window: `normal_n` and `tangential_n` are the per-step force summed over all
    contacts of the foot body against the floor. Returns the `contacts.<foot>` object."""
    fn = _series("normal force", normal_n)
    ft = _series("tangential force", tangential_n, fn.size)
    loaded = fn >= LOADED_N
    ratio = float(np.max(ft[loaded] / fn[loaded])) if loaded.any() else None
    return {"normal_force_peak_n": float(fn.max()), "friction_ratio_peak": ratio}


# ------------------------------------------------------------------------------ support polygon

def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points) -> list:
    """Andrew's monotone chain. Counter-clockwise vertices without collinear or duplicate points; fewer
    than three when the input is a point or lies on a line (within COLLINEAR_M2)."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 2:
        return pts
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= COLLINEAR_M2:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= COLLINEAR_M2:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:  # every point on one line: the chain doubles back on itself
        return [pts[0], pts[-1]]
    return hull


def _dist_to_segment(p, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def support_margin(contact_xy, com_xy) -> float:
    """Signed distance from the CoM's ground projection to the boundary of the convex hull of the
    floor-contact points: positive inside, zero on the boundary, negative outside. A hull of fewer than
    three non-collinear points (a point, a segment, nothing) is never positive: minus the distance to it.
    No contact points at all gives -inf."""
    hull = convex_hull(contact_xy)
    if not hull:
        return -math.inf
    p = (float(com_xy[0]), float(com_xy[1]))
    if len(hull) < 3:
        a, b = hull[0], hull[-1]
        return -_dist_to_segment(p, a, b)
    edges = [(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull))]
    inside = all(_cross(a, b, p) >= 0 for a, b in edges)
    if inside:
        return min(_cross(a, b, p) / math.dist(a, b) for a, b in edges)
    return -min(_dist_to_segment(p, a, b) for a, b in edges)


def min_support_margin(steps):
    """Minimum margin over (contact_xy, com_xy) steps that have floor contact; None if no step has any."""
    margins = [support_margin(c, com) for c, com in steps if len(c) > 0]
    return float(min(margins)) if margins else None
