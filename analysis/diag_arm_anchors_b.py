"""Volume-extractor brief 9 diagnostic (read-only): the B arm nodes (the proximal segment's skin-section centre line, extrapolated to the joint station, in the current
Ruler-chord frames), their cross-checks, a second iteration, the forearm roll and the blast radius of MakeHuman's arm-length targets. Reads the pickle of
`diag_elbow_anchor_build.py`; writes one result JSON. Changes no envelope, cache, registration or tool: every frame is built in memory.

Sections are the exact plane sections of the skin mesh (memo 43's `slice_loops`), unstretched x, y; stations are segment-frame z (stretched, <= 0 below the proximal node).
By the brief's hard limit nothing here reports a length or stretch between moved nodes: the second iteration's frames carry a stretch internally and only node positions
and offsets leave this script.

    python analysis/diag_arm_anchors_b.py ARMS.pkl OUT.json [--targets DIR]

DIR holds MakeHuman's measure/measure-{upperarm,lowerarm}-length-{incr,decr}.target (CC0) from the commit pinned in data/makehuman/mhm_sources.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "analysis"))
from envelope import arms, masses  # noqa: E402
from diag_elbow_anchor import area_centroid, registration_item, slice_loops, SideSeg  # noqa: E402

TRIM_MM = 40.0             # memo 43 section 2: the clean, cap-free window is the segment less 40 mm at each end
STEP_MM = 5.0
MIN_AREA_MM2 = 300.0
NEAR_MM = 80.0
COUNT_AREA_MM2 = 20.0      # a finger's section is about 150 to 250 mm2: counted, never selected
TARGETS = ("measure/measure-upperarm-length-incr.target", "measure/measure-upperarm-length-decr.target",
           "measure/measure-lowerarm-length-incr.target", "measure/measure-lowerarm-length-decr.target")
MOVED_MM = 0.1


class Sections:
    """Exact skin sections of the whole body in one arm frame (origin, R, k as `arms.ArmFrame`)."""

    def __init__(self, V, F, frame):
        self.fr, self.F = frame, F
        self.Q = (V - frame.origin) @ frame.R.T

    def loop(self, z, hint=(0.0, 0.0)):
        """The skin loop at station z: the one containing `hint`, else the one whose centroid is nearest it (area above MIN_AREA_MM2). Returns (loop, number of loops whose
        centroid lies within NEAR_MM of the hint: the plane also cuts the torso and legs, which are not counted)."""
        every = [lp for lp in slice_loops(self.Q, self.F, z / self.fr.k) if len(lp) >= 3 and area_centroid(lp)[0] > COUNT_AREA_MM2]
        loops = [lp for lp in every if area_centroid(lp)[0] > MIN_AREA_MM2]
        if not loops:
            return None, 0
        near = int(sum(np.linalg.norm(area_centroid(lp)[1] - np.asarray(hint)) < NEAR_MM for lp in every))
        inside = [lp for lp in loops if MPath(lp).contains_point(hint)]
        if inside:
            return max(inside, key=lambda p: area_centroid(p)[0]), near
        return min(loops, key=lambda p: np.linalg.norm(area_centroid(p)[1] - np.asarray(hint))), near

    def to_mesh(self, xy, z):
        return self.fr.inverse(np.array([[xy[0], xy[1], z]]))[0]

    def from_mesh(self, p):
        return self.fr.forward(np.atleast_2d(p))[0]


def fit_line(sec, z0, z1, step=STEP_MM):
    """Centroid line x(z), y(z) over stations z0 down to z1 (inclusive): slopes, intercepts at z = 0, residual rms, and the stations' loop counts."""
    zs = np.arange(z0, z1 - 1e-9, -step)
    rows, hint = [], (0.0, 0.0)
    for z in zs:
        lp, n = sec.loop(float(z), hint)
        if lp is None:
            continue
        A, c = area_centroid(lp)
        rows.append((float(z), c[0], c[1], A, n))
        hint = tuple(c)
    P = np.array(rows)
    fx, fy = np.polyfit(P[:, 0], P[:, 1], 1), np.polyfit(P[:, 0], P[:, 2], 1)
    qx, qy = np.polyfit(P[:, 0], P[:, 1], 2), np.polyfit(P[:, 0], P[:, 2], 2)
    res = np.column_stack([P[:, 1] - np.polyval(fx, P[:, 0]), P[:, 2] - np.polyval(fy, P[:, 0])])
    return {"z0": float(P[0, 0]), "z1": float(P[-1, 0]), "n": int(len(P)), "fx": fx, "fy": fy, "residual_rms_mm": [float(np.sqrt((res[:, i] ** 2).mean())) for i in (0, 1)],
            "residual_max_mm": [float(np.abs(res[:, i]).max()) for i in (0, 1)], "tilt_deg": float(np.degrees(np.arctan(np.hypot(fx[0], fy[0])))),
            "quadratic_coeff_per_mm": [float(qx[0]), float(qy[0])], "max_loops_at_a_station": int(P[:, 4].max()), "area_mm2_first_last": [float(P[0, 3]), float(P[-1, 3])]}


