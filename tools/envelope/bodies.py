"""The trunk bodies (volume-extractor brief 5, items 2 to 5): pelvis, abdomen, thorax, head and neck as whole-width voxel fields in the sheet's zero pose, the joint zones, the
per-body design numbers and the closure of the volumes.

Planes (sheet frame, horizontal in the zero pose: the template has no rotation on any trunk body, the 12 degree pelvic tilt exists only in the design stance): the pelvis is
HJC to LJC, the abdomen LJC to TJC, the thorax TJC to CJC, the head and neck CJC to the vertex. A cell on a plane belongs to the body above it (accounting only). The conform is
the legs' registration below the hip-centre node and `TrunkMap` above it: slope 1 up to the TJC, the thorax and the head and neck stretched to the sheet's lengths (the CJC from
the anchor of `trunk.PRIMARY_CANDIDATE`), plus the legs' shear, which is a constant translation above the hip.

Arms: a vertex is an arm vertex by the rule of memo 32 (`decompose.vertex_regions`: below the crotch apex a piece far from the midline, above it every piece but the largest in its
layer), and a cell goes to the arm when its nearest vertex is one. Where an arm and the core are one connected piece, above the axilla, the thorax is cut at the vertical plane
through the shoulder joint centres (the sheet's SJC: the upper-arm body origin in the thorax frame); what lies beyond the plane is the shoulder girdle of that side, part of the unbuilt remainder.
The axilla is found from the layer topology: the top of the highest layer in which a separate arm piece (at least ARM_PIECE_MIN_MM2) still exists, on each side.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

import numpy as np
from scipy import ndimage
from scipy.signal import find_peaks
from scipy.spatial import cKDTree

from . import decompose, features, field, ledger, register, trial, trunk
from .sheet import StopAndAsk

BODIES = ("pelvis", "abdomen", "thorax", "head_neck")
PLANES = {"pelvis": ("ljc", "hjc"), "abdomen": ("tjc", "ljc"), "thorax": ("cjc", "tjc"), "head_neck": ("vertex", "cjc")}    # (upper, lower)
ZONE_H_MM = 25.0                 # the brief: half-thickness of the slab around each joint-centre plane, and the radius of the shoulder zone (named, default 25 mm)
ARM_PIECE_MIN_MM2 = 500.0        # a non-largest piece of a layer counts as an arm only above this area (a hand's cross-section is several thousand mm2; this ignores fingertips and slivers)
PINCH_PROMINENCE_MM = 3.0        # a pinch station is a local minimum of the section's inscribed radius that stands out by at least this (the legs' knee feature uses 3 mm)
FREE_END_MM = 20.0               # the head's crown is a cap whose inscribed radius goes to 0 by geometry, not a pinch: its minimum radius is taken from this station down (the neck is what it finds)
INNER_MM = (3.0, 5.0, 8.0, 10.0)
RASTER_MM = 2.0
CLOSURE_TOL = 0.005              # the brief: sum of conformed volumes plus the remainder within 0.5% of the mesh volume
AREA_TOL = 0.01                  # gate 3 as for the legs
MATCHED_U = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
FIELD_VS_RASTER_TOL = 0.01       # my cross-check: a body's voxel-field volume against the raster accounting of the same body

# cell classes of the accounting
CLASSES = ("foot_R", "foot_L", "shank_R", "shank_L", "thigh_R", "thigh_L", "pelvis", "abdomen", "thorax", "head_neck", "arms", "shoulder_R", "shoulder_L")
CODE = {n: i for i, n in enumerate(CLASSES)}


@dataclass(frozen=True)
class TrunkMap:
    """The conform of the whole body: the legs' registration below the hip-centre node, a piecewise-linear map through (HJC, TJC, CJC, vertex) above it, slope 1 beyond the vertex."""
    reg: register.Registration
    mesh: tuple          # mesh heights (above the sole) of HJC, TJC, CJC, vertex
    sheet: tuple         # the same nodes in the sheet frame

    def forward(self, z):
        z = np.asarray(z, float)
        m, s = np.array(self.mesh), np.array(self.sheet)
        up = np.where(z > m[-1], s[-1] + (z - m[-1]), np.interp(z, m, s))
        return np.where(z > m[0], up, self.reg.axial.forward(z))

    def inverse(self, z):
        z = np.asarray(z, float)
        m, s = np.array(self.mesh), np.array(self.sheet)
        up = np.where(z > s[-1], m[-1] + (z - s[-1]), np.interp(z, s, m))
        return np.where(z > s[0], up, self.reg.axial.inverse(z))

    def slope(self, z):
        """d(sheet height)/d(mesh height) at mesh height z: the factor a thin slab there changes volume by."""
        z = np.asarray(z, float)
        m, s = self.mesh, self.sheet
        st = self.reg.axial.stretches()
        k = [(s[i + 1] - s[i]) / (m[i + 1] - m[i]) for i in range(3)]
        mn = self.reg.mesh_nodes
        return np.select([z < 0, z < mn["ajc"], z < mn["kjc"], z < m[0], z < m[1], z < m[2], z < m[3]], [1.0, st["foot"], st["shank"], st["thigh"], k[0], k[1], k[2]], 1.0)

    def apply(self, V):
        """Conformed vertices (sheet frame): the legs' shear in x and y, this map in z."""
        V = np.asarray(V, float)
        out = np.array(V, copy=True)
        dx, dy = self.reg.shear.at(V[:, 2])
        out[:, 0] += dx
        out[:, 1] += dy
        out[:, 2] = self.forward(V[:, 2])
        return out

    @property
    def shear_hjc(self):
        """(dx, dy) of the translation applied above the hip-centre node."""
        return float(self.reg.shear.dx[-1]), float(self.reg.shear.dy[-1])


