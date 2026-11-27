"""analysis/shoulder_room.py (shoulder-room brief, Group B, with Amendments 1 and 2): the room around the shoulder joint centre along axis 1, for the
differential-versus-serial-roll decision (adr-0025, Joe's).

Frame: the thorax model body frame (x anterior, y left, z up, mm, origin at the model's CJC). The centre is the envelope's shoulder joint (Amendment 1,
R1): the arm ledger's mesh SJC mapped through the trunk registration (`bodies.trunk_map(...).apply`), less the thorax's `origin_xyz`, less the thorax's
model-to-segment offset (`frames.segment_offset_mm`). It is computed here, never typed. The upper arm's field sits at its own origin there, unrotated
(the hanging, zero pose). u1 is read by address and normalised. s is the signed distance along u1 from the centre, positive toward its upper end.
The basis axis is memo 66 basin 2 (`axis_search.json#/basins/1/u1`); basin 1 (`#/basins/0/u1`) is run as a comparison, not basis (Amendment 2, R10).

The bounds (M1, Amendment 2):
  B  the ball of radius R_B about the centre that lies in upper_arm_R alone with margin t (the oracle, a capsule of zero length): R_B is already less t.
  N  (thorax and upper arm at neutral, held by region: `occupancy.skin_field`, Amendment 1, R3) union B (R6). A point no region holds counts only when it
     lies in B; a region-cut binding inside B therefore never binds (R8).
  S  the set thorax (held by its region) union B (R7).
  T  the thorax alone, held by its region (R9).
Reservations "on" subtract the thorax registry's reserved spine modules (`data/envelope/reserved/thorax.yaml`), dilated by their clearance, as the free
field does. `part.arm.upper_member` is reported where it meets a disc, never subtracted (the brief's decision 4).

Every r is a bisection to BISECT_TOL_MM on the feasibility of a sampled shape (`oracle.sample_shape`): every sample's margin at least t. The fields are
read from data/envelope/cache/ (gitignored); the cache's input hashes must equal the ledgers', and the file records each cache file's sha256.

No arguments. Writes data/shoulder/room.json (generated, tracked, banner keys, no timestamp) and, when matplotlib is installed, the r(s) plot
data/shoulder/map/room_profiles.png (gitignored).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from envelope import bodies, field, frames, masses, occupancy, oracle, registry, trial  # noqa: E402
from envelope.sheet import StopAndAsk  # noqa: E402

OUT = "data/shoulder/room.json"
PLOT = "data/shoulder/map/room_profiles.png"
THORAX, ARM = "thorax", "upper_arm_R"
SJC_BODY = "upper_arm_right"                                    # the model body whose origin is the model's SJC (snapshot upper_arm_right_pos_*)
AXES = {"basis": ("data/shoulder/axis_search.json", "/basins/1/u1"),         # Joe: memo 66 basin 2 (up-posterior-lateral upper end)
        "comparison": ("data/shoulder/axis_search.json", "/basins/0/u1")}    # Amendment 2, R10: memo 66 basin 1, comparison only
ROLE_LABEL = {"basis": "basis (memo 66 basin 2)", "comparison": "comparison, not basis"}
SHELL = ("data/characterization/inputs/upper_arm.yaml", "/shell/value")   # t = 5 mm, adr-0007 D4
MODULE = ("data/envelope/reservations.yaml", "/spine_v2/module")          # the AKH70 envelope (diameter, length): the catalog drawing's 90 and 81.5
RESERVED = "data/envelope/reserved/thorax.yaml"
ARM_CAD = "data/envelope/components/cad/upper_arm_R.yaml"
ARM_SECTIONS = "data/envelope/upper_arm_R_sections.csv"
TRUNK_BODIES = "data/envelope/trunk_bodies.json"
TRUNK_REGISTRATION = "data/envelope/trunk_registration.json"
DUMAS = "data/envelope/dumas2015_table1_female.json"
MESH = "data/makehuman/freyja-body-v3.obj"

S_FROM_MM, S_TO_MM, S_STEP_MM = -150.0, 60.0, 2.0              # M1: the s range, and the step (one voxel)
DISC_LENGTH_MM = 1.0                                           # M1: the thin cylinder
BISECT_TOL_MM = 0.5                                            # M1, R9, M4: every radius
R_BRACKET_MM = 200.0                                           # the bisection's upper end; a feasible bracket stops (it would hide the answer)
REPORT_STEP_MM = 10.0                                          # M1's and R9's tables
R_LEVELS_MM = (20.0, 30.0, 40.0)                               # M1: the s ranges with r at least these
W_MM = (10.0, 20.0, 30.0, 40.0, 50.0, 60.0)                    # M2
AXIS_STEP_MM = 0.25                                            # R9: the march along the axis to its skin exit (Section.ray's step)
EXIT_REACH_MM = 600.0                                          # R9: the march stops here; no exit within it stops the build
SHAFT_RADIUS_MM, SHAFT_TARGET_MM = 5.0, 25.0                   # R9: the coaxial drive shaft test (Amendment 2)
SPHERE_WITHIN_MM = 150.0                                       # the free-sphere hint: its centre within this of the centre
UNHELD_HALF_MM, UNHELD_STEP_MM = 60.0, 1.0                     # R6: the lattice the unheld sheet is measured on (memo 69's)
UNHELD_RADII_MM = (20.0, 40.0, 60.0)
C_ROWS_MM = (15.0, 25.0, 35.0)                                 # M4: sensitivity rows, none is basis (c is source_needed)
SJC_TOL_MM = 0.01                                              # G-B1 (Amendment 1, R2)
UNIT_TOL = 1e-12                                               # G-B1
VOXEL_MM = 2.0                                                 # the cache's voxel: G-B1's lateral clause, G-B2, G-B3
LATERAL_STATION_MM = 40.0                                      # G-B1: the upper arm's station 40
MEMO59_LATERAL_MM = 226.63                                     # G-B1: memo 59's skin distance from the midline (192.33 + 34.30), the brief's reference
COMBOS = ("N_off", "N_on", "S_off", "S_on")

# binding codes
SKIN_T, SKIN_A, BALL, CUT, SLAB = "thorax skin", "upper_arm_R skin", "joint ball", "region cut", "slab end"


# ---- reading ----------------------------------------------------------------------------------------------------------------------------

def _yaml(root, rel):
    return yaml.safe_load((Path(root) / rel).read_text(encoding="utf-8"))


def _json(root, rel):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def pointer(doc, ptr: str):
    for part in [p for p in ptr.split("/") if p != ""]:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def read_address(root, addr):
    rel, ptr = addr
    doc = _json(root, rel) if rel.endswith(".json") else _yaml(root, rel)
    return pointer(doc, ptr)


def sections_row(root, station: float) -> dict:
    text = (Path(root) / ARM_SECTIONS).read_text(encoding="utf-8")
    rows = list(csv.DictReader(l for l in io.StringIO(text) if l.strip() and not l.startswith("#")))
    key = next(k for k in rows[0])
    for r in rows:
        if abs(float(r[key]) - station) < 1e-9:
            return r
    raise StopAndAsk(f"{ARM_SECTIONS} has no row at station {station}")


def snapshot(root) -> dict:
    out = {}
    with open(Path(root) / "params" / "snapshot.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["placeholder"]] = r["value"]
    return out


def input_files() -> list:
    return sorted({AXES["basis"][0], SHELL[0], MODULE[0], RESERVED, ARM_CAD, ARM_SECTIONS, TRUNK_BODIES, TRUNK_REGISTRATION, DUMAS, MESH,
                   f"data/envelope/{THORAX}.yaml", f"data/envelope/{ARM}.yaml", "params/snapshot.csv", "data/ansur2/ratios.json"})


def inputs_hash(root: Path) -> str:
    h = hashlib.sha256()
    for n in input_files():
        h.update(n.encode())
        h.update((Path(root) / n).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


# ---- geometry ---------------------------------------------------------------------------------------------------------------------------

def frame_about(u) -> np.ndarray:
    """A rotation whose third column is u (unit): the oracle's shapes have their axis along local z. The roll about u is fixed by a cross product with
    the world axis least aligned with u, so it is deterministic; the shapes here are bodies of revolution, so the roll changes only where the rings' samples fall."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    ref = np.eye(3)[int(np.argmin(np.abs(u)))]
    e1 = np.cross(ref, u)
    e1 /= np.linalg.norm(e1)
    return np.column_stack([e1, np.cross(u, e1), u])