def at(fit, z):
    return np.array([np.polyval(fit["fx"], z), np.polyval(fit["fy"], z)])


def pub(fit):
    return {k: v for k, v in fit.items() if k not in ("fx", "fy")} | {"slope_x": float(fit["fx"][0]), "slope_y": float(fit["fy"][0])}


def anterior_angle_deg(frame):
    """The angle (about the frame's +z, from +x) of the mesh's +x projected onto the section plane: the anterior-preserving x."""
    u = frame.R.T @ np.array([0.0, 0.0, -1.0])                     # the segment axis (proximal to distal) in the mesh frame
    xr = np.array([1.0, 0.0, 0.0]) - u[0] * u
    r = frame.R @ (xr / np.linalg.norm(xr))
    return float(np.degrees(np.arctan2(r[1], r[0])))


def ml_extremes(lp, ant_deg):
    """The two skin points with the smallest and largest coordinate along the anterior-preserving y (ant_deg + 90 degrees), their midpoint, and the line through them
    (degrees from the frame's +x, modulo 180); and the same for the largest Feret diameter's end points."""
    a = np.radians(ant_deg + 90.0)
    yv = np.array([np.cos(a), np.sin(a)])
    s = lp @ yv
    p, q = lp[s.argmin()], lp[s.argmax()]
    D = np.linalg.norm(lp[:, None, :] - lp[None, :, :], axis=2)
    i, j = np.unravel_index(D.argmax(), D.shape)
    f1, f2 = lp[i], lp[j]

    def ang(u, v):
        d = v - u
        return float(np.degrees(np.arctan2(d[1], d[0])) % 180.0)
    return {"y_extremes": {"mid": (p + q) / 2, "line_deg": ang(p, q), "breadth_mm": float(s.max() - s.min())},
            "feret": {"mid": (f1 + f2) / 2, "line_deg": ang(f1, f2), "breadth_mm": float(D.max())}}


def wrap90(a):
    return (a + 90.0) % 180.0 - 90.0


def frame(origin, distal, L_sheet):
    """An arm frame as `arms.registration` would build it on these two nodes (the stretch is internal only)."""
    u = np.asarray(distal, float) - np.asarray(origin, float)
    return arms.ArmFrame(origin, u, L_sheet / np.linalg.norm(u))


# ---- items 2 to 4 ---------------------------------------------------------------------------------------------------------------------------

def b_nodes(inp, nodes, L, trim=TRIM_MM):
    """B elbow and wrist from the upper arm's and the forearm's centre lines in the frames on `nodes` (sjc, elbow, wrist), and the forearm's and hand's lines at their proximal
    stations. Mesh frame, mm."""
    V, F = inp.V, inp.F
    fu, ff = frame(nodes["sjc"], nodes["elbow"], L["upper_arm"]), frame(nodes["elbow"], nodes["wrist"], L["forearm"])
    su, sf = Sections(V, F, fu), Sections(V, F, ff)
    lu = fit_line(su, -trim, -(L["upper_arm"] - trim))
    lf = fit_line(sf, -trim, -(L["forearm"] - trim))
    be = su.to_mesh(at(lu, -L["upper_arm"]), -L["upper_arm"])
    bw = sf.to_mesh(at(lf, -L["forearm"]), -L["forearm"])
    fe = sf.to_mesh(at(lf, 0.0), 0.0)                                # the forearm's line at its own proximal station
    return {"frames": (fu, ff), "sections": (su, sf), "fits": (lu, lf), "elbow": be, "wrist": bw, "forearm_line_at_elbow": fe}


