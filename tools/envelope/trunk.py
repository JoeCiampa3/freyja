"""Trunk registration (volume-extractor brief 5, item 1): the sheet's trunk nodes against the mesh, the candidates for the mesh CJC, and the axial stretch each
sub-segment (pelvis, abdomen, thorax, head and neck) would need.

Sheet nodes, heights above the floor in the zero pose: HJC (the registration's), LJC = HJC + the sheet's LJC offset, TJC = LJC + abdomen length, CJC = TJC + thorax
length, vertex = CJC + head-and-neck length. The mesh has measured nodes at the HJC (the registration's) and at its top (the stature). The CJC is measured from a
landmark: the candidates differ in the landmark, each placed by its Dumas 2015 Table 1 offset to the CJC (scaled to the sheet's thorax). Where LJC and TJC sit in the mesh is
a choice of the map and is reported both ways: `slope1` (the map of the mass cuts of memo 32: slope 1 above the HJC node, so the pelvis and abdomen are not stretched) and
`uniform` (HJC to CJC stretched evenly).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import anthro, decompose, features, masses, register, trial

NAPE_VERTEX_ID = 1491                       # MakeHuman Ruler: the end of the neck-height chord and of the nape-to-waist chord (brief 5)
MODES = ("slope1", "uniform")
SUBSEGMENTS = ("pelvis", "abdomen", "thorax", "head_neck")
PAIRS = {"pelvis": ("hjc", "ljc"), "abdomen": ("ljc", "tjc"), "thorax": ("tjc", "cjc"), "head_neck": ("cjc", "vertex")}
PRIMARY_CANDIDATE = "nape_c7"               # the brief's anchor: the nape vertex as a C7 proxy
PRIMARY_MODE = "slope1"                     # the mass cuts' existing map
MC_N = 200                                  # Monte Carlo samples (the brief's N)
MC_SEED = 0
RASTER_MM = 2.0                             # whole-body raster for the neck plane (memo 32)
RESULT_PATH = "data/envelope/trunk_registration.json"
SD_CONVENTION = ("the ANSUR II female SD of the landmark's height ratio times the mesh stature, centred on the candidate (the convention of the leg anchors, memo 29); the "
                 "HJC takes the registration's SD; the vertex is the mesh's top and has none")


def sheet_nodes(sh) -> dict:
    """Heights (mm above the floor) of the sheet's trunk nodes in the zero pose."""
    tjc = sh.ljc + sh.abdomen_length_mm
    cjc = tjc + sh.thorax_length_mm
    return {"hjc": sh.hjc, "ljc": sh.ljc, "tjc": tjc, "cjc": cjc, "vertex": cjc + sh.head_neck_length_mm}


def standing_head_top(sh, root: Path) -> dict:
    """The zero-pose chain's top of head against the stature, and the pelvis non-verticality that explains the difference (ADR 0038: the stature stack is closed on vertical
    heights at the design tilt, the zero pose has the pelvis upright)."""
    snap = register.sheet.read_snapshot(root / "params/snapshot.csv")
    tilt = snap["stand_pelvis_tilt_deg"]
    x, y = snap["source_landmark_hjc_dumas_isb_x"] * 1000.0, abs(snap["source_landmark_hjc_dumas_isb_y"]) * 1000.0
    v_ref = x * np.sin(np.radians(tilt)) + y * np.cos(np.radians(tilt))
    n = sheet_nodes(sh)
    drop = sh.k_pelvis * v_ref
    return {"tilt_deg": tilt, "zero_pose_vertex_mm": n["vertex"], "stature_mm": sh.stature_mm, "shortfall_mm": sh.stature_mm - n["vertex"],
            "dumas_hjc_below_ljc_ref_mm": y, "dumas_hjc_ahead_of_ljc_ref_mm": x, "vertical_drop_at_tilt_mm": float(drop), "zero_pose_drop_mm": sh.ljc - sh.hjc,
            "note": "shortfall = vertical drop LJC to HJC at the design tilt minus the same drop in the zero pose (pelvis upright), both in the sheet's frame"}


