"""Checks of the exported v2 body against the rebuild, and the attribution of its volume change from v1 (volume-extractor brief 4, items 1, 2 and 9).

    python analysis/makehuman_v2_check.py --targets data/makehuman/cache/targets [--out data/envelope/v2_check.json]

1. Gate 1 on v2: the committed `freyja-body-v2.obj` against base.obj plus the weighted targets of `freyja-body-v2.mhm` (the rule of
   `analysis/makehuman_attribution.py`), per region (legs, torso, arms, head) after removing the exporter's translation.
2. The whole-body volume of v1 posed (the committed OBJ), v1 at rest (rebuilt) and v2, and the split of v2 - v1 into the pose effect (posed -> rest) and the
   slider effect (rest -> v2) by region, from `tools/envelope/decompose.py`. The slider effect is also split into the Height change alone and the two
   leg-height measures (exact volumes only).
3. The Ruler readouts and girth-loop heights of the committed v2 OBJ against `data/envelope/v2_prediction.json` (memo 31).

Everything written is deterministic and carries no absolute path or timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "tools"))
import makehuman_attribution as A  # noqa: E402
import makehuman_v2 as M  # noqa: E402
from envelope import cuts, decompose, features, masses, meshio, trial  # noqa: E402

V1_OBJ = REPO / "data/makehuman/freyja-body-v1.obj"
V2_OBJ = REPO / "data/makehuman/freyja-body-v2.obj"
V2_PREDICTION = REPO / "data/envelope/v2_prediction.json"
RASTER_MM = 2.0
FLAG_MM = 0.1                  # the brief: flag any deviation over 0.1 mm
STOP_MM = 1.0                  # the brief: stop and ask when the whole-body deviation from the rebuild exceeds 1 mm anywhere
UNEXPLAINED_STOP_L = 0.3       # the brief: stop and ask when more than this much of the v2 - v1 change is unexplained


def write_obj(path, V_dm, polys):
    lines = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in V_dm] + ["f " + " ".join(str(i + 1) for i in q) for q in polys]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def planes_and_profile(path, root=REPO, table=None):
    """(inputs, region planes in the mesh frame, profile, vertices in the mesh frame, raster) for the body OBJ at `path`."""
    inp = trial.load_inputs(root, path)
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    sh = inp.sheet
    ljc_m = reg.mesh_nodes["hjc"] + (sh.ljc - sh.hjc)
    dh = cuts.dumas_cut_heights(table or masses.load_dumas_table1(root), sh.abdomen_length_mm, ljc_m)
    raster = features.BodyRaster(inp.V, inp.F, inp.stature_mesh + 10.0, h=RASTER_MM)
    prof = decompose.profile(raster)
    planes = {"ajc": reg.mesh_nodes["ajc"], "kjc": reg.mesh_nodes["kjc"], "apex": feats["crotch_apex_mm"], "msr10": dh["MSR10"]}
    planes["neck"] = decompose.neck_height(prof, inp.stature_mesh)
    return inp, planes, prof, raster, dh, reg


def gate1(rebuilt_dm, obj_dm, inp, planes, raster) -> dict:
    d = obj_dm - rebuilt_dm
    off = d.mean(axis=0)
    dev = np.linalg.norm(d - off, axis=1) * A.DM_TO_MM
    # the regions are named on the loaded mesh (sheet axes, sole at 0), whose vertex order is the OBJ's
    names = np.array(decompose.vertex_regions(inp.V, raster, planes))
    out = {"export_translation_dm": [float(x) for x in off], "whole_body": {"vertices": int(len(dev)), "max_mm": float(dev.max()), "mean_mm": float(dev.mean())}, "regions": {}}
    for r in ("legs", "torso", "arms", "head"):
        m = names == r
        out["regions"][r] = {"vertices": int(m.sum()), "max_mm": float(dev[m].max()), "mean_mm": float(dev[m].mean()), "over_flag": int((dev[m] > FLAG_MM).sum())}
    out["flag_mm"] = FLAG_MM
    out["stop_mm"] = STOP_MM
    return out


def run(targets_dir, root=REPO) -> dict:
    base = A.read_obj_vertices(root / "data/makehuman/base.obj")
    T = A.Targets(targets_dir)
    v1_mhm = A.read_mhm(M.V1_MHM)
    v2_mhm = A.read_mhm_text(M.v2_mhm_text(M.V1_MHM.read_text()))
    n = A.BODY_VERTICES
    rest1 = T.mesh(base, v1_mhm)[:n]
    rest2 = T.mesh(base, v2_mhm)[:n]
    posed1 = A.read_obj_vertices(V1_OBJ)
    obj2 = A.read_obj_vertices(V2_OBJ)
    _, polys = meshio.read_obj(V1_OBJ)
    table = masses.load_dumas_table1(root)
    out = {"inputs": {"base_obj_sha256_12": hashlib.sha256((root / "data/makehuman/base.obj").read_bytes()).hexdigest()[:12],
                      "v2_obj_sha256_12": hashlib.sha256(V2_OBJ.read_bytes()).hexdigest()[:12], "v1_obj_sha256_12": hashlib.sha256(V1_OBJ.read_bytes()).hexdigest()[:12],
                      "raster_mm": RASTER_MM, "leg_y_max_mm": decompose.LEG_Y_MM_MAX, "dumas_table1": masses.DUMAS_TABLE1_PATH}}
    out["topology_v2_vs_base"] = meshio.topology_difference(V2_OBJ, root / "data/makehuman/base.obj") or "identical"

    # exact volumes, litres (mm coordinates)
    vol = lambda V_dm: masses.mesh_volume_l(V_dm * A.DM_TO_MM, np.array([q for p in polys for q in [(p[0], p[i], p[i + 1]) for i in range(1, len(p) - 1)]]))
    height_only = dict(v1_mhm)
    height_only[M.HEIGHT] = M.V2_CHANGES[M.HEIGHT]
    legs_only = dict(v1_mhm)
    legs_only.update({M.UPPER: M.V2_CHANGES[M.UPPER], M.LOWER: M.V2_CHANGES[M.LOWER]})
    exact = {"v1_posed (committed OBJ)": vol(posed1), "v1_rest (rebuilt)": vol(rest1), "v2 (committed OBJ)": vol(obj2), "v2 (rebuilt)": vol(rest2),
             "v1_rest + Height only (rebuilt)": vol(T.mesh(base, height_only)[:n]), "v1_rest + leg-height measures only (rebuilt)": vol(T.mesh(base, legs_only)[:n])}
    consts = masses.load_constants(root)
    blender_v2 = consts["blender_volume_v2_m3"] * 1000.0
    blender_v1 = consts["blender_volume_m3"] * 1000.0
    out["exact_volumes_l"] = exact
    out["gate6_v2"] = {"computed_l": exact["v2 (committed OBJ)"], "blender_l": blender_v2, "relative_difference": (exact["v2 (committed OBJ)"] - blender_v2) / blender_v2,
                       "tolerance": masses.BLENDER_TOLERANCE}
    out["blender_change"] = {"v1_l": blender_v1, "v2_l": blender_v2, "delta_l": blender_v2 - blender_v1, "delta_percent": (blender_v2 / blender_v1 - 1) * 100}

    with tempfile.TemporaryDirectory() as td:
        rest1_path = Path(td) / "v1_rest.obj"
        write_obj(rest1_path, rest1, polys)
        rest2_path = Path(td) / "v2_rebuilt.obj"
        write_obj(rest2_path, rest2, polys)
        # v2 first: its arms hang free, so its layers separate them, and the arm label found there is carried to the other two meshes by vertex index
        meshes = {"v2": V2_OBJ, "v1_rest": rest1_path, "v1_posed": V1_OBJ}
        regs, planes_by, totals = {}, {}, {}
        gate = None
        arm_mask = None
        for label, path in meshes.items():
            inp, planes, prof, raster, dh, reg = planes_and_profile(path, root, table)
            if arm_mask is None:
                names = np.array(decompose.vertex_regions(inp.V, raster, planes))
                arm_mask = names == "arms"
                out["arm_vertices"] = int(arm_mask.sum())
            regs[label] = {k: v / 1e6 for k, v in decompose.region_volumes(decompose.labelled_profile(raster, inp.V, arm_mask), planes).items()}
            totals[label] = decompose.total_volume(prof) / 1e6
            planes_by[label] = {k: float(v) for k, v in planes.items()}
            planes_by[label]["stature"] = float(inp.stature_mesh)
            planes_by[label]["dumas_RI"] = float(dh["RI"])
            planes_by[label]["dumas_MSR10"] = float(dh["MSR10"])
            if label == "v2":
                gate = gate1(rest2, obj2, inp, planes, raster)
        out["gate1_v2_vs_rebuild"] = gate
    out["planes_mesh_mm"] = planes_by
    out["regions_l"] = regs
    out["raster_total_l"] = totals
    exact_key = {"v1_posed": "v1_posed (committed OBJ)", "v1_rest": "v1_rest (rebuilt)", "v2": "v2 (committed OBJ)"}
    out["raster_minus_exact_l"] = {k: totals[k] - exact[exact_key[k]] for k in totals}

    def delta(a, b):
        return {r: regs[b][r] - regs[a][r] for r in decompose.REGIONS}

    pose, slider, total = delta("v1_posed", "v1_rest"), delta("v1_rest", "v2"), delta("v1_posed", "v2")
    d_exact = exact["v2 (committed OBJ)"] - exact["v1_posed (committed OBJ)"]
    out["decomposition_l"] = {
        "pose_effect (v1 posed -> v1 rest)": pose, "slider_effect (v1 rest -> v2)": slider, "total (v1 posed -> v2)": total,
        "sum_by_region": {"pose": sum(pose.values()), "slider": sum(slider.values()), "total": sum(total.values())},
        "exact": {"pose": exact["v1_rest (rebuilt)"] - exact["v1_posed (committed OBJ)"], "slider": exact["v2 (committed OBJ)"] - exact["v1_rest (rebuilt)"], "total": d_exact,
                  "height_only": exact["v1_rest + Height only (rebuilt)"] - exact["v1_rest (rebuilt)"],
                  "leg_measures_only": exact["v1_rest + leg-height measures only (rebuilt)"] - exact["v1_rest (rebuilt)"]},
        "unexplained_l": d_exact - sum(total.values()), "unexplained_stop_l": UNEXPLAINED_STOP_L}

    # item 9: the Ruler readouts and loop heights of the committed v2 OBJ against the memo-31 prediction
    measures = json.loads((root / "data/makehuman/ruler_measures.json").read_text())["measures"]
    pred = json.loads(V2_PREDICTION.read_text())
    key = "v2 predicted (rest, unposed)"
    got = M.readouts(np.vstack([obj2, base[n:]]), measures)
    out["ruler_readouts_cm"] = {k: {"v2_obj": got[k], "predicted": pred["rows"][key][k], "difference": got[k] - pred["rows"][key][k]} for k in sorted(pred["rows"][key])}
    loops = M.loop_heights_mm(np.vstack([obj2, base[n:]]), measures)
    out["girth_loops"] = {k: {"v2_obj": loops[k], "predicted": pred["girth_loops"][key][k]} for k in sorted(loops)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", default=str(REPO / "data/envelope/v2_check.json"))
    a = ap.parse_args(argv)
    res = run(a.targets)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    g = res["gate1_v2_vs_rebuild"]
    print(f"gate 1: topology {res['topology_v2_vs_base']}; whole body max {g['whole_body']['max_mm']:.4f} mm mean {g['whole_body']['mean_mm']:.4f} mm")
    for r, x in g["regions"].items():
        print(f"  {r}: {x['vertices']} vertices, max {x['max_mm']:.4f} mm, mean {x['mean_mm']:.4f} mm, over {FLAG_MM} mm: {x['over_flag']}")
    print("gate 6 (v2):", res["gate6_v2"])
    d = res["decomposition_l"]
    print("exact:", d["exact"], "unexplained", d["unexplained_l"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
