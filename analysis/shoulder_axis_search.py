"""Where the shoulder gimbal's fixed axis points (docs/briefs/ariadne/shoulder-axis-search-brief.md).

A three-axis gimbal with intersecting axes: axis 1 fixed in the thorax along u1, axis 2 perpendicular to axis 1 and axis 3, axis 3 along the
humerus. It is singular where the humerus is parallel to the line +/-u1. This script finds the u1 whose singular line lies farthest from every
humeral direction Freyja must reach. Directions and kinematics only: no model change, no collision, no actuator, no load.

Frame: the thorax body frame of sim/models/freyja.xml (x anterior, y left, z up). The humeral direction d is the unit vector from the shoulder
joint centre to the elbow joint centre. Angles in degrees at the interface, radians inside.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

INPUTS = "data/shoulder/inputs/axis_search.yaml"
OUT = "data/shoulder/axis_search.json"
SIDES = ("right", "left")
ROM_ADDRESSES = ("snapshot#/shoulder_flexion", "snapshot#/shoulder_extension", "snapshot#/shoulder_abduction")


def read_rom(root: Path = ROOT) -> dict:
    """The three ROM ends, read through the thread's address resolution (never typed). Raises naming the address that does not resolve."""
    from thread import build as tb
    b = tb.build_root(Path(root))
    out = {}
    for a in ROM_ADDRESSES:
        ok, v = b.resolve(a)
        if not ok:
            raise ValueError(f"{a} does not resolve")
        out[a] = float(v)
    return out


# ---- vectors ------------------------------------------------------------------------------------------------------------------------

def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def rot(axis, angle: float) -> np.ndarray:
    """Rotation matrix about a unit axis by `angle` radians (Rodrigues)."""
    k = np.asarray(axis, dtype=float)
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)


def mirror(v) -> np.ndarray:
    """The y-mirror (sagittal plane) of a vector or an array of vectors."""
    return np.asarray(v, dtype=float) * np.array([1.0, -1.0, 1.0])


# ---- the humeral direction, ISB humerothoracic Y-X-Y (Wu et al. 2005) -------------------------------------------------------------

def d_of(phi_deg, theta_deg, side: str = "right") -> np.ndarray:
    """d(phi, theta) = (sin t sin p, -sin t cos p, -cos t) for the right arm; the left arm is its y-mirror. theta is elevation from straight
    down; phi = 0 is abduction in the frontal plane, +90 forward flexion, negative behind the frontal plane. Broadcasts."""
    p, t = np.radians(np.asarray(phi_deg, float)), np.radians(np.asarray(theta_deg, float))
    d = np.stack([np.sin(t) * np.sin(p), -np.sin(t) * np.cos(p), -np.cos(t)], axis=-1)
    return d if side == "right" else mirror(d)


def phi_theta(d, side: str = "right"):
    """(phi, theta) in degrees of a unit direction; phi in (-180, 180]. phi is undefined at theta = 0 or 180 and returned as 0 there."""
    d = np.asarray(d, float)
    if side != "right":
        d = mirror(d)
    theta = np.degrees(np.arccos(np.clip(-d[..., 2], -1.0, 1.0)))
    phi = np.degrees(np.arctan2(d[..., 0], -d[..., 1]))
    if np.ndim(phi) == 0:
        return float(phi), float(theta)
    return phi, theta


# ---- the gimbal ---------------------------------------------------------------------------------------------------------------------

def gimbal_frame(u1):
    """(d0, u2): d0 the unit projection of straight down onto the plane perpendicular to u1 (the zero pose), u2 = u1 x d0 (axis 2 at q1 = 0)."""
    u1 = np.asarray(u1, float)
    down = np.array([0.0, 0.0, -1.0])
    p = down - (down @ u1) * u1
    n = np.linalg.norm(p)
    if n < 1e-12:
        raise ValueError("u1 is vertical: the zero pose d0 is undefined")
    d0 = p / n
    return d0, np.cross(u1, d0)


def gimbal_fk(u1, q1: float, q2: float) -> np.ndarray:
    """d = R(u1, q1) R(u2, q2) d0. Since u2 x d0 = -u1, R(u2, q2) d0 = cos q2 d0 - sin q2 u1: positive q2 tilts the arm toward -u1."""
    d0, u2 = gimbal_frame(u1)
    return rot(u1, q1) @ (rot(u2, q2) @ d0)


def gimbal_ik(u1, d):
    """(q1, q2) in radians on the branch q2 in [-pi/2, pi/2]: q2 = -asin(d . u1), q1 = atan2(d . u2, d . d0). Undefined (q1 arbitrary) when d
    is parallel to u1."""
    u1, d = np.asarray(u1, float), np.asarray(d, float)
    d0, u2 = gimbal_frame(u1)
    q2 = -math.asin(max(-1.0, min(1.0, float(d @ u1))))
    q1 = math.atan2(float(d @ u2), float(d @ d0))
    return q1, q2