def placed(shape: dict, centre, u) -> np.ndarray:
    return oracle.sample_shape(shape) @ frame_about(u).T + np.asarray(centre, float)


def disc(r):
    return {"type": "cylinder", "radius": float(r), "length": DISC_LENGTH_MM}


def rim_count(r) -> int:
    """How many of `oracle.sample_shape(disc(r))`'s samples are its two rim rings (they come first): checked first, since the rim binds most often."""
    return 2 * max(8, int(np.ceil(2 * np.pi * float(r) / oracle.SAMPLE_MM)))


def bisect(ok, bracket: float, tol: float = BISECT_TOL_MM, what: str = "radius") -> float:
    """The largest x in [0, bracket] with ok(x), to tol, assuming ok is monotone (a larger shape contains the samples of a smaller one, to the sampling).
    0 when ok(tol) fails. A feasible bracket stops: the answer would be the bracket, not the room."""
    if ok(bracket):
        raise StopAndAsk(f"the {what} bracket {bracket} mm is feasible; widen it")
    if not ok(tol):
        return 0.0
    lo, hi = tol, bracket
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo


def ball_disc_radius(R_B: float, s: float) -> float:
    """G-B6: the largest disc (thickness DISC_LENGTH_MM) at s inside the ball of radius R_B: its rim's far edge is (|s| + L/2, r) from the centre."""
    a = abs(float(s)) + DISC_LENGTH_MM / 2
    return math.sqrt(R_B * R_B - a * a) if a < R_B else 0.0


class Body:
    """One cached field placed in the model frame by a translation: model point p is the field's point p + offset."""

    def __init__(self, name, seg: field.Segment, offset):
        self.name, self.seg, self.offset = name, seg, np.asarray(offset, float)

    def local(self, P):
        return np.atleast_2d(P) + self.offset

    def in_slab(self, P):
        z = self.local(P)[:, 2]
        return (z <= self.seg.z_top) & (z >= self.seg.z_top - self.seg.length)

    def held(self, P):
        return self.seg.in_region(self.local(P)) & self.in_slab(P)

    def sd(self, P):
        return self.seg.signed_distance(self.local(P))


