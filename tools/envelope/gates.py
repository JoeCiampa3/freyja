"""`fy envelope gates`: the trial's gate table, the sensitivity of the required stretch and the two pelvis-scale variants.

Everything is computed here from the inputs; nothing is typed in. The result is written as thigh_R_trial.json beside the ledger
(deterministic: no timestamps, no absolute paths) and printed as a table.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import field, meshio, oracle, synthetic, trial

ASIS_TOL = 0.08           # gate 2: |s - 1| (the brief)
PERTURB_TOL = 0.015       # gate 2: relative move of s under a 5 mm landmark perturbation (the brief)
LENGTH_TOL_MM = 0.5       # gate 3 (the brief)
AREA_TOL = 0.01           # gate 3: section areas at matched normalised stations (the brief)
SYNTH_TOL_MM = 2.0        # gate 4: one voxel (the brief)
MATCHED_U = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)   # normalised stations compared in gate 3; the hip zone (u < 0.1) is left out


def _gate(name, ok, detail):
    return {"gate": name, "pass": bool(ok), "detail": detail}


def run(inp, p, args, root, label) -> int:
    out = {"landmark_file": "provisional" if inp.provisional else label(p["landmarks"], root), "voxel_mm": args.voxel}
    gates = []

    # gate 1: topology and watertightness
    topo = meshio.topology_difference(p["mesh"], root / "data/mesh/freyja-body-v1.obj")
    res = trial.build_thigh(inp, "asis", args.voxel)
    c = res.checks
    gates.append(_gate("1 topology matches base; thigh surface watertight", topo is None and c["boundary_edges_near_thigh"] == 0 and c["nonmanifold_edges_near_thigh"] == 0
                       and c["odd_parity_columns"] == 0,
                       f"topology difference: {topo or 'none'}; boundary edges near the thigh {c['boundary_edges_near_thigh']} (whole body {c['boundary_edges_whole_body']}); "
                       f"non-manifold {c['nonmanifold_edges_near_thigh']}; odd-parity columns {c['odd_parity_columns']}"))
    out["checks"] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in c.items()}
    for key in ("hjc_inside_body", "kjc_inside_body", "mid_axis_inside_region"):
        if not c[key]:
            gates.append(_gate(f"stop: {key}", False, "a landmark-derived point lies outside the plausible region; brief says stop and ask Joe"))

    # gate 2: required stretch and its sensitivity
    sens = {}
    for mode in ("asis", "sheet"):
        sv = trial.sensitivity(inp.P, inp.b1, inp.thigh_length_mm, k_mode=mode, k_fixed=inp.k_sheet)
        sens[mode] = sv
    s_asis = res.s
    out["stretch"] = {"s_asis": s_asis, "k_asis": res.k}
    sv = sens["asis"]
    worst = max(sv.one_at_a_time, key=lambda r: abs(r[4]))
    gates.append(_gate("2 |s-1| < 8% and moves < 1.5% under 5 mm perturbation",
                       abs(s_asis - 1) < ASIS_TOL and sv.max_relative_change < PERTURB_TOL,
                       f"s = {s_asis:.4f} (|s-1| = {abs(s_asis - 1) * 100:.2f}%); worst one-at-a-time move {sv.max_relative_change * 100:.2f}% "
                       f"({worst[0]} {worst[1]} {worst[2]:+.0f} mm); Monte Carlo N={sv.n}, sigma 5 mm: s = {sv.mc_mean:.4f} +- {sv.mc_std:.4f} (5-95%: {sv.mc_p5:.4f}-{sv.mc_p95:.4f})"))
    out["sensitivity"] = {m: {"max_relative_change": v.max_relative_change, "mc_mean": v.mc_mean, "mc_std": v.mc_std, "mc_p5": v.mc_p5, "mc_p95": v.mc_p95,
                              "mc_min": v.mc_min, "mc_max": v.mc_max, "n": v.n,
                              "one_at_a_time": [{"landmark": r[0], "axis": r[1], "delta_mm": r[2], "s": r[3], "relative_change": r[4]} for r in v.one_at_a_time]}
                          for m, v in sens.items()}

    # gate 3: conformed length and section areas at matched normalised stations
    raw = trial.build_thigh(inp, "asis", args.voxel, stretch=False)
    areas = []
    for u in MATCHED_U:
        a0 = raw.seg.section(u * raw.seg.length).area()
        a1 = res.seg.section(u * res.seg.length).area()
        areas.append((u, a0, a1, (a1 - a0) / a0))
    worst_area = max(abs(a[3]) for a in areas)
    dl = abs(res.seg.length - inp.thigh_length_mm)
    gates.append(_gate("3 length = sheet within 0.5 mm; matched-station areas within 1%", dl < LENGTH_TOL_MM and worst_area < AREA_TOL,
                       f"conformed length {res.seg.length:.3f} mm vs sheet {inp.thigh_length_mm:.3f} mm (diff {dl:.4f}); worst area change {worst_area * 100:.3f}% over u = 0.1..0.9"))
    out["conform"] = {"length_mm": res.seg.length, "sheet_length_mm": inp.thigh_length_mm, "areas": [{"u": a[0], "unstretched_mm2": a[1], "stretched_mm2": a[2], "relative": a[3]} for a in areas],
                      "volume_unstretched_l": raw.seg.volume() / 1e6, "volume_stretched_l": res.seg.volume() / 1e6}

    # gate 4: synthetic solids
    rep = synthetic.report(args.voxel)
    worst_syn = max(v for d in rep.values() for v in d.values())
    gates.append(_gate("4 oracle reproduces cylinder, box and cone within one voxel (2 mm)", worst_syn < SYNTH_TOL_MM,
                       "; ".join(f"{k}: V {d['volume']:.3f}, A {d['section_area']:.3f}, r {d['inscribed_radius']:.3f} mm" for k, d in rep.items())))
    out["synthetic_mm"] = rep

    # gate 5: the worked example through the oracle, feasible and infeasible
    ex = root / "data/envelope/examples"
    try:
        shapes = oracle.read_shapes(ex / "rod_shapes.yaml")
        feas = oracle.clearance(res.seg, shapes, oracle.read_poses(ex / "rod_feasible_poses.csv"))
        infe = oracle.clearance(res.seg, shapes, oracle.read_poses(ex / "rod_infeasible_poses.csv"))
        ok5 = feas["feasible"] and not infe["feasible"]
        gates.append(_gate("5 oracle CLI: margin and binding station, feasible and infeasible", ok5,
                           f"feasible case: margin {feas['margin_mm']:.2f} mm at station {feas['station_mm']:.1f} mm; infeasible case: margin {infe['margin_mm']:.2f} mm at station {infe['station_mm']:.1f} mm (pose {infe['pose_index']})"))
        out["example"] = {"feasible": {k: feas[k] for k in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible")},
                          "infeasible": {k: infe[k] for k in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible")}}
    except FileNotFoundError:
        gates.append(_gate("5 oracle CLI worked example", False, "data/envelope/examples/ is missing"))

    # k variants
    res_sheet = trial.build_thigh(inp, "sheet", args.voxel)
    out["k_variants"] = {
        v: {"k": r.k, "s": r.s, "hjc_sheet_mm": [float(x) for x in r.hjc], "skin_volume_l": r.seg.volume() / 1e6, "length_mesh_mm": r.L_mesh}
        for v, r in (("asis", res), ("sheet", res_sheet))}
    out["k_variants"]["delta"] = {"hjc_mm": float(np.linalg.norm(res.hjc - res_sheet.hjc)), "s": res_sheet.s - res.s,
                                  "skin_volume_l": res_sheet.seg.volume() / 1e6 - res.seg.volume() / 1e6}

    out["gates"] = gates
    outdir = p["out"]
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "thigh_R_trial.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"landmarks: {out['landmark_file']}   voxel {args.voxel} mm   k variants: asis {res.k:.4f}, sheet {res_sheet.k:.4f}")
    for g in gates:
        print(f"[{'PASS' if g['pass'] else 'FAIL'}] gate {g['gate']}\n        {g['detail']}")
    kv = out["k_variants"]
    print(f"k variants: asis k {kv['asis']['k']:.4f} s {kv['asis']['s']:.4f} V {kv['asis']['skin_volume_l']:.3f} l; sheet k {kv['sheet']['k']:.4f} s {kv['sheet']['s']:.4f} V {kv['sheet']['skin_volume_l']:.3f} l; HJC differs by {kv['delta']['hjc_mm']:.2f} mm")
    return 0 if all(g["pass"] for g in gates) else 1
