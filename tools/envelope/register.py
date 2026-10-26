"""Registration of the mesh to the sheet's zero pose: sheet nodes, mesh nodes, the piecewise axial stretch, the horizontal shear, and the
Monte Carlo over the mesh node heights.

Heights are millimetres above the floor (sheet) or above the mesh's sole plane (mesh). The conform moves every vertex by (a) a piecewise-linear
map of its height through the nodes sole, AJC, KJC, HJC (slope 1 outside) and (b) a horizontal translation that depends on height only, linear
between the nodes. Both leave every horizontal cross-section unchanged in shape and size.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import sheet
from .sheet import StopAndAsk

DUMAS_PELVIS_LENGTH_MM = 107.0     # the unscaled Dumas pelvis length (Joe, memo 27 follow-up; ADR 0038 keeps "107 x k" as the normaliser)
CROTCH_SD_MM = 2.0                 # repeatability of the crotch-apex detection (0.5 mm steps, 5 mm gap criterion); only enters the Monte Carlo
CENTRE_OFFSET_MM = 10.0            # half-range of the section-centre offsets in the Monte Carlo (the brief)
MAX_STRETCH_DEVIATION = 0.08       # gate 2: |stretch - 1| per sub-segment (the brief; provisional)
ROBUST_RADIUS_MM = 5.0             # gate 2: robust minimum inscribed radius within this of nominal (the brief; provisional)
ROBUST_VOLUME = 0.10               # gate 2: robust interior volume within this fraction of nominal (the brief; provisional)
DUMAS_GT_ABOVE_HJC_MM = 8.0        # Dumas 2007 Table 1B (female), greater trochanter Y in the thigh frame (up), unscaled; times the pelvis scale it is the expected trochanterion-above-HJC offset (brief 5, step 0)
TROCH_OFFSET_FLAG_MM = 10.0        # brief 5: flag when the ANSUR trochanterion, scaled, is more than this from the HJC plus the expected offset (the old 20 mm flag assumed zero offset)

# Values the brief asks to be asserted from the sheet pull (ISB frame, metres in the snapshot)
EXPECTED = {"rasis": (0.087, -0.013, 0.119), "mpsis": (-0.108, -0.013, 0.0), "hjc_dumas": (0.054, -0.093, 0.088)}


@dataclass(frozen=True)
class SheetNodes:
    ajc: float
    kjc: float
    hjc: float
    thigh_length: float
    shank_length: float
    lateral_y: float            # signed, right side negative (sheet frame y is left), from the sagittal midplane
    k_pelvis: float
    thigh_mass_kg: float
    stature_mm: float
    shank_mass_kg: float
    foot_mass_kg: float
    total_mass_kg: float          # the sum of the snapshot's segment masses (both sides), not the target
    target_mass_kg: float
    ljc: float                    # height of the lumbosacral joint (the pelvis body origin), mm above the floor
    pelvis_mass_kg: float
    checks: dict
    abdomen_mass_kg: float = float("nan")
    thorax_mass_kg: float = float("nan")
    abdomen_length_mm: float = float("nan")      # the sheet abdomen body's length (LJC to TJC); scales the Dumas 2015 Table 1 landmarks
    thorax_length_mm: float = float("nan")       # TJC to CJC
    head_neck_length_mm: float = float("nan")    # CJC to the vertex
    head_neck_mass_kg: float = float("nan")


SEGMENT_MASS_KEYS = ("abdomen", "head_neck", "pelvis", "thorax")                       # one body each
BILATERAL_MASS_KEYS = ("foot", "forearm", "hand", "shank", "thigh", "upper_arm")        # one per side


def total_mass(snap) -> float:
    """Sum of the sheet's segment masses (the toe is part of the foot row, not added again)."""
    return float(sum(snap[f"{k}_mass"] for k in SEGMENT_MASS_KEYS) + sum(snap[f"{k}_{s}_mass"] for k in BILATERAL_MASS_KEYS for s in ("left", "right")))