def trunk_map(inp, reg, table, candidate=trunk.PRIMARY_CANDIDATE) -> TrunkMap:
    sheet = trunk.sheet_nodes(inp.sheet)
    cjc_m = trunk.cjc_candidates(inp, table)[candidate]["cjc_mm"]
    m = trunk.mesh_nodes(sheet, reg.mesh_nodes["hjc"], cjc_m, inp.stature_mesh, trunk.PRIMARY_MODE)
    return TrunkMap(reg, (m["hjc"], m["tjc"], m["cjc"], m["vertex"]), (sheet["hjc"], sheet["tjc"], sheet["cjc"], sheet["vertex"]))


def sjc(table: dict, sh) -> dict:
    """The shoulder joint centre in the sheet's thorax frame (origin CJC): the snapshot's upper-arm body origin, `upper_arm_right_pos_x/y/z` (the sheet scales Dumas 2007 torso values by
    the torso length). Returns the lateral distance from the midline, the distance below the CJC and the distance ahead of it (mm; the left side mirrors y). The Dumas 2015 Table 1 SJC,
    scaled to the sheet's thorax, is kept as a cross-check only, with the difference sheet minus Dumas in the thorax frame's own signs (z is up, so a smaller drop is positive)."""
    x, y, z = (float(v) for v in sh.sjc_mm)
    if not np.isfinite([x, y, z]).all():
        raise StopAndAsk("the snapshot has no upper_arm_right_pos_x/y/z (the shoulder joint centre in the thorax frame)")
    s = sh.thorax_length_mm / float(table["reference_length_mm"]["thorax"])
    _, ty, tz = table["segments"]["thorax"]["landmarks"]["SJC"]
    dumas = {"lateral_mm": abs(tz) * s, "below_cjc_mm": -ty * s, "scale": s}
    return {"lateral_mm": abs(y), "below_cjc_mm": -z, "ahead_of_cjc_mm": x, "source": "snapshot upper_arm_right_pos_x/y/z (the sheet's upper-arm body origin)",
            "dumas2015": dumas, "sheet_minus_dumas_mm": {"lateral": abs(y) - dumas["lateral_mm"], "z": z - (-dumas["below_cjc_mm"])}}


def planes_sheet(sheet: dict) -> dict:
    return dict(sheet)


# ---- the axilla ------------------------------------------------------------------------------------------------------------------------

def axilla(prof: dict, apex_mm: float) -> dict:
    """The axilla level from the layer topology of `decompose.profile` (mesh heights above the sole): on each side the top of the highest layer above the crotch apex that still
    holds a separate piece of at least ARM_PIECE_MIN_MM2 on that side of the midline, the layers lacking that piece between its first and last appearance (an arm merging with the
    trunk below the axilla, or vanishing), and the level itself (the higher of the two sides). Stops when either arm is not found."""
    z0, h = prof["z0"], prof["h"]
    present = {"right": np.zeros(len(z0), bool), "left": np.zeros(len(z0), bool)}
    for k, pieces in enumerate(prof["layers"]):
        if z0[k] < apex_mm:
            continue
        for a, cy, big in pieces:
            if not big and a >= ARM_PIECE_MIN_MM2:
                present["right" if cy < 0 else "left"][k] = True
    out = {"arm_piece_min_mm2": ARM_PIECE_MIN_MM2}
    for side, p in present.items():
        idx = np.flatnonzero(p)
        if not len(idx):
            raise StopAndAsk(f"the axilla cannot be found from the layer topology: no separate {side} arm piece above the crotch apex")
        lo, hi = int(idx[0]), int(idx[-1])
        out[side] = {"first_layer_mm": float(z0[lo]), "top_mm": float(z0[hi] + h), "layers_missing_between": int((~p[lo:hi + 1]).sum())}
    out["level_mm"] = max(out["right"]["top_mm"], out["left"]["top_mm"])
    out["right_minus_left_mm"] = out["right"]["top_mm"] - out["left"]["top_mm"]
    out["merged_below_axilla"] = bool(out["right"]["layers_missing_between"] or out["left"]["layers_missing_between"])
    return out