class Room:
    """The margins of the bounds at points in the model frame: e >= 0 where the point is room (margin at least t, held, clear of the modules when
    reservations are on). `margin` is e alone; `excess` adds the code of the surface that decides it. Bounds: "N", "S", "T" (see the module docstring)."""

    def __init__(self, thorax, arm, union, t: float, centre, R_B: float, modules: list):
        self.T, self.A, self.N, self.t, self.c, self.R_B, self.modules = thorax, arm, union, t, np.asarray(centre, float), R_B, modules

    def _ball(self, P):
        return self.R_B - np.linalg.norm(P - self.c, axis=1)

    def _held_margin(self, body, P):
        held = body.held(P)
        return np.where(held, body.sd(P) - self.t, -np.inf), held

    def _skin(self, P, bound):
        P = np.atleast_2d(P)
        if bound == "N":
            e, _ = self._held_margin(self.N, P)
            return np.maximum(e, self._ball(P))
        if bound == "S":
            e, _ = self._held_margin(self.T, P)
            return np.maximum(e, self._ball(P))
        if bound == "T":
            return self._held_margin(self.T, P)[0]
        raise ValueError(f"unknown bound {bound!r} (N, S, T)")

    def margin(self, P, bound: str, on: bool):
        e = self._skin(P, bound)
        if on:
            for _, f, clr in self.modules:
                e = np.minimum(e, f(P) - clr)
        return e

    def ok(self, P, bound, on, first: int = 0) -> bool:
        if first and self.margin(P[:first], bound, on).min() < 0.0:
            return False
        return bool(self.margin(P[first:] if first else P, bound, on).min() >= 0.0)

    def _outside(self, P, bodies_):
        slab = np.zeros(len(P), bool)
        for b in bodies_:
            slab |= b.in_slab(P)
        return np.where(slab, CUT, SLAB)

    def excess(self, P, bound: str, on: bool):
        """(e, code). A failing point inside B cannot occur under N or S (the ball holds it, R8); outside B the code names the region's own surface."""
        P = np.atleast_2d(P)
        e = self._skin(P, bound)
        if bound == "N":
            th, ah = self.T.held(P), self.A.held(P)
            st = np.where(th, self.T.sd(P), -np.inf)
            sa = np.where(ah, self.A.sd(P), -np.inf)
            region = np.where(self.N.held(P), np.where(st >= sa, SKIN_T, SKIN_A), self._outside(P, (self.T, self.A)))
            code = np.where(self._ball(P) >= 0.0, BALL, region)
        elif bound == "S":
            th = self.T.held(P)
            code = np.where(th, SKIN_T, BALL)                     # beyond the thorax region S is the ball by definition: the ball binds
        else:
            th = self.T.held(P)
            code = np.where(th, SKIN_T, self._outside(P, (self.T,)))
        if on:
            for mid, f, clr in self.modules:
                em = f(P) - clr
                code = np.where(em < e, mid, code)
                e = np.minimum(e, em)
        return e, code

    def binding(self, P, bound, on) -> dict:
        """What fails on an infeasible shape: the codes of the failing samples with counts, and the mean point of the most common."""
        e, code = self.excess(P, bound, on)
        bad = e < 0
        names, counts = np.unique(code[bad], return_counts=True)
        order = np.argsort(-counts, kind="stable")
        top = names[order[0]]
        pt = P[bad & (code == top)].mean(axis=0)
        return {"surface": str(top), "failing": {str(names[i]): int(counts[i]) for i in order}, "point_mm": [_mm(v) for v in pt]}


def _mm(x):
    return round(float(x), 2) + 0.0


# ---- the measures -----------------------------------------------------------------------------------------------------------------------

def disc_radius(room: Room, centre, u, bound, on):
    return bisect(lambda r: room.ok(placed(disc(r), centre, u), bound, on, first=rim_count(r)), R_BRACKET_MM)


def profile(room: Room, u, s_values, bound, on):
    c = room.c
    return [disc_radius(room, c + s * u, u, bound, on) for s in s_values]


def disc_binding(room: Room, u, s, r, bound, on) -> dict:
    return room.binding(placed(disc(r + BISECT_TOL_MM), room.c + s * u, u), bound, on)


def runs_at_least(s_values, r, level):
    out, start = [], None
    for s, v in zip(s_values, r):
        if v >= level and start is None:
            start = s
        if v < level and start is not None:
            out.append([_mm(start), _mm(prev)])
            start = None
        prev = s
    if start is not None:
        out.append([_mm(start), _mm(prev)])
    return out


def window_budget(s_values, r, w):
    """M2: the largest R such that r(s) >= R over some window [a, a + w] of the s grid, and the window."""
    s = np.asarray(s_values)
    best = (-1.0, None)
    for i in range(len(s)):
        j = np.flatnonzero(s <= s[i] + w + 1e-9)
        if s[i] + w > s[-1] + 1e-9:
            break
        m = float(min(r[i:j[-1] + 1]))
        if m > best[0]:
            best = (m, [_mm(s[i]), _mm(s[i] + w)])
    return best


def bound_order(profiles: dict) -> list:
    """G-B4: every s where r_S > r_N or r(on) > r(off), as (s index, lower, upper)."""
    bad = []
    for i in range(len(profiles["N_off"])):
        for lo, hi in (("S_off", "N_off"), ("S_on", "N_on"), ("N_on", "N_off"), ("S_on", "S_off")):
            if profiles[lo][i] > profiles[hi][i]:
                bad.append((i, lo, hi))
    return bad


def axis_exit(room: Room, u, step: float = AXIS_STEP_MM, reach: float = EXIT_REACH_MM) -> dict:
    """R9: where the axis, followed from the centre toward negative s, leaves the thorax: the first point past its entry that is not both held by the
    thorax region and inside the skin (sd >= 0). A skin exit (still held) is interpolated on sd; a region exit is reported as the cut or slab it is."""
    s = -np.arange(0.0, reach + 1e-9, step)
    P = room.c + s[:, None] * np.asarray(u, float)
    held, sd = room.T.held(P), room.T.sd(P)
    inside = held & (sd >= 0.0)
    if not inside.any():
        raise StopAndAsk("the axis never enters the thorax within the reach")
    k_in = int(np.argmax(inside))
    after = np.flatnonzero(~inside[k_in:])
    if not len(after):
        raise StopAndAsk(f"the axis does not leave the thorax within {reach} mm")
    k = k_in + int(after[0])
    if held[k]:
        f = sd[k - 1] / (sd[k - 1] - sd[k])
        s_exit, surface = s[k - 1] + f * (s[k] - s[k - 1]), SKIN_T
    else:
        s_exit, surface = s[k], str(room._outside(P[k:k + 1], (room.T,))[0])
    p = room.c + s_exit * np.asarray(u, float)
    return {"s_mm": _mm(s_exit), "surface": surface, "point_mm": [_mm(v) for v in p], "entered_at_s_mm": _mm(s[k_in])}