def sheet_nodes(snapshot_path, side="right") -> SheetNodes:
    snap = sheet.read_snapshot(snapshot_path)
    need = [f"thigh_{side}_length", f"shank_{side}_length", f"thigh_{side}_mass", f"shank_{side}_mass", f"foot_{side}_mass", "target_mass", f"thigh_{side}_pos_y", "pelvis_length", "pelvis_pos_z",
            f"thigh_{side}_pos_z", "ansur_female_malleolusheight", "ansur_female_stature", "target_stature", "pelvis_mass", "abdomen_mass", "abdomen_length", "thorax_mass", "thorax_length", "head_neck_length", "head_neck_mass"]
    for k in need:
        if k not in snap:
            raise StopAndAsk(f"snapshot key {k} is missing")
    for name, want in EXPECTED.items():
        for ax, w in zip("xyz", want):
            key = f"source_landmark_{name}_isb_{ax}"
            if key not in snap:
                raise StopAndAsk(f"snapshot key {key} is missing (the source_landmarks range)")
            if abs(snap[key] - w) > 1e-9:
                raise StopAndAsk(f"{key} is {snap[key]}, the brief expects {w}")
    mm = 1000.0
    Lt, Ls = snap[f"thigh_{side}_length"] * mm, snap[f"shank_{side}_length"] * mm
    ajc = snap["ansur_female_malleolusheight"] * snap["target_stature"] / snap["ansur_female_stature"] * mm
    kjc, hjc = ajc + Ls, ajc + Ls + Lt
    k = snap["pelvis_length"] * mm / DUMAS_PELVIS_LENGTH_MM
    hjc_model = (snap["pelvis_pos_z"] + snap[f"thigh_{side}_pos_z"]) * mm
    checks = {
        "hjc_height_chain_minus_model_mm": hjc - hjc_model,                # the sheet's own pelvis origin + thigh offset, against ankle + shank + thigh
        "lateral_y_minus_dumas_times_k_mm": snap[f"thigh_{side}_pos_y"] * mm - snap["source_landmark_hjc_dumas_mjc_y"] * mm * k,
        "ankle_height_mm": ajc,
    }
    return SheetNodes(ajc, kjc, hjc, Lt, Ls, snap[f"thigh_{side}_pos_y"] * mm, k, snap[f"thigh_{side}_mass"],
                      snap["target_stature"] * mm, snap[f"shank_{side}_mass"], snap[f"foot_{side}_mass"], total_mass(snap), snap["target_mass"],
                      snap["pelvis_pos_z"] * mm, snap["pelvis_mass"], checks, snap["abdomen_mass"], snap["thorax_mass"], snap["abdomen_length"] * mm,
                      snap["thorax_length"] * mm, snap["head_neck_length"] * mm, snap["head_neck_mass"])


@dataclass(frozen=True)
class AxialMap:
    """Piecewise-linear height map through (sole 0, AJC, KJC, HJC); slope 1 below the sole and above the HJC."""
    mesh: tuple     # (ajc, kjc, hjc) heights above the sole
    sheet: tuple    # (ajc, kjc, hjc) heights above the floor

    def _nodes(self, a, b):
        return np.array([0.0, *a]), np.array([0.0, *b])

    def forward(self, z):
        m, s = self._nodes(self.mesh, self.sheet)
        z = np.asarray(z, float)
        return np.where(z > m[-1], z + (s[-1] - m[-1]), np.where(z < 0, z, np.interp(z, m, s)))

    def inverse(self, z):
        m, s = self._nodes(self.mesh, self.sheet)
        z = np.asarray(z, float)
        return np.where(z > s[-1], z + (m[-1] - s[-1]), np.where(z < 0, z, np.interp(z, s, m)))

    def stretches(self) -> dict:
        m, s = self._nodes(self.mesh, self.sheet)
        d = np.diff(s) / np.diff(m)
        return {"foot": float(d[0]), "shank": float(d[1]), "thigh": float(d[2])}


@dataclass(frozen=True)
class Shear:
    """Horizontal translation (dx, dy) as a function of mesh height: constant outside the nodes, linear between them."""
    z: tuple        # mesh heights of AJC, KJC, HJC
    dx: tuple
    dy: tuple

    def at(self, z):
        z = np.asarray(z, float)
        return np.interp(z, self.z, self.dx), np.interp(z, self.z, self.dy)