def axis_matrix(u1, q1: float, q2: float) -> np.ndarray:
    """The orientation Jacobian of the three intersecting revolute axes: the unit axes in the thorax frame as columns [u1, u2(q1), d]."""
    _, u2 = gimbal_frame(u1)
    return np.column_stack([np.asarray(u1, float), rot(u1, q1) @ u2, gimbal_fk(u1, q1, q2)])


def sigma_min(u1, d):
    """sqrt(1 - |u1 . d|): the least singular value of [u1, u2, d] (the others are 1 and sqrt(1 + |u1 . d|)). Broadcasts over d."""
    c = np.abs(np.asarray(d, float) @ np.asarray(u1, float))
    return np.sqrt(np.clip(1.0 - c, 0.0, None))


# ---- constants (each fixed before any search ran) -----------------------------------------------------------------------------------

ARC_STEP_DEG = 0.5            # brief: A1 to A3 at 0.5 deg; S1, also an elevation arc, takes the same step
B1_STEP_DEG = 1.0             # brief: B1 on a 1 deg grid with edges
SEEDS = (20_000, 80_000)      # brief V5: the global search seeded from both; the reported optimum is the 80 000-seeded one
BASIN_SEP_DEG = 20.0          # brief: distinct local optima are more than 20 deg apart (line angle)
N_BASINS = 3                  # brief: up to three
BINDING_BAND_DEG = 0.5        # brief: binding directions are every point within 0.5 deg of the floor's angular distance
SINGULAR_EXCLUDE_DEG = 1.0    # brief V3: directions within 1 deg of +/-u1 are excluded from the round trip, and counted
PATTERN_DIRS = 16             # refinement: compass directions in the tangent plane, 22.5 deg apart
PATTERN_H0_DEG = 1.0          # refinement: first step, the 20 000-point grid's spacing (sqrt(2 pi / 20000) = 1.01 deg)
PATTERN_TOL_RAD = 1e-10       # refinement: stop when the step is below this; 6e-9 deg, far below V5's 0.1 deg
POLISH_K = 12                 # vertex polish: the cap's rim points are sought among the 12 nearest directions (220 triples)
POLISH_RADIUS_DEG = 1.0       # vertex polish: a circumcentre further than this from the current point is not a local move
ACTIVE_TOL = 1e-12            # |u1 . d| within this of the largest counts as active in the local-maximum certificate
POLISH_SWITCH_RAD = 1e-6      # the coarse pattern search hands over to the vertex polish below this step (5.7e-5 deg): compass steps near
                              # a vertex overshoot and gain about 1e-15 each (the coordinate-axes test stalled at 1.3e-7 rad)
PATTERN_MAX_ITER = 20_000     # a pattern search that has not reached its tolerance by then hands back to refine(), which polishes
IMPROVE_TOL = 1e-15          # a polish step must lower max |u1 . d| by more than this: float noise in g is about 1e-16 (1 ulp at 0.9);
                              # 1e-15 is far below V5's floor tolerance (1e-6 in sigma, about 7e-7 in g at the optimum)
ROUND = 12                    # significant digits kept in the output file: finer than every gate's tolerance (1e-9), coarser than float noise
CHUNK = 256                   # rows per matrix product, for memory only
MAP_DIR = "data/shoulder/map"  # gitignored


# ---- the required set ---------------------------------------------------------------------------------------------------------------

def arc_values(end: float, step: float) -> np.ndarray:
    """0, step, 2 step, ... up to `end`, with `end` itself appended when it is off the step (172 is on it; 57.3 and 182.7 are not)."""
    n = int(math.floor(end / step + 1e-9))
    v = [i * step for i in range(n + 1)]
    if end - v[-1] > 1e-9:
        v.append(end)
    return np.array(v)


class Entry:
    """A named set of required directions with the parameters that place each one."""

    def __init__(self, name: str, params: dict, phi, theta, side: str):
        self.name, self.params = name, {k: np.asarray(v, float) for k, v in params.items()}
        self.phi, self.theta = np.asarray(phi, float), np.asarray(theta, float)
        self.d = d_of(self.phi, self.theta, side)

    def label(self, i: int) -> dict:
        return {"entry": self.name, **{k: float(v[i]) for k, v in self.params.items()}}


def read_inputs(root: Path = ROOT) -> dict:
    import yaml
    return yaml.safe_load((Path(root) / INPUTS).read_text(encoding="utf-8"))