def line_closest(p1, d1, p2, d2):
    d1, d2 = d1 / np.linalg.norm(d1), d2 / np.linalg.norm(d2)
    n = np.cross(d1, d2)
    return float(abs((p2 - p1) @ n) / np.linalg.norm(n))


def item2(inp, S, L):
    nodes = {k: np.asarray(v, float) for k, v in S["reg"]["nodes_mesh_mm"].items()}
    B = b_nodes(inp, nodes, L)
    fu, ff = B["frames"]
    su, sf = B["sections"]
    lu, lf = B["fits"]
    fh = S["frames"]["hand"]
    sh = Sections(inp.V, inp.F, fh)
    out = {"definition": f"centre line fitted on stations -{TRIM_MM:g} to -(L - {TRIM_MM:g}) mm, step {STEP_MM:g}, exact uncut skin sections; extrapolated to the joint station",
           "B_elbow": {"mesh_mm": B["elbow"].tolist(), "upper_arm_frame_xy_mm": su.from_mesh(B["elbow"])[:2].tolist(), "offset_from_current_node_mm": float(np.linalg.norm(B["elbow"] - nodes["elbow"])),
                       "fit": pub(lu)},
           "B_wrist": {"mesh_mm": B["wrist"].tolist(), "forearm_frame_xy_mm": sf.from_mesh(B["wrist"])[:2].tolist(), "offset_from_current_node_mm": float(np.linalg.norm(B["wrist"] - nodes["wrist"])),
                       "fit": pub(lf)}}
    # sensitivity of B to the trim (not the definition; reported only)
    sens = {}
    for t in (30.0, 50.0):
        Bt = b_nodes(inp, nodes, L, t)
        sens[f"trim_{t:g}"] = {"elbow_moves_mm": float(np.linalg.norm(Bt["elbow"] - B["elbow"])), "wrist_moves_mm": float(np.linalg.norm(Bt["wrist"] - B["wrist"]))}
    out["trim_sensitivity"] = sens
    # (a) gaps between the extrapolated lines at the joints
    g = B["forearm_line_at_elbow"] - B["elbow"]
    du = fu.R.T @ np.array([0.0, 0.0, -1.0])
    out["a_elbow_gap"] = {"forearm_line_at_its_elbow_station_mesh_mm": B["forearm_line_at_elbow"].tolist(), "distance_mm": float(np.linalg.norm(g)),
                          "along_upper_arm_axis_mm": float(g @ du), "in_upper_arm_section_plane_mm": float(np.linalg.norm(g - (g @ du) * du)),
                          "closest_approach_of_the_two_lines_mm": line_closest(B["elbow"], su.to_mesh(at(lu, -L["upper_arm"] + 10), -L["upper_arm"] + 10) - B["elbow"],
                                                                               B["forearm_line_at_elbow"], sf.to_mesh(at(lf, -10.0), -10.0) - B["forearm_line_at_elbow"])}
    # the forearm's line where it crosses the upper arm's joint plane (the plane of the B elbow): the gap on the B node's own station
    p0, p1 = B["forearm_line_at_elbow"], sf.to_mesh(at(lf, -10.0), -10.0)
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    t = ((B["elbow"] - p0) @ du) / (d @ du)
    x_up = p0 + t * d
    out["a_elbow_gap"]["forearm_line_on_upper_arm_joint_plane"] = {"mesh_mm": x_up.tolist(), "distance_mm": float(np.linalg.norm(x_up - B["elbow"])),
                                                                   "upper_arm_frame_xy_mm": su.from_mesh(x_up)[:2].tolist(), "line_parameter_mm_from_forearm_station_0": float(t)}
    # the hand: profile first, to find where the fingers split
    prof = []
    hint = (0.0, 0.0)
    for z in np.arange(-5.0, -150.0, -5.0):
        lp, n = sh.loop(float(z), hint)
        if lp is None:
            break
        A, c = area_centroid(lp)
        hint = tuple(c)
        prof.append({"station_mm": float(z), "loops": n, "area_mm2": float(A), "centroid_xy_mm": [float(c[0]), float(c[1])]})
    split = next((p["station_mm"] for p in prof if p["loops"] > 1), None)
    z_end = (split + 10.0) if split is not None else -60.0
    lh = fit_line(sh, -10.0, z_end)
    hw = sh.to_mesh(at(lh, 0.0), 0.0)
    gw = hw - B["wrist"]
    zz = np.array([p["station_mm"] for p in prof if -10.0 >= p["station_mm"] >= z_end])
    cc = np.array([p["centroid_xy_mm"] for p in prof if -10.0 >= p["station_mm"] >= z_end])
    q0 = np.array([np.polyval(np.polyfit(zz, cc[:, i], 2), 0.0) for i in (0, 1)])
    bw_xy = sf.from_mesh(B["wrist"])[:2]
    out["a_wrist_gap_quadratic_hand_fit"] = {"hand_quadratic_at_wrist_xy_mm": q0.tolist(), "distance_from_B_wrist_mm": float(np.linalg.norm(q0 - bw_xy)),
                                             "hand_section_5mm_distal_xy_mm": prof[0]["centroid_xy_mm"], "its_distance_from_B_wrist_xy_mm": float(np.linalg.norm(np.array(prof[0]["centroid_xy_mm"]) - bw_xy))}
    df = ff.R.T @ np.array([0.0, 0.0, -1.0])
    out["a_wrist_gap"] = {"hand_fit": pub(lh), "first_station_with_more_than_one_loop_mm": split, "hand_profile_every_5mm": prof,
                          "hand_line_at_wrist_mesh_mm": hw.tolist(), "distance_mm": float(np.linalg.norm(gw)), "along_forearm_axis_mm": float(gw @ df),
                          "in_forearm_section_plane_mm": float(np.linalg.norm(gw - (gw @ df) * df))}
    # (b) the mediolateral skin extremes' midpoint at the nearest clean station
    res = {}
    for joint, sec, Lj, Bn, fr in (("elbow", su, L["upper_arm"], B["elbow"], fu), ("wrist", sf, L["forearm"], B["wrist"], ff)):
        ant = anterior_angle_deg(fr)
        bxy = sec.from_mesh(Bn)[:2]
        fit = lu if joint == "elbow" else lf
        rows = []
        for z in ([-230.0] if joint == "elbow" else [-(Lj - d) for d in (40.0, 30.0, 25.0, 20.0, 15.0, 10.0, 5.0)]):
            lp, n = sec.loop(z, tuple(at(fit, z)))
            m = ml_extremes(lp, ant)
            row = {"station_mm": z, "loops": n, "area_mm2": float(area_centroid(lp)[0])}
            for kind in ("y_extremes", "feret"):
                mid = m[kind]["mid"]
                row[kind] = {"midpoint_xy_mm": mid.tolist(), "breadth_mm": m[kind]["breadth_mm"], "line_deg_from_frame_x": m[kind]["line_deg"],
                             "in_plane_distance_from_B_node_mm": float(np.linalg.norm(mid - bxy)),
                             "in_plane_distance_from_B_line_at_this_station_mm": float(np.linalg.norm(mid - at(fit, z))),
                             "distance_3d_from_B_node_mm": float(np.linalg.norm(sec.to_mesh(mid, z) - Bn))}
            rows.append(row)
        res[joint] = {"anterior_preserving_x_deg_in_frame": ant, "B_node_frame_xy_mm": bxy.tolist(), "stations": rows}
        if joint == "elbow":                     # sensitivity of the -230 mm result: neighbouring stations and the mediolateral direction turned by +-5 degrees
            sens = {}
            for z in (-220.0, -225.0, -230.0, -235.0, -240.0):
                lp, _ = sec.loop(z, tuple(at(fit, z)))
                for dth in (-5.0, 0.0, 5.0):
                    mid = ml_extremes(lp, ant + dth)["y_extremes"]["mid"]
                    sens[f"{z:g}_{dth:+g}deg"] = float(np.linalg.norm(mid - bxy))
            res[joint]["y_extremes_distance_sensitivity_mm"] = sens
    out["b_ml_midpoint"] = res
    return out, B


