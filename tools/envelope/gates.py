"""`fy envelope gates`: the trial's gate table, the feature report, the ANSUR diagnostics and the Monte Carlo.

Everything is computed here from the inputs; nothing is typed in. The result is written as thigh_R_trial.json beside the ledger
(deterministic: no timestamps, no absolute paths) and printed as a table.
"""
from __future__ import annotations

import json

import numpy as np

from . import meshio, oracle, register, synthetic, trial

LENGTH_TOL_MM = 0.5       # gate 3 (the brief)
AREA_TOL = 0.01           # gate 3: section areas at matched normalised stations (the brief)
SYNTH_TOL_MM = 2.0        # gate 4: one voxel (the brief)
MATCHED_U = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)   # normalised stations compared in gate 3; the hip zone (u < 0.1) is left out
MC_N = 200                # Monte Carlo samples (the brief)


def _gate(name, ok, detail):
    return {"gate": name, "pass": bool(ok), "detail": detail}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def run(p, args, root, label) -> int:
    inp = trial.load_inputs(root, p["mesh"])
    out = {"mesh_file": label(p["mesh"], root), "voxel_mm": args.voxel, "ansur_source": inp.ansur.get("source_sha256_12")}
    gates = []

    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "auto" if args.knee == "auto" else args.knee)
    summ = reg.summary()
    kn = feats["knee"]
    out["sole_plane"] = inp.sole
    out["sheet_checks"] = inp.sheet.checks
    out["features"] = {"ansur_scaled_to_mesh_stature_mm": feats["ansur_scaled_mm"], "mesh_stature_mm": inp.stature_mesh, "crotch_apex_mm": feats["crotch_apex_mm"],
                       "knee_breadth_feature": kn, "knee_source_used": reg.knee_source,
                       "knee_disagreement_mm": kn["z_mm"] - feats["ansur_scaled_mm"]["lateral_femoral_epicondyle"],
                       "crotch_disagreement_mm": feats["crotch_apex_mm"] - feats["ansur_scaled_mm"]["crotch"], "ruler": "not available (no Ruler.Measures vertex lists in the repo)"}
    out["diagnostics"] = register.diagnostics(inp.sheet, inp.ansur)
    out["registration"] = summ
    out["section_centroids_before_shear_mm"] = reg.centroids

    # gate 1: topology and watertightness
    topo = meshio.topology_difference(p["mesh"], root / "data/makehuman/freyja-body-v1.obj")
    res = trial.build_thigh(inp, reg, args.voxel)
    c = res.checks
    out["checks"] = _jsonable(c)
    ok1 = topo is None and c["boundary_edges_near_thigh"] == 0 and c["nonmanifold_edges_near_thigh"] == 0 and c["odd_parity_columns"] == 0
    gates.append(_gate("1 topology matches base; thigh surface watertight", ok1,
                       f"topology difference: {topo or 'none (the reference is this same file)'}; boundary edges near the thigh {c['boundary_edges_near_thigh']} "
                       f"(whole body {c['boundary_edges_whole_body']}); non-manifold {c['nonmanifold_edges_near_thigh']}; odd-parity columns {c['odd_parity_columns']}"))
    for key in ("hjc_inside_body", "kjc_inside_body", "ajc_inside_body", "mid_axis_inside_region"):
        if not c[key]:
            gates.append(_gate(f"stop: {key}", False, "a node of the conformed thigh lies outside the plausible region; the brief says stop and ask Joe"))

    # gate 2: per-sub-segment stretch, and the robust envelope
    prof = trial.build_profile(inp, feats, reg, args.voxel)
    mc = register.monte_carlo(prof, reg, n=MC_N, shells=trial.SHELLS_MM)
    out["monte_carlo"] = _jsonable(mc)
    st = summ["stretch"]
    worst = max(abs(v - 1) for v in st.values())
    nom_r, sp_r = mc["nominal"]["rmin_t0"], mc["spread"]["rmin_t0"]
    nom_v, sp_v = mc["nominal"]["volume_t0"], mc["spread"]["volume_t0"]
    dr = nom_r - sp_r["p5"]
    dv = max(abs(sp_v["p2_5"] - nom_v), abs(sp_v["p97_5"] - nom_v)) / nom_v
    ok2 = worst < register.MAX_STRETCH_DEVIATION and dr <= register.ROBUST_RADIUS_MM and dv <= register.ROBUST_VOLUME
    gates.append(_gate("2 |stretch-1| < 8% per sub-segment; robust radius within 5 mm, volume within 10%", ok2,
                       f"stretch foot {st['foot']:.4f}, shank {st['shank']:.4f}, thigh {st['thigh']:.4f}; min inscribed radius nominal {nom_r:.2f} mm at station "
                       f"{mc['nominal']['rmin_station_t0']:.0f}, robust (5th pct) {sp_r['p5']:.2f} mm (diff {dr:.2f}); skin volume nominal {nom_v / 1e6:.3f} l, "
                       f"95% range {sp_v['p2_5'] / 1e6:.3f}-{sp_v['p97_5'] / 1e6:.3f} l (max diff {dv * 100:.1f}%); N={mc['n']}"))

    # gate 3: conformed length and section areas at matched normalised stations
    s_th = st["thigh"]
    L_conf = float(reg.axial.forward(reg.mesh_nodes["hjc"]) - reg.axial.forward(reg.mesh_nodes["kjc"]))
    areas = []
    for u in MATCHED_U:
        s = u * res.seg.length
        zpre = reg.mesh_nodes["hjc"] - s / s_th
        a0 = float(np.interp(zpre, prof["z"], prof["area"][0.0]))
        a1 = res.seg.section(s).area()
        areas.append((u, a0, a1, (a1 - a0) / a0))
    worst_area = max(abs(a[3]) for a in areas)
    dl = max(abs(res.seg.length - inp.sheet.thigh_length), abs(L_conf - inp.sheet.thigh_length))
    gates.append(_gate("3 length = sheet within 0.5 mm; matched-station areas within 1%", dl < LENGTH_TOL_MM and worst_area < AREA_TOL,
                       f"conformed length {L_conf:.3f} mm vs sheet {inp.sheet.thigh_length:.3f} mm (diff {dl:.4f}); worst area change {worst_area * 100:.3f}% over u = 0.1..0.9"))
    out["conform"] = {"length_mm": L_conf, "sheet_length_mm": inp.sheet.thigh_length,
                      "areas": [{"u": a[0], "unconformed_mm2": a[1], "conformed_mm2": a[2], "relative": a[3]} for a in areas],
                      "volume_unconformed_slab_l": float(np.trapezoid(np.interp(np.linspace(reg.mesh_nodes['kjc'], reg.mesh_nodes['hjc'], 400), prof['z'], prof['area'][0.0]),
                                                                       np.linspace(reg.mesh_nodes['kjc'], reg.mesh_nodes['hjc'], 400))) / 1e6,
                      "volume_conformed_l": res.seg.volume() / 1e6, "volume_profile_nominal_l": mc["nominal"]["volume_t0"] / 1e6}

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
        gates.append(_gate("5 oracle CLI: margin and binding station, feasible and infeasible", feas["feasible"] and not infe["feasible"],
                           f"feasible case: margin {feas['margin_mm']:.2f} mm at station {feas['station_mm']:.1f} mm; infeasible case: margin {infe['margin_mm']:.2f} mm "
                           f"at station {infe['station_mm']:.1f} mm (pose {infe['pose_index']})"))
        out["example"] = {k: {kk: v[kk] for kk in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible")} for k, v in (("feasible", feas), ("infeasible", infe))}
    except FileNotFoundError:
        gates.append(_gate("5 oracle CLI worked example", False, "data/envelope/examples/ is missing"))

    # reported with the gates: volumes and density
    skin = res.seg.volume() / 1e6
    out["volumes"] = {"skin_l": skin, "inner_l": {f"t{t:g}": res.seg.volume(t) / 1e6 for t in trial.SHELLS_MM},
                      "sheet_thigh_mass_kg": inp.sheet.thigh_mass_kg, "implied_density_kg_per_l": inp.sheet.thigh_mass_kg / skin}
    out["gates"] = gates
    outdir = p["out"]
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "thigh_R_trial.json").write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    f = out["features"]
    print(f"mesh {out['mesh_file']}   voxel {args.voxel} mm   knee source: {reg.knee_source}")
    print(f"mesh stature {inp.stature_mesh:.1f} mm; crotch apex {f['crotch_apex_mm']:.1f} (ANSUR-scaled {feats['ansur_scaled_mm']['crotch']:.1f}); knee breadth peak {kn['z_mm']:.1f} "
          f"(prominence {kn['prominence_mm']:.2f} mm, feature: {kn['is_feature']}) vs ANSUR-scaled epicondyle {feats['ansur_scaled_mm']['lateral_femoral_epicondyle']:.1f}")
    d = out["diagnostics"]
    print(f"sheet vs ANSUR (scaled to {inp.sheet.stature_mm:.0f} mm): HJC - trochanterion {d['hjc_minus_scaled_trochanterion_mm']:+.1f} mm (flag {d['hjc_flag']}), "
          f"KJC - lateral epicondyle {d['kjc_minus_scaled_lateral_epicondyle_mm']:+.1f} mm")
    print(f"shear: thigh {summ['shear_mm']['thigh']:.1f} mm ({summ['shear_deg']['thigh']:.1f} deg), shank {summ['shear_mm']['shank']:.1f} mm ({summ['shear_deg']['shank']:.1f} deg)")
    for g in gates:
        print(f"[{'PASS' if g['pass'] else 'FAIL'}] gate {g['gate']}\n        {g['detail']}")
    v = out["volumes"]
    print(f"skin volume {v['skin_l']:.3f} l; inner: " + ", ".join(f"t={k[1:]} {x:.3f}" for k, x in v["inner_l"].items()) +
          f"; sheet mass {v['sheet_thigh_mass_kg']:.2f} kg -> {v['implied_density_kg_per_l']:.3f} kg/l")
    return 0 if all(g["pass"] for g in gates) else 1