def c7_above_cjc_mm(table: dict, sh) -> float:
    """Dumas 2015 Table 1 C7, Y (up) in the thorax frame (origin CJC), scaled by the sheet's thorax length over the reference's."""
    s = sh.thorax_length_mm / float(table["reference_length_mm"]["thorax"])
    return float(table["segments"]["thorax"]["landmarks"]["C7"][1]) * s


def sup_below_cjc_mm(table: dict, sh) -> float:
    """Dumas 2015 Table 1 SUP (the sternal notch), how far below the CJC, scaled the same way."""
    s = sh.thorax_length_mm / float(table["reference_length_mm"]["thorax"])
    return -float(table["segments"]["thorax"]["landmarks"]["SUP"][1]) * s


def mesh_nodes(sheet: dict, hjc_m, cjc_m, top_m, mode: str) -> dict:
    """Mesh heights of the trunk nodes (mm above the sole). hjc, cjc and the vertex are measured; ljc and tjc follow from the mode."""
    if mode not in MODES:
        raise ValueError(f"mode {mode!r}: choose from {MODES}")
    f = 1.0 if mode == "slope1" else (cjc_m - hjc_m) / (sheet["cjc"] - sheet["hjc"])
    return {"hjc": hjc_m, "ljc": hjc_m + f * (sheet["ljc"] - sheet["hjc"]), "tjc": hjc_m + f * (sheet["tjc"] - sheet["hjc"]), "cjc": cjc_m, "vertex": top_m}


def stretches(sheet: dict, mesh: dict) -> dict:
    """Sheet span over mesh span for each sub-segment: the factor the conform applies to the mesh's heights there."""
    return {k: (sheet[b] - sheet[a]) / (mesh[b] - mesh[a]) for k, (a, b) in PAIRS.items()}


def exceeding(stretch: dict) -> list:
    """Sub-segments whose stretch is more than the registration's 8% from 1 (the gate of the legs; the brief stops and asks for the thorax or head)."""
    return [k for k in SUBSEGMENTS if abs(stretch[k] - 1.0) > register.MAX_STRETCH_DEVIATION]


def monte_carlo(sheet: dict, hjc_m, cjc_m, top_m, sd_hjc, sd_cjc, mode, n=MC_N, seed=MC_SEED) -> dict:
    """Stretch per sub-segment under normal uncertainty in the mesh HJC and CJC heights (independent); the top is fixed."""
    rng = np.random.default_rng(seed)
    hjc = hjc_m + sd_hjc * rng.standard_normal(n)
    cjc = cjc_m + sd_cjc * rng.standard_normal(n)
    runs = [stretches(sheet, mesh_nodes(sheet, h, c, top_m, mode)) for h, c in zip(hjc, cjc)]
    out = {"n": n, "seed": seed}
    for k in SUBSEGMENTS:
        v = np.array([r[k] for r in runs])
        out[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)), "p2_5": float(np.percentile(v, 2.5)), "p97_5": float(np.percentile(v, 97.5)),
                  "fraction_beyond_8_percent": float((np.abs(v - 1.0) > register.MAX_STRETCH_DEVIATION).mean())}
    return out


def cjc_candidates(inp, table: dict) -> dict:
    """Mesh CJC height candidates (mm above the sole), each with its landmark and SD. `nape_c7` is the brief's; the others are cross-checks: the nape vertex taken as the CJC
    itself (offset zero, to show what the offset costs), ANSUR II cervicale (C7) and ANSUR II suprasternale (the sternal notch), both scaled to the mesh stature."""
    sh, S = inp.sheet, inp.stature_mesh
    nape = float(inp.V[NAPE_VERTEX_ID, 2])
    c7, sup = c7_above_cjc_mm(table, sh), sup_below_cjc_mm(table, sh)
    r = inp.ansur["landmarks"]
    cerv, sups = r["cervicale"]["ratio"], r["suprasternale"]["ratio"]
    return {
        "nape_c7": {"cjc_mm": nape - c7, "landmark_mm": nape, "offset_to_cjc_mm": -c7, "sd_mm": cerv["sd"] * S, "landmark": "nape vertex 1491 as the C7 proxy; CJC = nape - Dumas C7 offset"},
        "nape_as_cjc": {"cjc_mm": nape, "landmark_mm": nape, "offset_to_cjc_mm": 0.0, "sd_mm": cerv["sd"] * S, "landmark": "nape vertex 1491 taken as the CJC (diagnostic)"},
        "ansur_cervicale": {"cjc_mm": cerv["mean"] * S - c7, "landmark_mm": cerv["mean"] * S, "offset_to_cjc_mm": -c7, "sd_mm": cerv["sd"] * S,
                            "landmark": "ANSUR II female cervicale height ratio x mesh stature; CJC = cervicale - Dumas C7 offset"},
        "ansur_suprasternale": {"cjc_mm": sups["mean"] * S + sup, "landmark_mm": sups["mean"] * S, "offset_to_cjc_mm": sup, "sd_mm": sups["sd"] * S,
                                "landmark": "ANSUR II female suprasternale height ratio x mesh stature; CJC = suprasternale + Dumas SUP offset"},
    }


