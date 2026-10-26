"""The report of the trunk bodies (volume-extractor brief 5): the oracle examples, the assembled result and its gates. Pure assembly of what `bodies.build` computed."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import bodies, masses, oracle, trunk
from .bodies import BODIES

EXAMPLES = {"pelvis_box": "pelvis", "thorax_box": "thorax"}       # worked examples in data/envelope/examples: <name>_shapes.yaml, <name>_feasible_poses.csv, <name>_infeasible_poses.csv
UNION_EXAMPLE = ("trunk_union", ("pelvis", "abdomen"))            # a rod across the LJC plane, in the pelvis frame


def example_gates(tb: bodies.TrunkBuild, root) -> tuple:
    """Gate 5 for the new bodies: a box in the pelvis and one in the thorax, a feasible and an infeasible placement each, and a rod across the LJC plane for the union query."""
    ex = Path(root) / "data/envelope/examples"
    gates, out = [], {}
    for ex_name, body in EXAMPLES.items():
        try:
            shapes = oracle.read_shapes(ex / f"{ex_name}_shapes.yaml")
            feas = oracle.clearance(tb.results[body].seg, shapes, oracle.read_poses(ex / f"{ex_name}_feasible_poses.csv"))
            infe = oracle.clearance(tb.results[body].seg, shapes, oracle.read_poses(ex / f"{ex_name}_infeasible_poses.csv"))
        except FileNotFoundError:
            gates.append({"gate": f"5 oracle example {ex_name}", "pass": False, "detail": f"data/envelope/examples/{ex_name}_* is missing"})
            continue
        gates.append({"gate": f"5 oracle example {ex_name}: box in the {body}, feasible and infeasible", "pass": bool(feas["feasible"] and not infe["feasible"]),
                      "detail": f"feasible: margin {feas['margin_mm']:.2f} mm at station {feas['station_mm']:.1f} mm; infeasible: margin {infe['margin_mm']:.2f} mm at station {infe['station_mm']:.1f} mm (pose {infe['pose_index']})"})
        out[ex_name] = {k: {kk: v[kk] for kk in ("margin_mm", "station_mm", "pose_index", "point_mm", "feasible", "slab_overrun_mm")} for k, v in (("feasible", feas), ("infeasible", infe))}
    name, names = UNION_EXAMPLE
    try:
        shapes = oracle.read_shapes(ex / f"{name}_shapes.yaml")
        o0 = np.array(tb.results[names[0]].origin_xyz)
        parts = [(tb.results[n].seg, np.array(tb.results[n].origin_xyz) - o0) for n in names]
        pf, pi = oracle.read_poses(ex / f"{name}_feasible_poses.csv"), oracle.read_poses(ex / f"{name}_infeasible_poses.csv")
        feas, infe = oracle.clearance_union(parts, shapes, pf), oracle.clearance_union(parts, shapes, pi)
        single = oracle.clearance(tb.results[names[0]].seg, shapes, pf)
        gates.append({"gate": f"5 oracle union query {name}: rod across the {names[0]}-{names[1]} plane, feasible and infeasible", "pass": bool(feas["feasible"] and not infe["feasible"] and not single["feasible"]),
                      "detail": f"feasible in the union: margin {feas['margin_mm']:.2f} mm (the {names[0]} alone overruns its slab by {single['slab_overrun_mm']:.1f} mm); infeasible: margin {infe['margin_mm']:.2f} mm, overrun {infe['slab_overrun_mm']:.1f} mm"})
        out[name] = {"feasible": {k: feas[k] for k in ("margin_mm", "slab_overrun_mm", "feasible")}, "infeasible": {k: infe[k] for k in ("margin_mm", "slab_overrun_mm", "feasible")},
                     "single_body_overrun_mm": single["slab_overrun_mm"]}
    except FileNotFoundError:
        gates.append({"gate": f"5 oracle union query {name}", "pass": False, "detail": f"data/envelope/examples/{name}_* is missing"})
    return gates, out


def whole_body_density(total_mass_kg: float, mesh_volume_l: float, v_lung_l: float) -> dict:
    """The whole-body average density the sheet's total mass needs, on two bases (brief 6, item 0c): over the whole mesh volume (the robot has no lungs: the comparator for a packaging
    density) and over the mesh volume less the lung gas (the tissue basis of memo 32)."""
    return {"sheet_total_mass_kg": total_mass_kg, "mesh_volume_l": mesh_volume_l, "v_lung_l": v_lung_l, "robot_kg_per_l": total_mass_kg / mesh_volume_l,
            "tissue_kg_per_l": total_mass_kg / (mesh_volume_l - v_lung_l),
            "comparator": "robot_kg_per_l (sheet total mass over the mesh volume) is the comparator for a packaging density; tissue_kg_per_l is the same mass over the volume less the lung gas"}


def report(tb: bodies.TrunkBuild, leg_results: dict, mesh_volume_l: float, topo, root, inputs_sha: str) -> tuple:
    """(result dict, gates) of the trunk bodies: design numbers, the pair, zones, shoulders, closure, shares, the arm rule's cross-check and the gates."""
    built = {n: tb.design[n]["skin_volume_l"] for n in BODIES}
    for n in ("thigh", "shank", "foot"):
        built[f"{n}s"] = 2.0 * leg_results[n].seg.volume(0.0) / 1e6         # the right segment, twice (the left is its mirror in the mesh to under 0.5% in area)
    clo = bodies.closure(built, tb.acc, mesh_volume_l)
    gates = bodies.gate_rows(tb, topo, mesh_volume_l, clo)
    eg, ex = example_gates(tb, root)
    gates += eg
    zt = bodies.zone_table(tb.acc)
    sph = tb.acc["spheres"]
    shoulder = {"plane": {"lateral_mm": tb.sjc["lateral_mm"], "below_cjc_mm": tb.sjc["below_cjc_mm"], "ahead_of_cjc_mm": tb.sjc["ahead_of_cjc_mm"], "x_mesh_mm": sph["centre_x_mesh_mm"],
                          "source": tb.sjc["source"], "dumas2015_cross_check": tb.sjc["dumas2015"], "sheet_minus_dumas_mm": tb.sjc["sheet_minus_dumas_mm"],
                          "x_note": "the sheet's x offset (ahead of the CJC) added to the mesh thorax's centre line at the CJC plane (cjc_x_mesh_mm)",
                          "cjc_x_mesh_mm": sph["cjc_x_mesh_mm"], "thorax_mean_x_at_sphere_height_mesh_mm": sph["centre_x_thorax_mean_mesh_mm"],
                          "x_sheet_minus_previous_rule_mm": sph["centre_x_mesh_mm"] - sph["centre_x_thorax_mean_mesh_mm"]},
                "sphere_radius_mm": sph["radius_mm"], "centre_height_mm": sph["centre_height_mm"],
                "thorax_with_zone_l": tb.acc["volume_l"]["thorax"],
                "thorax_without_zone_l": tb.acc["volume_l"]["thorax"] - zt["thorax"]["shoulder_spheres_in_thorax_l"],
                "thorax_in_spheres_l": zt["thorax"]["shoulder_spheres_in_thorax_l"],
                "shoulder_girdle_assigned_to_the_arm_side_l": {"right": tb.acc["volume_l"]["shoulder_R"], "left": tb.acc["volume_l"]["shoulder_L"]},
                "spheres": sph["sides"], "axilla": tb.axilla,
                "arm_labelled_cells_above_axilla_inside_the_planes_l": tb.acc["arm_labelled_above_axilla_inside_shoulder_planes_l"],
                "leaked_arm_cells_reclassified_below_axilla_l": tb.acc["leaked_arm_cells_reclassified_l"]}
    res = {
        "generated_by": "fy envelope gates", "inputs": f"mesh, snapshot, ANSUR II ratios, Dumas 2015 Table 1 (inputs sha256:{inputs_sha})", "schema": "trunk-bodies/1",
        "cjc_anchor": trunk.PRIMARY_CANDIDATE, "map": trunk.PRIMARY_MODE, "mesh_nodes_mm": dict(zip(("hjc", "tjc", "cjc", "vertex"), tb.tm.mesh)), "sheet_nodes_mm": tb.sheet,
        "neck_plane_mm": tb.neck_mm, "zone_h_mm": bodies.ZONE_H_MM,
        "whole_body_density": whole_body_density(leg_results["thigh"].reg.sheet.total_mass_kg, mesh_volume_l, masses.load_constants(Path(root))["v_lung_l"]),
        "design": tb.design, "pair_abdomen_pelvis": bodies.pair_numbers(tb.design["abdomen"], tb.design["pelvis"]),
        "pinch_prominence_mm": bodies.PINCH_PROMINENCE_MM, "free_end_mm": bodies.FREE_END_MM,
        "zones": zt, "zone_planes_raw_l": tb.acc["zones"], "shoulder": shoulder,
        "accounting_l": {"conformed": tb.acc["volume_l"], "unconformed": tb.acc["volume_unconformed_l"], "raster_total": tb.acc["raster_total_l"]},
        "closure": clo, "arm_rule_cross_check": tb.arm_method,
        "matched_areas": tb.matched, "field_vs_raster_l": {n: {"field": tb.design[n]["skin_volume_l"], "raster": tb.acc["volume_l"][n]} for n in BODIES},
        "oracle_examples": ex,
    }
    return res, gates