@dataclass
class Registration:
    sheet: SheetNodes
    mesh_nodes: dict            # name -> height above the sole, mm
    axial: AxialMap
    shear: Shear
    target_xy: tuple            # the common vertical line (x*, y*) of the three section centres, mm, mesh frame (y from the midplane)
    centroids: dict             # node name -> (x, y) of the right-of-midplane section centroid before the shear
    sigmas: dict                # node name -> SD of the mesh height used in the Monte Carlo, mm
    knee_source: str = ""       # where the mesh KJC height came from

    def apply(self, V):
        """Conformed vertices (sheet frame, floor at z = 0, y from the midplane)."""
        V = np.asarray(V, float)
        out = np.array(V, copy=True)
        dx, dy = self.shear.at(V[:, 2])
        out[:, 0] += dx
        out[:, 1] += dy
        out[:, 2] = self.axial.forward(V[:, 2])
        return out

    def summary(self) -> dict:
        a, k, h = (self.centroids[n] for n in ("ajc", "kjc", "hjc"))
        st = self.axial.stretches()
        sh = lambda p, q: float(np.hypot(*(np.array(self.shear_at_node(p)) - np.array(self.shear_at_node(q)))))
        L_th, L_sh = self.sheet.thigh_length, self.sheet.shank_length
        thigh_sh, shank_sh = sh("hjc", "kjc"), sh("kjc", "ajc")
        return {
            "stretch": st,
            "shear_mm": {"thigh": thigh_sh, "shank": shank_sh},
            "shear_deg": {"thigh": float(np.degrees(np.arctan2(thigh_sh, L_th))), "shank": float(np.degrees(np.arctan2(shank_sh, L_sh)))},
            "section_centre_offset_before_shear_mm": {"thigh": float(np.hypot(h[0] - k[0], h[1] - k[1])), "shank": float(np.hypot(k[0] - a[0], k[1] - a[1]))},
            "mesh_nodes_mm": self.mesh_nodes, "sheet_nodes_mm": {"ajc": self.sheet.ajc, "kjc": self.sheet.kjc, "hjc": self.sheet.hjc},
        }

    def shear_at_node(self, name):
        i = ("ajc", "kjc", "hjc").index(name)
        return (self.shear.dx[i], self.shear.dy[i])


def make_registration(sh: SheetNodes, mesh_nodes: dict, centroids: dict, sigmas: dict) -> Registration:
    names = ("ajc", "kjc", "hjc")
    axial = AxialMap(tuple(mesh_nodes[n] for n in names), (sh.ajc, sh.kjc, sh.hjc))
    xs = centroids["kjc"][0]            # the knee section keeps its anterior-posterior position; the line is vertical through it
    ys = sh.lateral_y                   # the hip's lateral position is the sheet's (pelvis factor x Dumas), from the midplane
    shear = Shear(tuple(mesh_nodes[n] for n in names), tuple(xs - centroids[n][0] for n in names), tuple(ys - centroids[n][1] for n in names))
    return Registration(sh, mesh_nodes, axial, shear, (xs, ys), centroids, sigmas)


def diagnostics(sh: SheetNodes, ansur: dict) -> dict:
    """Sheet nodes against the ANSUR landmarks scaled to the sheet stature (the brief's step 7)."""
    scale = sh.stature_mm / ansur["stature_mm"]["mean"]
    L = ansur["landmarks"]
    troch = L["trochanterion"]["height_mm"]["mean"] * scale
    expected = DUMAS_GT_ABOVE_HJC_MM * sh.k_pelvis      # the trochanterion sits this far above the HJC (Dumas 2007 Table 1B)
    epi = L["lateral_femoral_epicondyle"]["height_mm"]["mean"] * scale
    out = {
        "scale_to_sheet_stature": scale,
        "hjc_minus_scaled_trochanterion_mm": sh.hjc - troch,
        "expected_trochanterion_above_hjc_mm": expected,
        "trochanterion_minus_expected_mm": troch - (sh.hjc + expected),
        "kjc_minus_scaled_lateral_epicondyle_mm": sh.kjc - epi,
        "ajc_minus_scaled_lateral_malleolus_mm": sh.ajc - L["lateral_malleolus"]["height_mm"]["mean"] * scale,
        "hjc_flag": bool(abs(troch - (sh.hjc + expected)) > TROCH_OFFSET_FLAG_MM),
    }
    return out