def entries(rom: dict, inputs: dict, side: str = "right", b1_widen_deg: float = 0.0) -> dict:
    """Every required-set entry, basis (A1 to A3, B1) and sensitivity (S1 to S3), keyed by name. `b1_widen_deg` widens B1's plane bounds at
    each end (T4)."""
    flex, ext, abd = (rom[a] for a in ROM_ADDRESSES)
    out = {}
    b = arc_values(flex, ARC_STEP_DEG)
    out["A1"] = Entry("A1", {"beta_deg": b}, np.full_like(b, 90.0), b, side)        # flexion: d = (sin b, 0, -cos b)
    b = arc_values(ext, ARC_STEP_DEG)
    out["A2"] = Entry("A2", {"beta_deg": b}, np.full_like(b, -90.0), b, side)       # extension: d = (-sin b, 0, -cos b)
    a = arc_values(abd, ARC_STEP_DEG)
    out["A3"] = Entry("A3", {"alpha_deg": a}, np.zeros_like(a), a, side)            # abduction: d = (0, -sin a, -cos a)
    B = inputs["required"]["B1"]
    p_lo, p_hi = B["plane_min"]["value"] - b1_widen_deg, B["plane_max"]["value"] + b1_widen_deg
    t_lo, t_hi = B["elevation_min"]["value"], B["elevation_max"]["value"]
    P, T = np.meshgrid(np.arange(p_lo, p_hi + 1e-9, B1_STEP_DEG), np.arange(t_lo, t_hi + 1e-9, B1_STEP_DEG), indexing="ij")
    out["B1"] = Entry("B1", {"phi_deg": P.ravel(), "theta_deg": T.ravel()}, P.ravel(), T.ravel(), side)
    S = inputs["sensitivity"]
    t = arc_values(rom[S["S1"]["elevation_max"]["address"]], ARC_STEP_DEG)
    out["S1"] = Entry("S1", {"theta_deg": t}, np.full_like(t, float(S["S1"]["plane"]["value"])), t, side)
    for name in ("S2", "S3"):
        p, t = float(S[name]["plane"]["value"]), float(S[name]["elevation"]["value"])
        out[name] = Entry(name, {"phi_deg": [p], "theta_deg": [t]}, [p], [t], side)
    return out


BASIS = ("A1", "A2", "A3", "B1")


def stack(es: dict, names) -> np.ndarray:
    return np.vstack([es[n].d for n in names])


def unique_dirs(D: np.ndarray) -> np.ndarray:
    """The distinct directions (to 13 decimals): repeated points (theta = 0 in every B1 column, the arcs' shared start) change no floor."""
    return np.unique(np.round(D, 13), axis=0)


# ---- the floor ----------------------------------------------------------------------------------------------------------------------

def gmax(U, D) -> np.ndarray:
    """max over the rows d of D of |u . d|, for each row u of U: the cosine of the angle from u's line to its nearest required direction."""
    U = np.atleast_2d(np.asarray(U, float))
    out = np.empty(len(U))
    for i in range(0, len(U), CHUNK):
        M = U[i:i + CHUNK] @ D.T
        out[i:i + CHUNK] = np.maximum(M.max(axis=1), -M.min(axis=1))
    return out


def floor_numbers(g: float) -> dict:
    """The floor as sigma_min, angular distance and joint-rate gain, from g = max |u1 . d|."""
    g = min(1.0, float(g))
    s = math.sqrt(max(0.0, 1.0 - g))
    return {"sigma_min": s, "angle_deg": math.degrees(math.acos(g)), "rate_gain": (1.0 / s) if s > 0 else None}


def fibonacci_hemisphere(n: int) -> np.ndarray:
    """n directions on the upper hemisphere (z > 0), Fibonacci lattice: z = 1 - (k + 1/2)/n, longitude k times the golden angle. u1 and -u1
    are the same line, so the hemisphere covers every line."""
    k = np.arange(n, dtype=float)
    z = 1.0 - (k + 0.5) / n
    r = np.sqrt(1.0 - z * z)
    a = k * math.pi * (3.0 - math.sqrt(5.0))
    return np.column_stack([r * np.cos(a), r * np.sin(a), z])


def canonical(u) -> np.ndarray:
    """The end of the line with z > 0 (then x > 0, then y > 0 on a tie): u1 is reported as its upper end."""
    u = np.asarray(u, float)
    for c in (u[2], u[0], u[1]):
        if c != 0.0:
            return u if c > 0 else -u
    return u


def tangent(u):
    ref = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = unit(ref - (ref @ u) * u)
    return e1, np.cross(u, e1)


def _near(D, u, g, radius: float) -> np.ndarray:
    """The rows of D within (u's floor angle) + 2 radius of u's line. Exact for any candidate within `radius` of u: its nearest direction is
    at most floor + radius from it, hence within floor + 2 radius of u (the angle between lines is a metric)."""
    lim = math.acos(min(1.0, g)) + 2.0 * radius + 1e-9
    return D if lim >= math.pi / 2 else D[np.abs(D @ u) >= math.cos(lim)]


_COMPASS = np.column_stack([np.cos(np.arange(PATTERN_DIRS) * (2.0 * math.pi / PATTERN_DIRS)),
                            np.sin(np.arange(PATTERN_DIRS) * (2.0 * math.pi / PATTERN_DIRS))])


