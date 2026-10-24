"""The thigh trial: landmarks -> Dumas joint centres -> required stretch -> conformed thigh -> voxel field. Pure functions of their inputs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import numpy as np

from . import field, landmarks as lm, meshio, pelvis, sheet, thigh

VOXEL_MM = 2.0                      # the brief's voxel
MARGIN_MM = 40.0                    # extension of the solid beyond both slab planes, so cut caps never shrink the inscribed radius
SIDE_PAD_MM = 15.0                  # grid padding around the thigh's vertices
MAX_STRETCH_DEVIATION = 0.08        # gate 2: |s - 1| (the brief)
HIP_ZONE_MM = 40.0                  # the proximal end is the hip zone: reported apart (the brief)
LANDMARK_NAMES = lm.REQUIRED


def triangulate(polys):
    out = []
    for p in polys:
        for i in range(1, len(p) - 1):
            out.append((p[0], p[i], p[i + 1]))
    return np.array(out, dtype=int)


@dataclass
class Inputs:
    V: np.ndarray                    # body vertices, sheet frame, mm
    F: np.ndarray                    # triangles
    P: dict                          # landmark name -> point (sheet frame, mm)
    b1: dict
    thigh_length_mm: float
    thigh_mass_kg: float
    k_sheet: float
    landmark_source: str
    provisional: bool = False


def load_inputs(mesh_path, landmarks_path, b1_path, snapshot_path, side="right") -> Inputs:
    doc = json.loads(Path(landmarks_path).read_text(encoding="utf-8"))
    problems = lm.validate(doc)
    if problems:
        raise sheet.StopAndAsk("landmarks file invalid: " + "; ".join(problems))
    v, polys = meshio.read_obj(mesh_path)
    if len(v) != meshio.BODY_VERTICES:
        raise sheet.StopAndAsk(f"mesh has {len(v)} vertices, expected {meshio.BODY_VERTICES}")
    V = meshio.to_sheet_mm(v)
    b1 = sheet.load_b1(b1_path)
    ti = sheet.thigh_inputs(snapshot_path, side)
    P = {n: V[doc["landmarks"][n]["vertex"]].copy() for n in LANDMARK_NAMES}
    return Inputs(V, triangulate(polys), P, b1, ti["length_mm"], ti["mass_kg"], sheet.sheet_pelvis_factor(snapshot_path, b1),
                  landmark_source=str(landmarks_path), provisional=bool(doc.get("provisional", False)))


def joint_centres(P, b1, k):
    """(HJC_R, KJC, pelvis frame) from landmark points."""
    hjc = pelvis.hip_joint_centre(P["ASIS_R"], P["ASIS_L"], P["SACRAL_MID"], b1, k)
    kjc = (P["EPI_MED_R"] + P["EPI_LAT_R"]) / 2
    return hjc, kjc, pelvis.pelvis_frame(P["ASIS_R"], P["ASIS_L"], P["SACRAL_MID"])


def stretch_for(P, b1, L_sheet, k=None):
    """Required stretch for landmark points P; k defaults to the mesh inter-ASIS scale."""
    k = pelvis.scale_from_asis(P["ASIS_R"], P["ASIS_L"], b1["rows"]) if k is None else k
    hjc, kjc, _ = joint_centres(P, b1, k)
    return thigh.required_stretch(hjc, kjc, L_sheet), k, hjc, kjc


@dataclass
class Sensitivity:
    one_at_a_time: list = dc_field(default_factory=list)     # (landmark, axis, sign, s, relative change)
    max_relative_change: float = 0.0
    mc_mean: float = 0.0
    mc_std: float = 0.0
    mc_min: float = 0.0
    mc_max: float = 0.0
    mc_p5: float = 0.0
    mc_p95: float = 0.0
    n: int = 0


def sensitivity(P, b1, L_sheet, k_mode="asis", k_fixed=None, delta=5.0, n=200, sigma=5.0, seed=0) -> Sensitivity:
    """Spread of the required stretch under landmark error. Perturbations are in the sheet frame, mm; k follows the perturbed ASISs in
    'asis' mode and is held in 'sheet' mode."""
    def s_of(Q):
        return stretch_for(Q, b1, L_sheet, None if k_mode == "asis" else k_fixed)[0]

    s0 = s_of(P)
    out = Sensitivity()
    for name in LANDMARK_NAMES:
        for ax, axname in enumerate("xyz"):
            for sign in (+1, -1):
                Q = {k: v.copy() for k, v in P.items()}
                Q[name][ax] += sign * delta
                s = s_of(Q)
                out.one_at_a_time.append((name, axname, sign * delta, float(s), float((s - s0) / s0)))
    out.max_relative_change = max(abs(r[4]) for r in out.one_at_a_time)
    rng = np.random.default_rng(seed)
    ss = []
    for _ in range(n):
        Q = {k: v + rng.normal(0.0, sigma, 3) for k, v in P.items()}
        ss.append(s_of(Q))
    ss = np.array(ss)
    out.n = n
    out.mc_mean, out.mc_std = float(ss.mean()), float(ss.std(ddof=1))
    out.mc_min, out.mc_max = float(ss.min()), float(ss.max())
    out.mc_p5, out.mc_p95 = (float(x) for x in np.percentile(ss, [5, 95]))
    return out


@dataclass
class ThighResult:
    seg: field.Segment
    k: float
    k_variant: str
    s: float
    hjc: np.ndarray
    kjc: np.ndarray
    L_mesh: float
    L_sheet: float
    frame: thigh.SegmentFrame
    pelvis_frame: pelvis.Frame
    mass_kg: float
    checks: dict


def build_thigh(inp: Inputs, k_variant="asis", voxel=VOXEL_MM, stretch=True) -> ThighResult:
    """Conform and voxelise the right thigh. k_variant 'asis' (mesh inter-ASIS over the sheet's) or 'sheet' (the sheet's pelvis factor).
    stretch=False builds the unstretched thigh, for the section-area comparison of gate 3."""
    b1 = inp.b1
    k = pelvis.scale_from_asis(inp.P["ASIS_R"], inp.P["ASIS_L"], b1["rows"]) if k_variant == "asis" else inp.k_sheet
    hjc, kjc, pf = joint_centres(inp.P, b1, k)
    L_mesh = float(np.linalg.norm(hjc - kjc))
    s_req = thigh.required_stretch(hjc, kjc, inp.thigh_length_mm)
    s = s_req if stretch else 1.0
    fr = thigh.segment_frame(hjc, kjc, pf.X)
    Vs = thigh.conform(fr.to_segment(inp.V), s)
    L = L_mesh * s
    mid = (inp.P["ASIS_R"] + inp.P["ASIS_L"]) / 2
    n_mid = fr.R.T @ pf.Z                     # pelvis Z (to the right) in the segment frame
    m_seg = fr.to_segment(mid[None])[0]

    def right_of_midplane(X, Y, Z):
        d = (X - m_seg[0]) * n_mid[0] + (Y - m_seg[1]) * n_mid[1] + (Z / s - m_seg[2]) * n_mid[2]
        return d > 0

    # grid in x, y: the thigh's own vertices (slab plus margin, right of the midplane) with padding
    inz = (Vs[:, 2] <= MARGIN_MM) & (Vs[:, 2] >= -L - MARGIN_MM)
    right = right_of_midplane(Vs[:, 0], Vs[:, 1], Vs[:, 2])
    sel = Vs[inz & right]
    xy = (sel[:, 0].min() - SIDE_PAD_MM, sel[:, 0].max() + SIDE_PAD_MM, sel[:, 1].min() - SIDE_PAD_MM, sel[:, 1].max() + SIDE_PAD_MM)
    axis_mid = np.array([0.0, 0.0, -L / 2])
    seg = field.build_segment(Vs, inp.F, length=L, voxel=voxel, z_top=0.0, margin=MARGIN_MM, xy=xy,
                              region_fn=right_of_midplane, seed_point=axis_mid)
    # watertightness of the surface around the thigh: faces with a vertex in the extended slab on the right side
    touch = (inz & right)[inp.F].any(axis=1)
    checks = {
        "hjc_inside_body": bool(field.contains(inp.V, inp.F, hjc)),
        "kjc_inside_body": bool(field.contains(inp.V, inp.F, kjc)),
        "boundary_edges_near_thigh": field.watertight(inp.F, touch)["boundary_edges"],
        "nonmanifold_edges_near_thigh": field.watertight(inp.F, touch)["nonmanifold_edges"],
        "boundary_edges_whole_body": field.watertight(inp.F)["boundary_edges"],
        "odd_parity_columns": seg.odd_columns,
        "mid_axis_inside_region": bool(seg.in_region(axis_mid[None])[0]),
    }
    return ThighResult(seg, k, k_variant, s_req, hjc, kjc, L_mesh, inp.thigh_length_mm, fr, pf, inp.thigh_mass_kg, checks)


def inputs_hash(inp: Inputs, extra: dict) -> str:
    """Twelve hex of the sha256 of everything the result depends on (mesh and landmark vertex positions, sheet values, parameters)."""
    h = hashlib.sha256()
    h.update(np.round(inp.V, 4).tobytes())
    for n in LANDMARK_NAMES:
        h.update(np.round(inp.P[n], 4).tobytes())
    h.update(json.dumps({"b1": inp.b1, "L": inp.thigh_length_mm, "m": inp.thigh_mass_kg, "ksheet": round(inp.k_sheet, 9),
                         "prov": inp.provisional, **extra}, sort_keys=True).encode())
    return h.hexdigest()[:12]
