"""The thigh trial: mesh features -> registration to the sheet's nodes -> conformed thigh -> voxel field. Pure functions of their inputs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import anthro, features, field, meshio, register
from .sheet import StopAndAsk

VOXEL_MM = 2.0                      # the brief's voxel
MARGIN_MM = 40.0                    # extension of the solid beyond both slab planes, so cut caps never shrink the inscribed radius
SIDE_PAD_MM = 15.0                  # grid padding around the thigh's vertices
HIP_ZONE_MM = 40.0                  # the proximal end is the hip zone: reported apart (the brief)
PROFILE_PAD_MM = 80.0               # the unstretched section profile reaches this far beyond the nominal HJC and KJC (covers the Monte Carlo)
PROFILE_STEP_MM = 2.0
SHELLS_MM = (0.0, 3.0, 5.0, 8.0, 10.0)   # the sheet's Design Inputs hold no shell thickness: the brief's sweep
KNEE_SEARCH_FROM = "lateral_femoral_epicondyle"


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
    try:
        label = Path(mesh_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        label = Path(mesh_path).name
    return Inputs(V, triangulate(polys), sh, ansur, float(V[:, 2].max()), {**sole, "y_mid_mm": y_mid}, y_mid, label)


def find_features(inp: Inputs) -> dict:
    """Everything read off the mesh, with the independent estimates side by side."""
    S = inp.stature_mesh
    L = inp.ansur["landmarks"]
    cuts = features.Cuts(inp.V, inp.F)
    est = {k: L[k]["ratio"]["mean"] * S for k in ("crotch", "trochanterion", "lateral_femoral_epicondyle", "lateral_malleolus", "iliocristale", "tenth_rib")}
    apex, zs, gaps = features.crotch_apex(cuts, 0.0, est["crotch"] - 80.0, est["crotch"] + 80.0)
    bz, bb = features.breadth_profile(cuts, 0.0, est["lateral_femoral_epicondyle"] - 90.0, est["lateral_femoral_epicondyle"] + 90.0)
    knee = features.knee_level(bz, bb, est["lateral_femoral_epicondyle"])
    raster = features.BodyRaster(inp.V, inp.F, est["crotch"] + 120.0)
    return {"ansur_scaled_mm": est, "crotch_apex_mm": apex, "knee": knee, "breadth_profile": (bz, bb), "raster": raster, "cuts": cuts}


def make_registration(inp: Inputs, feats: dict, knee_source="auto") -> register.Registration:
    """Mesh nodes: AJC from the ANSUR lateral-malleolus ratio (no mesh feature stands for it); KJC from the knee-breadth feature when the mesh has
    one, else the ANSUR lateral-epicondyle ratio; HJC from the measured crotch apex plus the ANSUR trochanterion-above-crotch offset. The three are
    scaled to the mesh stature."""
    S = inp.stature_mesh
    L = inp.ansur["landmarks"]
    off = inp.ansur["trochanterion_minus_crotch_ratio"]
    ajc = feats["ansur_scaled_mm"]["lateral_malleolus"]
    kjc_a = feats["ansur_scaled_mm"]["lateral_femoral_epicondyle"]
    use_feature = feats["knee"]["is_feature"] if knee_source == "auto" else knee_source == "feature"
    kjc = feats["knee"]["z_mm"] if use_feature else kjc_a
    hjc = feats["crotch_apex_mm"] + off["mean"] * S
    nodes = {"ajc": ajc, "kjc": kjc, "hjc": hjc}
    sig = {"ajc": L["lateral_malleolus"]["ratio"]["sd"] * S, "kjc": L["lateral_femoral_epicondyle"]["ratio"]["sd"] * S,
           "hjc": float(np.hypot(off["sd"] * S, register.CROTCH_SD_MM))}
    r = feats["raster"]
    cent = {}
    for n, z in nodes.items():
        area, c, _ = r.right_section(z, 0.0)
        if not area > 0:
            raise StopAndAsk(f"no right-side section at the mesh {n.upper()} height {z:.1f} mm")
        cent[n] = c
    reg = register.make_registration(inp.sheet, nodes, cent, sig)
    reg.knee_source = "feature" if use_feature else "ansur ratio"
    return reg


@dataclass
class ThighResult:
    seg: field.Segment
    reg: register.Registration
    checks: dict
    origin_xyz: tuple


def build_thigh(inp: Inputs, reg: register.Registration, voxel=VOXEL_MM) -> ThighResult:
    """The conformed right thigh as a voxel field in the segment frame (origin at the hip centre on the vertical axis, z up, x anterior, y left)."""
    sh = inp.sheet
    Vt = reg.apply(inp.V)
    xs, ys = reg.target_xy
    origin = np.array([xs, ys, sh.hjc])
    Vs = Vt - origin
    L = sh.thigh_length

    def right_of_midplane(X, Y, Z):
        zpre = reg.axial.inverse(Z + sh.hjc)
        _, dy = reg.shear.at(zpre)
        return (Y + ys - dy) < 0.0

    inz = (Vs[:, 2] <= MARGIN_MM) & (Vs[:, 2] >= -L - MARGIN_MM)
    right = right_of_midplane(Vs[:, 0], Vs[:, 1], Vs[:, 2])
    sel = Vs[inz & right]
    xy = (sel[:, 0].min() - SIDE_PAD_MM, sel[:, 0].max() + SIDE_PAD_MM, sel[:, 1].min() - SIDE_PAD_MM, sel[:, 1].max() + SIDE_PAD_MM)
    seed = np.array([0.0, 0.0, -L / 2])
    seg = field.build_segment(Vs, inp.F, length=L, voxel=voxel, z_top=0.0, margin=MARGIN_MM, xy=xy, region_fn=right_of_midplane, seed_point=seed)
    touch = (inz & right)[inp.F].any(axis=1)
    wt = field.watertight(inp.F, touch)
    checks = {
        "hjc_inside_body": bool(field.contains(Vt, inp.F, origin)),
        "kjc_inside_body": bool(field.contains(Vt, inp.F, origin + [0, 0, -L])),
        "ajc_inside_body": bool(field.contains(Vt, inp.F, origin + [0, 0, -L - sh.shank_length])),
        "boundary_edges_near_thigh": wt["boundary_edges"], "nonmanifold_edges_near_thigh": wt["nonmanifold_edges"],
        "boundary_edges_whole_body": field.watertight(inp.F)["boundary_edges"],
        "odd_parity_columns": seg.odd_columns,
        "mid_axis_inside_region": bool(seg.in_region(seed[None])[0]),
    }
    return ThighResult(seg, reg, checks, tuple(float(x) for x in origin))


def build_profile(inp: Inputs, feats: dict, reg: register.Registration, voxel=VOXEL_MM, shells=SHELLS_MM) -> dict:
    """Section area and Chebyshev radius of the *unconformed* mesh on a fine height grid around the thigh, for each shell thickness. Cross-sections
    are unchanged by the axial stretch and the shear, so every Monte Carlo sample is a remapping of this profile."""
    hj, kj = reg.mesh_nodes["hjc"], reg.mesh_nodes["kjc"]
    z_top = hj + PROFILE_PAD_MM
    length = (hj - kj) + 2 * PROFILE_PAD_MM
    V = inp.V - np.array([0.0, 0.0, z_top])
    zmid = (hj + kj) / 2
    _, c, _ = feats["raster"].right_section(zmid, 0.0)
    seed = np.array([c[0], c[1], zmid - z_top])
    leg = V[(V[:, 2] > -length - MARGIN_MM) & (V[:, 2] < MARGIN_MM) & (V[:, 1] < 0) & (V[:, 1] > -260)]
    xy = (leg[:, 0].min() - SIDE_PAD_MM, leg[:, 0].max() + SIDE_PAD_MM, leg[:, 1].min() - SIDE_PAD_MM, min(leg[:, 1].max() + SIDE_PAD_MM, 40.0))
    seg = field.build_segment(V, inp.F, length=length, voxel=voxel, z_top=0.0, margin=MARGIN_MM, xy=xy, region_fn=lambda X, Y, Z: Y < 0.0, seed_point=seed)
    zs = np.arange(kj - 70.0, hj + 70.0 + 1e-9, PROFILE_STEP_MM)
    A = {t: [] for t in shells}
    R = {t: [] for t in shells}
    for z in zs:
        sec = seg.section(z_top - z)
        for t in shells:
            A[t].append(sec.area(t))
            R[t].append(sec.chebyshev(t)[2])
    return {"z": zs, "area": {t: np.array(v) for t, v in A.items()}, "radius": {t: np.array(v) for t, v in R.items()}, "segment": seg}


def inputs_hash(inp: Inputs, extra: dict) -> str:
    """Twelve hex of the sha256 of everything the result depends on."""
    h = hashlib.sha256()
    h.update(np.round(inp.V, 4).tobytes())
    h.update(json.dumps({"sheet": [inp.sheet.ajc, inp.sheet.kjc, inp.sheet.hjc, inp.sheet.lateral_y, inp.sheet.k_pelvis, inp.sheet.thigh_mass_kg],
                         "ansur": inp.ansur.get("source_sha256_12"), "pelvis_ref_mm": register.DUMAS_PELVIS_LENGTH_MM, **extra}, sort_keys=True).encode())
    return h.hexdigest()[:12]