def directions(u, S, e1, e2) -> np.ndarray:
    """Unit tangent directions (in the e1, e2 basis) to try from u: the compass, plus those the POLISH_K nearest directions of S define. For
    each such point p (at the end nearer u) its tangent a = p - (p . u) u gives -a, the steepest move away from it; for each pair the two
    directions perpendicular to a_i - a_j, along which both distances change at the same rate. A ridge between two points runs along one of
    these, and an ascent cone narrower than the compass spacing (22.5 deg) lies around it, so the compass alone stalls there."""
    c = S @ u
    near = np.argsort(-np.abs(c), kind="stable")[:POLISH_K]
    P = S[near] * np.where(c[near] >= 0, 1.0, -1.0)[:, None]
    A = np.column_stack([P @ e1, P @ e2])        # the tangent part of each point, in the e1, e2 basis
    out = [_COMPASS]
    n = np.linalg.norm(A, axis=1)
    ok = n > 1e-15
    out.append(-A[ok] / n[ok, None])
    if len(A) >= 2:
        i, j = np.triu_indices(len(A), 1)
        W = A[i] - A[j]
        wn = np.linalg.norm(W, axis=1)
        W = W[wn > 1e-15] / wn[wn > 1e-15, None]
        perp = np.column_stack([-W[:, 1], W[:, 0]])
        out += [perp, -perp]
    return np.vstack(out)


def pattern(u, D, tol: float = PATTERN_TOL_RAD, h0: float = math.radians(PATTERN_H0_DEG)):
    """Pattern search on the sphere minimising max |u . d|: move to the best candidate at step h along `directions` when it improves by more
    than IMPROVE_TOL (smaller differences are the last bit of products over different subsets) and double h (up to h0), else halve h. Stops
    when h falls below `tol` (returns converged True) or after PATTERN_MAX_ITER iterations (converged False). Returns (u, g, converged)."""
    u = unit(u)
    g = float(gmax(u, D)[0])
    h = h0
    for _ in range(PATTERN_MAX_ITER):
        if h <= tol:
            return u, g, True
        e1, e2 = tangent(u)
        S = _near(D, u, g, h * 1.0001)
        V = directions(u, S, e1, e2)
        C = unit(u + h * (np.outer(V[:, 0], e1) + np.outer(V[:, 1], e2)))
        gc = gmax(C, S)
        j = int(np.argmin(gc))
        if gc[j] < g - IMPROVE_TOL:
            u, g = C[j], float(gc[j])
            h = min(2.0 * h, h0)
        else:
            h *= 0.5
    return u, g, False


def polish(u, D):
    """The local maximum of a max-min distance to a finite set is a cap whose rim passes through three points: try the circumcentre of every
    triple of the POLISH_K nearest directions (each taken at the end nearer u) within POLISH_RADIUS_DEG of u; return the best and its g."""
    c = D @ u
    g = float(np.abs(c).max())
    P = D * np.where(c >= 0, 1.0, -1.0)[:, None]
    near = np.argsort(-np.abs(c), kind="stable")[:POLISH_K]
    tri = np.array(list(itertools.combinations(near, 3)))
    A, B, C = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
    N = np.cross(B - A, C - A)
    nn = np.linalg.norm(N, axis=1)
    keep = nn >= 1e-14
    N = N[keep] / nn[keep, None]
    N *= np.where(N @ u < 0, -1.0, 1.0)[:, None]
    r = math.radians(POLISH_RADIUS_DEG)
    N = N[N @ u >= math.cos(r)]
    if not len(N):
        return u, g
    gc = gmax(N, _near(D, u, g, r))
    j = int(np.argmin(gc))
    return N[j], float(gc[j])


def _g(u, D) -> float:
    return float(gmax(u, D)[0])


def refine(u, D):
    """Coarse pattern search down to POLISH_SWITCH_RAD, then the vertex polish, alternating while the polish improves; then a fine pattern
    search down to PATTERN_TOL_RAD from small steps, and the polish again, until neither improves by more than IMPROVE_TOL. Near a vertex
    the compass overshoots and gains about 1e-15 a step; the polish lands on the vertex exactly, so it takes over below POLISH_SWITCH_RAD.
    g is always re-evaluated on all of D, so a last-bit difference between a product over a subset and over all of D is never taken for an
    improvement. Returns (canonical u1, g)."""
    u, _, _ = pattern(u, D, POLISH_SWITCH_RAD)
    g = _g(u, D)
    for _ in range(1000):
        v, _ = polish(u, D)
        if _g(v, D) < g - IMPROVE_TOL:
            u, _, _ = pattern(v, D, POLISH_SWITCH_RAD)
            g = _g(u, D)
            continue
        w, _, done = pattern(u, D, PATTERN_TOL_RAD, POLISH_SWITCH_RAD)
        gw = _g(w, D)
        if not gw < g - IMPROVE_TOL:
            return canonical(u), g
        if not done:
            v, _ = polish(w, D)
            if not _g(v, D) < gw - IMPROVE_TOL:
                raise RuntimeError(f"refinement stalled at {w} without a polish step")
        u, g = w, gw
    raise RuntimeError("refinement did not converge")


def certificate(u, D) -> dict:
    """Local-maximum certificate: the active directions (|u . d| within ACTIVE_TOL of the largest) and the largest angular gap between their
    tangent-plane directions seen from u. When that gap is below 180 deg, 0 lies in their convex hull and no move increases every distance."""
    c = np.abs(D @ u)
    act = np.where(c >= c.max() - ACTIVE_TOL)[0]
    P = D[act] * np.sign(D[act] @ u)[:, None]
    e1, e2 = tangent(u)
    T = P - np.outer(P @ u, u)
    a = np.sort(np.arctan2(T @ e2, T @ e1))
    gap = float(np.diff(np.concatenate([a, [a[0] + 2.0 * math.pi]])).max()) if len(a) else 2.0 * math.pi
    return {"active": int(len(act)), "largest_gap_deg": math.degrees(gap), "local_maximum": bool(len(act) >= 2 and gap < math.pi - 1e-9)}


