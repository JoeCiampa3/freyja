"""The v3 sculpt (adr-0042 D3, brief 10): v2 plus the pinned arm-length targets at the weights that close each arm segment on the adr-0042 D1 nodes, and the in-memory evaluation against C1 to C4.

    python analysis/makehuman_v3.py solve [--forearm-only] [--sjc X Y Z]               # the weights: D1 node-to-node length = sheet within 0.1 mm, the D1 nodes recomputed at every step
    python analysis/makehuman_v3.py write [--upper W] [--lower W] [--out DIR]          # freyja-body-v3.obj and .mhm into data/makehuman/cache/v3-candidate (gitignored)
    python analysis/makehuman_v3.py evaluate --mesh OBJ --out DIR                      # `fy envelope gates` in memory on the D1 nodes and D4 roll; its result files go to DIR, never to data/envelope
    python analysis/makehuman_v3.py compare --base DIR --cand DIR                      # C1 to C4 and the numbers reported beside them

v3 is generated, never exported by hand: the targets come through the manifest (data/makehuman/mhm_sources.json) and their hashes are verified, a target's deltas are added at its weight to the
body vertices of v2's OBJ (13,380; helper deltas are ignored) and every other byte of the OBJ stays, so topology, face order, UVs, line endings and the four-decimal format are v2's. The OBJ and the
.mhm carry the same six-decimal weights. Nothing here edits tools/, checks/ or data/envelope: `evaluate` patches `arms.registration` and `arms.rotation_to_down` for the length of the call, the
stand-ins for what Phase 3 implements in tools/envelope/arms.py.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "tools"))
import makehuman_fetch as fetch  # noqa: E402
from envelope import arms, field, frames, gates, meshio, occupancy, register, registry, trial  # noqa: E402

V2_OBJ = REPO / "data/makehuman/freyja-body-v2.obj"
V2_MHM = REPO / "data/makehuman/freyja-body-v2.mhm"
CANDIDATE = REPO / "data/makehuman/cache/v3-candidate"
TARGETS = REPO / "data/makehuman/cache/targets"
MANIFEST = REPO / "data/makehuman/mhm_sources.json"
UPPER_REL, LOWER_REL = "measure/measure-upperarm-length-incr.target", "measure/measure-lowerarm-length-incr.target"
UPPER_MOD, LOWER_MOD = "measure/measure-upperarm-length-decr|incr", "measure/measure-lowerarm-length-decr|incr"
AFTER_MOD = "modifier measure/measure-lowerleg-height-decr|incr "                # v2's last measure line; the arm lines follow it
V3_WEIGHTS = {"upper": 0.381365, "lower": 0.512871}                             # `solve` on the committed SJC, memo 52; the SJC moved 0.007 mm on v3, so no second pass
LENGTH_TOL_MM = 0.1            # adr-0042 D3
SOLVE_STEP = 0.01              # the weight step of the finite-difference Jacobian; the lengths are close to linear in the weights
SKIN_SAMPLE_MM = 0.5           # memo 43: sampling of the exact nearest-skin distance (error at most half of it)
TRUNK_BODIES = ("pelvis", "abdomen", "thorax", "head_neck")
C2_LIMIT, C3_LIMIT_MM, C4_LIMIT = 0.005, 2.0, 0.005                             # adr-0042 D3
C1_LIMIT = register.MAX_STRETCH_DEVIATION                                       # ADR 0007 D10's 8%

SHORTEST_ARC = arms.rotation_to_down


# ---- the pinned targets and the two writers ---------------------------------------------------------------------------------------------

def read_verified_target(manifest: dict, folder, rel: str, n_body: int) -> np.ndarray:
    """The target's deltas (n_body, 3) in the OBJ's own axes and units (decimetres, MakeHuman axes), after checking the file against the manifest; helper vertices are dropped."""
    p = Path(folder) / rel
    data = p.read_bytes()
    if fetch.sha256(data) != manifest["files"][rel]["sha256"]:
        raise ValueError(f"{rel}: the file's hash differs from the manifest")
    D = np.zeros((n_body, 3))
    for line in data.decode("utf-8").splitlines():
        if line and not line.startswith("#"):
            s = line.split()
            if int(s[0]) < n_body:
                D[int(s[0])] = [float(s[1]), float(s[2]), float(s[3])]
    return D


def v3_obj_bytes(v2: bytes, delta: np.ndarray, n_body: int = meshio.BODY_VERTICES) -> bytes:
    """v2's OBJ with `delta` (n_body, 3; decimetres) added to its v lines. A vertex with no delta keeps its line byte for byte; everything else in the file stays."""
    lines = v2.split(b"\n")
    at = [i for i, s in enumerate(lines) if s.startswith(b"v ")]
    if len(at) != n_body or len(delta) != n_body:
        raise ValueError(f"the OBJ has {len(at)} vertices, delta {len(delta)}, expected {n_body}")
    for i, d in zip(at, delta):
        if np.any(d != 0.0):
            cr = lines[i].endswith(b"\r")
            p = np.array(lines[i].split()[1:4], float) + d
            lines[i] = (f"v {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}").encode("ascii") + (b"\r" if cr else b"")
    return b"\n".join(lines)