# ---- accounting of every cell ----------------------------------------------------------------------------------------------------------

def classify(raster, V, arm_mask, tm: TrunkMap, sheet: dict, apex_mm: float, axilla_mm: float, lateral_mm: float, sjc_below_mm: float, h_zone: float = ZONE_H_MM, sjc_ahead_mm: float | None = None) -> dict:
    """Every inside cell of the raster (mesh frame, sole at 0) to a class, with the conformed volumes. Returns volumes (litres, conformed and unconformed) by class, the per-layer
    areas by class (mm2, for the matched-station check), the zone accounting and the shoulder spheres.

    A cell's conformed height is the map's; its conformed volume is h^3 times the map's slope. Right and left are the mesh's own sides (the legs; the shoulder). Beyond the vertical
    planes at +-lateral_mm and above the axilla, thorax cells are shoulder girdle. Joint zones: for each plane the volume of every class within +-h_zone of it, below and above."""
    inside, h, o = raster.inside, raster.h, raster.o
    ii, jj, kk = np.nonzero(inside)
    P = np.column_stack([o[0] + h * (ii + 0.5), o[1] + h * (jj + 0.5), o[2] + h * (kk + 0.5)])
    arm_mask = np.asarray(arm_mask, bool)
    d_arm = cKDTree(V[arm_mask]).query(P, workers=-1)[0]
    d_rest = cKDTree(V[~arm_mask]).query(P, workers=-1)[0]
    is_arm = d_arm < d_rest
    # the nearest-vertex rule leaves arm cells next to an arm vertex that the label put on the torso (the layers just below the axilla): between the crotch apex and the axilla an arm is
    # a separate piece of its layer, so any non-arm cell outside the layer's largest non-arm piece is an arm cell; the voxel field drops them the same way (they are not connected to its seed)
    grid = np.zeros(inside.shape, bool)
    grid[ii, jj, kk] = is_arm
    leaked = 0
    for k in range(max(int(np.ceil((apex_mm - o[2]) / h)), 0), min(int((axilla_mm - o[2]) / h), inside.shape[2])):
        m = inside[:, :, k] & ~grid[:, :, k]
        lab, n = ndimage.label(m)
        if n > 1:
            areas = ndimage.sum(m, lab, range(1, n + 1))
            extra = m & (lab != 1 + int(np.argmax(areas)))
            leaked += int(extra.sum())
            grid[:, :, k] |= extra
    is_arm = grid[ii, jj, kk]
    zc, y = P[:, 2], P[:, 1]
    zlo, zhi = tm.forward(zc - h / 2), tm.forward(zc + h / 2)         # the cell's conformed span; a plane that falls inside a cell splits it by overlap
    thick = zhi - zlo
    zf = 0.5 * (zlo + zhi)
    right = y < 0
    lateral_cell = (zc >= axilla_mm) & (np.abs(y) > lateral_mm)
    edges = [-np.inf, sheet["ajc"], sheet["kjc"], sheet["hjc"], sheet["ljc"], sheet["tjc"], sheet["cjc"], np.inf]     # bands: foot, shank, thigh, pelvis, abdomen, thorax, head and neck

    def band_class(b):
        """Class code of every cell for the band b (arms override everything)."""
        if b <= 2:
            c = np.where(right, CODE[("foot", "shank", "thigh")[b] + "_R"], CODE[("foot", "shank", "thigh")[b] + "_L"])
        elif b == 5:
            c = np.where(lateral_cell, np.where(right, CODE["shoulder_R"], CODE["shoulder_L"]), CODE["thorax"])
        else:
            c = np.full(len(P), CODE[{3: "pelvis", 4: "abdomen", 6: "head_neck"}[b]])
        return np.where(is_arm, CODE["arms"], c)

    def interval(a_, b_, lo_z=zlo, hi_z=zhi, edge=edges):
        """Volume (mm3) by class code of the part of every cell inside the height interval [a_, b_) of the frame the cell spans lo_z, hi_z and the band edges are in."""
        out = np.zeros(len(CLASSES))
        th = hi_z - lo_z
        for b in range(7):
            lo, hi = max(a_, edge[b]), min(b_, edge[b + 1])
            if lo >= hi:
                continue
            w = np.clip((np.minimum(hi_z, hi) - np.maximum(lo_z, lo)) / th, 0.0, 1.0)
            m = w > 0
            out += np.bincount(band_class(b)[m], weights=(w * th)[m] * h * h, minlength=len(CLASSES))
        return out

    cell = h ** 3
    cls = np.empty(len(P), np.int8)                           # whole-cell class by the centre (for the layer areas and the spheres)
    band = np.digitize(zf, edges[1:-1])
    for b in range(7):
        cls[band == b] = band_class(b)[band == b]
    vol_c = interval(-np.inf, np.inf) / 1e6
    edges_mesh = [-np.inf, *[float(tm.inverse(e)) for e in edges[1:-1]], np.inf]
    vol_u = interval(-np.inf, np.inf, zc - h / 2, zc + h / 2, edges_mesh) / 1e6
    nz = inside.shape[2]
    layer = {n: np.bincount(kk[cls == CODE[n]], minlength=nz) * h * h for n in ("pelvis", "abdomen", "thorax", "head_neck")}
    zones = {}
    for pname in ("hjc", "ljc", "tjc", "cjc"):
        zones[pname] = {}
        for side, (a_, b_) in (("below", (sheet[pname] - h_zone, sheet[pname])), ("above", (sheet[pname], sheet[pname] + h_zone))):
            v = interval(a_, b_) / 1e6
            zones[pname][side] = {CLASSES[c]: float(v[c]) for c in range(len(CLASSES)) if v[c] > 0}
    slope = thick / h
    arm_above = is_arm & (zc >= axilla_mm) & (np.abs(y) <= lateral_mm)
    # shoulder spheres: centre at the SJC, the plane's lateral distance from the midline, sjc_below_mm below the CJC. x: the thorax's centre line in the mesh is its mean x within 5 mm
    # of the CJC plane (thorax cells inside the shoulder planes), and the SJC lies sjc_ahead_mm in front of it (the sheet's x offset in the thorax frame). Without an offset the
    # centre is the thorax's mean x at the sphere height, the rule before the sheet's SJC was used; that mean is reported either way
    zs = sheet["cjc"] - sjc_below_mm
    mean_x = lambda z0: (lambda sel: float(P[sel, 0].mean()) if sel.any() else float("nan"))((np.abs(zf - z0) < 5.0) & (cls == CODE["thorax"]) & (np.abs(y) < lateral_mm))
    x_sphere_level, x_cjc = mean_x(zs), mean_x(sheet["cjc"])
    xc = x_sphere_level if sjc_ahead_mm is None else x_cjc + sjc_ahead_mm
    spheres = {"centre_height_mm": zs, "centre_x_mesh_mm": xc, "cjc_x_mesh_mm": x_cjc, "centre_x_thorax_mean_mesh_mm": x_sphere_level, "lateral_mm": lateral_mm, "radius_mm": h_zone, "sides": {}}
    for side, sgn in (("R", -1.0), ("L", 1.0)):
        dist = np.sqrt((P[:, 0] - xc) ** 2 + (y - sgn * lateral_mm) ** 2 + (zf - zs) ** 2)
        m = dist < h_zone
        spheres["sides"][side] = {CLASSES[c]: float((slope[m & (cls == c)] * cell).sum() / 1e6) for c in range(len(CLASSES)) if (m & (cls == c)).any()}
    return {"volume_l": {CLASSES[i]: float(vol_c[i]) for i in range(len(CLASSES))}, "volume_unconformed_l": {CLASSES[i]: float(vol_u[i]) for i in range(len(CLASSES))},
            "raster_total_l": float(len(P) * cell / 1e6), "layer_area_mm2": layer, "layer_z0": o[2] + h * np.arange(nz), "layer_h": h, "zones": zones, "spheres": spheres,
            "arm_cells_nearest_vertex": int(is_arm.sum()), "cells": int(len(P)), "leaked_arm_cells_reclassified_l": leaked * h ** 3 / 1e6,
            "arm_labelled_above_axilla_inside_shoulder_planes_l": float((slope[arm_above] * cell).sum() / 1e6)}