def search(D: np.ndarray, n: int) -> dict:
    """Global search: the Fibonacci grid's floors, greedy seeds (best first, each more than BASIN_SEP_DEG from every earlier seed), every seed
    refined, the refined optima ranked and kept when more than BASIN_SEP_DEG from every better one."""
    U = fibonacci_hemisphere(n)
    G = gmax(U, D)
    order = np.argsort(G, kind="stable")
    cs = math.cos(math.radians(BASIN_SEP_DEG))
    seeds = []
    for i in order:
        if not seeds or np.abs(np.array(seeds) @ U[i]).max() < cs:
            seeds.append(U[i])
    refined = sorted((refine(s, D) for s in seeds), key=lambda r: r[1])
    basins = []
    for u, g in refined:
        if not basins or max(abs(u @ b[0]) for b in basins) < cs:
            basins.append((u, g))
    return {"n": n, "seeds": len(seeds), "grid_best_u1": canonical(U[order[0]]), "grid_best_g": float(G[order[0]]), "basins": basins}


# ---- reading a result ---------------------------------------------------------------------------------------------------------------

def words(v, side: str = "right") -> str:
    lat = v[1] < 0 if side == "right" else v[1] > 0
    return ", ".join(["up" if v[2] > 0 else "down", "anterior" if v[0] > 0 else "posterior", "lateral" if lat else "medial"])


def ends(u, side: str = "right") -> list:
    out = []
    for v in (u, -u):
        p, t = phi_theta(v, side)
        out.append({"u": v, "phi_deg": p, "theta_deg": t, "words": words(v, side)})
    return out


def line_angle_deg(a, b) -> float:
    """The angle between the lines along a and b, in degrees; atan2(|a x b|, |a . b|), well conditioned near 0 where acos is not."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return math.degrees(math.atan2(float(np.linalg.norm(np.cross(a, b))), abs(float(a @ b))))


def near_points(u, es: dict, names, band_deg: float) -> list:
    """Every labelled direction within band_deg of the floor's angular distance, with its angle and the end of the line it is near."""
    g = max(float(gmax(u, es[n].d).max()) for n in names)
    lim = math.acos(min(1.0, g)) + math.radians(band_deg)
    out = []
    for n in names:
        c = es[n].d @ u
        for i in np.where(np.abs(c) >= math.cos(lim) - 1e-15)[0]:
            out.append({**es[n].label(int(i)), "angle_deg": math.degrees(math.acos(min(1.0, abs(float(c[i]))))), "end": "+u1" if c[i] > 0 else "-u1"})
    return sorted(out, key=lambda r: (round(r["angle_deg"], 9), r["entry"], sorted((k, v) for k, v in r.items() if k.endswith("_deg") and k != "angle_deg")))


def binding_summary(points: list) -> dict:
    """Per entry: how many points, the nearest, the ends of the line they are near, and the range of each parameter among them."""
    out = {}
    for p in points:
        e = out.setdefault(p["entry"], {"count": 0, "min_angle_deg": p["angle_deg"], "ranges": {}, "ends": set()})
        e["count"] += 1
        e["min_angle_deg"] = min(e["min_angle_deg"], p["angle_deg"])
        e["ends"].add(p["end"])
        for k, v in p.items():
            if k.endswith("_deg") and k != "angle_deg":
                lo, hi = e["ranges"].get(k, (v, v))
                e["ranges"][k] = (min(lo, v), max(hi, v))
    for e in out.values():
        e["ends"] = sorted(e["ends"])
        e["ranges"] = {k: list(v) for k, v in e["ranges"].items()}
    return out


def ik_all(u1, D: np.ndarray):
    d0, u2 = gimbal_frame(u1)
    return np.arctan2(D @ u2, D @ d0), -np.arcsin(np.clip(D @ u1, -1.0, 1.0))