def v3_mhm_text(v2_text: str, upper, lower) -> str:
    """v2's text with the arm modifier lines after its last measure line, in its format. A weight of None leaves that line out (the forearm-only fallback)."""
    out, seen = [], False
    for line in v2_text.split("\n"):
        out.append(line)
        if line.startswith(AFTER_MOD):
            seen = True
            out += [f"modifier {m} {w:.6f}" for m, w in ((UPPER_MOD, upper), (LOWER_MOD, lower)) if w is not None]
    if not seen:
        raise ValueError("v2's .mhm is not the file this edit was written for")
    return "\n".join(out)


def write_candidate(upper, lower, out=CANDIDATE) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    delta = np.zeros((meshio.BODY_VERTICES, 3))
    for rel, w in ((UPPER_REL, upper), (LOWER_REL, lower)):
        if w:
            delta += w * read_verified_target(manifest, TARGETS, rel, meshio.BODY_VERTICES)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    obj = v3_obj_bytes(V2_OBJ.read_bytes(), delta)
    (out / "freyja-body-v3.obj").write_bytes(obj)
    (out / "freyja-body-v3.mhm").write_text(v3_mhm_text(V2_MHM.read_text(encoding="utf-8"), upper, lower), encoding="utf-8", newline="\n")
    return {"topology_vs_v2": meshio.topology_difference(out / "freyja-body-v3.obj", V2_OBJ), "sha256_12": {f: fetch.sha256((out / f).read_bytes())[:12] for f in ("freyja-body-v3.obj", "freyja-body-v3.mhm")},
            "vertices_moved": int(np.any(delta != 0.0, axis=1).sum()), "max_delta_mm": float(np.linalg.norm(delta, axis=1).max() * meshio.DM_TO_MM)}


# ---- adr-0042: the D1 nodes, the D4 roll ---------------------------------------------------------------------------------------------------

def rotation_to_down_d4(u) -> np.ndarray:
    """adr-0042 D4: the shortest arc onto -z, then the twist about z that maps the mesh's +x, projected onto the section plane, onto +x."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    R = SHORTEST_ARC(u)
    r = R @ (np.array([1.0, 0.0, 0.0]) - u[0] * u)
    a = np.arctan2(r[1], r[0])
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]) @ R


def d1_nodes(inp, sjc, chord_elbow, chord_wrist, L) -> dict:
    """adr-0042 D1: each joint on the proximal segment's section centre line in the Ruler-chord frame; one pass, no iteration. Returns the nodes and the fits."""
    import diag_arm_anchors_b as diag
    return diag.b_nodes(inp, {"sjc": np.asarray(sjc, float), "elbow": chord_elbow, "wrist": chord_wrist}, L)