def zone_table(acc: dict, h_zone: float = ZONE_H_MM) -> dict:
    """Each body's volume (litres, conformed) with and without the slab of +-h around each of its joint-centre planes, and without all of them; the thorax also without the shoulder
    spheres. The thigh row is both thighs, its only zone the hip plane (the slab below it)."""
    v, Z = acc["volume_l"], acc["zones"]
    own = {"pelvis": ("pelvis", ("ljc", "hjc")), "abdomen": ("abdomen", ("ljc", "tjc")), "thorax": ("thorax", ("tjc", "cjc")), "head_neck": ("head_neck", ("cjc",))}
    out = {}
    for name, (cls, planes) in own.items():
        total = v[cls]
        cut = {p: sum(Z[p][s].get(cls, 0.0) for s in ("below", "above")) for p in planes}
        out[name] = {"with_zones_l": total, "slab_l": cut, "without_each_l": {p: total - c for p, c in cut.items()}, "without_all_l": total - sum(cut.values())}
    sph = acc["spheres"]["sides"]
    in_thorax = sum(s.get("thorax", 0.0) for s in sph.values())
    out["thorax"]["shoulder_spheres_in_thorax_l"] = in_thorax
    out["thorax"]["without_all_and_spheres_l"] = out["thorax"]["without_all_l"] - in_thorax
    thigh = v["thigh_R"] + v["thigh_L"]
    hip = sum(Z["hjc"][s].get(c, 0.0) for s in ("below",) for c in ("thigh_R", "thigh_L"))
    out["thighs"] = {"with_zones_l": thigh, "slab_l": {"hjc": hip}, "without_all_l": thigh - hip}
    out["zone_h_mm"] = h_zone
    out["ownership"] = "a cell on a joint-centre plane belongs to the body above it; accounting only"
    return out


