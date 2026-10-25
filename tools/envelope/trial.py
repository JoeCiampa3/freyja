"""The leg trial: mesh features -> registration to the sheet's nodes -> conformed thigh, shank and foot -> voxel fields. Pure functions of their inputs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import anthro, features, field, meshio, register, ruler
from .sheet import StopAndAsk

VOXEL_MM = 2.0                      # the brief's voxel
MARGIN_MM = 40.0                    # extension of the solid beyond both slab planes, so cut caps never shrink the inscribed radius
SIDE_PAD_MM = 15.0                  # grid padding around the segment's vertices
HIP_ZONE_MM = 40.0                  # the proximal end of the thigh is the hip zone: reported apart (the brief)
PROFILE_PAD_MM = 80.0               # the unconformed section profile reaches this far beyond the nominal nodes (covers the Monte Carlo and the cut shifts)
PROFILE_STEP_MM = 2.0
LOOP_SD_MM = 3.0                    # position scatter of a Ruler loop about its mean height (loops are tilted; spread of a loop's vertices is 10-60 mm)
SHELLS_MM = (0.0, 3.0, 5.0, 8.0, 10.0)   # the sheet's Design Inputs hold no shell thickness: the brief's sweep
KNEE_SOURCES = ("ruler", "ansur", "chords", "breadth")
# segment -> (proximal node, distal node or None for the sole); the segment is the slab between the two nodes' planes
SEGMENTS = {"thigh": ("hjc", "kjc"), "shank": ("kjc", "ajc"), "foot": ("ajc", None)}


def triangulate(polys):
    return np.array([(p[0], p[i], p[i + 1]) for p in polys for i in range(1, len(p) - 1)], dtype=int)


@dataclass
class Inputs:
    V: np.ndarray                    # body vertices: sheet axes, mm, z above the sole, y from the sagittal midplane
    F: np.ndarray
    sheet: register.SheetNodes
    ansur: dict
    stature_mesh: float
    sole: dict
    y_mid: float
    mesh_label: str
    ruler: dict                      # Ruler loop and chord statistics (left leg; heights and lengths carry to the right)
    z_sole_mm: float                 # the sole's height in the original mesh coordinates (to map back to them)


def load_inputs(root: Path, mesh_path, snapshot_path=None) -> Inputs:
    snapshot_path = snapshot_path or root / "params/snapshot.csv"
    v, polys = meshio.read_obj(mesh_path)
    if len(v) != meshio.BODY_VERTICES:
        raise StopAndAsk(f"mesh has {len(v)} vertices, expected {meshio.BODY_VERTICES}")
    V = meshio.to_sheet_mm(v)
    sole = features.sole_plane(V)
    y_mid = features.midline_y(V, sole["z_mm"])
    V = V - np.array([0.0, y_mid, sole["z_mm"]])
    sh = register.sheet_nodes(snapshot_path)
    ansur = anthro.load_summary(root)
    rs = ruler.all_stats(V, ruler.load(root))
    try:
        label = Path(mesh_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        label = Path(mesh_path).name
    return Inputs(V, triangulate(polys), sh, ansur, float(V[:, 2].max()), {**sole, "y_mid_mm": y_mid}, y_mid, label, rs, sole["z_mm"])


def find_features(inp: Inputs) -> dict:
    """Everything read off the mesh, with the independent estimates side by side."""
    S = inp.stature_mesh
    L = inp.ansur["landmarks"]
    cuts = features.Cuts(inp.V, inp.F)
    est = {k: L[k]["ratio"]["mean"] * S for k in ("crotch", "trochanterion", "lateral_femoral_epicondyle", "lateral_malleolus", "iliocristale", "tenth_rib", "midpatella")}
    apex, zs, gaps = features.crotch_apex(cuts, 0.0, est["crotch"] - 80.0, est["crotch"] + 80.0)
    bz, bb = features.breadth_profile(cuts, 0.0, est["lateral_femoral_epicondyle"] - 90.0, est["lateral_femoral_epicondyle"] + 90.0)
    knee = features.knee_level(bz, bb, est["lateral_femoral_epicondyle"])
    raster = features.BodyRaster(inp.V, inp.F, est["crotch"] + 120.0)
    rl = inp.ruler
    off = inp.ansur["epicondyle_minus_midpatella"]["ratio"]
    kjc_est = {
        "ansur_ratio": est["lateral_femoral_epicondyle"],
        "ruler_loop_plus_ansur_offset": rl["knee"]["z_mm"] + off["mean"] * S,
        "ruler_chords_mean": (rl["upperleg_height"]["bottom_z_mm"] + rl["lowerleg_height"]["top_z_mm"]) / 2,
        "breadth_peak": knee["z_mm"] if knee["is_feature"] else None,
    }
    hjc_est = {"crotch_apex_plus_ansur_offset": apex + inp.ansur["trochanterion_minus_crotch_ratio"]["mean"] * S, "ruler_upperleg_chord_top": rl["upperleg_height"]["top_z_mm"],
               "ansur_trochanterion": est["trochanterion"]}
    ajc_est = {"ansur_ratio": est["lateral_malleolus"], "ruler_ankle_loop_height": rl["ankle"]["z_mm"], "ruler_lowerleg_chord_bottom": rl["lowerleg_height"]["bottom_z_mm"]}
    return {"ansur_scaled_mm": est, "crotch_apex_mm": apex, "knee": knee, "breadth_profile": (bz, bb), "raster": raster, "cuts": cuts,
            "kjc_estimates_mm": kjc_est, "hjc_estimates_mm": hjc_est, "ajc_estimates_mm": ajc_est}


def make_registration(inp: Inputs, feats: dict, knee_source="ruler") -> register.Registration:
    """Mesh nodes. AJC: the ANSUR lateral-malleolus ratio (ANSUR gives no offset from the Ruler ankle loop to the ankle joint, see memo 29). KJC: the
    Ruler knee loop plus the ANSUR epicondyle-above-midpatella offset ('ruler', assumes the loop sits at the midpatella), the ANSUR ratio ('ansur'),
    the mean of the two Ruler leg-height chord ends ('chords'), or the knee-breadth peak when the mesh has one ('breadth'). HJC: the measured crotch
    apex plus the ANSUR trochanterion-above-crotch offset."""
    if knee_source not in KNEE_SOURCES:
        raise ValueError(f"knee source {knee_source!r}: choose from {KNEE_SOURCES}")
    S = inp.stature_mesh
    L = inp.ansur["landmarks"]
    off = inp.ansur["trochanterion_minus_crotch_ratio"]
    e = feats["kjc_estimates_mm"]
    knee_off_sd = inp.ansur["epicondyle_minus_midpatella"]["ratio"]["sd"] * S
    if knee_source == "breadth" and e["breadth_peak"] is None:
        raise StopAndAsk("the mesh has no knee-breadth feature (peak on the band edge or under 3 mm prominence)")
    kjc, kjc_sd = {"ruler": (e["ruler_loop_plus_ansur_offset"], float(np.hypot(knee_off_sd, LOOP_SD_MM))),
                   "ansur": (e["ansur_ratio"], L["lateral_femoral_epicondyle"]["ratio"]["sd"] * S),
                   "chords": (e["ruler_chords_mean"], float(np.hypot(knee_off_sd, LOOP_SD_MM))),
                   "breadth": (e["breadth_peak"], L["lateral_femoral_epicondyle"]["ratio"]["sd"] * S)}[knee_source]
    nodes = {"ajc": feats["ajc_estimates_mm"]["ansur_ratio"], "kjc": kjc, "hjc": feats["hjc_estimates_mm"]["crotch_apex_plus_ansur_offset"]}
    sig = {"ajc": L["lateral_malleolus"]["ratio"]["sd"] * S, "kjc": kjc_sd, "hjc": float(np.hypot(off["sd"] * S, register.CROTCH_SD_MM))}
    cent = {}
    for n, z in nodes.items():
        area, c, _ = feats["raster"].right_section(z, 0.0)
        if not area > 0:
            raise StopAndAsk(f"no right-side section at the mesh {n.upper()} height {z:.1f} mm")
        cent[n] = c
    reg = register.make_registration(inp.sheet, nodes, cent, sig)
    reg.knee_source = knee_source
    return reg


@dataclass
class SegResult:
    name: str
    seg: field.Segment
    reg: register.Registration
    checks: dict
    origin_xyz: tuple
    mass_kg: float


def segment_geometry(inp: Inputs, reg: register.Registration, name: str):
    """(upper node name, lower node name or None, sheet height of the upper plane, sheet length, mesh height of the upper plane, mesh height of the lower plane)."""
    up, low = SEGMENTS[name]
    sh = inp.sheet
    u_s = getattr(sh, up)
    l_s = getattr(sh, low) if low else 0.0
    return up, low, u_s, u_s - l_s, reg.mesh_nodes[up], (reg.mesh_nodes[low] if low else 0.0)


def _mass(inp, name):
    return {"thigh": inp.sheet.thigh_mass_kg, "shank": inp.sheet.shank_mass_kg, "foot": inp.sheet.foot_mass_kg}[name]


def _seed_point(feats, z_mesh):
    """A point inside the right-side section at mesh height z_mesh: the mask pixel nearest the section centroid (mesh frame, pre-conform)."""
    r = feats["raster"]
    area, c, m = r.right_section(z_mesh, 0.0)
    ii, jj = np.nonzero(m)
    x = r.o[0] + r.h * (ii + 0.5)
    y = r.o[1] + r.h * (jj + 0.5)
    k = int(np.argmin((x - c[0]) ** 2 + (y - c[1]) ** 2))
    return np.array([x[k], y[k], z_mesh])


def build_segment(inp: Inputs, feats: dict, reg: register.Registration, name="thigh", voxel=VOXEL_MM) -> SegResult:
    """The conformed right segment as a voxel field in its own frame (origin at the proximal plane on the vertical axis, z up, x anterior, y left)."""
    up, low, u_s, L, u_m, l_m = segment_geometry(inp, reg, name)
    Vt = reg.apply(inp.V)
    xs, ys = reg.target_xy
    origin = np.array([xs, ys, u_s])
    Vs = Vt - origin

    def right_of_midplane(X, Y, Z):
        zpre = reg.axial.inverse(Z + u_s)
        _, dy = reg.shear.at(zpre)
        return (Y + ys - dy) < 0.0

    inz = (Vs[:, 2] <= MARGIN_MM) & (Vs[:, 2] >= -L - MARGIN_MM)
    right = right_of_midplane(Vs[:, 0], Vs[:, 1], Vs[:, 2])
    sel = Vs[inz & right]
    xy = (sel[:, 0].min() - SIDE_PAD_MM, sel[:, 0].max() + SIDE_PAD_MM, sel[:, 1].min() - SIDE_PAD_MM, sel[:, 1].max() + SIDE_PAD_MM)
    sp = _seed_point(feats, (u_m + l_m) / 2)
    seed = reg.apply(sp[None, :])[0] - origin
    seg = field.build_segment(Vs, inp.F, length=L, voxel=voxel, z_top=0.0, margin=MARGIN_MM, xy=xy, region_fn=right_of_midplane, seed_point=seed)
    touch = (inz & right)[inp.F].any(axis=1)
    wt = field.watertight(inp.F, touch)
    checks = {
        "boundary_edges_near_segment": wt["boundary_edges"], "nonmanifold_edges_near_segment": wt["nonmanifold_edges"],
        "boundary_edges_whole_body": field.watertight(inp.F)["boundary_edges"], "odd_parity_columns": seg.odd_columns,
        "seed_inside_region": bool(seg.in_region(seed[None])[0]),
    }
    if name == "thigh":       # the three joint axes' end points sit inside the body (the brief's plausibility check)
        sh = inp.sheet
        checks.update({"hjc_inside_body": bool(field.contains(Vt, inp.F, origin)), "kjc_inside_body": bool(field.contains(Vt, inp.F, origin + [0, 0, -L])),
                       "ajc_inside_body": bool(field.contains(Vt, inp.F, origin + [0, 0, -L - sh.shank_length]))})
    return SegResult(name, seg, reg, checks, tuple(float(x) for x in origin), _mass(inp, name))


def build_profile(inp: Inputs, feats: dict, reg: register.Registration, name="thigh", voxel=VOXEL_MM, shells=SHELLS_MM) -> dict:
    """Section area, perimeter and Chebyshev radius of the *unconformed* mesh on a fine height grid around a segment, for each shell thickness. Cross-
    sections are unchanged by the axial stretch and the shear, so every Monte Carlo sample and every cut shift is a remapping of this profile."""
    up, low, u_s, L, u_m, l_m = segment_geometry(inp, reg, name)
    z_top = u_m + PROFILE_PAD_MM
    z_bot = l_m - PROFILE_PAD_MM if low else -10.0
    V = inp.V - np.array([0.0, 0.0, z_top])
    length = z_top - z_bot
    leg = V[(V[:, 2] > -length - MARGIN_MM) & (V[:, 2] < MARGIN_MM) & (V[:, 1] < 0) & (V[:, 1] > -260)]
    xy = (leg[:, 0].min() - SIDE_PAD_MM, leg[:, 0].max() + SIDE_PAD_MM, leg[:, 1].min() - SIDE_PAD_MM, min(leg[:, 1].max() + SIDE_PAD_MM, 40.0))
    sp = _seed_point(feats, (u_m + l_m) / 2)
    seg = field.build_segment(V, inp.F, length=length, voxel=voxel, z_top=0.0, margin=MARGIN_MM, xy=xy, region_fn=lambda X, Y, Z: Y < 0.0,
                              seed_point=sp - np.array([0.0, 0.0, z_top]))
    zs = np.arange(z_bot, z_top + 1e-9, PROFILE_STEP_MM)
    A = {t: [] for t in shells}
    R = {t: [] for t in shells}
    P = []
    for z in zs:
        sec = seg.section(z_top - z)
        P.append(sec.perimeter(0.0))
        for t in shells:
            A[t].append(sec.area(t))
            R[t].append(sec.chebyshev(t)[2])
    return {"z": zs, "area": {t: np.array(v) for t, v in A.items()}, "radius": {t: np.array(v) for t, v in R.items()}, "perimeter": np.array(P), "segment": seg}


def inputs_hash(inp: Inputs, extra: dict) -> str:
    """Twelve hex of the sha256 of everything the result depends on."""
    h = hashlib.sha256()
    h.update(np.round(inp.V, 4).tobytes())
    h.update(json.dumps({"sheet": [inp.sheet.ajc, inp.sheet.kjc, inp.sheet.hjc, inp.sheet.lateral_y, inp.sheet.k_pelvis, inp.sheet.thigh_mass_kg],
                         "ansur": inp.ansur.get("source_sha256_12"), "pelvis_ref_mm": register.DUMAS_PELVIS_LENGTH_MM, "ruler": inp.ruler, **extra}, sort_keys=True).encode())
    return h.hexdigest()[:12]