def coaxial_runs(s_values, r) -> list:
    """R9: the maximal runs of s with r > 0, each with its largest coaxial diameter (2 r) and where."""
    out, cur = [], []
    for s, v in list(zip(s_values, r)) + [(None, 0.0)]:
        if v > 0.0:
            cur.append((s, v))
        elif cur:
            sm, vm = max(cur, key=lambda x: x[1])
            out.append({"s_range_mm": [_mm(cur[0][0]), _mm(cur[-1][0])], "max_diameter_mm": _mm(2 * vm), "s_at_max_mm": _mm(sm)})
            cur = []
    return out


def shaft_test(s_values, r, R_B: float, shaft: float = SHAFT_RADIUS_MM, target: float = SHAFT_TARGET_MM) -> dict:
    """R9: a continuous coaxial path of radius `shaft` from the joint ball to a run where r >= target. Walking from s = 0 toward negative s, a grid point
    passes when the shaft's disc fits in the ball (the joint ball is arm flesh at every pose) or r(s) >= shaft; the path exists when a point with r >= target
    is reached before one fails. Returns the verdict, the first failing s (None when none fails), the s reached, and the least r outside the ball on the
    way to the target (or to the end): the margin the verdict rests on, which a single block within the bisection tolerance does not show."""
    out = {"exists": False, "blocked_at_s_mm": None, "r_at_block_mm": None, "reached_target_at_s_mm": None, "path_min_r_mm": None, "path_min_at_s_mm": None}
    for s, v in zip(s_values, r):
        if v >= target:
            out["reached_target_at_s_mm"] = _mm(s)
            out["exists"] = out["blocked_at_s_mm"] is None
            break
        in_ball = math.hypot(abs(s) + DISC_LENGTH_MM / 2, shaft) <= R_B
        if in_ball:
            continue
        if out["path_min_r_mm"] is None or v < out["path_min_r_mm"]:
            out["path_min_r_mm"], out["path_min_at_s_mm"] = _mm(v), _mm(s)
        if v < shaft and out["blocked_at_s_mm"] is None:
            out["blocked_at_s_mm"], out["r_at_block_mm"] = _mm(s), _mm(v)
    return out


def ball_radius_oracle(arm: field.Segment, t: float) -> dict:
    """R_B by the oracle on upper_arm_R alone: a capsule of zero length (a sphere) at the arm frame's origin, the largest radius that is feasible (margin
    at least t, no slab overrun). Also what binds just above it."""
    def res(r):
        return oracle.clearance(arm, [{"name": "ball", "type": "capsule", "radius": r, "length": 0.0}], [[0.0, 0.0, 0.0]], required_mm=t)
    R = bisect(lambda r: res(r)["feasible"], R_BRACKET_MM, what="ball radius")
    above = res(R + BISECT_TOL_MM)
    return {"R_B_mm": R, "above": {"margin_mm": _mm(above["margin_mm"]), "slab_overrun_mm": _mm(above["slab_overrun_mm"]), "point_mm": [_mm(v) for v in above["point_mm"]],
                                   "binds": SLAB if above["margin_mm"] >= t else "skin"}}


def ball_radius_field(arm: field.Segment, t: float) -> float:
    """G-B3's independent figure: the least distance from the arm frame's origin to the arm's skin, the zero crossings of sd between neighbouring cells both
    in the region (linear interpolation along each grid axis), less t."""
    sd, reg, h, o = arm.sd, arm.region, arm.h, arm.o
    best = np.inf
    for ax in range(3):
        a = [slice(None)] * 3
        b = [slice(None)] * 3
        a[ax], b[ax] = slice(0, -1), slice(1, None)
        s0, s1 = sd[tuple(a)], sd[tuple(b)]
        m = (np.sign(s0) != np.sign(s1)) & reg[tuple(a)] & reg[tuple(b)]
        idx = np.argwhere(m)
        f = s0[m] / (s0[m] - s1[m])
        p = o + h * (idx + 0.5)
        p[:, ax] += f * h
        best = min(best, float(np.linalg.norm(p, axis=1).min()))
    return best - t


def unheld_sheet(room: Room) -> dict:
    """R6: the flesh both fields agree on (sd >= t in the thorax and the arm) that no region holds, on a 1 mm lattice about the centre: a known region
    artefact (the A-pose shoulder-girdle labels, rotated with the arm), reported, not fixed."""
    g = np.arange(-UNHELD_HALF_MM, UNHELD_HALF_MM + 1e-9, UNHELD_STEP_MM)
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    P = room.c + np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    flesh = (room.T.sd(P) >= room.t) & (room.A.sd(P) >= room.t)
    gap = flesh & ~room.N.held(P)
    d = np.linalg.norm(P - room.c, axis=1)
    cell = UNHELD_STEP_MM ** 3 / 1000.0
    out = {"lattice_mm": [UNHELD_HALF_MM, UNHELD_STEP_MM], "agreed_flesh_cm3": _mm(flesh.sum() * cell), "unheld_cm3": _mm(gap.sum() * cell),
           "inside_ball_cm3": _mm((gap & (d <= room.R_B)).sum() * cell), "ball_cm3": _mm(4.0 / 3.0 * np.pi * room.R_B ** 3 / 1000.0),
           "nearest_unheld_mm": _mm(d[gap].min()) if gap.any() else None}
    for R in UNHELD_RADII_MM:
        out[f"within_{int(R)}_mm_cm3"] = _mm((gap & (d <= R)).sum() * cell)
    return out


# ---- build ------------------------------------------------------------------------------------------------------------------------------