def neck_plane_mm(inp) -> float:
    """Height of the narrowest core section between 80% and 90% of the stature (memo 32's neck plane), mesh frame."""
    raster = features.BodyRaster(inp.V, inp.F, inp.stature_mesh + 10.0, h=RASTER_MM)
    return decompose.neck_height(decompose.profile(raster), inp.stature_mesh)


def _inputs_hash(inp, table, extra) -> str:
    h = hashlib.sha256()
    h.update(np.round(inp.V, 4).tobytes())
    h.update(json.dumps({"sheet": sheet_nodes(inp.sheet), "ansur": inp.ansur.get("source_sha256_12"), "table": table, "extra": extra}, sort_keys=True).encode())
    return h.hexdigest()[:12]


def run(root: Path, mesh_path, n=MC_N, seed=MC_SEED) -> dict:
    """The trunk registration report of a mesh: plain data, deterministic, no absolute paths."""
    root = Path(root)
    inp = trial.load_inputs(root, mesh_path)
    sh = inp.sheet
    feats = trial.find_features(inp)
    reg = trial.make_registration(inp, feats, "chords")
    table = masses.load_dumas_table1(root)
    for need in ("cervicale", "suprasternale"):
        if need not in inp.ansur["landmarks"]:
            raise register.StopAndAsk(f"data/ansur2/ratios.json has no {need}; run `fy envelope ratios`")
    sheet = sheet_nodes(sh)
    hjc_m, sd_hjc, top_m = reg.mesh_nodes["hjc"], reg.sigmas["hjc"], inp.stature_mesh
    neck = neck_plane_mm(inp)
    cands = cjc_candidates(inp, table)
    in_sheet_frame = lambda z: z - hjc_m + sh.hjc            # slope 1 above the HJC node
    out_c = {}
    for name, c in cands.items():
        modes = {}
        for mode in MODES:
            mesh = mesh_nodes(sheet, hjc_m, c["cjc_mm"], top_m, mode)
            st = stretches(sheet, mesh)
            modes[mode] = {"mesh_nodes_mm": mesh, "stretch": st, "exceeding_8_percent": exceeding(st),
                           "monte_carlo": monte_carlo(sheet, hjc_m, c["cjc_mm"], top_m, sd_hjc, c["sd_mm"], mode, n, seed)}
        head_closed = (sheet["vertex"] - sheet["cjc"] + (sh.stature_mm - sheet["vertex"])) / (top_m - c["cjc_mm"])
        out_c[name] = {**c, "cjc_in_sheet_frame_mm": in_sheet_frame(c["cjc_mm"]), "cjc_minus_sheet_cjc_mm": in_sheet_frame(c["cjc_mm"]) - sheet["cjc"],
                       "neck_plane_above_cjc_mm": neck - c["cjc_mm"], "modes": modes, "head_neck_stretch_if_closed_at_stature": head_closed}
    prim = out_c[PRIMARY_CANDIDATE]["modes"][PRIMARY_MODE]
    sha = _inputs_hash(inp, table, {"n": n, "seed": seed})
    return {
        "generated_by": "fy envelope trunk",
        "inputs": f"mesh, snapshot, ANSUR II ratios, Dumas 2015 Table 1 (inputs sha256:{sha})",
        "schema": "trunk-registration/1",
        "mesh_file": inp.mesh_label,
        "sheet": {"nodes_mm": sheet, "target_stature_mm": sh.stature_mm, "lengths_mm": {"abdomen": sh.abdomen_length_mm, "thorax": sh.thorax_length_mm, "head_neck": sh.head_neck_length_mm,
                                                                                         "hjc_to_ljc": sh.ljc - sh.hjc}},
        "standing_head_top": standing_head_top(sh, root),
        "mesh": {"stature_mm": top_m, "hjc_mm": hjc_m, "hjc_sd_mm": sd_hjc, "nape_vertex_id": NAPE_VERTEX_ID, "nape_vertex_mm": float(inp.V[NAPE_VERTEX_ID, 2]),
                 "neck_plane_mm": neck, "c7_above_cjc_mm": c7_above_cjc_mm(table, sh), "sup_below_cjc_mm": sup_below_cjc_mm(table, sh),
                 "sheet_cjc_in_mesh_frame_mm": hjc_m + sheet["cjc"] - sheet["hjc"], "frame_note": "mesh heights are above the sole; the mesh-to-sheet map is slope 1 above the HJC node"},
        "monte_carlo": {"n": n, "seed": seed, "sd_convention": SD_CONVENTION},
        "candidates": out_c,
        "primary_candidate": PRIMARY_CANDIDATE, "primary_mode": PRIMARY_MODE,
        "primary_exceeding_8_percent": prim["exceeding_8_percent"],
        "stop_and_ask": bool(prim["exceeding_8_percent"] and any(k in prim["exceeding_8_percent"] for k in ("thorax", "head_neck"))),
    }