def item3(inp, B, sjc, L):
    n2 = {"sjc": sjc, "elbow": B["elbow"], "wrist": B["wrist"]}
    B2 = b_nodes(inp, n2, L)
    return {"elbow_moves_mm": float(np.linalg.norm(B2["elbow"] - B["elbow"])), "wrist_moves_mm": float(np.linalg.norm(B2["wrist"] - B["wrist"])),
            "elbow_2_mesh_mm": B2["elbow"].tolist(), "wrist_2_mesh_mm": B2["wrist"].tolist(),
            "fit_residual_rms_mm": {"upper_arm": B2["fits"][0]["residual_rms_mm"], "forearm": B2["fits"][1]["residual_rms_mm"]},
            "note": "frames rebuilt on the B nodes (upper arm SJC to B elbow; forearm B elbow to B wrist), centre lines refitted on the same station window; the stretch is internal only"}


def item4(inp, S, L, B):
    ff = S["frames"]["forearm"]
    sf = Sections(inp.V, inp.F, ff)
    lf = B["fits"][1]
    ant = anterior_angle_deg(ff)
    z_hi, z_lo = -round(L["forearm"] * 2.0 / 3.0 / STEP_MM) * STEP_MM, -(L["forearm"] - 5.0)       # the wrist has no cap (one plane for forearm and hand): every section above it is clean
    rows = []
    for z in np.arange(z_hi, z_lo - 1e-9, -STEP_MM):
        lp, n = sf.loop(float(z), tuple(at(lf, z)))
        m = ml_extremes(lp, ant)
        rows.append({"station_mm": float(z), "loops": n, "feret_line_deg": m["feret"]["line_deg"], "feret_breadth_mm": m["feret"]["breadth_mm"],
                     "y_extremes_line_deg": m["y_extremes"]["line_deg"], "y_breadth_mm": m["y_extremes"]["breadth_mm"]})
    out = {"stations": [z_hi, float(z_lo)], "anterior_preserving_x_deg_in_frame": ant, "rows": rows,
           "sign": "angles about the forearm frame's +z (proximal), from its +x; for the right arm a positive rotation turns anterior toward medial: pronation"}
    for window, lo in (("to_wrist", z_lo), ("centre_line_window", -(L["forearm"] - TRIM_MM))):
        sel = [r for r in rows if r["station_mm"] >= lo - 1e-9]
        for kind in ("feret_line_deg", "y_extremes_line_deg"):
            a = np.array([r[kind] for r in sel])
            ref = a[0]
            a = ref + wrap90(a - ref)
            mean = float(a.mean())
            x_impl = ant + wrap90(mean - 90.0 - ant)
            out.setdefault(window, {"stations": [z_hi, float(sel[-1]["station_mm"])], "n": len(sel)})[kind.replace("_line_deg", "")] = {
                "spread_deg": float(a.max() - a.min()), "sd_deg": float(a.std()), "mean_line_deg": mean % 180.0, "implied_x_deg_in_frame": x_impl,
                "offset_from_anterior_preserving_x_deg": float(x_impl - ant)}
    return out