def format_summary(res: dict) -> str:
    L = ["trunk bodies (CJC anchor " + res["cjc_anchor"] + ", map " + res["map"] + "):"]
    for n, d in res["design"].items():
        r = d["min_inscribed_radius"]
        L.append(f"  {n}: skin {d['skin_volume_l']:.3f} l, inner t5 {d['inner_volume_l']['t5']:.3f} l, sheet {d['sheet_mass_kg']:.3f} kg -> {d['required_density_skin_kg_per_l']:.3f} kg/l over the skin, "
                 f"{d['required_density_inner_kg_per_l']['t5']:.3f} over t5; min r {r['r_mm']:.1f} mm at station {r['station_mm']:.0f}; pinch " + (", ".join(f"{p['station_mm']:.0f} ({p['r_mm']:.1f} mm)" for p in d["pinch_stations"]) or "none"))
    p = res["pair_abdomen_pelvis"]
    L.append(f"  abdomen + pelvis: skin {p['skin_volume_l']:.3f} l, sheet {p['sheet_mass_kg']:.3f} kg -> {p['required_density_skin_kg_per_l']:.3f} kg/l over the skin, {p['required_density_inner_kg_per_l']['t5']:.3f} over t5")
    w = res["whole_body_density"]
    L.append(f"  whole body: sheet {w['sheet_total_mass_kg']:.3f} kg over the mesh {w['mesh_volume_l']:.3f} l = {w['robot_kg_per_l']:.3f} kg/l (robot basis, the packaging comparator), "
             f"over the mesh less {w['v_lung_l']:.3f} l of lung gas = {w['tissue_kg_per_l']:.3f} kg/l (tissue basis)")
    c = res["closure"]
    L.append(f"  closure: {c['sum_l']:.4f} l against {c['mesh_volume_l']:.4f} l ({c['relative_difference'] * 100:+.3f}%); shares sum to {sum(c['shares'].values()):.6f}")
    return "\n".join(L)