# ---- the voxel bodies ------------------------------------------------------------------------------------------------------------------

def _seed(raster, z_mesh, y_mid=0.0):
    """A cell inside the largest piece of the layer at mesh height z_mesh (nearest to the piece's centroid): the mask pixel for the connected-component seed."""
    L = raster.layer(z_mesh)
    lab, n = ndimage.label(L)
    areas = ndimage.sum(L, lab, range(1, n + 1))
    m = lab == (1 + int(np.argmax(areas)))
    ii, jj = np.nonzero(m)
    cx, cy = ii.mean(), jj.mean()
    k = int(np.argmin((ii - cx) ** 2 + (jj - cy) ** 2))
    return np.array([raster.o[0] + raster.h * (ii[k] + 0.5), raster.o[1] + raster.h * (jj[k] + 0.5), z_mesh])


def build_body(inp, raster, tm: TrunkMap, name, arm_mask, sheet, axilla_mm, lateral_mm, voxel=trial.VOXEL_MM) -> trial.SegResult:
    """The conformed body as a voxel field in its own frame: origin on the vertical line through the knee section's x and the midline's y, at the body's upper plane, z up, x anterior,
    y left (the midline is y = 0), stations the distance below the upper plane. Arm-nearest cells and, above the axilla, cells beyond the shoulder plane are outside the region."""
    up, low = PLANES[name]
    z_top, z_bot = sheet[up], sheet[low]
    L = z_top - z_bot
    reg = tm.reg
    xs = reg.target_xy[0]
    _, dy = tm.shear_hjc
    origin = np.array([xs, dy, z_top])
    Vt = tm.apply(inp.V)
    Vs = Vt - origin
    arm_mask = np.asarray(arm_mask, bool)
    ax_sheet = float(tm.forward(axilla_mm))
    inz = (Vs[:, 2] <= trial.MARGIN_MM) & (Vs[:, 2] >= -L - trial.MARGIN_MM)
    core = Vs[inz & ~arm_mask]
    lat = lateral_mm if (z_top > ax_sheet) else np.inf             # a body that reaches above the axilla is clipped at the shoulder planes
    pad = trial.SIDE_PAD_MM
    xy = (core[:, 0].min() - pad, core[:, 0].max() + pad, max(core[:, 1].min() - pad, -lat - pad), min(core[:, 1].max() + pad, lat + pad))
    tree_arm, tree_rest = cKDTree(Vs[arm_mask]), cKDTree(Vs[~arm_mask])

    def region(X, Y, Z):
        P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        keep = tree_rest.query(P, workers=-1)[0] <= tree_arm.query(P, workers=-1)[0]
        keep &= ~(((Z.ravel() + z_top) > ax_sheet) & (np.abs(Y.ravel()) > lat))
        return keep.reshape(X.shape)

    z_mid_mesh = float(tm.inverse(0.5 * (z_top + z_bot)))
    sp = _seed(raster, z_mid_mesh)
    seed = tm.apply(sp[None, :])[0] - origin
    seg = field.build_segment(Vs, inp.F, length=L, voxel=voxel, z_top=0.0, margin=trial.MARGIN_MM, xy=xy, region_fn=region, seed_point=seed)
    touch = inz[inp.F].any(axis=1)
    wt = field.watertight(inp.F, touch)
    checks = {"boundary_edges_near_segment": wt["boundary_edges"], "nonmanifold_edges_near_segment": wt["nonmanifold_edges"],
              "boundary_edges_whole_body": field.watertight(inp.F)["boundary_edges"], "odd_parity_columns": seg.odd_columns, "seed_inside_region": bool(seg.in_region(seed[None])[0])}
    mass = {"pelvis": inp.sheet.pelvis_mass_kg, "abdomen": inp.sheet.abdomen_mass_kg, "thorax": inp.sheet.thorax_mass_kg, "head_neck": inp.sheet.head_neck_mass_kg}[name]
    seg.meta = {"segment": name, "origin_xyz": [float(x) for x in origin], "z_top_sheet_mm": z_top, "z_bottom_sheet_mm": z_bot}
    return trial.SegResult(name, seg, reg, checks, tuple(float(x) for x in origin), mass)