def envelope_sjc(root, thorax_meta, arm_ledger):
    """Amendment 1, R1: the arm ledger's mesh SJC through the trunk map, less the thorax origin, into the thorax model frame. Also the map itself (R4)."""
    inp = trial.load_inputs(root, root / MESH)
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    tm = bodies.trunk_map(inp, reg, masses.load_dumas_table1(root))
    origin = np.asarray(thorax_meta["origin_xyz"], float)
    off = np.asarray(frames.segment_offset_mm(THORAX, thorax_meta), float)

    def to_model(p_mesh):
        conformed = tm.apply(np.atleast_2d(np.asarray(p_mesh, float)))[0]
        return conformed - origin - off, conformed
    mesh_sjc = np.asarray(arm_ledger["mesh_nodes_mm"]["sjc"], float)
    sjc, conf = to_model(mesh_sjc)
    return sjc, {"mesh_mm": [_mm(v) for v in mesh_sjc], "conformed_mm": [_mm(v) for v in conf], "shear_above_hip_mm": [_mm(v) for v in tm.shear_hjc],
                 "thorax_origin_xyz_mm": [_mm(v) for v in origin], "thorax_model_to_segment_mm": [_mm(v) for v in off]}, to_model


def axis_block(root, room: Room, role: str, s_values, members) -> dict:
    """M1, M2 and R9 on one axis, with G-B4's and G-B6's figures."""
    u_raw = np.asarray(read_address(root, AXES[role]), float)
    u = u_raw / np.linalg.norm(u_raw)
    uinfo = {"address": f"{AXES[role][0]}#{AXES[role][1]}", "as_read": [float(v) for v in u_raw], "used": [float(v) for v in u],
             "norm_residual_as_read": float(abs(np.linalg.norm(u_raw) - 1.0)), "norm_residual_used": float(abs(np.linalg.norm(u) - 1.0)), "tolerance": UNIT_TOL,
             "pass": bool(abs(np.linalg.norm(u) - 1.0) <= UNIT_TOL)}

    # M1
    prof = {c: profile(room, u, s_values, c[0], c.endswith("on")) for c in COMBOS}
    summ = {}
    for combo in COMBOS:
        r = prof[combo]
        k = int(np.argmax(r))
        summ[combo] = {"r_max_mm": _mm(r[k]), "s_at_max_mm": _mm(s_values[k]),
                       "s_ranges_mm": {f"r_ge_{int(L)}": runs_at_least(s_values, r, L) for L in R_LEVELS_MM},
                       "binding_at_max": disc_binding(room, u, s_values[k], r[k], combo[0], combo.endswith("on"))}
    table = [{"s_mm": _mm(s), **{c: _mm(prof[c][i]) for c in COMBOS}} for i, s in enumerate(s_values) if abs((s - S_FROM_MM) % REPORT_STEP_MM) < 1e-9]

    # G-B6: S's maximum against the ball's own disc there, and B inside S at every s it reaches
    kS = int(np.argmax(prof["S_off"]))
    b_at = summ["S_off"]["binding_at_max"]["surface"]
    resid = ball_disc_radius(room.R_B, s_values[kS]) - prof["S_off"][kS]
    below = [(s, ball_disc_radius(room.R_B, s) - r) for s, r in zip(s_values, prof["S_off"]) if ball_disc_radius(room.R_B, s) > 0]
    worst = max(below, key=lambda x: x[1])
    g6 = {"s_at_max_mm": _mm(s_values[kS]), "r_S_max_mm": _mm(prof["S_off"][kS]), "ball_disc_mm": _mm(ball_disc_radius(room.R_B, s_values[kS])),
          "residual_mm": float(f"{resid:.4f}") + 0.0, "binding_at_max": b_at, "tolerance_mm": BISECT_TOL_MM,
          "ball_inside_S_worst": {"s_mm": _mm(worst[0]), "ball_disc_less_r_S_mm": float(f"{worst[1]:.4f}") + 0.0}}
    g6["pass"] = bool((b_at != BALL or 0.0 <= resid <= BISECT_TOL_MM) and worst[1] <= BISECT_TOL_MM)

    # part.arm.upper_member against each disc (reported, not subtracted)
    member = []
    for cid, f, clr in members:
        for combo in ("N_off", "S_off"):
            hits = []
            for s, r in zip(s_values, prof[combo]):
                if r <= 0:
                    continue
                dmin = float((f(placed(disc(r), room.c + s * u, u) - room.c) - clr).min())
                if dmin < 0:
                    hits.append([_mm(s), _mm(-dmin)])
            member.append({"id": cid, "combo": combo, "s_mm_and_depth_mm": hits, "s_range_mm": [hits[0][0], hits[-1][0]] if hits else None,
                           "max_depth_mm": max(h[1] for h in hits) if hits else 0.0})

    # M2
    m2 = []
    for w in W_MM:
        row = {"w_mm": w}
        for combo in COMBOS:
            R, win = window_budget(s_values, prof[combo], w)
            row[combo] = {"R_w_mm": _mm(R), "window_s_mm": win}
        m2.append(row)

    # R9: the thorax alone from the centre to the axis's skin exit
    ex = axis_exit(room, u)
    s9 = [float(-x) for x in np.arange(0.0, -ex["s_mm"] + 1e-9, S_STEP_MM)]          # the grid points from the centre to the exit, the exit's side included
    r9 = {"T_off": profile(room, u, s9, "T", False), "T_on": profile(room, u, s9, "T", True)}
    runs, shaft = {}, {}
    for state, key in (("off", "T_off"), ("on", "T_on")):
        runs[state] = coaxial_runs(s9, r9[key])
        for run in runs[state]:
            k = s9.index(run["s_at_max_mm"])
            run["binding"] = disc_binding(room, u, s9[k], r9[key][k], "T", state == "on")
        shaft[state] = shaft_test(s9, r9[key], room.R_B)
        if shaft[state]["blocked_at_s_mm"] is not None:
            k = s9.index(shaft[state]["blocked_at_s_mm"])
            shaft[state]["binding"] = disc_binding(room, u, s9[k], max(r9[key][k], 0.0), "T", state == "on")
    r9_table = [{"s_mm": _mm(s), "T_off": _mm(r9["T_off"][i]), "T_on": _mm(r9["T_on"][i])} for i, s in enumerate(s9) if abs(s % REPORT_STEP_MM) < 1e-9]

    order = bound_order(prof)
    t_order = [_mm(s) for s, on, off in zip(s9, r9["T_on"], r9["T_off"]) if on > off]
    g4 = {"violations": [{"s_mm": _mm(s_values[i]), "lower": a, "upper": b} for i, a, b in order], "thorax_alone_on_above_off_at_s_mm": t_order,
          "pass": not order and not t_order}
    return {"role": ROLE_LABEL[role], "u1": uinfo,
            "m1": {"s_mm": [_mm(s) for s in s_values], "r_mm": {c: [_mm(v) for v in prof[c]] for c in COMBOS}, "table": table, "summary": summ, "upper_member": member},
            "m2": m2,
            "r9": {"exit": ex, "s_mm": [_mm(s) for s in s9], "r_mm": {k: [_mm(v) for v in r9[k]] for k in r9}, "table": r9_table, "runs": runs, "shaft_test": shaft,
                   "shaft_rule": f"radius {SHAFT_RADIUS_MM} mm from the joint ball (credited while the shaft's disc fits in it) to a point with thorax-alone r >= {SHAFT_TARGET_MM} mm"},
            "_gates": {"G-B4": g4, "G-B6": g6}}


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    t = float(read_address(root, SHELL))
    led = {n: _yaml(root, f"data/envelope/{n}.yaml") for n in (THORAX, ARM)}
    segs, cache = {}, {}
    for n in (THORAX, ARM):
        p = root / "data" / "envelope" / "cache" / f"{n}.npz"
        b = p.read_bytes()
        cache[n] = {"path": f"data/envelope/cache/{n}.npz", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
        segs[n] = field.Segment.load(p)
        if segs[n].meta.get("inputs_sha256_12") != led[n]["inputs_sha256_12"]:
            raise StopAndAsk(f"{n}: the cache was built from inputs {segs[n].meta.get('inputs_sha256_12')}, the ledger from {led[n]['inputs_sha256_12']}")
    T, A = segs[THORAX], segs[ARM]
    snap = snapshot(root)
    model_sjc = np.array([float(snap[f"{SJC_BODY}_pos_{k}"]) * 1000.0 for k in "xyz"])
    sjc, chain, to_model = envelope_sjc(root, T.meta, led[ARM])
    off_T = np.asarray(frames.segment_offset_mm(THORAX, T.meta), float)

    # G-B1: the centre and the lateral skin (u1 is checked per axis)
    d = sjc - model_sjc
    row = sections_row(root, LATERAL_STATION_MM)
    ray = A.section(LATERAL_STATION_MM).ray((0.0, 0.0), 270.0)
    lateral = abs(sjc[1]) + ray
    g1 = {"sjc_mm": [_mm(v) for v in sjc], "chain": chain, "upper_arm_right_mm": [_mm(v) for v in model_sjc],
          "x_difference_mm": _mm(d[0]), "y_difference_mm": float(f"{d[1]:.6f}") + 0.0, "z_difference_mm": float(f"{d[2]:.6f}") + 0.0,
          "yz_tolerance_mm": SJC_TOL_MM, "yz_pass": bool(abs(d[1]) <= SJC_TOL_MM and abs(d[2]) <= SJC_TOL_MM),
          "lateral": {"station_mm": LATERAL_STATION_MM, "arm_frame_z_mm": _mm(A.z_top - LATERAL_STATION_MM), "ray_along_minus_y_mm": _mm(ray), "skin_from_midline_mm": _mm(lateral),
                      "ledger_hw_lat_mm": float(row["hw_lat_mm"]), "ledger_from_midline_mm": _mm(abs(sjc[1]) + float(row["hw_lat_mm"])), "memo59_mm": MEMO59_LATERAL_MM,
                      "tolerance_mm": VOXEL_MM, "pass": bool(abs(lateral - MEMO59_LATERAL_MM) <= VOXEL_MM)}}

    # the ball
    rb = ball_radius_oracle(A, t)
    R_B = rb["R_B_mm"]
    rb_field = ball_radius_field(A, t)
    g3 = {"R_B_oracle_mm": _mm(R_B), "R_B_field_mm": _mm(rb_field), "difference_mm": _mm(R_B - rb_field), "tolerance_mm": VOXEL_MM, "pass": bool(abs(R_B - rb_field) <= VOXEL_MM),
          "sd_at_centre_less_t_mm": _mm(A.signed_distance([[0.0, 0.0, 0.0]])[0] - t), "above": rb["above"]}

    # bodies in the model frame
    arm_origin_in_T = sjc + off_T
    thorax = Body(THORAX, T, off_T)
    arm = Body(ARM, A, -sjc)
    U = occupancy.skin_field([(T, (0.0, 0.0, 0.0)), (A, tuple(arm_origin_in_T))], t)
    union = Body("N", U, off_T)
    reg_T = registry.load(root / RESERVED)
    modules = []
    for comp in reg_T.placed():
        b = occupancy.Body(comp, reg_T)
        for pose in reg_T.poses(comp):
            modules.append((comp.id, b.placed(pose)[1], float(comp.clearance_mm)))
    room = Room(thorax, arm, union, t, sjc, R_B, modules)
    reg_A = registry.load_generated(root / ARM_CAD)
    members = []
    for comp in reg_A.placed():
        b = occupancy.Body(comp, reg_A)
        members.append((comp.id, b.placed(reg_A.poses(comp)[0])[1], float(comp.clearance_mm)))

    s_values = [float(s) for s in np.arange(S_FROM_MM, S_TO_MM + 1e-9, S_STEP_MM)]
    axes = {role: axis_block(root, room, role, s_values, members) for role in ("basis", "comparison")}
    g4 = {role: axes[role]["_gates"].pop("G-B4") for role in axes}
    g6 = {role: axes[role]["_gates"].pop("G-B6") for role in axes}
    for role in axes:
        axes[role].pop("_gates")
    g1["u1_pass"] = all(axes[r]["u1"]["pass"] for r in axes)
    g1["pass"] = bool(g1["yz_pass"] and g1["u1_pass"] and g1["lateral"]["pass"])
    g4["pass"] = all(g4[r]["pass"] for r in axes)
    g6["pass"] = all(g6[r]["pass"] for r in axes)

    akh = read_address(root, MODULE)
    marks = {"address": f"{MODULE[0]}#{MODULE[1]}", "diameter_mm": float(akh["diameter_mm"]), "length_mm": float(akh["length_mm"]), "radius_mm": float(akh["diameter_mm"]) / 2,
             "note": "scale marks only: a serial roll actuator lying along axis 2 has axial thickness along u1 equal to its diameter and radial extent its distance from the SJC plus its length"}

    # the free-sphere hint (kept as written: the free field, reservations on)
    spheres = {}
    for tag, parts in (("thorax", [(T, (0.0, 0.0, 0.0))]), ("thorax+upper_arm_R", [(T, (0.0, 0.0, 0.0)), (A, tuple(arm_origin_in_T))])):
        reg_T.frame_offset_mm = tuple(off_T)
        virt, _ = occupancy.free_field(parts, [(reg_T, (0.0, 0.0, 0.0))], t)
        C = [virt.o[i] + virt.h * (np.arange(virt.sd.shape[i]) + 0.5) for i in range(3)]
        X, Y, Z = np.meshgrid(*C, indexing="ij")
        dist = np.sqrt((X - arm_origin_in_T[0]) ** 2 + (Y - arm_origin_in_T[1]) ** 2 + (Z - arm_origin_in_T[2]) ** 2)
        masked = np.where(virt.region & (dist <= SPHERE_WITHIN_MM), virt.sd, -np.inf)
        kk = np.unravel_index(int(np.argmax(masked)), masked.shape)
        centre = np.array([C[0][kk[0]], C[1][kk[1]], C[2][kk[2]]]) - off_T
        rel = centre - sjc
        spheres[tag] = {"radius_mm": _mm(masked[kk]), "centre_mm": [_mm(v) for v in centre], "distance_from_sjc_mm": _mm(np.linalg.norm(rel)),
                        **{f"{role}_s_along_u1_mm": _mm(rel @ np.asarray(axes[role]["u1"]["used"])) for role in axes},
                        **{f"{role}_off_axis_mm": _mm(np.linalg.norm(rel - (rel @ np.asarray(axes[role]["u1"]["used"])) * np.asarray(axes[role]["u1"]["used"]))) for role in axes}}
    reg_T.frame_offset_mm = (0.0, 0.0, 0.0)

    # M4: the clavicle corridor
    tb = _json(root, TRUNK_BODIES)
    dumas = _json(root, DUMAS)
    L_thorax = float(snap["thorax_length"]) * 1000.0
    k_scale = L_thorax / float(dumas["reference_length_mm"]["thorax"])
    sup = dumas["segments"]["thorax"]["landmarks"]["SUP"]
    cjc_x_mesh = float(tb["shoulder"]["plane"]["cjc_x_mesh_mm"])
    cjc_z_mesh = float(tb["mesh_nodes_mm"]["cjc"])
    sup_mesh = np.array([cjc_x_mesh + sup[0] * k_scale, 0.0, cjc_z_mesh + sup[1] * k_scale])
    sup_model, _ = to_model(sup_mesh)
    m4 = {"thorax_length_mm": _mm(L_thorax), "thorax_length_address": "snapshot#/thorax_length", "scale": float(k_scale), "dumas_sup_mm": sup,
          "mesh_cjc_mm": {"x_centre_line": _mm(cjc_x_mesh), "z": _mm(cjc_z_mesh)}, "sup_mesh_mm": [_mm(v) for v in sup_mesh], "sup_model_mm": [_mm(v) for v in sup_model],
          "registration_places_sup": False, "registration_sup_below_cjc_mm": _mm(read_address(root, (TRUNK_REGISTRATION, "/mesh/sup_below_cjc_mm"))),
          "registration_note": f"the trunk registration uses SUP's height only, as a CJC cross-check ({TRUNK_REGISTRATION}#/mesh/sup_below_cjc_mm); it places no SUP point",
          "rows": []}
    for cc in C_ROWS_MM:
        node = sup_model + np.array([0.0, -cc, 0.0])
        seg_vec = sjc - node
        length = float(np.linalg.norm(seg_vec))
        dirn = seg_vec / length
        mid = 0.5 * (node + sjc)
        ts = np.linspace(0.0, length, int(np.ceil(length / 0.5)) + 1)
        held = thorax.held(node + ts[:, None] * dirn)
        out_idx = np.flatnonzero(~held)
        switch = float(ts[out_idx[0]]) if len(out_idx) else None
        row = {"c_mm": cc, "node_mm": [_mm(v) for v in node], "length_mm": _mm(length), "leaves_thorax_region_at_mm_from_node": _mm(switch) if switch is not None else None,
               "node_inside_thorax_region": bool(held[0]), "node_thorax_sd_mm": _mm(thorax.sd(node[None])[0])}
        for on in (False, True):
            def cap(r, on=on):
                return placed({"type": "capsule", "radius": r, "length": length}, mid, dirn)
            r = bisect(lambda r: room.ok(cap(r), "S", on), R_BRACKET_MM)
            b = room.binding(cap(r + BISECT_TOL_MM), "S", on)
            b["at_mm_from_node"] = _mm((np.asarray(b["point_mm"]) - node) @ dirn)

            def ball(r, on=on):
                return placed({"type": "capsule", "radius": r, "length": 0.0}, node, dirn)
            rb_ = bisect(lambda r: room.ok(ball(r), "T", on), R_BRACKET_MM)
            row["on" if on else "off"] = {"capsule_radius_mm": _mm(r), "capsule_binding": b, "node_ball_radius_mm": _mm(rb_),
                                          "node_ball_binding": room.binding(ball(rb_ + BISECT_TOL_MM), "T", on)}
        m4["rows"].append(row)

    return {
        "schema": "shoulder-room/1", "generated_by": "analysis/shoulder_room.py", "inputs": f"sha256:{inputs_hash(root)}", "arguments": {},
        "frame": "thorax model body frame: x anterior, y left, z up, mm, origin at the model's CJC; s along u1 from the envelope SJC, positive toward u1's upper end",
        "shell_t_mm": t, "shell_address": f"{SHELL[0]}#{SHELL[1]}",
        "cache": cache, "ledgers": {n: {"file": f"data/envelope/{n}.yaml", "inputs_sha256_12": led[n]["inputs_sha256_12"]} for n in (THORAX, ARM)},
        "constants": {"s_mm": [S_FROM_MM, S_TO_MM, S_STEP_MM], "disc_length_mm": DISC_LENGTH_MM, "bisection_tolerance_mm": BISECT_TOL_MM, "sample_mm": oracle.SAMPLE_MM,
                      "r_bracket_mm": R_BRACKET_MM, "axis_step_mm": AXIS_STEP_MM, "exit_reach_mm": EXIT_REACH_MM, "shaft_mm": [SHAFT_RADIUS_MM, SHAFT_TARGET_MM]},
        "bounds": {"B": "ball of radius R_B about the SJC, inside upper_arm_R alone with margin t (R_B already less t)",
                   "N": "(thorax and upper_arm_R held by region, occupancy.skin_field) union B (Amendment 2, R6)", "S": "thorax held by region union B (R7)",
                   "T": "thorax alone, held by region (R9)"},
        "reserved_modules": [{"id": m[0], "clearance_mm": m[2]} for m in modules],
        "gates": {"G-B1": g1, "G-B3": g3, "G-B4": g4, "G-B6": g6,
                  "G-B2": "synthetic: tests/test_shoulder_room.py (no cache)", "G-B5": "tests/test_shoulder_room.py rebuilds and compares with this file"},
        "ball": {"R_B_mm": _mm(R_B), **rb["above"]},
        "unheld_sheet": unheld_sheet(room),
        "axes": axes,
        "akh70_marks": marks,
        "free_spheres": spheres,
        "free_sphere_note": f"a hint at off-axis motor room for a belt or cable drive: the largest free sphere (skin margin t, the reserved modules out) whose centre is within {SPHERE_WITHIN_MM:g} mm of the SJC",
        "m4": m4,
    }


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.str_):
        return str(o)
    raise TypeError(type(o))


