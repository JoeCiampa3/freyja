"""The arm bodies (volume-extractor brief 8, Phase A): upper arm, forearm and hand of one side, each as a voxel field in its own segment frame.

The model's arms hang straight down in the zero pose (the forearm at -L_upper_arm and the hand at -L_forearm along the arm's z); the mesh is in an A-pose. A segment is therefore taken
from the mesh by a rigid rotation about its proximal joint centre that turns the segment's axis (proximal to distal node) onto -z, then an axial stretch along that axis to the sheet's
length (a shear would inflate sections by 1/cos of the angle; a rotation leaves every section as it is, the stretch changes only lengths). The hand takes the forearm's rotation and no
stretch. Each segment is extracted in its own frame; no assembled arm exists. The frame origin is the proximal node, which for the upper arm is the mesh's own shoulder joint centre (the sheet's
SJC carried through the trunk registration, as in brief 5's shoulder planes), so `origin_xyz` of a built arm is the position in a model-frame stack of the arm (upper arm 0, forearm -L_upper arm,
hand -(L_upper arm + L_forearm)), used by the oracle's union query only.

Membership (mesh frame): a cell is arm when its nearest body vertex is an arm vertex (`decompose.vertex_regions`) or `bodies.classify` moved it to the arm in the clean-up below the axilla;
the upper arm also takes the shoulder girdle of its side (thorax band, above the axilla, beyond the SJC plane). Every segment is cut by its own plane (perpendicular to its axis) at its distal end; at the
elbow, whose axes meet at about 40 degrees, the two planes overlap on the inner side (0.048 l a side, counted twice) and leave a small gap on the outer (0.008 l), so the cells of the overlap are
given to one body by the bisector plane through the EJC (a cell is the upper arm's on its proximal side and the forearm's on the other); the gap stays. The wrist needs no such rule: the hand takes
the forearm's rotation, so the two planes are one.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import anthro, bodies, field, frames, ledger, ruler, sheet, trial
from .sheet import StopAndAsk

NAMES = ("upper_arm", "forearm", "hand")
SIGMA_MM = 17.3                  # Joe, memo 38 decision 1: the knee anchor SD, a stated assumption; the arm stretch gate is GATE_SIGMAS x sigma / sheet length (the legs': 2 x 17.3 / 398 = 8.7%)
GATE_SIGMAS = 2.0
ZONE_H_MM = bodies.ZONE_H_MM
UPPER_ID, FORE_ID = ("measure/measure-upperarm-length-decr|incr", "measure/measure-lowerarm-length-decr|incr")
GIRDLE_PAD_MM = 6.0              # the upper arm's top: the highest frame z of the girdle and arm vertices plus this, rounded up to a voxel
SEG_KEY = {"upper_arm": "upper_arm_R", "forearm": "forearm_R", "hand": "hand_R"}


def sheet_arm(snapshot_path, side="right") -> dict:
    """Lengths (mm) and masses (kg) of the sheet's arm segments from the snapshot."""
    snap = sheet.read_snapshot(snapshot_path)
    out = {}
    for n in NAMES:
        for k, scale, key in ((f"{n}_{side}_mass", 1.0, "mass_kg"), (f"{n}_{side}_length", 1000.0, "length_mm")):
            if k not in snap:
                raise StopAndAsk(f"snapshot key {k} is missing")
            out.setdefault(n, {})[key] = snap[k] * scale
    return out