# ---- design numbers --------------------------------------------------------------------------------------------------------------------

def pinch_stations(rows, key="cheb_r_mm", prominence=PINCH_PROMINENCE_MM) -> list:
    """Interior local minima of the inscribed radius along the stations that stand out by at least `prominence`."""
    s = np.array([r["s_mm"] for r in rows])
    r = np.array([r[key] for r in rows])
    idx, props = find_peaks(-r, prominence=prominence)
    return [{"station_mm": float(s[i]), "r_mm": float(r[i]), "prominence_mm": float(p)} for i, p in zip(idx, props["prominences"])]


def design_numbers(res: trial.SegResult, rows) -> dict:
    """Skin and inner volumes (litres), the sheet mass, the density the body must average (kg/l) over the skin and over each inner volume, the minimum inscribed radius and its station,
    and the pinch stations."""
    seg = res.seg
    skin = seg.volume(0.0) / 1e6
    inner = {f"t{t:g}": seg.volume(t) / 1e6 for t in INNER_MM}
    body = [r for r in rows if r["s_mm"] >= FREE_END_MM] if res.name == "head_neck" else rows
    k = min(body, key=lambda r: r["cheb_r_mm"])
    out = {"length_mm": seg.length, "skin_volume_l": skin, "inner_volume_l": inner, "sheet_mass_kg": res.mass_kg, "required_density_skin_kg_per_l": res.mass_kg / skin,
           "required_density_inner_kg_per_l": {t: res.mass_kg / v for t, v in inner.items()},
           "min_inscribed_radius": {"r_mm": k["cheb_r_mm"], "station_mm": k["s_mm"], "from_station_mm": FREE_END_MM if res.name == "head_neck" else 0.0},
           "min_inscribed_radius_inner": {f"t{t:g}": (lambda r: {"r_mm": r[f"cheb_r_t{t:g}_mm"], "station_mm": r["s_mm"]})(min(body, key=lambda r: r[f"cheb_r_t{t:g}_mm"])) for t in INNER_MM},
           "pinch_stations": pinch_stations(body)}
    return out


def pair_numbers(a: dict, b: dict) -> dict:
    """The abdomen + pelvis pair: one budget (the sheet's abdomen plus pelvis mass) over the summed volumes."""
    skin = a["skin_volume_l"] + b["skin_volume_l"]
    mass = a["sheet_mass_kg"] + b["sheet_mass_kg"]
    inner = {t: a["inner_volume_l"][t] + b["inner_volume_l"][t] for t in a["inner_volume_l"]}
    return {"skin_volume_l": skin, "inner_volume_l": inner, "sheet_mass_kg": mass, "required_density_skin_kg_per_l": mass / skin,
            "required_density_inner_kg_per_l": {t: mass / v for t, v in inner.items()}}


# ---- closure ---------------------------------------------------------------------------------------------------------------------------

def closure(built_l: dict, acc: dict, mesh_volume_l: float) -> dict:
    """Sum of the conformed segment volumes (the trunk bodies as built, each leg segment twice for the two sides) plus the unbuilt remainder (the arms and hands, and the shoulder
    girdle beyond the shoulder planes, as the raster measures them in the mesh as it is) against the mesh volume. The shares use the sum as their denominator, so they sum to 1."""
    U = acc["volume_unconformed_l"]
    remainder = {"arms": U["arms"], "shoulder_R": U["shoulder_R"], "shoulder_L": U["shoulder_L"]}
    parts = dict(built_l)
    total = sum(parts.values()) + sum(remainder.values())
    diff = (total - mesh_volume_l) / mesh_volume_l
    # the same classes measured on the raster without the conform: the decomposition error alone; the difference of the two is the conform's effect on volume
    raster_unconf = acc["raster_total_l"]
    return {"built_l": parts, "remainder_l": remainder, "sum_l": total, "mesh_volume_l": mesh_volume_l, "relative_difference": diff, "tolerance": CLOSURE_TOL,
            "within_tolerance": bool(abs(diff) <= CLOSURE_TOL), "raster_total_l": raster_unconf, "raster_minus_mesh_l": raster_unconf - mesh_volume_l,
            "conform_effect_l": sum(acc["volume_l"][c] - U[c] for c in CLASSES if c not in remainder),
            "share_denominator_l": total,
            "shares": {**{k: v / total for k, v in parts.items()}, "remainder": sum(remainder.values()) / total}}


# ---- matched-station areas -------------------------------------------------------------------------------------------------------------