# ---- item 5 -----------------------------------------------------------------------------------------------------------------------------------

def read_target(path):
    idx, d = [], []
    for line in Path(path).read_text().splitlines():
        if line and not line.startswith("#"):
            p = line.split()
            idx.append(int(p[0]))
            d.append([float(p[1]), float(p[2]), float(p[3])])
    D = np.array(d) * 100.0                       # dm -> mm
    return np.array(idx, int), np.column_stack([D[:, 2], D[:, 0], D[:, 1]])    # MakeHuman OBJ (x left, y up, z anterior) -> sheet axes (x anterior, y left, z up)


def labels(inp, data):
    """A label per body vertex: <segment>_<side> for the arm-labelled vertices (by the current frames' planes), girdle_<side> for the shoulder girdle, else not_arm."""
    V = inp.V
    lab = np.full(len(V), "not_arm", dtype=object)
    tb = data["tb"]
    for side in "RL":
        S = data[side]
        reg = S["reg"]
        mem = arms.Membership(inp, tb, side)
        nodes, ax = reg["nodes_mesh_mm"], reg["axes"]
        ne = ax["upper_arm"] + ax["forearm"]
        ne = ne / np.linalg.norm(ne)
        own = mem.arm_mask & mem.side_ok(V)
        b = (V - nodes["elbow"]) @ ne
        w = (V - nodes["wrist"]) @ ax["forearm"]
        lab[own & (b <= 0)] = f"upper_arm_{side}"
        lab[own & (b > 0) & (w <= 0)] = f"forearm_{side}"
        lab[own & (b > 0) & (w > 0)] = f"hand_{side}"
        lab[~own & mem.girdle_rule(V) & mem.side_ok(V)] = f"girdle_{side}"
    return lab