def d1_registration(orig):
    """`arms.registration` on the D1 nodes and the 8% gate: the chord nodes come from the original (which still stops on its own gate), then every quantity on the nodes is recomputed as there."""
    def registration(inp, tb, rm, sh, side="R"):
        r = orig(inp, tb, rm, sh, side)
        chord, sheet_len = r["nodes_mesh_mm"], r["lengths_sheet_mm"]
        names = ("upper_arm", "forearm")
        B = d1_nodes(inp, chord["sjc"], chord["elbow"], chord["wrist"], {n: sheet_len[n] for n in names})
        sjc, elbow, wrist = chord["sjc"], B["elbow"], B["wrist"]
        u_up, u_fo = elbow - sjc, wrist - elbow
        l_mesh = {"upper_arm": float(np.linalg.norm(u_up)), "forearm": float(np.linalg.norm(u_fo))}
        k = {n: sheet_len[n] / l_mesh[n] for n in names}
        u_fo_n = u_fo / l_mesh["forearm"]
        V, sgn = inp.V, -1.0 if side == "R" else 1.0
        zone = (V[:, 1] * sgn > 0) & tb.arm_mask & (V[:, 2] < elbow[2] + 1.0)
        s = (V - wrist) @ u_fo_n
        hand = zone & (s > 0.0)
        H = V[hand]
        tip = H[int(np.argmax(np.linalg.norm(H - wrist, axis=1)))]
        u_hand = (tip - wrist) / np.linalg.norm(tip - wrist)
        r["chord_nodes_mesh_mm"] = {k_: v for k_, v in chord.items()}
        r["nodes_mesh_mm"] = {"sjc": sjc, "elbow": elbow, "wrist": wrist, "fingertip": tip}
        r["lengths_mesh_mm"], r["stretch"] = l_mesh, k
        r["gate"] = {n: C1_LIMIT for n in names}
        r["sigma_mm"], r["gate_rule"] = None, "8% (ADR 0007 D10, adr-0042 D3)"
        r["axes"] = {"upper_arm": u_up / l_mesh["upper_arm"], "forearm": u_fo_n}
        r["angle_from_vertical_deg"] = {"upper_arm": arms.angle_from_vertical_deg(u_up), "forearm": arms.angle_from_vertical_deg(u_fo), "hand": arms.angle_from_vertical_deg(u_hand)}
        r["elbow_bend_deg"] = float(np.degrees(np.arccos(np.clip(r["axes"]["upper_arm"] @ u_fo_n, -1, 1))))
        r["wrist_bend_deg"] = float(np.degrees(np.arccos(np.clip(u_fo_n @ u_hand, -1, 1))))
        r["hand"] = {"vertices": int(hand.sum()), "fingertip_distance_from_wrist_mm": float(np.linalg.norm(tip - wrist)), "extent_along_forearm_axis_mm": float(s[hand].max()), "stretch": 1.0,
                     "sheet_scs_length_mm": sheet_len["hand"]}
        r["exceeding_gate"] = [n for n in names if abs(k[n] - 1.0) > C1_LIMIT]
        r["fit"] = {"upper_arm_residual_rms_mm": B["fits"][0]["residual_rms_mm"], "forearm_residual_rms_mm": B["fits"][1]["residual_rms_mm"]}
        return r
    return registration


# ---- 2.2: the weights --------------------------------------------------------------------------------------------------------------------

def solve_weights(lengths, target, start, tol_mm=1e-3, max_iter=12) -> np.ndarray:
    """Newton on lengths(w) = target with a finite-difference Jacobian. The arms' weights couple through the elbow node, so the two are solved together."""
    w = np.asarray(start, float)
    for _ in range(max_iter):
        f = lengths(w) - target
        if np.abs(f).max() < tol_mm:
            break
        J = np.column_stack([(lengths(w + SOLVE_STEP * e) - target - f) / SOLVE_STEP for e in np.eye(len(w))])
        w = w - np.linalg.solve(J, f)
    return w