def matched_areas(res: trial.SegResult, acc: dict, tm: TrunkMap) -> dict:
    """The field's section area at the matched normalised stations against the raster's layer area of the same body at the mesh height the station came from (a section is unchanged
    by the conform, so the two agree up to the two discretisations)."""
    seg, name = res.seg, res.name
    zc = acc["layer_z0"] + acc["layer_h"] / 2
    area = acc["layer_area_mm2"][name]
    rows = []
    for u in MATCHED_U:
        s = u * seg.length
        z_mesh = float(tm.inverse(res.seg.meta["z_top_sheet_mm"] - s))
        a0 = float(np.interp(z_mesh, zc, area))
        a1 = seg.section(s).area()
        rows.append({"u": u, "raster_mm2": a0, "field_mm2": a1, "relative": (a1 - a0) / a0})
    return {"rows": rows, "worst": max(abs(r["relative"]) for r in rows)}


# ---- the build -------------------------------------------------------------------------------------------------------------------------

@dataclass
class TrunkBuild:
    tm: TrunkMap
    sheet: dict
    arm_mask: np.ndarray
    axilla: dict
    sjc: dict
    acc: dict
    results: dict                    # name -> SegResult
    rows: dict                       # name -> ledger rows
    design: dict                     # name -> design numbers
    matched: dict
    neck_mm: float
    arm_method: dict
    timings: dict = dc_field(default_factory=dict)


def build(inp, feats, reg, table, voxel=trial.VOXEL_MM, h_zone=ZONE_H_MM) -> TrunkBuild:
    """Everything of items 2 to 5 for the four trunk bodies. Stops (StopAndAsk) when the mesh is not watertight, when an arm merges with the core below the axilla, or when the
    axilla cannot be found."""
    sh = inp.sheet
    wt = field.watertight(inp.F)
    if wt["boundary_edges"] or wt["nonmanifold_edges"]:
        raise StopAndAsk(f"the mesh is not watertight: {wt['boundary_edges']} boundary and {wt['nonmanifold_edges']} non-manifold edges")
    tm = trunk_map(inp, reg, table)
    sheet = {"ajc": sh.ajc, "kjc": sh.kjc, **trunk.sheet_nodes(sh)}
    raster = features.BodyRaster(inp.V, inp.F, inp.stature_mesh + 10.0, h=RASTER_MM)
    prof = decompose.profile(raster)
    apex = feats["crotch_apex_mm"]
    neck = decompose.neck_height(prof, inp.stature_mesh)
    names = np.array(decompose.vertex_regions(inp.V, raster, {"apex": apex, "neck": neck}))
    arm_mask = names == "arms"
    ax = axilla(prof, apex)
    if ax["merged_below_axilla"]:
        raise StopAndAsk(f"an arm piece is missing from a layer below the axilla (right {ax['right']['layers_missing_between']}, left {ax['left']['layers_missing_between']} layers): an arm merges with the trunk raster")
    sj = sjc(table, sh)
    acc = classify(raster, inp.V, arm_mask, tm, sheet, apex, ax["level_mm"], sj["lateral_mm"], sj["below_cjc_mm"], h_zone, sj["ahead_of_cjc_mm"])
    results, rows, design, matched = {}, {}, {}, {}
    for name in BODIES:
        res = build_body(inp, raster, tm, name, arm_mask, sheet, ax["level_mm"], sj["lateral_mm"], voxel)
        results[name] = res
        rows[name] = ledger.rows_for(res.seg, "trunk")
        design[name] = design_numbers(res, rows[name])
        matched[name] = matched_areas(res, acc, tm)
    # the arm rule against the layer topology: every cell above the hip-centre node that is not an arm by vertex label, against the core pieces of the layers (unconformed)
    core_topology = decompose.band(prof, "core", tm.mesh[0], np.inf, apex) / 1e6
    by_label = sum(acc["volume_unconformed_l"][c] for c in ("pelvis", "abdomen", "thorax", "head_neck", "shoulder_R", "shoulder_L"))
    arm_method = {"core_by_layer_topology_l": core_topology, "core_by_vertex_label_l": by_label, "difference_l": by_label - core_topology, "relative": (by_label - core_topology) / core_topology}
    return TrunkBuild(tm, sheet, arm_mask, ax, sj, acc, results, rows, design, matched, neck, arm_method)