def spans(u1, es: dict, names=BASIS) -> dict:
    """q1 lifted continuously from the neutral arm (q1 = 0 at straight down, which every entry contains): along each arc in its parameter's
    order, and over B1 column by column in theta. q2 directly. Degrees."""
    per, lifted, q2s = {}, {}, {}
    for n in names:
        e = es[n]
        q1, q2 = ik_all(u1, e.d)
        if n == "B1":
            L = np.empty_like(q1)
            for p in np.unique(e.phi):
                idx = np.where(e.phi == p)[0]
                idx = idx[np.argsort(e.theta[idx], kind="stable")]
                L[idx] = np.unwrap(q1[idx])
        else:
            L = np.unwrap(q1)  # the arcs are built in their parameter's order from 0
        lifted[n], q2s[n] = np.degrees(L), np.degrees(q2)
        per[n] = {"q1_deg": [float(lifted[n].min()), float(lifted[n].max())], "q2_deg": [float(q2s[n].min()), float(q2s[n].max())]}
    # the lifts must agree where entries share a direction (A1 is B1's phi = 90 column and A3 its phi = 0 column, up to theta 108)
    worst = 0.0
    for arc, phi in (("A1", 90.0), ("A3", 0.0)):
        if arc in names and "B1" in names:
            b1 = es["B1"]
            for i in np.where(b1.phi == phi)[0]:
                j = np.where(np.abs(es[arc].theta - b1.theta[i]) < 1e-9)[0]
                if len(j):
                    worst = max(worst, abs(float(lifted[arc][j[0]] - lifted["B1"][i])))
    q1 = np.concatenate([lifted[n] for n in names])
    q2 = np.concatenate([q2s[n] for n in names])
    wrapped = np.sort(np.mod(q1, 360.0))
    gap = float(np.diff(np.concatenate([wrapped, [wrapped[0] + 360.0]])).max())
    span = float(q1.max() - q1.min())
    return {
        "per_entry": per,
        "q1_deg": [float(q1.min()), float(q1.max())], "q1_span_deg": span, "q1_covering_arc_deg": 360.0 - gap,
        "lift_disagreement_deg": worst, "encircles_u1": bool(span >= 360.0 or worst > 1e-6),
        "q2_deg": [float(q2.min()), float(q2.max())], "q2_span_deg": float(q2.max() - q2.min()),
        "convention": "u1 is the upper end (z > 0); q1 = atan2(d . u2, d . d0), q2 = -asin(d . u1); R(u2, q2) d0 = cos q2 d0 - sin q2 u1, so "
                      "positive q2 tilts the arm toward -u1",
    }


def neutral_pose(u1) -> dict:
    q1, q2 = gimbal_ik(u1, np.array([0.0, 0.0, -1.0]))
    return {"q1_deg": math.degrees(q1), "q2_deg": math.degrees(q2),
            "note": "the neutral arm (straight down) is q1 = 0, q2 = asin(u1_z); it is q = 0 only when u1 is horizontal"}


def round_trip(u1, D: np.ndarray) -> dict:
    """V3: IK then FK over D, excluding directions within SINGULAR_EXCLUDE_DEG of +/-u1."""
    excl = np.abs(D @ u1) > math.cos(math.radians(SINGULAR_EXCLUDE_DEG))
    worst = 0.0
    for d in D[~excl]:
        q1, q2 = gimbal_ik(u1, d)
        worst = max(worst, float(np.linalg.norm(gimbal_fk(u1, q1, q2) - d)))
    return {"directions": int(len(D)), "excluded_within_deg": SINGULAR_EXCLUDE_DEG, "excluded": int(excl.sum()), "max_error": worst}


def describe(u, g, es: dict, names, D: np.ndarray, side: str = "right") -> dict:
    pts = near_points(u, es, names, BINDING_BAND_DEG)
    floor_deg = math.degrees(math.acos(min(1.0, g)))
    return {"u1": u, "ends": ends(u, side), "floor": floor_numbers(g), "certificate": certificate(u, D),
            "active": [p for p in pts if p["angle_deg"] - floor_deg < 1e-7],
            "binding_entries": binding_summary(pts), "binding_points": pts}


# ---- T4: sensitivity ----------------------------------------------------------------------------------------------------------------

B1_WIDEN_DEG = 10.0           # brief T4: B1's plane bounds widened by 10 deg at each end
SENSITIVITY = (               # brief T4: (case, entries searched, B1 widening)
    ("R+S1", BASIS + ("S1",), 0.0),
    ("R+S2", BASIS + ("S2",), 0.0),
    ("R+S3", BASIS + ("S3",), 0.0),
    ("R+S1+S2+S3", BASIS + ("S1", "S2", "S3"), 0.0),
    ("R-B1", ("A1", "A2", "A3"), 0.0),
    ("R, B1 plane +/-10", BASIS, B1_WIDEN_DEG),
)


def at_axis(u, e: Entry) -> dict:
    """An entry evaluated at a fixed u1, without re-optimising: its nearest direction to the line, as floor numbers, and where."""
    c = np.abs(e.d @ u)
    i = int(np.argmax(c))
    return {**floor_numbers(c[i]), "at": e.label(i)}