def monte_carlo(profile, reg: Registration, segment="thigh", n=200, seed=0, shells=(0.0, 3.0, 5.0, 8.0, 10.0), hip_zone=40.0, stations=None) -> dict:
    """Envelope outputs of a segment under uncertainty in the mesh node heights (normal, SD from the registration) and the section-centre offsets
    (uniform +-10 mm).

    `profile` holds the unconformed section areas and Chebyshev radii on a fine height grid (they are invariant under the axial stretch and the shear,
    so each sample's outputs follow by remapping): station s of a sample sits at mesh height upper - s / stretch. Volume is the stretch times the
    integral of area over the mapped interval. The centre offsets move sections sideways and so change none of these outputs; they are drawn and
    reported as the spread of the shear. `hip_zone` (mm from the proximal plane) is excluded from the minimum radius for the thigh only."""
    rng = np.random.default_rng(seed)
    z, A, R = profile["z"], profile["area"], profile["radius"]
    upper, lower = {"thigh": ("hjc", "kjc"), "shank": ("kjc", "ajc"), "foot": ("ajc", None)}[segment]
    sh = reg.sheet
    L = {"thigh": sh.thigh_length, "shank": sh.shank_length, "foot": sh.ajc}[segment]
    zone = hip_zone if segment == "thigh" else 0.0
    st = np.array(stations if stations is not None else np.arange(0.0, L + 1e-9, 10.0))
    names = ("ajc", "kjc", "hjc")

    def evaluate(nodes):
        zu, zl = nodes[upper], (nodes[lower] if lower else 0.0)
        s_seg = L / (zu - zl)
        zz = zu - st / s_seg
        out = {"stretch": s_seg, "stretch_thigh": L_th / (nodes["hjc"] - nodes["kjc"]), "stretch_shank": L_sh / (nodes["kjc"] - nodes["ajc"]), "stretch_foot": sh.ajc / nodes["ajc"]}
        body = st >= zone
        fine = np.linspace(zl, zu, 400)
        for t in shells:
            a = np.interp(zz, z, A[t])
            r = np.interp(zz, z, R[t])
            out[f"area_t{t:g}"] = a
            out[f"rmin_t{t:g}"] = float(r[body].min())
            out[f"rmin_station_t{t:g}"] = float(st[body][np.argmin(r[body])])
            out[f"volume_t{t:g}"] = float(s_seg * np.trapezoid(np.interp(fine, z, A[t]), fine))
        return out

    L_th, L_sh = sh.thigh_length, sh.shank_length
    nominal = evaluate({n_: reg.mesh_nodes[n_] for n_ in names})
    runs = [evaluate({n_: reg.mesh_nodes[n_] + rng.normal(0.0, reg.sigmas[n_]) for n_ in names}) for _ in range(n)]
    pair = {"thigh": ("hjc", "kjc"), "shank": ("kjc", "ajc"), "foot": ("kjc", "ajc")}[segment]
    shear_seg = []
    base = np.array([[reg.shear.dx[i], reg.shear.dy[i]] for i in range(3)])
    for _ in range(n):
        d = rng.uniform(-CENTRE_OFFSET_MM, CENTRE_OFFSET_MM, (3, 2))
        sh_ = base - d                      # the centres were off by d, so the shear differs by -d
        i, j = names.index(pair[0]), names.index(pair[1])
        shear_seg.append(float(np.hypot(*(sh_[i] - sh_[j]))))
    res = {"n": n, "segment": segment, "nominal": {k: (v if np.isscalar(v) else [float(x) for x in v]) for k, v in nominal.items()},
           "stations_mm": [float(x) for x in st],
           "shear_mm": {"nominal": reg.summary()["shear_mm"]["thigh" if segment == "thigh" else "shank"], "p2_5": float(np.percentile(shear_seg, 2.5)),
                        "p97_5": float(np.percentile(shear_seg, 97.5))}}
    spread = {}
    for key in runs[0]:
        vals = np.array([r[key] for r in runs])
        if vals.ndim == 1:
            spread[key] = {"mean": float(vals.mean()), "sd": float(vals.std(ddof=1)), "p2_5": float(np.percentile(vals, 2.5)), "p5": float(np.percentile(vals, 5)),
                           "p95": float(np.percentile(vals, 95)), "p97_5": float(np.percentile(vals, 97.5))}
        else:
            spread[key] = {"p2_5": [float(x) for x in np.percentile(vals, 2.5, axis=0)], "p97_5": [float(x) for x in np.percentile(vals, 97.5, axis=0)]}
    res["spread"] = spread
    return res