def rotation_to_down(u) -> np.ndarray:
    """The rotation that turns the unit vector u onto (0, 0, -1) by the shortest arc (Rodrigues)."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    d = np.array([0.0, 0.0, -1.0])
    v, c = np.cross(u, d), float(u @ d)
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1.0 + c)


class ArmFrame:
    """mesh -> segment frame: rotate about `origin`, then stretch the axial (z) coordinate by k."""

    def __init__(self, origin, axis, k=1.0):
        self.origin, self.R, self.k = np.asarray(origin, float), rotation_to_down(axis), float(k)

    def forward(self, P):
        Q = (np.atleast_2d(P) - self.origin) @ self.R.T
        return Q * np.array([1.0, 1.0, self.k])

    def inverse(self, Q):
        return (np.atleast_2d(Q) / np.array([1.0, 1.0, self.k])) @ self.R + self.origin


def angle_from_vertical_deg(u) -> float:
    u = np.asarray(u, float) / np.linalg.norm(u)
    return float(np.degrees(np.arccos(np.clip(-u[2], -1, 1))))


def _mirror_ids(V, ids):
    """Vertex ids of the opposite side: the nearest vertex to the mirrored position (the mesh is left-right symmetric)."""
    tree = cKDTree(V)
    out, gap = [], 0.0
    for i in ids:
        p = V[i] * np.array([1.0, -1.0, 1.0])
        d, j = tree.query(p)
        out.append(int(j))
        gap = max(gap, float(d))
    return out, gap


def registration(inp, tb, ruler_measures, arm_sheet, side="R") -> dict:
    """Nodes, lengths, the stretch against the segment's own gate, and the rotation angle of each arm segment. Stops when a stretch is beyond its gate. Mesh frame, mm.

    SJC: the sheet's, through the trunk registration (x the shoulder sphere's centre, y the plane's lateral distance, z the inverse of the trunk map at the sheet's SJC height). Elbow: the mean
    of the Ruler upper-arm chord's end and the forearm chord's start. Wrist: the forearm chord's end. The Ruler lists belong to the left arm; the right arm takes the nearest vertex to each
    mirrored position. Hand: the arm-labelled vertices of the side beyond the wrist plane (normal to the forearm axis), below the elbow; the fingertip is the farthest of them from the wrist."""
    V = inp.V
    ids = [ruler_measures[UPPER_ID][0], ruler_measures[UPPER_ID][1], ruler_measures[FORE_ID][0], ruler_measures[FORE_ID][1]]
    mirror_gap = 0.0
    if side == "R":
        ids, mirror_gap = _mirror_ids(V, ids)
    sgn = -1.0 if side == "R" else 1.0
    P = V[ids]
    sph = tb.acc["spheres"]
    z_sjc = float(tb.tm.inverse(sph["centre_height_mm"]))
    sjc = np.array([sph["centre_x_mesh_mm"], sgn * tb.sjc["lateral_mm"], z_sjc])
    elbow, wrist = 0.5 * (P[1] + P[2]), P[3]
    u_up, u_fo = (elbow - sjc), (wrist - elbow)
    l_mesh = {"upper_arm": float(np.linalg.norm(u_up)), "forearm": float(np.linalg.norm(u_fo))}
    sheet_len = {n: arm_sheet[n]["length_mm"] for n in NAMES}
    k = {n: sheet_len[n] / l_mesh[n] for n in ("upper_arm", "forearm")}
    gate = {n: GATE_SIGMAS * SIGMA_MM / sheet_len[n] for n in ("upper_arm", "forearm")}
    u_fo_n = u_fo / np.linalg.norm(u_fo)
    zone = (V[:, 1] * sgn > 0) & tb.arm_mask & (V[:, 2] < elbow[2] + 1.0)
    s = (V - wrist) @ u_fo_n
    hand = zone & (s > 0.0)
    H = V[hand]
    tip = H[int(np.argmax(np.linalg.norm(H - wrist, axis=1)))]
    u_hand = (tip - wrist) / np.linalg.norm(tip - wrist)
    out = {"side": side, "mirror_gap_mm": mirror_gap, "vertex_ids": dict(zip(("upper_arm_chord_start", "upper_arm_chord_end", "forearm_chord_start", "forearm_chord_end"), ids)),
           "nodes_mesh_mm": {"sjc": sjc, "elbow": elbow, "wrist": wrist, "fingertip": tip}, "lengths_mesh_mm": l_mesh, "lengths_sheet_mm": sheet_len, "stretch": k, "gate": gate,
           "sigma_mm": SIGMA_MM, "gate_rule": f"{GATE_SIGMAS:g} x sigma / sheet length, sigma {SIGMA_MM} mm (memo 38 decision 1)",
           "angle_from_vertical_deg": {"upper_arm": angle_from_vertical_deg(u_up), "forearm": angle_from_vertical_deg(u_fo), "hand": angle_from_vertical_deg(u_hand)},
           "elbow_bend_deg": float(np.degrees(np.arccos(np.clip((u_up / np.linalg.norm(u_up)) @ u_fo_n, -1, 1)))),
           "wrist_bend_deg": float(np.degrees(np.arccos(np.clip(u_fo_n @ u_hand, -1, 1)))),
           "hand": {"vertices": int(hand.sum()), "fingertip_distance_from_wrist_mm": float(np.linalg.norm(tip - wrist)),
                    "extent_along_forearm_axis_mm": float(s[hand].max()), "stretch": 1.0, "sheet_scs_length_mm": sheet_len["hand"]},
           "axes": {"upper_arm": u_up / np.linalg.norm(u_up), "forearm": u_fo_n}}
    over = [n for n in ("upper_arm", "forearm") if abs(k[n] - 1.0) > gate[n]]
    out["exceeding_gate"] = over
    if over:
        raise StopAndAsk("arm stretch beyond its gate: " + ", ".join(f"{n} {k[n]:.4f} (gate +-{gate[n] * 100:.1f}%)" for n in over))
    return out


def ansur_check(inp, reg) -> dict:
    """The pose-invariant ANSUR lengths scaled to the mesh stature against the mesh and the sheet (context only: they are surface-landmark distances, not joint-centre ones)."""
    a = inp.ansur.get("arm_lengths")
    if not a or set(a) != set(anthro.ARM_COLUMNS):
        raise StopAndAsk("data/ansur2/ratios.json has no arm_lengths; run `fy envelope ratios`")
    S = inp.stature_mesh
    L = reg["lengths_mesh_mm"]
    rows = {n: {"ansur_scaled_mm": a[n]["ratio"]["mean"] * S, "sd_mm": a[n]["ratio"]["sd"] * S} for n in a}
    rows["shoulder_elbow"]["mesh_node_to_node_mm"], rows["shoulder_elbow"]["compared_with"] = L["upper_arm"], "SJC to elbow (the ANSUR length runs acromion to olecranon: expect it longer)"
    rows["radiale_stylion"]["mesh_node_to_node_mm"], rows["radiale_stylion"]["compared_with"] = L["forearm"], "elbow to wrist"
    rows["radiale_stylion"]["mesh_over_ansur"] = L["forearm"] / rows["radiale_stylion"]["ansur_scaled_mm"]
    rows["forearm_hand"]["mesh_node_to_node_mm"] = L["forearm"] + reg["hand"]["extent_along_forearm_axis_mm"]
    rows["forearm_hand"]["compared_with"] = "elbow to wrist plus the hand's extent along the forearm axis"
    rows["hand_length"]["mesh_node_to_node_mm"] = reg["hand"]["fingertip_distance_from_wrist_mm"]
    rows["hand_length"]["compared_with"] = "wrist to fingertip"
    return rows


# ---- membership and the build ----------------------------------------------------------------------------------------------------------

class Membership:
    """Which point of the mesh frame is arm / girdle for one side: the nearest-vertex rule, the cells `classify` moved to the arm, and the shoulder girdle (an analytic rule)."""

    def __init__(self, inp, tb, side):
        self.V, self.side = inp.V, side
        self.sgn = -1.0 if side == "R" else 1.0
        am = np.asarray(tb.arm_mask, bool)
        self.arm_tree, self.rest_tree = cKDTree(inp.V[am]), cKDTree(inp.V[~am])
        self.arm_mask = am & (inp.V[:, 2] <= tb.tm.mesh[2])        # the label also holds the ears (a separate piece of the head's layers): only what lies below the CJC can be an arm vertex
        self.leak = tb.acc["leak_grid"]
        self.o, self.h = np.array(tb.acc["raster_origin_mm"]), float(tb.acc["layer_h"])
        self.axilla, self.lateral, self.tm, self.sheet = tb.axilla["level_mm"], tb.sjc["lateral_mm"], tb.tm, tb.sheet

    def arm(self, P):
        P = np.atleast_2d(P)
        a = self.arm_nearest(P)
        g = np.floor((P - self.o) / self.h).astype(int)
        ok = np.all((g >= 0) & (g < np.array(self.leak.shape)), axis=1)
        leak = np.zeros(len(P), bool)
        leak[ok] = self.leak[g[ok, 0], g[ok, 1], g[ok, 2]]
        return a | leak

    def girdle_rule(self, P):
        """Thorax band, above the axilla, beyond the SJC plane on this side: what `bodies.classify` calls the shoulder girdle (before the arm label overrides)."""
        P = np.atleast_2d(P)
        zf = self.tm.forward(P[:, 2])
        return (P[:, 2] >= self.axilla) & (self.sgn * P[:, 1] > self.lateral) & (zf >= self.sheet["tjc"]) & (zf < self.sheet["cjc"])

    def arm_nearest(self, P):
        """The nearest-vertex rule alone (without the cells `classify` moved)."""
        P = np.atleast_2d(P)
        return self.arm_tree.query(P, workers=-1)[0] < self.rest_tree.query(P, workers=-1)[0]

    def side_ok(self, P):
        return self.sgn * np.atleast_2d(P)[:, 1] > 0.0


def build_segment(inp, tb, reg, mem, name, voxel=trial.VOXEL_MM, h_zone=ZONE_H_MM) -> trial.SegResult:
    """One arm segment of one side as a voxel field in its own frame (origin at the proximal node, z up, the distal plane at z = -sheet length; the upper arm reaches above the SJC by the
    girdle: its z_top is that height and its stations are measured down from it)."""
    nodes, axes = reg["nodes_mesh_mm"], reg["axes"]
    L_sheet = reg["lengths_sheet_mm"]
    if name == "upper_arm":
        frame, L = ArmFrame(nodes["sjc"], axes["upper_arm"], reg["stretch"]["upper_arm"]), L_sheet["upper_arm"]
    elif name == "forearm":
        frame, L = ArmFrame(nodes["elbow"], axes["forearm"], reg["stretch"]["forearm"]), L_sheet["forearm"]
    else:
        frame, L = ArmFrame(nodes["wrist"], axes["forearm"], 1.0), reg["hand"]["extent_along_forearm_axis_mm"]
        L = float(np.ceil(L / voxel) * voxel)
    Vf = frame.forward(inp.V)
    own = mem.arm_mask & mem.side_ok(inp.V)           # vertices bearing on the segment
    gird = mem.girdle_rule(inp.V) & mem.side_ok(inp.V)
    cand = (own | gird) if name == "upper_arm" else own
    z_top = 0.0
    if name == "upper_arm":
        z_top = float(np.ceil((Vf[cand & (Vf[:, 2] > -L - 40.0), 2].max() + GIRDLE_PAD_MM) / voxel) * voxel)
    length = L + z_top
    slab = (Vf[:, 2] <= z_top + trial.MARGIN_MM) & (Vf[:, 2] >= z_top - length - trial.MARGIN_MM)
    sel = Vf[cand & slab]
    pad = trial.SIDE_PAD_MM
    xy = (sel[:, 0].min() - pad, sel[:, 0].max() + pad, sel[:, 1].min() - pad, sel[:, 1].max() + pad)

    def region(X, Y, Z):
        Pm = frame.inverse(np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]))
        ok = mem.side_ok(Pm) & (mem.arm(Pm) | (mem.girdle_rule(Pm) if name == "upper_arm" else False))
        if name in ("upper_arm", "forearm"):             # the elbow is cut on the bisector plane through the EJC, so a cell in both bodies' slabs goes to exactly one of them
            side = (Pm - nodes["elbow"]) @ mem.elbow_normal
            ok &= (side <= 0.0) if name == "upper_arm" else (side > 0.0)
        return ok.reshape(X.shape)

    def seed_point():
        if name == "hand":
            s = (inp.V - nodes["wrist"]) @ axes["forearm"]
            for lo, hi in ((20.0, 60.0), (10.0, 40.0), (0.0, 30.0)):          # the mean of the hand's surface vertices at the first wrist-side window that lies inside the skin (the hand curves away from the forearm axis)
                c = inp.V[own & (s > lo) & (s < hi)].mean(axis=0)
                if field.contains(inp.V, inp.F, c):
                    return frame.forward(c)[0]
            raise StopAndAsk("no point inside the hand near the wrist for the connected-component seed")
        return np.array([0.0, 0.0, -0.5 * L_sheet[name]])

    seed = seed_point()
    seg = field.build_segment(Vf, inp.F, length=length, voxel=voxel, z_top=z_top, margin=trial.MARGIN_MM, xy=xy, region_fn=region, seed_point=seed, full_ray=True)
    touch = (cand & slab)[inp.F].any(axis=1)
    wt = field.watertight(inp.F, touch)
    checks = {"boundary_edges_near_segment": wt["boundary_edges"], "nonmanifold_edges_near_segment": wt["nonmanifold_edges"],
              "boundary_edges_whole_body": field.watertight(inp.F)["boundary_edges"], "odd_parity_columns": seg.odd_columns, "seed_inside_region": bool(seg.in_region(seed[None])[0])}
    stack = {"upper_arm": 0.0, "forearm": -L_sheet["upper_arm"], "hand": -(L_sheet["upper_arm"] + L_sheet["forearm"])}[name]
    origin = (0.0, 0.0, stack)
    seg.meta = {"segment": SEG_KEY[name], "origin_xyz": list(origin), "origin_note": "the position in a model-frame stack of the arm (zero-pose): upper arm 0, forearm -L_upper_arm, hand -(L_upper_arm + L_forearm); the oracle's union query only",
                "frame_origin_mesh_mm": [float(v) for v in frame.origin], "rotation_mesh_to_segment": frame.R.tolist(), "axial_stretch": frame.k, "z_top_mm": z_top, "side": mem.side,
                "joint_station_mm": z_top if name == "upper_arm" else 0.0}
    return trial.SegResult(SEG_KEY[name], seg, tb.tm.reg, checks, origin, reg["masses_kg"][name])


# ---- numbers ---------------------------------------------------------------------------------------------------------------------------

FREE_END_MM = bodies.FREE_END_MM
ELBOW_CUT_MM = 15.0              # the bisector cut at the elbow slants the end faces: it takes up to about r x tan(bend / 2) = 36 mm x tan 21 deg = 14 mm off the inner side, so the minimum radius leaves the last / first 15 mm out


def design_in_range(res, rows, name, station_range) -> dict:
    """`bodies.design_numbers` over the stations in `station_range` for the minimum inscribed radius and the pinch stations: the hand's fingertip cap and the upper arm's shoulder dome go to
    a radius of 0 by geometry (as the head's crown), so the search leaves them out; the range is reported."""
    lo, hi = station_range
    keep = [r for r in rows if lo <= r["s_mm"] <= hi]
    d = bodies.design_numbers(res, keep)
    d["min_inscribed_radius"]["from_station_mm"], d["min_inscribed_radius"]["to_station_mm"] = lo, hi
    d["skin_volume_l"] = res.seg.volume(0.0) / 1e6                 # the volumes are of the whole body, not of the range
    d["inner_volume_l"] = {f"t{t:g}": res.seg.volume(t) / 1e6 for t in bodies.INNER_MM}
    d["required_density_skin_kg_per_l"] = res.mass_kg / d["skin_volume_l"]
    d["required_density_inner_kg_per_l"] = {t: res.mass_kg / v for t, v in d["inner_volume_l"].items()}
    d["pinch_stations"] = bodies.pinch_stations(keep)
    return d


def _ramp(seg, t=0.0):
    return seg._fraction(t) * seg.region


def volume_where(seg, mask_fn, t=0.0) -> float:
    """Volume (mm3) of {sd >= t} in the segment whose voxel centres satisfy mask_fn(centres (n, 3) in the segment frame)."""
    C = [seg.centres(i) for i in range(3)]
    X, Y, Z = np.meshgrid(*C, indexing="ij")
    P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    zl = C[2]
    w = np.clip((zl - (seg.z_top - seg.length)) / seg.h + 0.5, 0, 1) * np.clip((seg.z_top - 0.0 - zl) / seg.h + 0.5, 0, 1) * seg.zweight
    m = mask_fn(P).reshape(X.shape)
    return float((_ramp(seg, t) * w[None, None, :] * m).sum() * seg.h ** 3)


def zone_numbers(seg, name, mem, frame, h_zone=ZONE_H_MM) -> dict:
    """Volume (litres) with and without the joint-zone slab (+-h of each joint plane the body owns: for the upper arm the elbow slab and the SJC sphere; the forearm the elbow and wrist
    slabs; the hand the wrist slab), and for the upper arm with and without the shoulder girdle."""
    v = seg.volume(0.0) / 1e6
    L, zt = seg.length, seg.z_top
    out = {"with_zones_l": v, "zone_h_mm": h_zone}
    if name == "upper_arm":
        elbow = seg.volume(0.0, L - h_zone, L) / 1e6
        sph = volume_where(seg, lambda P: np.linalg.norm(P, axis=1) < h_zone) / 1e6
        gird = volume_where(seg, lambda P: mem.girdle_rule(frame.inverse(P)) & ~mem.arm_nearest(frame.inverse(P))) / 1e6
        out.update({"slab_l": {"elbow": elbow, "sjc_sphere": sph}, "without_all_l": v - elbow - sph, "girdle_l": gird, "without_girdle_l": v - gird, "without_girdle_and_zones_l": v - gird - elbow - sph})
    elif name == "forearm":
        a, b = seg.volume(0.0, 0.0, h_zone) / 1e6, seg.volume(0.0, L - h_zone, L) / 1e6
        out.update({"slab_l": {"elbow": a, "wrist": b}, "without_all_l": v - a - b})
    else:
        a = seg.volume(0.0, 0.0, h_zone) / 1e6
        out.update({"slab_l": {"wrist": a}, "without_all_l": v - a})
    return out


def hand_numbers(seg) -> dict:
    """The hand's volume, bounding dimensions in its frame and the wrist interface section at the WJC plane."""
    m = seg.region & (seg.sd >= 0.0)
    ii, jj, kk = np.nonzero(m)
    lo = [float(seg.centres(a)[idx].min()) for a, idx in enumerate((ii, jj, kk))]
    hi = [float(seg.centres(a)[idx].max()) for a, idx in enumerate((ii, jj, kk))]
    sec = seg.section(0.0)
    cx, cy, r = sec.chebyshev(0.0)
    mk = sec.mask(0.0)
    X, Y = np.meshgrid(sec.x, sec.y, indexing="ij")
    return {"volume_l": seg.volume(0.0) / 1e6, "bounding_box_mm": {"x_anterior": hi[0] - lo[0], "y_lateral": hi[1] - lo[1], "z_axial": hi[2] - lo[2]},
            "wrist_section": {"area_mm2": sec.area(0.0), "perimeter_mm": sec.perimeter(0.0), "width_x_mm": float(X[mk].max() - X[mk].min()) if mk.any() else 0.0,
                              "width_y_mm": float(Y[mk].max() - Y[mk].min()) if mk.any() else 0.0, "cheb_r_mm": r}}


def interface_sections(res: dict) -> dict:
    """Section areas at the elbow and wrist interfaces (upper arm end vs forearm start; forearm end vs hand start)."""
    ua, fa, hd = res["upper_arm"].seg, res["forearm"].seg, res["hand"].seg
    out = {}
    for label, a, sa, b, sb in (("elbow", ua, ua.length, fa, 0.0), ("wrist", fa, fa.length, hd, 0.0)):
        A, B = a.section(sa).area(0.0), b.section(sb).area(0.0)
        out[label] = {"upper_side_area_mm2": A, "lower_side_area_mm2": B, "relative": (B - A) / A}
    return out


def raster_arm_volumes(acc, side) -> dict:
    """The accounting's mesh-frame volumes for one side (litres, unconformed): the arm class is both arms together, so only the shoulder girdle splits by side."""
    return {"arms_both_l": acc["volume_unconformed_l"]["arms"], "girdle_l": acc["volume_unconformed_l"][f"shoulder_{side}"]}


def build_side(inp, tb, ruler_measures, arm_sheet, side="R", voxel=trial.VOXEL_MM) -> dict:
    """Registration and the three bodies of one side."""
    reg = registration(inp, tb, ruler_measures, arm_sheet, side)
    reg["masses_kg"] = {n: arm_sheet[n]["mass_kg"] for n in NAMES}
    mem = Membership(inp, tb, side)
    ne = reg["axes"]["upper_arm"] + reg["axes"]["forearm"]
    mem.elbow_normal = ne / np.linalg.norm(ne)           # the bisector of the two axes: the plane that cuts the elbow
    res = {n: build_segment(inp, tb, reg, mem, n, voxel) for n in NAMES}
    frames_ = {"upper_arm": ArmFrame(reg["nodes_mesh_mm"]["sjc"], reg["axes"]["upper_arm"], reg["stretch"]["upper_arm"]),
               "forearm": ArmFrame(reg["nodes_mesh_mm"]["elbow"], reg["axes"]["forearm"], reg["stretch"]["forearm"]),
               "hand": ArmFrame(reg["nodes_mesh_mm"]["wrist"], reg["axes"]["forearm"], 1.0)}
    rows, design, zones = {}, {}, {}
    for n in NAMES:
        rows[n] = ledger.rows_for(res[n].seg, "right")
        Ls = res[n].seg.length
        rng = {"upper_arm": (res[n].seg.meta["joint_station_mm"], Ls - ELBOW_CUT_MM), "forearm": (ELBOW_CUT_MM, Ls), "hand": (0.0, Ls - FREE_END_MM)}[n]
        design[n] = design_in_range(res[n], rows[n], n, rng)
        zones[n] = zone_numbers(res[n].seg, n, mem, frames_[n])
        k = frames_[n].k
        design[n]["axial_stretch"] = k
        design[n]["unconformed_skin_volume_l"] = design[n]["skin_volume_l"] / k
        design[n]["conform_volume_change_l"] = design[n]["skin_volume_l"] - design[n]["unconformed_skin_volume_l"]
    # where the nodes sit in the skin: the signed distance (positive inside) at each segment's proximal node and, for the upper arm and forearm, its distal node, both on the segment's axis
    nd = {}
    for n in NAMES:
        L = reg["lengths_sheet_mm"][n]
        pts = np.array([[0.0, 0.0, 0.0]] + ([[0.0, 0.0, -L]] if n != "hand" else []))
        sd = res[n].seg.signed_distance(pts)
        nd[n] = {"proximal_node_skin_distance_mm": float(sd[0]), **({"distal_node_skin_distance_mm": float(sd[1])} if n != "hand" else {})}
        cx, cy, r = res[n].seg.section(float(res[n].seg.meta["joint_station_mm"])).chebyshev(0.0)
        nd[n]["section_inscribed_centre_at_proximal_node_mm"] = {"x": cx, "y": cy, "r": r, "offset_from_axis_mm": float(np.hypot(cx, cy))}
    reg["node_skin_distance"] = nd
    return {"side": side, "reg": reg, "results": res, "rows": rows, "design": design, "zones": zones, "hand": hand_numbers(res["hand"].seg), "interfaces": interface_sections(res), "frames": frames_}