def sensitivity(rom: dict, inputs: dict, u_basis, basins=()) -> dict:
    """Each SENSITIVITY case searched as the basis is (SEEDS[-1] seeds); then S1 to S3 at the basis optimum, and at each basis basin, without
    re-optimising."""
    cases = {}
    for name, names, widen in SENSITIVITY:
        es = entries(rom, inputs, "right", b1_widen_deg=widen)
        D = unique_dirs(stack(es, names))
        r = search(D, SEEDS[-1])
        u, g = r["basins"][0]
        pts = near_points(u, es, names, BINDING_BAND_DEG)
        floor_deg = math.degrees(math.acos(min(1.0, g)))
        lifted = tuple(n for n in names if n not in ("S2", "S3"))  # S2 and S3 are single points: no path from the neutral arm to lift q1 along
        sp = spans(u, es, lifted)
        cases[name] = {"entries": list(names), "b1_widen_deg": widen, "u1": u, "ends": ends(u), "floor": floor_numbers(g),
                       "angle_from_basis_optimum_deg": line_angle_deg(u, u_basis), "certificate": certificate(u, D),
                       "active": [p for p in pts if p["angle_deg"] - floor_deg < 1e-7], "binding_entries": binding_summary(pts),
                       "q1_span_deg": sp["q1_span_deg"], "q2_span_deg": sp["q2_span_deg"], "spans_over": list(lifted),
                       "basins": [{"u1": b, "ends": ends(b), "floor": floor_numbers(gb), "angle_from_basis_optimum_deg": line_angle_deg(b, u_basis)}
                                  for b, gb in r["basins"][:N_BASINS]]}
    es = entries(rom, inputs, "right")
    at_basis = {n: at_axis(np.asarray(u_basis, float), es[n]) for n in ("S1", "S2", "S3")}
    at_basins = [{"u1": b, **{n: at_axis(np.asarray(b, float), es[n]) for n in ("S1", "S2", "S3")}} for b in basins]
    return {"cases": cases, "s_at_basis_optimum": at_basis, "s_at_basis_basins": at_basins}


# ---- build --------------------------------------------------------------------------------------------------------------------------

def input_files() -> list:
    return sorted(["params/snapshot.csv", INPUTS])


def inputs_hash(root: Path) -> str:
    h = hashlib.sha256()
    for n in input_files():
        h.update(n.encode())
        h.update((Path(root) / n).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def baseline(es: dict, D: np.ndarray) -> dict:
    """V2: the model's current chain, u1 = (0, -1, 0)."""
    u0 = np.array([0.0, -1.0, 0.0])
    g0 = float(gmax(u0, D)[0])
    pts = near_points(u0, es, BASIS, 0.0)
    bound = math.sqrt(1.0 - math.cos(math.radians(ARC_STEP_DEG)))
    at = [p for p in pts if p["angle_deg"] < 1e-9]
    ok = math.sqrt(max(0.0, 1.0 - g0)) <= bound and any(p["entry"] == "A3" and abs(p["alpha_deg"] - 90.0) < 1e-9 for p in at)
    return {"u1": u0, "floor": floor_numbers(g0), "at": at, "v2_bound_sigma": bound, "pass": bool(ok)}


def build(root: Path = ROOT) -> dict:
    rom = read_rom(root)
    inputs = read_inputs(root)
    es = entries(rom, inputs, "right")
    D_all = stack(es, BASIS)
    D = unique_dirs(D_all)

    runs = {n: search(D, n) for n in SEEDS}
    u, g = runs[SEEDS[-1]]["basins"][0]
    basins = [describe(b, gb, es, BASIS, D) | {"angle_from_optimum_deg": line_angle_deg(b, u), "spans": spans(b, es, BASIS), "neutral_pose": neutral_pose(b)}
              for b, gb in runs[SEEDS[-1]]["basins"][:N_BASINS]]
    opt = dict(basins[0])
    del opt["angle_from_optimum_deg"]
    opt["axis3_span"] = "open: needs a definition of the gimbal's induced axial offset against ISB axial rotation, which is adr-0025's to choose"

    u20, g20 = runs[SEEDS[0]]["basins"][0]
    v5 = {"angle_between_deg": line_angle_deg(u20, u), "sigma_difference": abs(floor_numbers(g20)["sigma_min"] - floor_numbers(g)["sigma_min"]),
          "per_seed": {str(n): {"seeds": r["seeds"], "grid_best_u1": r["grid_best_u1"], "grid_best": floor_numbers(r["grid_best_g"]),
                                "u1": r["basins"][0][0], "floor": floor_numbers(r["basins"][0][1])} for n, r in runs.items()}}
    v5["pass"] = bool(v5["angle_between_deg"] < 0.1 and v5["sigma_difference"] < 1e-6)

    left = search(unique_dirs(stack(entries(rom, inputs, "left"), BASIS)), SEEDS[-1])
    ul, gl = left["basins"][0]
    v4 = {"u1_left": ul, "floor_left": floor_numbers(gl), "mirror_difference": float(np.abs(mirror(ul) - u).max()),
          "sigma_difference": abs(floor_numbers(gl)["sigma_min"] - floor_numbers(g)["sigma_min"])}
    v4["pass"] = bool(v4["mirror_difference"] < 1e-9 and v4["sigma_difference"] < 1e-9)

    v3 = round_trip(u, stack(es, BASIS + ("S1", "S2", "S3")))
    v3["pass"] = bool(v3["max_error"] < 1e-9)

    up = opt["ends"][0]["words"]
    hypothesis = {"stated": "one end up, behind (posterior) and lateral; the other down, forward (anterior) and medial",
                  "upper_end": up, "lower_end": opt["ends"][1]["words"], "matches": up == "up, posterior, lateral"}

    return {
        "schema": "shoulder-axis-search/1", "generated_by": "analysis/shoulder_axis_search.py", "inputs": f"sha256:{inputs_hash(root)}",
        "brief": "docs/briefs/ariadne/shoulder-axis-search-brief.md",
        "frame": "thorax body frame of sim/models/freyja.xml: x anterior, y left, z up; right arm unless stated; phi, theta ISB humerothoracic Y-X-Y",
        "addresses": rom,
        "constants": {"arc_step_deg": ARC_STEP_DEG, "b1_step_deg": B1_STEP_DEG, "seeds": list(SEEDS), "basin_separation_deg": BASIN_SEP_DEG,
                      "binding_band_deg": BINDING_BAND_DEG, "singular_exclude_deg": SINGULAR_EXCLUDE_DEG, "pattern_directions": PATTERN_DIRS,
                      "pattern_first_step_deg": PATTERN_H0_DEG, "pattern_tolerance_rad": PATTERN_TOL_RAD, "polish_nearest": POLISH_K,
                      "polish_radius_deg": POLISH_RADIUS_DEG, "polish_switch_rad": POLISH_SWITCH_RAD, "pattern_max_iterations": PATTERN_MAX_ITER,
                      "active_tolerance": ACTIVE_TOL, "improve_tolerance": IMPROVE_TOL,
                      "significant_digits": ROUND},
        "required_set": {"basis": list(BASIS), "directions": int(len(D_all)), "unique_directions": int(len(D)),
                         "entries": {n: {"count": int(len(es[n].d)), **{k: [float(v.min()), float(v.max())] for k, v in es[n].params.items()}} for n in es}},
        "baseline": baseline(es, D), "optimum": opt, "basins": basins, "hypothesis": hypothesis,
        "v3_round_trip": v3, "v4_mirror": v4, "v5_convergence": v5,
        "sensitivity": sensitivity(rom, inputs, u, [b for b, _ in runs[SEEDS[-1]]["basins"][:N_BASINS]]),
    }


# ---- output -------------------------------------------------------------------------------------------------------------------------

def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_clean(v) for v in o.tolist()]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (np.floating, float)):
        r = float(f"{float(o):.{ROUND}g}")
        return 0.0 if r == 0.0 else r
    if isinstance(o, np.integer):
        return int(o)
    return o