def body_header(name, tb: TrunkBuild, rows, inputs_sha, mesh_label) -> dict:
    """Header scalars of a trunk body's ledger, the keys of the thigh's header where they apply."""
    res = tb.results[name]
    seg, d = res.seg, tb.design[name]
    up, low = PLANES[name]
    st = trunk.stretches({k: tb.sheet[k] for k in ("hjc", "ljc", "tjc", "cjc", "vertex")}, trunk.mesh_nodes(tb.sheet, tb.tm.mesh[0], tb.tm.mesh[2], tb.tm.mesh[3], trunk.PRIMARY_MODE))
    return {
        "segment": name,
        "frame": "body: origin on the vertical line through the knee section's x and the midline, at the body's upper plane, z up (lower plane at z = -length), x anterior, y left; stations are distances below the upper plane",
        "planes": {"upper": up, "lower": low, "upper_sheet_mm": round(tb.sheet[up], 2), "lower_sheet_mm": round(tb.sheet[low], 2)},
        "length_mm": round(seg.length, 2),
        "stretch": round(st[name], 5),
        "mesh_nodes_mm": {k: round(v, 2) for k, v in zip(("hjc", "tjc", "cjc", "vertex"), tb.tm.mesh)},
        "cjc_anchor": trunk.PRIMARY_CANDIDATE, "map": trunk.PRIMARY_MODE,
        "axilla_mesh_mm": round(tb.axilla["level_mm"], 1), "shoulder_plane_lateral_mm": round(tb.sjc["lateral_mm"], 2),
        "mesh_file": mesh_label, "voxel_mm": seg.h,
        "skin_volume_l": round(d["skin_volume_l"], 4), "inner_volume_l": {k: round(v, 4) for k, v in d["inner_volume_l"].items()},
        "sheet_mass_kg": round(d["sheet_mass_kg"], 4),
        "required_density_skin_kg_per_l": round(d["required_density_skin_kg_per_l"], 4),
        "required_density_inner_kg_per_l": {k: round(v, 4) for k, v in d["required_density_inner_kg_per_l"].items()},
        "min_inscribed_radius": d["min_inscribed_radius"],
        "min_inscribed_radius_inner": d["min_inscribed_radius_inner"],
        "pinch_stations": d["pinch_stations"], "pinch_prominence_mm": PINCH_PROMINENCE_MM,
        "directions": {str(a): n for a, n in ledger.direction_names("trunk").items()},
        "checks": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else int(v)) for k, v in res.checks.items()},
        "sections_csv": f"{name}_sections.csv", "inputs_sha256_12": inputs_sha,
    }


def gate_rows(tb: TrunkBuild, topo, mesh_volume_l, closure_row) -> list:
    """Gates of brief 5 item 7 for the trunk: topology and watertightness per body, the stretches, the matched-station areas, and the closure."""
    def g(name, ok, detail):
        return {"gate": name, "pass": bool(ok), "detail": detail}
    out = []
    for name in BODIES:
        c = tb.results[name].checks
        ok = topo is None and c["boundary_edges_near_segment"] == 0 and c["nonmanifold_edges_near_segment"] == 0 and c["odd_parity_columns"] == 0 and c["seed_inside_region"]
        out.append(g(f"1 {name}: topology matches base; surface watertight", ok, f"topology vs base.obj: {topo or 'identical'}; boundary edges near the body {c['boundary_edges_near_segment']} (whole body {c['boundary_edges_whole_body']}); "
                                                                           f"non-manifold {c['nonmanifold_edges_near_segment']}; odd-parity columns {c['odd_parity_columns']}"))
    sheet5 = {k: tb.sheet[k] for k in ("hjc", "ljc", "tjc", "cjc", "vertex")}
    st = trunk.stretches(sheet5, trunk.mesh_nodes(sheet5, tb.tm.mesh[0], tb.tm.mesh[2], tb.tm.mesh[3], trunk.PRIMARY_MODE))
    out.append(g("2 trunk: |stretch-1| < 8% per sub-segment", not trunk.exceeding(st), "; ".join(f"{k} {v:.4f} ({(v - 1) * 100:+.2f}%)" for k, v in st.items())))
    for name in BODIES:
        m = tb.matched[name]
        out.append(g(f"3 {name}: matched-station areas within 1% of the raster layers", m["worst"] < AREA_TOL, f"worst {m['worst'] * 100:.3f}% over u = 0.1..0.9"))
        v_field = tb.design[name]["skin_volume_l"]
        v_rast = tb.acc["volume_l"][name]
        out.append(g(f"3b {name}: field volume within 1% of the raster accounting", abs(v_field - v_rast) / v_rast < FIELD_VS_RASTER_TOL, f"field {v_field:.4f} l, raster {v_rast:.4f} l ({(v_field - v_rast) / v_rast * 100:+.3f}%)"))
    c = closure_row
    out.append(g("7 closure: conformed bodies + remainder = mesh volume within 0.5%", c["within_tolerance"],
                 f"sum {c['sum_l']:.4f} l against mesh {c['mesh_volume_l']:.4f} l ({c['relative_difference'] * 100:+.3f}%); remainder {sum(c['remainder_l'].values()):.4f} l; conform effect {c['conform_effect_l']:+.4f} l; raster minus mesh {c['raster_minus_mesh_l']:+.4f} l"))
    return out
