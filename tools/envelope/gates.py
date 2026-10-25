"""`fy envelope gates`: the trial's gate table, the feature report, the ANSUR diagnostics, the Monte Carlo, the mass base, the girth check and the cut sensitivity.

Everything is computed here from the inputs; nothing is typed in. The result is written as leg_R_trial.json beside the ledgers (deterministic: no
timestamps, no absolute paths) and printed as a table.
"""
from __future__ import annotations

import json

import numpy as np

from . import masses, meshio, oracle, register, synthetic, trial

LENGTH_TOL_MM = 0.5       # gate 3 (the brief)
AREA_TOL = 0.01           # gate 3: section areas at matched normalised stations (the brief)
SYNTH_TOL_MM = 2.0        # gate 4: one voxel (the brief)
MATCHED_U = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)   # normalised stations compared in gate 3; the hip zone (u < 0.1) is left out
MC_N = 200                # Monte Carlo samples (the brief)
CUT_SHIFT_MM = 15.0       # brief 2 item 5: shift of each cut plane
GIRTH_FLAG = 0.02         # brief 2 item 6: flag when the ledger perimeter and the Ruler loop's own perimeter differ by more than this
KNEE_VARIANTS = ("ruler", "ansur", "chords")   # anchors compared in the report (the `breadth` anchor does not exist for this mesh)


def _gate(name, ok, detail):
    return {"gate": name, "pass": bool(ok), "detail": detail}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def _volume_window(profile, reg, segment, t, up_shift_mm=0.0, low_shift_mm=0.0):
    """Conformed volume (mm3) of a segment whose proximal and distal cut planes are shifted by the given millimetres in the sheet frame."""
    up, low = trial.SEGMENTS[segment]
    s = reg.axial.stretches()[segment]
    zu = reg.mesh_nodes[up] + up_shift_mm / s
    zl = (reg.mesh_nodes[low] if low else 0.0) + low_shift_mm / s
    zz = np.linspace(zl, zu, 400)
    return float(s * np.trapezoid(np.interp(zz, profile["z"], profile["area"][t]), zz))


def knee_report(inp, feats, S=None):
    """Registration summary for each knee anchor, no voxel work: stretches, shears and the mesh node heights."""
    out = {}
    for src in KNEE_VARIANTS:
        reg = trial.make_registration(inp, feats, src)
        out[src] = {**reg.summary(), "kjc_sd_mm": reg.sigmas["kjc"]}
    return out