def item5(inp, data, targets_dir):
    V0, F = inp.V, inp.F
    n = len(V0)
    lab = labels(inp, data)
    vol0 = masses.mesh_volume_l(V0, F)
    S = data["R"]
    reg = S["reg"]
    ids = reg["vertex_ids"]
    sjc = np.asarray(reg["nodes_mesh_mm"]["sjc"], float)
    L_sheet = reg["lengths_sheet_mm"]

    def nodes(V):
        e = 0.5 * (V[ids["upper_arm_chord_end"]] + V[ids["forearm_chord_start"]])
        return e, V[ids["forearm_chord_end"]]
    e0, w0 = nodes(V0)
    len0 = {"upper_arm": float(np.linalg.norm(e0 - sjc)), "forearm": float(np.linalg.norm(w0 - e0))}
    need = {k: L_sheet[k] - len0[k] for k in len0}
    out = {"current": {"lengths_mesh_mm": len0, "sheet_mm": L_sheet, "shortfall_mm": need, "shortfall_pct_of_mesh": {k: 100 * need[k] / len0[k] for k in len0}},
           "sjc_note": "the SJC is held at its current position (the trunk registration is not rerun); the vertices within 40 mm of it are reported per target", "targets": {}}
    near_sjc = np.linalg.norm(V0 - sjc, axis=1) < 40.0
    for rel in TARGETS:
        p = Path(targets_dir) / rel
        if not p.exists():
            out["targets"][rel] = "missing"
            continue
        idx, D = read_target(p)
        keep = idx < n
        V = V0.copy()
        V[idx[keep]] += D[keep]
        disp = np.linalg.norm(V - V0, axis=1)
        mv = disp > MOVED_MM
        groups = {}
        for g in sorted(set(lab[mv])):
            sel = mv & (lab == g)
            groups[g] = {"vertices": int(sel.sum()), "of_label": int((lab == g).sum()), "max_mm": float(disp[sel].max())}
            if not g.startswith(("upper_arm", "forearm", "hand")):
                P = V0[sel]
                groups[g]["where_mesh_mm"] = {"z_range": [float(P[:, 2].min()), float(P[:, 2].max())], "abs_y_range": [float(np.abs(P[:, 1]).min()), float(np.abs(P[:, 1]).max())],
                                             "x_range": [float(P[:, 0].min()), float(P[:, 0].max())], "sjc_z_mm": float(sjc[2]), "sjc_abs_y_mm": float(abs(sjc[1]))}
        e1, w1 = nodes(V)
        l1 = {"upper_arm": float(np.linalg.norm(e1 - sjc)), "forearm": float(np.linalg.norm(w1 - e1))}
        dl = {k: l1[k] - len0[k] for k in l1}
        out["targets"][rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "entries": int(len(idx)), "helper_entries_ignored": int((~keep).sum()),
                               "moved_over_0p1mm": groups, "moved_total": int(mv.sum()), "outside_arm": {g: v for g, v in groups.items() if not g.startswith(("upper_arm", "forearm", "hand"))},
                               "volume_change_l": masses.mesh_volume_l(V, F) - vol0, "max_disp_within_40mm_of_sjc_mm": float(disp[near_sjc].max()),
                               "node_moves_mm": {"elbow": float(np.linalg.norm(e1 - e0)), "wrist": float(np.linalg.norm(w1 - w0))},
                               "length_change_mm": dl, "length_change_pct": {k: 100 * dl[k] / len0[k] for k in dl},
                               "covers_shortfall": {k: dl[k] / need[k] for k in dl}}
    out["mesh_volume_l"] = vol0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkl"), ap.add_argument("out"), ap.add_argument("--targets")
    a = ap.parse_args()
    data = pickle.load(open(a.pkl, "rb"))
    inp, S = data["inp"], data["R"]
    L = {k: S["reg"]["lengths_sheet_mm"][k] for k in ("upper_arm", "forearm")}
    res = {"frames": {n: registration_item(SideSeg(S, inp, n), "R") for n in ("upper_arm", "forearm")}}
    res["item2"], B = item2(inp, S, L)
    res["item3"] = item3(inp, B, np.asarray(S["reg"]["nodes_mesh_mm"]["sjc"], float), L)
    res["item4"] = item4(inp, S, L, B)
    if a.targets:
        res["item5"] = item5(inp, data, a.targets)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)) + "\n", encoding="utf-8")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
