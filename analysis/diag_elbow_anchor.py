"""Memo 43 diagnostic, step 2 (read-only): where the elbow node sits in the upper arm's skin, and why. Reads the pickle of `diag_elbow_anchor_build.py`; writes a result JSON
and an inspect bundle at the elbow (`--bundle DIR`, default under the gitignored cache). Changes no envelope, cache or registration: the counterfactual is built in memory.

Sections are cut from the skin mesh itself (the exact plane section of the rotated, unstretched mesh), so they carry no voxel error and no bisector cap; the field's own sections
(`field.Section.mask`, which is cut by the segment region) are reported beside them where the cap matters.

    python analysis/diag_elbow_anchor.py ARMS.pkl OUT.json [--bundle DIR]
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MPath
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from envelope import arms, bundle, field  # noqa: E402

STATIONS = (0.0, -50.0, -100.0, -150.0, -200.0, -230.0, -255.0)
FIT_STEP = 5.0
SAMPLE_MM = 0.5            # skin sampling for the exact nearest-skin distance (error at most half of it)


# ---- exact plane sections of the skin ---------------------------------------------------------------------------------------------------

def slice_loops(P, F, z):
    """Closed loops (list of (n, 2) arrays) of the plane z = const through the triangle mesh (P, F)."""
    d = P[:, 2] - z
    d = np.where(d == 0.0, 1e-9, d)
    pos = d > 0
    ts = pos[F]
    cross = ts.any(axis=1) & ~ts.all(axis=1)
    Ft = F[cross]
    pts, adj = {}, {}
    for tri in Ft:
        keys = []
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            if pos[a] != pos[b]:
                k = (int(min(a, b)), int(max(a, b)))
                if k not in pts:
                    t = d[a] / (d[a] - d[b])
                    pts[k] = (P[a, :2] + t * (P[b, :2] - P[a, :2]))
                keys.append(k)
        if len(keys) == 2:
            adj.setdefault(keys[0], []).append(keys[1])
            adj.setdefault(keys[1], []).append(keys[0])
    seen, loops = set(), []
    for k0 in adj:
        if k0 in seen:
            continue
        loop, prev, cur = [k0], None, k0
        seen.add(k0)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        loops.append(np.array([pts[k] for k in loop]))
    return loops


def area_centroid(poly):
    x, y = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    c = x * y1 - x1 * y
    a = c.sum() / 2.0
    return abs(a), np.array([((x + x1) * c).sum(), ((y + y1) * c).sum()]) / (6.0 * a)


def perimeter(poly):
    return float(np.linalg.norm(np.roll(poly, -1, axis=0) - poly, axis=1).sum())


def clip_halfplane(poly, n, c):
    """Sutherland-Hodgman: keep the part of the polygon with n . p <= c."""
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa, fb = n @ a - c, n @ b - c
        if fa <= 0:
            out.append(a)
        if (fa <= 0) != (fb <= 0):
            out.append(a + (b - a) * fa / (fa - fb))
    return np.array(out)


def widths(poly):
    """Extents along x and y of the frame, the largest Feret diameter and its direction, the smallest caliper width and its direction (degrees from +x)."""
    ang = np.radians(np.arange(0, 180, 0.5))
    proj = np.array([[np.cos(a), np.sin(a)] for a in ang]) @ poly.T
    w = proj.max(axis=1) - proj.min(axis=1)
    return {"extent_x_mm": float(np.ptp(poly[:, 0])), "extent_y_mm": float(np.ptp(poly[:, 1])), "feret_max_mm": float(w.max()), "feret_max_dir_deg": float(np.degrees(ang[w.argmax()])),
            "caliper_min_mm": float(w.min()), "caliper_min_dir_deg": float(np.degrees(ang[w.argmin()]))}


class SideSeg:
    """One arm segment of one side: rotated, unstretched mesh coordinates and the exact sections."""

    def __init__(self, S, inp, name):
        self.S, self.name = S, name
        self.fr = S["frames"][name]
        self.reg = S["reg"]
        self.res = S["results"][name]
        self.Q = (inp.V - self.fr.origin) @ self.fr.R.T                  # rotated, not stretched
        self.F = inp.F
        self.k = self.fr.k
        self.L = self.reg["lengths_sheet_mm"][name]
        ne = self.reg["axes"]["upper_arm"] + self.reg["axes"]["forearm"]
        self.bis_n = (ne / np.linalg.norm(ne))                           # the bisector plane's normal (mesh frame), through the elbow node
        self.elbow = np.asarray(self.reg["nodes_mesh_mm"]["elbow"], float)

    def to_frame(self, pts_mesh):
        return self.fr.forward(pts_mesh)

    def loop_at(self, z_station, clip=False):
        """The skin loop around the axis at the segment-frame station z (<= 0 is below the proximal node), unstretched x, y; with `clip` cut by the elbow bisector plane (upper-arm side
        for the upper arm, forearm side for the forearm)."""
        zr = z_station / self.k
        loops = slice_loops(self.Q, self.F, zr)
        inside = [lp for lp in loops if MPath(lp).contains_point((0.0, 0.0))]
        if not inside:
            return None
        lp = max(inside, key=lambda p: area_centroid(p)[0])
        if clip:
            nr = self.fr.R @ self.bis_n
            e_r = (self.elbow - self.fr.origin) @ self.fr.R.T
            # (q - e) . nr <= 0 on the plane z = zr:  nr_xy . q_xy <= nr_xy . e_xy + nr_z (e_z - zr)  (upper arm side); the forearm side is the reverse
            sgn = 1.0 if self.name == "upper_arm" else -1.0
            lp = clip_halfplane(lp, sgn * nr[:2], sgn * (nr[:2] @ e_r[:2] + nr[2] * (e_r[2] - zr)))
        return lp

    def section_numbers(self, z_station, clip=False):
        lp = self.loop_at(z_station, clip)
        if lp is None or len(lp) < 3:
            return None
        A, c = area_centroid(lp)
        return {"station_mm": z_station, "centroid_x_mm": float(c[0]), "centroid_y_mm": float(c[1]), "area_mm2": float(A), "perimeter_mm": perimeter(lp), **widths(lp)}, lp

    def field_section(self, z_station):
        """The field's own section (cut by the segment region) at the station: centroid of the mask, its area, and the mask's perimeter by the field."""
        seg = self.res.seg
        s = seg.z_top - z_station
        sec = seg.section(s)
        m = sec.mask(0.0)
        if not m.any():
            return None
        X, Y = np.meshgrid(sec.x, sec.y, indexing="ij")
        return {"centroid_x_mm": float(X[m].mean()), "centroid_y_mm": float(Y[m].mean()), "area_mm2": float(sec.area(0.0)), "perimeter_mm": float(sec.perimeter(0.0))}


# ---- the analysis ----------------------------------------------------------------------------------------------------------------------

def axis_angle(R):
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    w, v = np.linalg.eig(R)
    ax = np.real(v[:, np.argmin(np.abs(w - 1))])
    ax /= np.linalg.norm(ax)
    return float(ang), ax


def registration_item(sg, side):
    reg, fr = sg.reg, sg.fr
    ang, ax = axis_angle(fr.R)
    name = sg.name
    u = reg["axes"][name]
    dist = {"upper_arm": ("sjc", "elbow"), "forearm": ("elbow", "wrist")}[name]
    a, b = (np.asarray(reg["nodes_mesh_mm"][n], float) for n in dist)
    line = fr.forward(np.vstack([a, b]))
    xref = np.array([1.0, 0.0, 0.0]) - u[0] * u
    xref /= np.linalg.norm(xref)
    r = fr.R @ xref
    roll = float(np.degrees(np.arctan2(r[1], r[0])))                       # the angle of the projected mesh anterior in the frame, from +x about +z
    ex_mesh = fr.R.T @ np.array([1.0, 0.0, 0.0])
    return {"rotation_deg": ang, "rotation_axis_mesh": [float(v) for v in ax], "axis_perpendicular_to_segment_axis": float(abs(ax @ u)), "axis_horizontal_in_mesh": float(abs(ax[2])),
            "angle_from_vertical_deg": float(reg["angle_from_vertical_deg"][name]), "roll_convention": "shortest arc (Rodrigues) turning the proximal-to-distal axis onto -z; no roll is fixed beyond that",
            "node_line_in_frame_xy_mm": [float(np.abs(line[1, :2]).max())], "node_line_in_frame_z_mm": float(line[1, 2]), "sheet_length_mm": sg.L,
            "frame_plus_x_in_mesh": [float(v) for v in ex_mesh], "roll_vs_projected_mesh_anterior_deg": roll}


def local_ap(sg, z_station):
    """The section's own anterior-posterior direction: the direction of its smallest caliper width (the mediolateral breadth is the largest), as the angle from the frame's +x."""
    out = sg.section_numbers(z_station)
    if out is None:
        return None
    n, _ = out
    d = n["caliper_min_dir_deg"]
    d = (d + 90.0) % 180.0 - 90.0
    return {"station_mm": z_station, "ap_axis_vs_frame_x_deg": float(d), "feret_max_dir_vs_frame_y_deg": float(((n["feret_max_dir_deg"] - 90.0) + 90.0) % 180.0 - 90.0)}


def centroid_table(sg, stations):
    rows = []
    for z in stations:
        r = sg.section_numbers(z)
        rc = sg.section_numbers(z, clip=True)
        f = sg.field_section(z)
        rows.append({"station_mm": z, "uncut": None if r is None else {k: r[0][k] for k in ("centroid_x_mm", "centroid_y_mm", "area_mm2")},
                     "cut_by_bisector": None if rc is None else {k: rc[0][k] for k in ("centroid_x_mm", "centroid_y_mm", "area_mm2")},
                     "field_mask": f})
    return rows


def fit_centreline(sg, z0, z1, clip=False):
    zs = np.arange(z0, z1 - 1e-9, -FIT_STEP)
    pts = []
    for z in zs:
        n = sg.section_numbers(float(z), clip=clip)
        if n:
            pts.append((z, n[0]["centroid_x_mm"], n[0]["centroid_y_mm"]))
    pts = np.array(pts)
    zz = pts[:, 0]
    fx = np.polyfit(zz, pts[:, 1], 1)
    fy = np.polyfit(zz, pts[:, 2], 1)
    res = np.column_stack([pts[:, 1] - np.polyval(fx, zz), pts[:, 2] - np.polyval(fy, zz)])
    # slope is d(centroid)/dz with z pointing up: the centreline direction going distal (-z) is (-sx, -sy, -1)
    tilt_x, tilt_y = np.degrees(np.arctan(fx[0])), np.degrees(np.arctan(fy[0]))
    return {"stations": [float(zz.max()), float(zz.min())], "n": int(len(zz)), "slope_x": float(fx[0]), "slope_y": float(fy[0]), "tilt_x_deg": float(tilt_x), "tilt_y_deg": float(tilt_y),
            "tilt_total_deg": float(np.degrees(np.arctan(np.hypot(fx[0], fy[0])))), "centre_at_z0_mm": [float(np.polyval(fx, 0.0)), float(np.polyval(fy, 0.0))],
            "centre_at_distal_mm": [float(np.polyval(fx, z1)), float(np.polyval(fy, z1))], "residual_rms_mm": [float(np.sqrt((res[:, 0] ** 2).mean())), float(np.sqrt((res[:, 1] ** 2).mean()))],
            "residual_last_5_mean_mm": [float(res[-5:, 0].mean()), float(res[-5:, 1].mean())], "raw": pts}


def skin_samples(inp):
    pts = field.sample_surface(inp.V, inp.F, SAMPLE_MM)
    return pts, cKDTree(pts)


def nearest_skin(sg, tree, pts, p_frame):
    """Exact-to-sampling distance from a point in the segment frame to the whole-body skin (no cap), and where the nearest skin point is, in the frame."""
    p_mesh = sg.fr.inverse(np.atleast_2d(p_frame))
    d, i = tree.query(p_mesh)
    q = pts[i[0]] if np.ndim(i) else pts[i]
    qf = sg.fr.forward(q)[0]
    side = float((q - sg.elbow) @ sg.bis_n)
    return {"distance_mm": float(np.atleast_1d(d)[0]), "nearest_skin_in_frame_mm": [float(v) for v in qf], "bisector_side_mm": side,
            "on": "the upper-arm side of the bisector" if side <= 0 else "the forearm side of the bisector"}


def side_report(S, inp, tree, pts, which):
    out = {}
    for name in ("upper_arm", "forearm"):
        sg = SideSeg(S, inp, name)
        seg = sg.res.seg
        L = sg.L
        item = {"registration": registration_item(sg, which)}
        stations = STATIONS if name == "upper_arm" else (0.0, -15.0, -30.0, -50.0, -100.0)
        item["field_sd_at_proximal_node_mm"] = float(seg.signed_distance(np.array([[0.0, 0.0, 0.0]]))[0])
        item["field_sd_at_distal_node_mm"] = float(seg.signed_distance(np.array([[0.0, 0.0, -L]]))[0])
        item["skin_distance_on_axis"] = {f"{z:g}": nearest_skin(sg, tree, pts, np.array([0.0, 0.0, z]))["distance_mm"] for z in stations}
        item["centroids"] = centroid_table(sg, stations)
        if name == "upper_arm":
            item["ap_axis_local"] = {"sjc_z0": local_ap(sg, -6.0), "ejc": local_ap(sg, -L + 12.0), "mid": local_ap(sg, -130.0)}
            item["nearest_skin_at_ejc"] = nearest_skin(sg, tree, pts, np.array([0.0, 0.0, -L]))
            item["nearest_skin_at_sjc"] = nearest_skin(sg, tree, pts, np.array([0.0, 0.0, 0.0]))
            item["fit_full"] = fit_centreline(sg, 0.0, -(L - 5.0))
            item["fit_trimmed"] = fit_centreline(sg, -40.0, -(L - 40.0))
            item["fit_trimmed_cut"] = fit_centreline(sg, -40.0, -(L - 40.0), clip=True)
            prof = []
            for z in np.arange(-190.0, -L + 1e-9, -5.0).tolist() + [-L]:
                u_, c_ = sg.section_numbers(float(z)), sg.section_numbers(float(z), clip=True)
                prof.append({"station_mm": float(z), "uncut": None if u_ is None else {k: u_[0][k] for k in ("extent_x_mm", "extent_y_mm", "feret_max_mm", "feret_max_dir_deg", "caliper_min_mm", "perimeter_mm", "area_mm2")},
                             "cut_by_bisector": None if c_ is None else {k: c_[0][k] for k in ("extent_x_mm", "extent_y_mm", "feret_max_mm", "feret_max_dir_deg", "caliper_min_mm", "perimeter_mm", "area_mm2")}})
            item["width_profile"] = prof
            ids = S["reg"]["vertex_ids"]
            P4 = inp.V[[ids["upper_arm_chord_start"], ids["upper_arm_chord_end"], ids["forearm_chord_start"], ids["forearm_chord_end"]]]
            item["chord_vertices"] = {"upper_end_to_forearm_start_mm": float(np.linalg.norm(P4[1] - P4[2])),
                                      "in_upper_arm_frame_mm": {n_: [float(v) for v in sg.to_frame(P4[i])[0]] for i, n_ in enumerate(("upper_start", "upper_end", "forearm_start", "forearm_end"))},
                                      "distance_to_skin_mm": [float(tree.query(p)[0]) for p in P4]}
            n, lp = sg.section_numbers(-L)
            nc, lpc = sg.section_numbers(-L, clip=True)
            item["ejc_section"] = {"uncut": n, "cut_by_bisector": nc, "field_mask": sg.field_section(-L)}
        else:
            item["ap_axis_local"] = {"proximal": local_ap(sg, -12.0)}
            item["nearest_skin_at_proximal"] = nearest_skin(sg, tree, pts, np.array([0.0, 0.0, 0.0]))
        out[name] = item
    return out


def strip_raw(o):
    if isinstance(o, dict):
        return {k: strip_raw(v) for k, v in o.items() if k != "raw"}
    if isinstance(o, list):
        return [strip_raw(v) for v in o]
    return o


# ---- the counterfactual: the elbow node at the section centroid --------------------------------------------------------------------------

def counterfactual(data, elbow_new, mesh_volume_l, closure_old):
    """Build the right side in memory with the elbow node at `elbow_new` (mesh frame) and report; nothing is written."""
    orig = arms.registration

    def patched(inp, tb, rm, sh, side="R"):
        r = orig(inp, tb, rm, sh, side)
        sjc, wrist = r["nodes_mesh_mm"]["sjc"], r["nodes_mesh_mm"]["wrist"]
        e = np.asarray(elbow_new, float)
        u_up, u_fo = e - sjc, wrist - e
        l = {"upper_arm": float(np.linalg.norm(u_up)), "forearm": float(np.linalg.norm(u_fo))}
        k = {n: r["lengths_sheet_mm"][n] / l[n] for n in l}
        r["nodes_mesh_mm"]["elbow"] = e
        r["lengths_mesh_mm"] = l
        r["stretch"] = k
        r["gate"] = {n: arms.GATE_SIGMAS * arms.SIGMA_MM / r["lengths_sheet_mm"][n] for n in l}
        r["axes"] = {"upper_arm": u_up / l["upper_arm"], "forearm": u_fo / l["forearm"]}
        r["angle_from_vertical_deg"]["upper_arm"] = arms.angle_from_vertical_deg(u_up)
        r["angle_from_vertical_deg"]["forearm"] = arms.angle_from_vertical_deg(u_fo)
        r["elbow_bend_deg"] = float(np.degrees(np.arccos(np.clip(r["axes"]["upper_arm"] @ r["axes"]["forearm"], -1, 1))))
        r["exceeding_gate"] = [n for n in l if abs(k[n] - 1.0) > r["gate"][n]]
        return r

    arms.registration = patched
    try:
        S = arms.build_side(data["inp"], data["tb"], data["rm"], data["sh"], "R", 2.0)
    finally:
        arms.registration = orig
    old = data["R"]
    vol = {n: S["results"][n].seg.volume(0.0) / 1e6 for n in arms.NAMES}
    vol_old = {n: old["results"][n].seg.volume(0.0) / 1e6 for n in arms.NAMES}
    new_sum = closure_old["sum_l"] + 2.0 * sum(vol[n] - vol_old[n] for n in arms.NAMES)
    rel = (new_sum - mesh_volume_l) / mesh_volume_l
    ax_old, ax_new = old["reg"]["axes"]["upper_arm"], S["reg"]["axes"]["upper_arm"]
    return {"elbow_mesh_mm": [float(v) for v in elbow_new], "moved_mm": float(np.linalg.norm(np.asarray(elbow_new) - old["reg"]["nodes_mesh_mm"]["elbow"])),
            "stretch": S["reg"]["stretch"], "gate": S["reg"]["gate"], "stretch_old": old["reg"]["stretch"], "angle_from_vertical_deg": S["reg"]["angle_from_vertical_deg"],
            "elbow_bend_deg": S["reg"]["elbow_bend_deg"], "upper_arm_axis_tilt_vs_old_deg": float(np.degrees(np.arccos(np.clip(ax_old @ ax_new, -1, 1)))),
            "node_skin_distance_mm": S["reg"]["node_skin_distance"], "conformed_volume_l": vol, "conformed_volume_old_l": vol_old, "closure_relative_difference": float(rel),
            "closure_old_relative_difference": float(closure_old["relative_difference"]), "closure_gate": float(closure_old["tolerance"]), "closure_holds": bool(abs(rel) <= closure_old["tolerance"])}


# ---- the inspect bundle -----------------------------------------------------------------------------------------------------------------

def octahedron(c, r):
    c = np.asarray(c, float)
    v = np.array([c + [r, 0, 0], c - [r, 0, 0], c + [0, r, 0], c - [0, r, 0], c + [0, 0, r], c - [0, 0, r]])
    f = [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]]
    return v, f


def write_bundle(outdir, inp, sgU, loops, markers):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    verts, faces, groups = [], [], []
    for name, p in markers.items():
        v, f = octahedron(bundle.to_mh_dm(np.asarray(p)[None, :], inp)[0], 0.25)
        groups.append((name, len(faces)))
        faces += [(np.array(x) + len(verts)).tolist() for x in f]
        verts += v.tolist()
    bundle.write_obj(outdir / "elbow_markers.obj", np.array(verts), faces, groups)
    lines, lv = ["# GENERATED by analysis/diag_elbow_anchor.py (decimetres, MakeHuman OBJ axes): skin sections as polylines"], 0
    for name, lp in loops.items():
        lines.append(f"g {name}")
        pts = bundle.to_mh_dm(lp, inp)
        lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in pts]
        lines.append("l " + " ".join(str(lv + i + 1) for i in range(len(pts))) + f" {lv + 1}")
        lv += len(pts)
    (outdir / "elbow_sections.obj").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    src = ROOT / "data/envelope/cache/inspect"
    for fn in ("original.obj", "envelope_arms_t5.obj"):
        if (src / fn).exists():
            (outdir / fn).write_bytes((src / fn).read_bytes())
    doc = {"schema": "inspect-bundle/1", "frame": "MakeHuman OBJ axes (x subject-left, y up, z anterior), decimetres; heights are y", "side": "right",
           "meshes": {"original": "original.obj", "arm_envelope": "envelope_arms_t5.obj", "markers": "elbow_markers.obj", "sections": "elbow_sections.obj"},
           "elbow_markers_dm": {k: [float(v) for v in bundle.to_mh_dm(np.asarray(p)[None, :], inp)[0]] for k, p in markers.items()},
           "note": "markers: sjc, ejc (the elbow node as registered), centroid_cut (upper-arm section centroid at the EJC station, cut by the bisector), centroid_uncut; sections: skin loops at the EJC station"}
    (outdir / "inspect.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkl"), ap.add_argument("out")
    ap.add_argument("--bundle", default=str(ROOT / "data/envelope/cache/inspect-elbow"))
    a = ap.parse_args()
    data = pickle.load(open(a.pkl, "rb"))
    inp = data["inp"]
    pts, tree = skin_samples(inp)
    res = {"R": strip_raw(side_report(data["R"], inp, tree, pts, "R")), "L": strip_raw(side_report(data["L"], inp, tree, pts, "L"))}
    arm = json.loads((ROOT / "data/envelope/arm_bodies.json").read_text(encoding="utf-8"))
    closure_old = arm["closure"]
    mesh_vol = closure_old["mesh_volume_l"]
    sgU = SideSeg(data["R"], inp, "upper_arm")
    L = sgU.L
    nU, lpU = sgU.section_numbers(-L)
    nC, lpC = sgU.section_numbers(-L, clip=True)
    # centroids back to the mesh frame: the loop lives in the rotated unstretched frame at z = -L / k
    zr = -L / sgU.k

    def to_mesh(xy):
        return sgU.fr.inverse(np.array([[xy[0], xy[1], -L]]))[0]

    ejc_mesh = np.asarray(data["R"]["reg"]["nodes_mesh_mm"]["elbow"], float)
    c_unc, c_cut = to_mesh([nU["centroid_x_mm"], nU["centroid_y_mm"]]), to_mesh([nC["centroid_x_mm"], nC["centroid_y_mm"]])
    res["counterfactual"] = {"centroid_cut": counterfactual(data, c_cut, mesh_vol, closure_old), "centroid_uncut": counterfactual(data, c_unc, mesh_vol, closure_old)}
    res["counterfactual"]["centroid_cut"]["is"] = "elbow node at the centroid of the skin section at the current EJC station, cut by the bisector (upper-arm side)"
    res["counterfactual"]["centroid_uncut"]["is"] = "the same section, uncut"
    ft = fit_centreline(sgU, -40.0, -(L - 40.0))
    c_ext = to_mesh([ft["centre_at_z0_mm"][0] + ft["slope_x"] * -L, ft["centre_at_z0_mm"][1] + ft["slope_y"] * -L])
    res["counterfactual"]["centreline_extrapolated"] = counterfactual(data, c_ext, mesh_vol, closure_old)
    res["counterfactual"]["centreline_extrapolated"]["is"] = "elbow node on the centroid line fitted over stations -40 to -215 mm (uncut sections, cap-free), extrapolated to the EJC station"
    res["counterfactual"]["centreline_extrapolated"]["frame_xy_mm"] = [float(ft["centre_at_z0_mm"][0] + ft["slope_x"] * -L), float(ft["centre_at_z0_mm"][1] + ft["slope_y"] * -L)]
    markers = {"sjc": data["R"]["reg"]["nodes_mesh_mm"]["sjc"], "ejc": ejc_mesh, "centroid_cut": c_cut, "centroid_uncut": c_unc, "centreline_extrapolated": c_ext}
    loops = {"upper_arm_section_uncut": sgU.fr.inverse(np.column_stack([lpU, np.full(len(lpU), -L)])), "upper_arm_section_cut": sgU.fr.inverse(np.column_stack([lpC, np.full(len(lpC), -L)]))}
    write_bundle(a.bundle, inp, sgU, loops, markers)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", a.out, "and the bundle", a.bundle)


if __name__ == "__main__":
    main()
