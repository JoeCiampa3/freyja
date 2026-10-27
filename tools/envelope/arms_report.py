"""Products and report of the arm bodies (volume-extractor brief 8): the ledgers, silhouettes and cache of each body, the inspect layer, the closure with the arms built, the final share table,
the left-right comparison, the gates and the oracle examples. Pure assembly of what `arms.build_side` computed."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import arms, bodies, frames, ledger, oracle
from .arms import NAMES, SEG_KEY

EXAMPLES = {"upper_arm_cylinder": "upper_arm", "forearm_box": "forearm"}      # data/envelope/examples/<name>_shapes.yaml, <name>_feasible_poses.csv, <name>_infeasible_poses.csv
UNION_EXAMPLE = ("arm_union", ("upper_arm", "forearm"))                       # a rod across the elbow plane, in the upper arm frame


def header(name, S, inputs_sha, mesh_label) -> dict:
    """Header scalars of an arm body's ledger (the keys of the trunk bodies' headers where they apply)."""
    res, reg, d, z = S["results"][name], S["reg"], S["design"][name], S["zones"][name]
    seg, meta = res.seg, res.seg.meta
    n = {"upper_arm": ("sjc", "elbow"), "forearm": ("elbow", "wrist"), "hand": ("wrist", "fingertip")}[name]
    return {
        "segment": SEG_KEY[name],
        "frame": ("arm segment: origin at the proximal node (upper arm: the mesh's own SJC; forearm: the elbow; hand: the wrist), z up with the distal plane at z = -sheet length (the hand: its extent), x anterior, "
                  "y left; the segment is the mesh rotated rigidly about the origin onto this frame and stretched along z; stations are distances below the top of the field"),
        "stations": {"top_z_mm": meta["z_top_mm"], "joint_station_mm": meta["joint_station_mm"], "note": "the upper arm reaches above its SJC by the shoulder girdle: the SJC is at joint_station_mm"},
        "nodes": {"proximal": n[0], "distal": n[1]},
        "length_mm": round(seg.length, 2),
        "sheet_length_mm": round(reg["lengths_sheet_mm"][name], 3),
        "mesh_length_mm": round(reg["lengths_mesh_mm"].get(name, reg["hand"]["extent_along_forearm_axis_mm"]), 3),
        "stretch": round(S["frames"][name].k, 5), "stretch_gate": round(reg["gate"][name], 5) if name in reg["gate"] else None, "gate_rule": reg["gate_rule"],
        "angle_from_vertical_deg": round(reg["angle_from_vertical_deg"][name], 2),
        "mesh_nodes_mm": {k: [round(float(x), 2) for x in v] for k, v in reg["nodes_mesh_mm"].items()},
        "mesh_file": mesh_label, "voxel_mm": seg.h,
        "skin_volume_l": round(d["skin_volume_l"], 4), "unconformed_skin_volume_l": round(d["unconformed_skin_volume_l"], 4), "conform_volume_change_l": round(d["conform_volume_change_l"], 4),
        "inner_volume_l": {k: round(v, 4) for k, v in d["inner_volume_l"].items()},
        "sheet_mass_kg": round(d["sheet_mass_kg"], 4),
        "required_density_skin_kg_per_l": round(d["required_density_skin_kg_per_l"], 4),
        "required_density_inner_kg_per_l": {k: round(v, 4) for k, v in d["required_density_inner_kg_per_l"].items()},
        "min_inscribed_radius": d["min_inscribed_radius"], "min_inscribed_radius_inner": d["min_inscribed_radius_inner"],
        "pinch_stations": d["pinch_stations"], "pinch_prominence_mm": bodies.PINCH_PROMINENCE_MM,
        "joint_zone_volumes_l": {k: (round(v, 4) if isinstance(v, float) else {kk: round(vv, 4) for kk, vv in v.items()}) for k, v in z.items()},
        "directions": {str(a): nm for a, nm in ledger.direction_names("right").items()},
        "checks": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in res.checks.items()},
        "sections_csv": f"{SEG_KEY[name]}_sections.csv", "inputs_sha256_12": inputs_sha,
    }


def write_products(S, out, cache, inputs_sha, mesh_label) -> list:
    """Ledger YAML and CSV, silhouettes and the cache of each body of the side S (right)."""
    from . import plots
    names = []
    for n in NAMES:
        res = S["results"][n]
        hdr = header(n, S, inputs_sha, mesh_label)
        (out / f"{SEG_KEY[n]}.yaml").write_text(ledger.to_yaml(hdr, inputs_sha), encoding="utf-8", newline="\n")
        (out / f"{SEG_KEY[n]}_sections.csv").write_text(ledger.to_csv(S["rows"][n], inputs_sha), encoding="utf-8", newline="\n")
        title = f"right {n.replace('_', ' ')}, rigid rotation + axial stretch {hdr['stretch']:.4f}; rotated {hdr['angle_from_vertical_deg']:.1f} deg from vertical"
        for view in ("sagittal", "coronal"):
            plots.silhouette_png(res.seg, out / f"{SEG_KEY[n]}_{view}.png", view, ledger.SHELL_MM, f"{view}: {title}")
        res.seg.meta = {**res.seg.meta, "inputs_sha256_12": inputs_sha}
        res.seg.save(cache / f"{SEG_KEY[n]}.npz")
        names.append(SEG_KEY[n])
    return names


def inspect_layer(S, inp, outdir) -> str:
    """The arms' t = 5 mm envelopes, mapped back from their segment frames into the original mesh frame (the arms have no assembled conformed frame), as envelope_arms_t5.obj in the inspect
    bundle; registered in inspect.json under `arm_envelope`."""
    from . import bundle
    verts, faces, groups = [], [], []
    for n in NAMES:
        seg = S["results"][n].seg
        vals = np.where(seg.region, seg.sd.astype(float), -1.0e3)
        V, F = bundle.marching_tetrahedra(vals, seg.o + seg.h / 2, seg.h, bundle.SHELL_MM)
        Vm = S["frames"][n].inverse(V)
        groups.append((SEG_KEY[n], len(faces)))
        faces += [(f + len(verts)).tolist() for f in F]
        verts += bundle.to_mh_dm(Vm, inp).tolist()
    bundle.write_obj(Path(outdir) / "envelope_arms_t5.obj", np.array(verts), faces, groups)
    p = Path(outdir) / "inspect.json"
    if p.exists():
        j = json.loads(p.read_text(encoding="utf-8"))
        j["arm_envelope"] = {"file": "envelope_arms_t5.obj", "frame": "original mesh (the arms are not conformed into a common frame); groups " + ", ".join(SEG_KEY[n] for n in NAMES),
                             "nodes_original": {k: bundle.to_mh_dm(np.array(v)[None, :], inp)[0].tolist() for k, v in S["reg"]["nodes_mesh_mm"].items()}}
        p.write_text(json.dumps(j, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return "envelope_arms_t5.obj"


def closure(trunk_leg_built_l: dict, arm_built: dict, acc: dict, mesh_volume_l: float) -> dict:
    """Closure with the arms built: the sum of every conformed body (the trunk bodies as built, each leg segment and each arm segment twice for the two sides) against the mesh volume. There
    is no remainder. `arm_built` is {segment: {"conformed_l", "unconformed_l"}} for the right side (mirrored for the left). The conform effect is the legs' and trunk's (the accounting's)
    plus the arms' (built conformed minus unconformed)."""
    U = acc["volume_unconformed_l"]
    unbuilt = ("arms", "shoulder_R", "shoulder_L")
    parts = dict(trunk_leg_built_l)
    for n, d in arm_built.items():
        parts[f"{n}s"] = 2.0 * d["conformed_l"]
    total = sum(parts.values())
    diff = (total - mesh_volume_l) / mesh_volume_l
    arm_conform = 2.0 * sum(d["conformed_l"] - d["unconformed_l"] for d in arm_built.values())
    arm_raster = sum(U[c] for c in unbuilt)
    arm_built_unconf = 2.0 * sum(d["unconformed_l"] for d in arm_built.values())
    return {"built_l": parts, "remainder_l": {}, "sum_l": total, "mesh_volume_l": mesh_volume_l, "relative_difference": diff, "tolerance": bodies.CLOSURE_TOL,
            "within_tolerance": bool(abs(diff) <= bodies.CLOSURE_TOL), "raster_total_l": acc["raster_total_l"], "raster_minus_mesh_l": acc["raster_total_l"] - mesh_volume_l,
            "conform_effect_l": sum(acc["volume_l"][c] - U[c] for c in bodies.CLASSES if c not in unbuilt) + arm_conform, "conform_effect_arms_l": arm_conform,
            "arms_built_unconformed_l": arm_built_unconf, "arms_and_girdles_raster_l": arm_raster, "arms_built_minus_raster_l": arm_built_unconf - arm_raster,
            "share_denominator_l": total, "shares": {k: v / total for k, v in parts.items()}}


SHARE_ROLES = {"head_neck": "result", "thorax": "result", "forearms": "result", "hands": "result", "whole_arms": "result", "lumped_abdomen_to_thigh": "result", "shanks": "result", "feet": "result",
               "upper_arms": "diagnostic", "abdomen": "diagnostic", "pelvis": "diagnostic", "thighs": "diagnostic"}


def share_table(clo: dict, sheet_masses_kg: dict, total_mass_kg: float) -> dict:
    """The final share table on the sum-of-conformed-volumes denominator (brief 8 item 4): per row the conformed skin volume of the bodies (both sides where bilateral), the volume share, the
    sheet's mass and mass share (over the sheet's total, both sides), the raw ratio (mass share over volume share; primary) and the density the row's mass needs over its skin volume. Results:
    head and neck, thorax, forearm, hand, whole arm, the lumped abdomen-to-thigh region, shank, foot; diagnostics: the upper arm (its top cut is unknown), abdomen, pelvis, thigh."""
    b, den = clo["built_l"], clo["share_denominator_l"]
    vol = {k: b[k] for k in ("head_neck", "thorax", "abdomen", "pelvis", "thighs", "shanks", "upper_arms", "forearms", "hands")}
    vol["feet"] = b["foots"]                                       # the closure's key for the two feet
    vol["whole_arms"] = vol["upper_arms"] + vol["forearms"] + vol["hands"]
    vol["lumped_abdomen_to_thigh"] = vol["abdomen"] + vol["pelvis"] + vol["thighs"]
    m = dict(sheet_masses_kg)
    m["whole_arms"] = m["upper_arms"] + m["forearms"] + m["hands"]
    m["lumped_abdomen_to_thigh"] = m["abdomen"] + m["pelvis"] + m["thighs"]
    rows = {}
    for k in SHARE_ROLES:
        sv, sm = vol[k] / den, m[k] / total_mass_kg
        rows[k] = {"role": SHARE_ROLES[k], "volume_l": vol[k], "volume_share": sv, "sheet_mass_kg": m[k], "mass_share": sm, "raw_ratio": sm / sv, "required_density_kg_per_l": m[k] / vol[k]}
    return {"denominator_l": den, "denominator": "sum of the conformed segment volumes (closure.sum_l)", "sheet_total_mass_kg": total_mass_kg, "rows": rows,
            "note": "raw ratio = sheet mass share / sculpt volume share; the lumped row is the frame bodies abdomen + pelvis + both thighs (planes LJC, TJC and the KJC), not memo 33's MSR10 region"}


def left_right(R: dict, L: dict, acc: dict) -> dict:
    """The left arm built the same way against the right: conformed volumes per body and the difference, and the accounting's girdle volumes."""
    out = {"bodies": {}}
    for n in NAMES:
        r, l = R["design"][n]["skin_volume_l"], L["design"][n]["skin_volume_l"]
        out["bodies"][n] = {"right_l": r, "left_l": l, "left_minus_right_percent": (l - r) / r * 100.0}
    tr, tl = sum(R["design"][n]["skin_volume_l"] for n in NAMES), sum(L["design"][n]["skin_volume_l"] for n in NAMES)
    out["whole_arm"] = {"right_l": tr, "left_l": tl, "left_minus_right_percent": (tl - tr) / tr * 100.0}
    U = acc["volume_unconformed_l"]
    out["raster_girdle_l"] = {"right": U["shoulder_R"], "left": U["shoulder_L"], "left_minus_right_percent": (U["shoulder_L"] - U["shoulder_R"]) / U["shoulder_R"] * 100.0}
    out["left_stretch"] = L["reg"]["stretch"]
    return out


def example_gates(S: dict, root) -> tuple:
    """Gate 5 for the arms: a cylinder in the upper arm, a box in the forearm (a feasible and an infeasible placement each) and a rod across the elbow plane for the union query."""
    ex = Path(root) / "data/envelope/examples"
    res = S["results"]
    gates, out = [], {}
    for ex_name, body in EXAMPLES.items():
        try:
            shapes = oracle.read_shapes(ex / f"{ex_name}_shapes.yaml")
            feas = oracle.clearance(res[body].seg, shapes, oracle.read_poses(ex / f"{ex_name}_feasible_poses.csv"))
            infe = oracle.clearance(res[body].seg, shapes, oracle.read_poses(ex / f"{ex_name}_infeasible_poses.csv"))
        except FileNotFoundError:
            gates.append({"gate": f"5 oracle example {ex_name}", "pass": False, "detail": f"data/envelope/examples/{ex_name}_* is missing"})
            continue
        gates.append({"gate": f"5 oracle example {ex_name}: in the {SEG_KEY[body]}, feasible and infeasible", "pass": bool(feas["feasible"] and not infe["feasible"]),
                      "detail": f"feasible: margin {feas['margin_mm']:.2f} mm at station {feas['station_mm']:.1f} mm; infeasible: margin {infe['margin_mm']:.2f} mm at station {infe['station_mm']:.1f} mm (pose {infe['pose_index']})"})
        out[ex_name] = {k: {kk: v[kk] for kk in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible", "slab_overrun_mm")} for k, v in (("feasible", feas), ("infeasible", infe))}
    name, names = UNION_EXAMPLE
    try:
        shapes = oracle.read_shapes(ex / f"{name}_shapes.yaml")
        o0 = np.array(res[names[0]].origin_xyz)
        parts = [(res[n].seg, np.array(res[n].origin_xyz) - o0) for n in names]
        pf, pi = oracle.read_poses(ex / f"{name}_feasible_poses.csv"), oracle.read_poses(ex / f"{name}_infeasible_poses.csv")
        feas, infe = oracle.clearance_union(parts, shapes, pf), oracle.clearance_union(parts, shapes, pi)
        single = oracle.clearance(res[names[0]].seg, shapes, pf)
        gates.append({"gate": f"5 oracle union query {name}: rod across the elbow plane, feasible and infeasible", "pass": bool(feas["feasible"] and not infe["feasible"] and not single["feasible"]),
                      "detail": f"feasible in the union: margin {feas['margin_mm']:.2f} mm (the upper arm alone overruns its slab by {single['slab_overrun_mm']:.1f} mm); infeasible: margin {infe['margin_mm']:.2f} mm, overrun {infe['slab_overrun_mm']:.1f} mm"})
        out[name] = {"feasible": {k: feas[k] for k in ("margin_mm", "slab_overrun_mm", "feasible")}, "infeasible": {k: infe[k] for k in ("margin_mm", "slab_overrun_mm", "feasible")},
                     "single_body_overrun_mm": single["slab_overrun_mm"]}
    except FileNotFoundError:
        gates.append({"gate": f"5 oracle union query {name}", "pass": False, "detail": f"data/envelope/examples/{name}_* is missing"})
    return gates, out


def gate_rows(R: dict, clo: dict, topo) -> list:
    """Gates of brief 8 for the arms: topology and watertightness per body, the stretch against its own gate, and the field volume against the raster accounting of both arms (the closure gate 7 is `bodies.gate_rows`'s, on the closure with the arms)."""
    g = lambda name, ok, detail: {"gate": name, "pass": bool(ok), "detail": detail}
    out = []
    for n in NAMES:
        c = R["results"][n].checks
        ok = topo is None and c["boundary_edges_near_segment"] == 0 and c["nonmanifold_edges_near_segment"] == 0 and c["odd_parity_columns"] == 0 and c["seed_inside_region"]
        out.append(g(f"1 {SEG_KEY[n]}: topology matches base; surface watertight", ok, f"topology vs base.obj: {topo or 'identical'}; boundary edges near the body {c['boundary_edges_near_segment']} "
                                                                                  f"(whole body {c['boundary_edges_whole_body']}); non-manifold {c['nonmanifold_edges_near_segment']}; odd-parity columns {c['odd_parity_columns']}"))
    reg = R["reg"]
    out.append(g("2 arms: |stretch-1| within 2 x 17.3 mm / sheet length per segment", not reg["exceeding_gate"],
                 "; ".join(f"{n} {reg['stretch'][n]:.4f} ({(reg['stretch'][n] - 1) * 100:+.2f}%, gate +-{reg['gate'][n] * 100:.2f}%)" for n in ("upper_arm", "forearm")) + "; hand 1.0000 (no stretch)"))
    both, ras = clo["arms_built_unconformed_l"], clo["arms_and_girdles_raster_l"]
    out.append(g("3b arms: field volume (unconformed, both sides) within 1% of the raster accounting of arms and girdles", abs(both - ras) / ras < bodies.FIELD_VS_RASTER_TOL,
                 f"field {both:.4f} l, raster {ras:.4f} l ({(both - ras) / ras * 100:+.3f}%)"))
    return out


def result(S, L, clo, shares, lr, ansur, gates, examples, inputs_sha) -> dict:
    """The committed result `arm_bodies.json`."""
    reg = S["reg"]
    return {"generated_by": "fy envelope gates", "schema": "arm-bodies/1", "inputs": f"mesh, snapshot, ANSUR II ratios (inputs sha256:{inputs_sha})", "side": "right (the left is built for the comparison only)",
            "registration": {k: reg[k] for k in ("nodes_mesh_mm", "lengths_mesh_mm", "lengths_sheet_mm", "stretch", "gate", "gate_rule", "sigma_mm", "angle_from_vertical_deg", "elbow_bend_deg", "wrist_bend_deg",
                                                 "vertex_ids", "mirror_gap_mm", "hand", "node_skin_distance")},
            "ansur_cross_check": ansur, "design": S["design"], "joint_zone_volumes_l": S["zones"], "hand": S["hand"], "interface_sections": S["interfaces"],
            "closure": clo, "share_table": shares, "left_right": lr, "oracle_examples": examples}