def render(result: dict) -> str:
    return json.dumps(_clean(result), indent=1, sort_keys=True) + "\n"


def write_map(root: Path, result: dict) -> Path:
    """T3: an equirectangular map of the floor over u1 in (phi, theta) of the right arm, both hemispheres, with the required set overlaid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rom, inputs = read_rom(root), read_inputs(root)
    es = entries(rom, inputs, "right")
    D = unique_dirs(stack(es, BASIS))
    P, T = np.meshgrid(np.arange(-180.0, 180.01, 1.0), np.arange(0.0, 180.01, 1.0))
    F = np.degrees(np.arccos(np.clip(gmax(d_of(P.ravel(), T.ravel()), D), -1, 1))).reshape(P.shape)
    fig, ax = plt.subplots(figsize=(12, 6.5))
    im = ax.imshow(F, origin="lower", extent=(-180.5, 180.5, -0.5, 180.5), aspect="auto", cmap="viridis")
    fig.colorbar(im, ax=ax, label="floor: angle from the line +/-u1 to the nearest required direction (deg)")
    ax.contour(P, T, F, levels=[15.0], colors="w", linewidths=0.8)
    for n, style in (("A1", "r-"), ("A2", "r-"), ("A3", "r-"), ("S1", "m--")):
        ax.plot(es[n].phi, es[n].theta, style, lw=1.2)
    b = inputs["required"]["B1"]
    ax.add_patch(plt.Rectangle((b["plane_min"]["value"], b["elevation_min"]["value"]), b["plane_max"]["value"] - b["plane_min"]["value"],
                               b["elevation_max"]["value"] - b["elevation_min"]["value"], fill=False, ec="r", lw=1.2))
    for n in ("S2", "S3"):
        ax.plot(es[n].phi, es[n].theta, "m^")
    for i, bsn in enumerate(result["basins"]):
        for e in bsn["ends"]:
            ax.plot(e["phi_deg"], e["theta_deg"], "w*" if i == 0 else "wo", ms=12 if i == 0 else 7, mec="k")
    ax.set_xlabel("plane of elevation phi of an end of u1 (deg; 0 frontal/abduction, +90 flexion)")
    ax.set_ylabel("elevation theta of an end of u1 (deg from straight down)")
    ax.set_title("Floor over u1 (right arm). Red: A1-A3, B1; magenta: S1-S3; star: optimum ends; circles: other basins; white: 15 deg")
    out = Path(root) / MAP_DIR / "floor_map.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def main(argv) -> int:
    if argv not in ([], ["--map"]):
        print("usage: python analysis/shoulder_axis_search.py [--map]", file=sys.stderr)
        return 2
    result = build(ROOT)
    with open(ROOT / OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(result))
    print(f"wrote {OUT}")
    if argv == ["--map"]:
        print(f"wrote {write_map(ROOT, _clean(result)).relative_to(ROOT).as_posix()} (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