def run(p, args, root, label) -> int:
    inp = trial.load_inputs(root, p["mesh"])
    out = {"mesh_file": label(p["mesh"], root), "voxel_mm": args.voxel, "ansur_source": inp.ansur.get("source_sha256_12")}
    gates = []

    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, args.knee)
    summ = reg.summary()
    kn = feats["knee"]
    out["knee_source_used"] = reg.knee_source
    out["sole_plane"] = inp.sole
    out["sheet_checks"] = inp.sheet.checks
    out["features"] = {"ansur_scaled_to_mesh_stature_mm": feats["ansur_scaled_mm"], "mesh_stature_mm": inp.stature_mesh, "crotch_apex_mm": feats["crotch_apex_mm"],
                       "knee_breadth_feature": kn, "kjc_estimates_mm": feats["kjc_estimates_mm"], "hjc_estimates_mm": feats["hjc_estimates_mm"],
                       "ajc_estimates_mm": feats["ajc_estimates_mm"], "ruler": inp.ruler,
                       "kjc_disagreement_vs_ansur_ratio_mm": {k: (v - feats["kjc_estimates_mm"]["ansur_ratio"]) if v is not None else None for k, v in feats["kjc_estimates_mm"].items()},
                       "ruler_ankle_loop_above_ansur_ankle_ratio_mm": feats["ajc_estimates_mm"]["ruler_ankle_loop_height"] - feats["ajc_estimates_mm"]["ansur_ratio"],
                       "ankle_offset_source": "none: ANSUR II gives the minimum ankle circumference but not its height above the floor, so the Ruler ankle loop cannot anchor the AJC"}
    out["diagnostics"] = register.diagnostics(inp.sheet, inp.ansur)
    out["registration"] = summ
    out["knee_variants"] = knee_report(inp, feats)
    out["section_centroids_before_shear_mm"] = reg.centroids

    results = {name: trial.build_segment(inp, feats, reg, name, args.voxel) for name in trial.SEGMENTS}
    profiles = {name: trial.build_profile(inp, feats, reg, name, args.voxel) for name in ("thigh", "shank")}
    mcs = {name: register.monte_carlo(profiles[name], reg, name, n=MC_N, shells=trial.SHELLS_MM) for name in profiles}
    out["monte_carlo"] = _jsonable(mcs)
    out["checks"] = {n: _jsonable(r.checks) for n, r in results.items()}

    st = summ["stretch"]
    topo = meshio.topology_difference(p["mesh"], root / "data/makehuman/freyja-body-v1.obj")
    for name in ("thigh", "shank"):
        res, prof, mc = results[name], profiles[name], mcs[name]
        c = res.checks
        up, low, u_s, L, u_m, l_m = trial.segment_geometry(inp, reg, name)
        ok1 = topo is None and c["boundary_edges_near_segment"] == 0 and c["nonmanifold_edges_near_segment"] == 0 and c["odd_parity_columns"] == 0 and c["seed_inside_region"]
        gates.append(_gate(f"1 {name}: topology matches base; surface watertight", ok1,
                           f"topology difference: {topo or 'none (the reference is this same file)'}; boundary edges near the {name} {c['boundary_edges_near_segment']} "
                           f"(whole body {c['boundary_edges_whole_body']}); non-manifold {c['nonmanifold_edges_near_segment']}; odd-parity columns {c['odd_parity_columns']}"))
        if name == "thigh":
            for key in ("hjc_inside_body", "kjc_inside_body", "ajc_inside_body"):
                if not c[key]:
                    gates.append(_gate(f"stop: {key}", False, "a node of the conformed leg lies outside the body; the brief says stop and ask Joe"))
        # gate 2: the stretch of this segment, and the robust envelope
        s_seg = st[name]
        nom_r, sp_r = mc["nominal"]["rmin_t0"], mc["spread"]["rmin_t0"]
        nom_v, sp_v = mc["nominal"]["volume_t0"], mc["spread"]["volume_t0"]
        dr = nom_r - sp_r["p5"]
        dv = max(abs(sp_v["p2_5"] - nom_v), abs(sp_v["p97_5"] - nom_v)) / nom_v
        ok2 = abs(s_seg - 1) < register.MAX_STRETCH_DEVIATION and dr <= register.ROBUST_RADIUS_MM and dv <= register.ROBUST_VOLUME
        gates.append(_gate(f"2 {name}: |stretch-1| < 8%; robust radius within 5 mm, volume within 10%", ok2,
                           f"stretch {s_seg:.4f} ({(s_seg - 1) * 100:+.1f}%); min inscribed radius nominal {nom_r:.2f} mm at station {mc['nominal']['rmin_station_t0']:.0f}, robust (5th pct) "
                           f"{sp_r['p5']:.2f} mm (diff {dr:.2f}); skin volume nominal {nom_v / 1e6:.3f} l, 95% range {sp_v['p2_5'] / 1e6:.3f}-{sp_v['p97_5'] / 1e6:.3f} l "
                           f"(max diff {dv * 100:.1f}%); N={mc['n']}"))
        # gate 3: conformed length and section areas at matched normalised stations
        L_conf = float(reg.axial.forward(u_m) - reg.axial.forward(l_m)) if low else float(reg.axial.forward(u_m) - 0.0)
        areas = []
        for u in MATCHED_U:
            s = u * res.seg.length
            zpre = u_m - s / s_seg
            a0 = float(np.interp(zpre, prof["z"], prof["area"][0.0]))
            a1 = res.seg.section(s).area()
            areas.append((u, a0, a1, (a1 - a0) / a0))
        worst_area = max(abs(a[3]) for a in areas)
        sheet_len = {"thigh": inp.sheet.thigh_length, "shank": inp.sheet.shank_length}[name]
        dl = max(abs(res.seg.length - sheet_len), abs(L_conf - sheet_len))
        gates.append(_gate(f"3 {name}: length = sheet within 0.5 mm; matched-station areas within 1%", dl < LENGTH_TOL_MM and worst_area < AREA_TOL,
                           f"conformed length {L_conf:.3f} mm vs sheet {sheet_len:.3f} mm (diff {dl:.4f}); worst area change {worst_area * 100:.3f}% over u = 0.1..0.9"))
        out.setdefault("conform", {})[name] = {"length_mm": L_conf, "sheet_length_mm": sheet_len,
                                              "areas": [{"u": a[0], "unconformed_mm2": a[1], "conformed_mm2": a[2], "relative": a[3]} for a in areas],
                                              "volume_conformed_l": res.seg.volume() / 1e6, "volume_profile_nominal_l": nom_v / 1e6}
    st_foot = st["foot"]
    gates.append(_gate("2 foot: |stretch-1| < 8%", abs(st_foot - 1) < register.MAX_STRETCH_DEVIATION, f"stretch {st_foot:.4f} ({(st_foot - 1) * 100:+.2f}%)"))

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
        feas = oracle.clearance(results["thigh"].seg, shapes, oracle.read_poses(ex / "rod_feasible_poses.csv"))
        infe = oracle.clearance(results["thigh"].seg, shapes, oracle.read_poses(ex / "rod_infeasible_poses.csv"))
        gates.append(_gate("5 oracle CLI: margin and binding station, feasible and infeasible", feas["feasible"] and not infe["feasible"],
                           f"feasible case: margin {feas['margin_mm']:.2f} mm at station {feas['station_mm']:.1f} mm; infeasible case: margin {infe['margin_mm']:.2f} mm "
                           f"at station {infe['station_mm']:.1f} mm (pose {infe['pose_index']})"))
        out["example"] = {k: {kk: v[kk] for kk in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible")} for k, v in (("feasible", feas), ("infeasible", infe))}
    except FileNotFoundError:
        gates.append(_gate("5 oracle CLI worked example", False, "data/envelope/examples/ is missing"))

    # mass base (item 3), thigh restated (item 4)
    consts = masses.load_constants(root)
    mb = masses.report(inp, results, consts)
    out["mass_base"] = mb
    gates.append(_gate("6 mesh volume matches Joe's Blender volume within 0.5%", bool(mb["blender_within_tolerance"]),
                       f"computed {mb['mesh_volume_l']:.4f} l, Blender {mb['blender_volume_l']:.4f} l ({mb['blender_relative_difference'] * 100:+.4f}%)"))

    # how the knee anchor moves volume between thigh and shank, and what that does to the implied densities (profile volumes, so no extra voxel builds)
    kv = {}
    total = inp.sheet.total_mass_kg
    for src in KNEE_VARIANTS:
        rv = trial.make_registration(inp, feats, src)
        vt, vs = (_volume_window(profiles[n], rv, n, 0.0) / 1e6 for n in ("thigh", "shank"))
        kv[src] = {"stretch": rv.axial.stretches(), "thigh_skin_l": vt, "shank_skin_l": vs, "cases": {}}
        for lab, c in mb["cases"].items():
            kv[src]["cases"][lab] = {"thigh_implied_density": inp.sheet.thigh_mass_kg / total * c["mesh_mass_kg"] / vt, "shank_implied_density": inp.sheet.shank_mass_kg / total * c["mesh_mass_kg"] / vs}
    out["knee_anchor_mass_sensitivity"] = kv

    # cut sensitivity of the shank volume (item 5)
    cut = {}
    for t in (0.0, 5.0):
        v0 = _volume_window(profiles["shank"], reg, "shank", t)
        row = {"nominal_l": v0 / 1e6}
        for label_, (us, ls) in {"KJC plane +15": (CUT_SHIFT_MM, 0.0), "KJC plane -15": (-CUT_SHIFT_MM, 0.0), "AJC plane +15": (0.0, CUT_SHIFT_MM), "AJC plane -15": (0.0, -CUT_SHIFT_MM)}.items():
            v = _volume_window(profiles["shank"], reg, "shank", t, us, ls)
            row[label_] = {"volume_l": v / 1e6, "change_percent": (v - v0) / v0 * 100.0}
        cut[f"t{t:g}"] = row
    out["shank_cut_sensitivity"] = cut

    # girth check on the UNCONFORMED mesh at the Ruler loop heights (item 6)
    girth = {}
    for name, prof in (("thigh", profiles["thigh"]), ("knee", profiles["shank"]), ("calf", profiles["shank"]), ("ankle", profiles["shank"])):
        rl = inp.ruler["thigh" if name == "thigh" else name]
        z = rl["z_mm"]
        perim = float(np.interp(z, prof["z"], prof["perimeter"]))
        area = float(np.interp(z, prof["z"], prof["area"][0.0]))
        girth[name] = {"loop_height_mm": z, "loop_length_mm": rl["length_mm"], "loop_tilt_deg": rl["tilt_deg"], "section_perimeter_mm": perim,
                       "equivalent_circle_mm": 2 * float(np.sqrt(np.pi * area)), "difference_percent": (perim - rl["length_mm"]) / rl["length_mm"] * 100.0,
                       "flag": bool(abs(perim - rl["length_mm"]) / rl["length_mm"] > GIRTH_FLAG)}
    out["girth_check"] = girth
    # indicative comparison of two ANSUR girths with the mesh's TRUE section perimeters (the unconformed mesh; the equivalent circle is given beside each)
    sp = profiles["shank"]
    ans = inp.ansur["circumferences_mm"]
    calf_band = (sp["z"] >= inp.ruler["calf"]["z_mm"] - 60) & (sp["z"] <= inp.ruler["calf"]["z_mm"] + 60)
    ank_band = (sp["z"] >= 60) & (sp["z"] <= 200)
    i = np.flatnonzero(calf_band)[np.argmax(sp["perimeter"][calf_band])]
    j = np.flatnonzero(ank_band)[np.argmin(sp["perimeter"][ank_band])]
    out["girth_vs_ansur"] = {
        "calf_maximum": {"mesh_true_perimeter_mm": float(sp["perimeter"][i]), "mesh_equivalent_circle_mm": 2 * float(np.sqrt(np.pi * sp["area"][0.0][i])), "height_mm": float(sp["z"][i]),
                         "ansur_mean_mm": ans["calf_maximum"]["mean"], "ansur_sd_mm": ans["calf_maximum"]["sd"],
                         "z_score": (float(sp["perimeter"][i]) - ans["calf_maximum"]["mean"]) / ans["calf_maximum"]["sd"]},
        "ankle_minimum": {"mesh_true_perimeter_mm": float(sp["perimeter"][j]), "mesh_equivalent_circle_mm": 2 * float(np.sqrt(np.pi * sp["area"][0.0][j])), "height_mm": float(sp["z"][j]),
                          "ansur_mean_mm": ans["ankle_minimum"]["mean"], "ansur_sd_mm": ans["ankle_minimum"]["sd"],
                          "z_score": (float(sp["perimeter"][j]) - ans["ankle_minimum"]["mean"]) / ans["ankle_minimum"]["sd"]}}

    out["gates"] = gates
    outdir = p["out"]
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "leg_R_trial.json").write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    _print(out, gates, feats, inp, reg)
    return 0 if all(g["pass"] for g in gates) else 1


def _print(out, gates, feats, inp, reg):
    f = out["features"]
    print(f"mesh {out['mesh_file']}   voxel {out['voxel_mm']} mm   knee anchor: {reg.knee_source}")
    print(f"mesh stature {inp.stature_mesh:.1f} mm; crotch apex {f['crotch_apex_mm']:.1f}")
    print("KJC estimates (mm above sole): " + "; ".join(f"{k} {v:.1f}" if v is not None else f"{k} none" for k, v in f["kjc_estimates_mm"].items()) + f"; sheet {inp.sheet.kjc:.1f}")
    print("HJC estimates: " + "; ".join(f"{k} {v:.1f}" for k, v in f["hjc_estimates_mm"].items()) + f"; sheet {inp.sheet.hjc:.1f}")
    print("AJC estimates: " + "; ".join(f"{k} {v:.1f}" for k, v in f["ajc_estimates_mm"].items()) + f"; sheet {inp.sheet.ajc:.1f}")
    print("stretch by knee anchor: " + "; ".join(f"{k}: thigh {v['stretch']['thigh']:.4f} shank {v['stretch']['shank']:.4f}" for k, v in out["knee_variants"].items()))
    for g in gates:
        print(f"[{'PASS' if g['pass'] else 'FAIL'}] gate {g['gate']}\n        {g['detail']}")
    mb = out["mass_base"]
    for lab, c in mb["cases"].items():
        print(f"mass base {lab}: density {c['body_density_kg_per_l']:.4f} kg/l, M_mesh {c['mesh_mass_kg']:.2f} kg, sculpt BMI {c['sculpt_bmi_kg_per_m2']:.2f}, robot needs {c['robot_required_average_density_kg_per_l']:.3f} kg/l")
    for n, r in mb["segments"].items():
        print(f"  {n}: skin {r['skin_volume_l']:.3f} l, fraction {r['sheet_mass_fraction']:.4f}, implied density " + ", ".join(f"{k} {v['implied_density_kg_per_l']:.3f}" for k, v in r["cases"].items()) + f" (ref {r['reference_density_kg_per_l']})")
    for n, g in out["girth_check"].items():
        print(f"  girth {n}: loop {g['loop_length_mm']:.0f} mm, section {g['section_perimeter_mm']:.0f} mm ({g['difference_percent']:+.1f}%, flag {g['flag']}), equivalent circle {g['equivalent_circle_mm']:.0f}")