def render(result: dict) -> str:
    return json.dumps(result, indent=1, sort_keys=True, default=_default) + "\n"


def plot(result: dict, path: Path) -> bool:
    """The r(s) profiles of M1, the four combinations on one axis per basin, with the AKH70 radius marked (T4). False when matplotlib is absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    ink, ink2 = "#191919", "#666666"
    style = {"N_off": ("#257de0", "-"), "N_on": ("#257de0", (0, (4, 3))), "S_off": ("#f47230", "-"), "S_on": ("#f47230", (0, (4, 3)))}
    label = {"N_off": "N (region union ∪ ball), reservations off", "N_on": "N, reservations on", "S_off": "S (thorax ∪ ball), reservations off", "S_on": "S, reservations on"}
    fig, axs = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    for ax, role in zip(axs, ("basis", "comparison")):
        a = result["axes"][role]
        s = a["m1"]["s_mm"]
        for c in COMBOS:
            col, ls = style[c]
            ax.plot(s, a["m1"]["r_mm"][c], color=col, ls=ls, lw=2, label=label[c])
        for c in ("N_off", "S_off"):
            sm = a["m1"]["summary"][c]
            ax.annotate(f"{sm['r_max_mm']:.1f}", (sm["s_at_max_mm"], sm["r_max_mm"]), xytext=(0, 6), textcoords="offset points", ha="center", color=ink, fontsize=9)
        R = result["akh70_marks"]["radius_mm"]
        ax.axhline(R, color=ink2, lw=1, ls=":")
        ax.text(S_TO_MM, R + 0.6, f"AKH70 radius {R:g} mm (scale mark)", ha="right", va="bottom", color=ink2, fontsize=9)
        ax.set_title(f"r(s) about u1 = {a['u1']['address']}: {a['role']}", color=ink, fontsize=11)
        ax.set_ylabel("largest disc radius about u1, t = 5 mm (mm)", color=ink)
        ax.set_ylim(0, 50)
        ax.grid(color="#e6e6e6", lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=ink)
    axs[-1].set_xlabel("s along u1 from the envelope SJC (mm); negative: toward the lower end", color=ink)
    axs[-1].set_xlim(S_FROM_MM, S_TO_MM)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=100)
    plt.close(fig)
    return True


def main(argv) -> int:
    if argv:
        print("analysis/shoulder_room.py takes no arguments", file=sys.stderr)
        return 2
    result = build(ROOT)
    with open(ROOT / OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(result))
    print(f"wrote {OUT}")
    if plot(result, ROOT / PLOT):
        print(f"wrote {PLOT} (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