def write(res: dict, root: Path) -> Path:
    p = Path(root) / RESULT_PATH
    p.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return p


def format_report(res: dict) -> str:
    L = [f"mesh {res['mesh_file']}; sheet nodes (mm above the floor): " + ", ".join(f"{k} {v:.1f}" for k, v in res["sheet"]["nodes_mm"].items())]
    h = res["standing_head_top"]
    L.append(f"zero-pose vertex {h['zero_pose_vertex_mm']:.2f} mm, {h['shortfall_mm']:.2f} mm below the stature {h['stature_mm']:.0f}; vertical LJC-HJC drop at {h['tilt_deg']:g} deg "
             f"{h['vertical_drop_at_tilt_mm']:.2f} mm against {h['zero_pose_drop_mm']:.2f} mm in the zero pose")
    m = res["mesh"]
    L.append(f"mesh: stature {m['stature_mm']:.1f}, HJC {m['hjc_mm']:.1f} (SD {m['hjc_sd_mm']:.1f}), nape vertex {m['nape_vertex_id']} at {m['nape_vertex_mm']:.1f}, neck plane {m['neck_plane_mm']:.1f}; "
             f"the sheet's CJC is at {m['sheet_cjc_in_mesh_frame_mm']:.1f} in the mesh frame")
    for name, c in res["candidates"].items():
        L.append(f"{name}: CJC {c['cjc_mm']:.1f} mm (landmark {c['landmark_mm']:.1f}, SD {c['sd_mm']:.1f}); minus the sheet's CJC {c['cjc_minus_sheet_cjc_mm']:+.1f}; "
                 f"head and neck closed at the stature: {c['head_neck_stretch_if_closed_at_stature']:.4f}")
        for mode, d in c["modes"].items():
            s, mc = d["stretch"], d["monte_carlo"]
            L.append(f"    {mode:8s} " + "  ".join(f"{k} {s[k]:.4f} (MC {mc[k]['p2_5']:.4f}-{mc[k]['p97_5']:.4f})" for k in SUBSEGMENTS) + (f"   OVER 8%: {', '.join(d['exceeding_8_percent'])}" if d["exceeding_8_percent"] else ""))
    L.append("STOP, ask Joe: the primary anchor puts " + ", ".join(res["primary_exceeding_8_percent"]) + " beyond 8%" if res["stop_and_ask"] else "no stop: the primary anchor is within 8%")
    return "\n".join(L)