def solve(forearm_only=False, sjc=None) -> dict:
    """The weights on the committed registration's vertex ids and sheet lengths. `sjc` (mesh frame, mm) replaces the committed SJC, for the pass after the trunk registration has been rerun."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    inp = trial.load_inputs(REPO, V2_OBJ)
    D = {k: meshio.to_sheet_mm(read_verified_target(manifest, TARGETS, rel, meshio.BODY_VERTICES)) for k, rel in (("upper", UPPER_REL), ("lower", LOWER_REL))}
    reg = json.loads((REPO / "data/envelope/arm_bodies.json").read_text(encoding="utf-8"))["registration"]
    ids = reg["vertex_ids"]
    sjc_ = np.asarray(sjc if sjc is not None else reg["nodes_mesh_mm"]["sjc"], float)
    L = {n: reg["lengths_sheet_mm"][n] for n in ("upper_arm", "forearm")}
    target = np.array([L["upper_arm"], L["forearm"]])

    def lengths_at(wu, wl):
        V = inp.V + wu * D["upper"] + wl * D["lower"]
        i2 = dataclasses.replace(inp, V=V)
        B = d1_nodes(i2, sjc_, 0.5 * (V[ids["upper_arm_chord_end"]] + V[ids["forearm_chord_start"]]), V[ids["forearm_chord_end"]], L)
        return np.array([np.linalg.norm(B["elbow"] - sjc_), np.linalg.norm(B["wrist"] - B["elbow"])])
    if forearm_only:
        w = solve_weights(lambda x: lengths_at(0.0, x[0])[1:], target[1:], (0.4,))
        wu, wl = None, round(float(w[0]), 6)
    else:
        w = solve_weights(lambda x: lengths_at(x[0], x[1]), target, (0.4, 0.4))
        wu, wl = round(float(w[0]), 6), round(float(w[1]), 6)
    final = lengths_at(wu or 0.0, wl)
    return {"weights": {"upper": wu, "lower": wl}, "lengths_mm": final.tolist(), "sheet_mm": target.tolist(), "residual_mm": (final - target).tolist(), "v2_lengths_mm": lengths_at(0.0, 0.0).tolist(),
            "tolerance_mm": LENGTH_TOL_MM, "in_bounds": all(x is None or 0.0 <= x <= 1.0 for x in (wu, wl)), "sjc_mesh_mm": sjc_.tolist()}


# ---- 2.1 and 2.4: the evaluation ---------------------------------------------------------------------------------------------------------

def placeholder_margin(seg) -> dict:
    """The elbow placeholder's least skin distance, as `fy envelope check` computes the 10.97 mm (positive inside): `occupancy.component_skin_margins` of the CAD registry in the segment's field."""
    r = registry.find(REPO / "data/envelope/components/cad", "upper_arm_R")
    r.frame_offset_mm = frames.segment_offset_mm("upper_arm_R", seg.meta)
    return occupancy.component_skin_margins(seg.signed_distance, r, (0.0, 0.0, 0.0))


def node_report(inp, S) -> dict:
    """Node positions, stretches, exact nearest-skin distances (the whole body's skin, sampled) and the rolls left in the frames."""
    import diag_arm_anchors_b as diag
    reg = S["reg"]
    pts = field.sample_surface(inp.V, inp.F, SKIN_SAMPLE_MM)
    tree = cKDTree(pts)
    n = reg["nodes_mesh_mm"]
    return {"nodes_mesh_mm": {k: np.asarray(v, float).tolist() for k, v in n.items()}, "chord_nodes_mesh_mm": {k: np.asarray(v, float).tolist() for k, v in reg["chord_nodes_mesh_mm"].items()},
            "lengths_mesh_mm": reg["lengths_mesh_mm"], "lengths_sheet_mm": reg["lengths_sheet_mm"], "stretch": reg["stretch"], "exceeding_8pct": reg["exceeding_gate"],
            "skin_distance_mm": {k: float(tree.query(np.asarray(n[k], float))[0]) for k in ("elbow", "wrist")},
            "inside_skin": {k: bool(field.contains(inp.V, inp.F, np.asarray(n[k], float))) for k in ("elbow", "wrist")},
            "field_node_skin_distance_mm": reg["node_skin_distance"], "residual_rms_mm": reg["fit"], "elbow_bend_deg": reg["elbow_bend_deg"], "angle_from_vertical_deg": reg["angle_from_vertical_deg"],
            "roll_left_deg": {name: diag.anterior_angle_deg(S["frames"][name]) for name in ("upper_arm", "forearm")}}


def evaluate(mesh, out) -> dict:
    """`fy envelope gates` with the arms on the D1 nodes and the D4 roll. Its three result files go to `out`. Gate 6 (Blender) and the arm gate's printed label do not apply to a candidate."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(voxel=2.0, knee="chords", base=None)
    p = {"mesh": Path(mesh), "out": out, "cache": out / "cache"}
    keep = {}
    reg0, side0, rot0 = arms.registration, arms.build_side, arms.rotation_to_down

    def side(inp, tb, rm, sh, s="R", voxel=2.0):
        keep[s] = side0(inp, tb, rm, sh, s, voxel)
        keep["inp"] = inp
        return keep[s]
    arms.registration, arms.build_side, arms.rotation_to_down = d1_registration(reg0), side, rotation_to_down_d4
    try:
        code = gates.run(p, args, REPO, lambda f, root: Path(f).name)
    finally:
        arms.registration, arms.build_side, arms.rotation_to_down = reg0, side0, rot0
    res = {"gates_exit": code, "mesh": Path(mesh).name, "R": node_report(keep["inp"], keep["R"]), "L": node_report(keep["inp"], keep["L"]),
           "placeholder_inside_skin_mm": placeholder_margin(keep["R"]["results"]["upper_arm"].seg)}
    (out / "v3_eval.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return res


def compare(base, cand) -> dict:
    """C1 to C4 of the candidate directory against the base directory, and the numbers reported with no criterion."""
    def load(d):
        d = Path(d)
        return {k: json.loads((d / f"{k}.json").read_text(encoding="utf-8")) for k in ("arm_bodies", "trunk_bodies", "leg_R_trial", "v3_eval")}
    A, B = load(base), load(cand)
    ea, eb = A["v3_eval"], B["v3_eval"]
    vol = lambda X, n: X["trunk_bodies"]["design"][n]["skin_volume_l"]
    st = eb["R"]["stretch"]
    worst_c1 = max(abs(v - 1.0) for s in "RL" for v in eb[s]["stretch"].values())
    clo = B["arm_bodies"]["closure"]["relative_difference"]
    sjc_move = float(np.linalg.norm(np.array(eb["R"]["nodes_mesh_mm"]["sjc"]) - np.array(ea["R"]["nodes_mesh_mm"]["sjc"])))
    tr = {n: {"base_l": vol(A, n), "cand_l": vol(B, n), "change": vol(B, n) / vol(A, n) - 1.0} for n in TRUNK_BODIES}
    worst_c4 = max(abs(v["change"]) for v in tr.values())
    table = {"C1 arm stretch within 8%": {"measured": st, "worst_abs_both_sides": worst_c1, "limit": C1_LIMIT, "pass": worst_c1 <= C1_LIMIT},
             "C2 closure": {"measured": clo, "limit": C2_LIMIT, "pass": abs(clo) <= C2_LIMIT},
             "C3 SJC move mm": {"measured": sjc_move, "limit": C3_LIMIT_MM, "pass": sjc_move <= C3_LIMIT_MM},
             "C4 trunk body volume": {"measured": tr, "worst_abs": worst_c4, "limit": C4_LIMIT, "pass": worst_c4 <= C4_LIMIT}}
    leg = lambda X, k: X["arm_bodies"]["closure"]["built_l"][k]
    rows = lambda X: X["arm_bodies"]["share_table"]["rows"]
    mb = lambda X: X["leg_R_trial"]["mass_base"]
    return {"criteria": table, "all_pass": all(v["pass"] for v in table.values()),
            "legs_l": {k: {"base": leg(A, k), "cand": leg(B, k), "change": leg(B, k) / leg(A, k) - 1.0} for k in ("thighs", "shanks", "foots")},
            "arms_l": {k: {"base": leg(A, k), "cand": leg(B, k)} for k in ("upper_arms", "forearms", "hands")},
            "closure": {k: (A["arm_bodies"]["closure"][k], B["arm_bodies"]["closure"][k]) for k in ("sum_l", "mesh_volume_l", "relative_difference")},
            "mass_base": {k: (mb(A)["cases"][k]["mesh_mass_kg"], mb(B)["cases"][k]["mesh_mass_kg"], mb(A)["cases"][k]["sculpt_bmi_kg_per_m2"], mb(B)["cases"][k]["sculpt_bmi_kg_per_m2"]) for k in mb(A)["cases"]},
            "d8": {k: (A["trunk_bodies"]["whole_body_density"][k], B["trunk_bodies"]["whole_body_density"][k]) for k in ("robot_kg_per_l", "tissue_kg_per_l")},
            "d7_raw_ratio": {k: (rows(A)[k]["raw_ratio"], rows(B)[k]["raw_ratio"], rows(A)[k]["role"]) for k in rows(A)},
            "placeholder_inside_skin_mm": (ea["placeholder_inside_skin_mm"], eb["placeholder_inside_skin_mm"]),
            "nodes_skin_mm": (ea["R"]["skin_distance_mm"], eb["R"]["skin_distance_mm"]), "rolls_deg": (ea["R"]["roll_left_deg"], eb["R"]["roll_left_deg"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("solve")
    p.add_argument("--forearm-only", action="store_true"), p.add_argument("--sjc", nargs=3, type=float)
    p = sub.add_parser("write")
    p.add_argument("--upper", type=float, default=V3_WEIGHTS["upper"]), p.add_argument("--lower", type=float, default=V3_WEIGHTS["lower"]), p.add_argument("--out", default=str(CANDIDATE))
    p = sub.add_parser("evaluate")
    p.add_argument("--mesh", default=str(V2_OBJ)), p.add_argument("--out", required=True)
    p = sub.add_parser("compare")
    p.add_argument("--base", required=True), p.add_argument("--cand", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "solve":
        res = solve(a.forearm_only, a.sjc)
    elif a.cmd == "write":
        if a.lower is None:
            ap.error("no weights: V3_WEIGHTS is unset, pass --upper and --lower")
        res = write_candidate(a.upper, a.lower, a.out)
    elif a.cmd == "evaluate":
        res = evaluate(a.mesh, a.out)
    else:
        res = compare(a.base, a.cand)
    print(json.dumps(res, indent=1, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
