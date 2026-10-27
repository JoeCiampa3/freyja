"""Reservations (volume-extractor brief 8, item 5): the spine modules of `data/envelope/reservations.yaml` as reserved registry components in the candidate trunk bodies, the free volume left, the
mass impact and the density the rest must carry, and a search for the placements of three modules that fit around the trunk axis.

A module is a vertical cylinder (its axis parallel to the trunk axis; the file gives no orientation, so this is an assumption, reported) of the file's diameter and length. A placement is three
modules at one height; it is feasible at skin margin m when every module lies inside {skin sd >= m} over its whole length and the modules keep the file's clearance between their surfaces. For
one height the feasible centres of one module are the cells whose 2-D distance to the edge of {sd >= m} is at least the radius, over every layer of the module's length; three centres at least
D + clearance apart exist or not (a triangle in the graph of the feasible centres). The best arrangement is the one with the largest m (bisected on a 0.5 mm grid up to MAX_MARGIN_MM), at the
height and centres with the smallest offset of the modules' centroid from the model's trunk axis. m >= the design shell t (5 mm) is feasible in the sense of ADR 0007 D4; a smaller m says how far
the body is from holding the modules.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage

from . import field, frames, occupancy, registry
from .sheet import StopAndAsk

PATH = "data/envelope/reservations.yaml"
VOLUME_CHECK_MM3 = 1.55e6                  # the brief's figure for three modules' bounding cylinders
VOLUME_TOL = 0.02
MAX_MARGIN_MM = 30.0
MARGIN_STEP_MM = 0.5
GRID_STRIDE = 3                            # the centre lattice for the triangle search: this many voxels (6 mm at 2 mm); the margin found is a lower bound, short by up to about one lattice step
Z_STRIDE_MM = 4.0                          # heights tried


def load(root) -> dict:
    p = Path(root) / PATH
    if not p.exists():
        raise StopAndAsk(f"{PATH} is missing")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if doc.get("schema") != "reservations/1":
        raise StopAndAsk(f"{PATH}: schema is {doc.get('schema')!r}, expected 'reservations/1'")
    return doc


def module_check(doc) -> dict:
    """Three times the bounding cylinder's volume against the brief's 1.55e6 mm3 (2%)."""
    s = doc["spine_v2"]
    m = s["module"]
    v = m["count"] * math.pi / 4.0 * m["diameter_mm"] ** 2 * m["length_mm"]
    return {"count": m["count"], "diameter_mm": m["diameter_mm"], "length_mm": m["length_mm"], "mass_kg": m["mass_kg"], "volume_mm3": v, "reference_mm3": VOLUME_CHECK_MM3,
            "relative_difference": (v - VOLUME_CHECK_MM3) / VOLUME_CHECK_MM3, "within_2_percent": bool(abs(v - VOLUME_CHECK_MM3) / VOLUME_CHECK_MM3 <= VOLUME_TOL),
            "clearance_mm": s["clearance_mm"], "candidates": list(s["candidate_bodies"]), "v1_ballast": s.get("v1_ballast")}


def _layers(seg: field.Segment, margin: float):
    """Per voxel layer of the segment's slab: the 2-D distance (mm) to the edge of {sd >= margin} inside the region, zero outside; and the layers' heights."""
    zl = seg.centres(2)
    keep = np.flatnonzero((zl <= seg.z_top) & (zl >= seg.z_top - seg.length))
    D = np.zeros((seg.sd.shape[0], seg.sd.shape[1], len(keep)), np.float32)
    for n, k in enumerate(keep):
        m = (seg.sd[:, :, k] >= margin) & seg.region[:, :, k]
        if m.any():
            D[:, :, n] = ndimage.distance_transform_edt(m, sampling=seg.h) - seg.h / 2
    return D, zl[keep]


def _feasible_centres(D, zs, h, radius, length):
    """For every start layer k0: the boolean map of centres whose disc of `radius` fits in every layer k0 .. k0 + n - 1, n the module's length in layers. Returns {k0: map}."""
    nz = int(math.ceil(length / h))
    if nz > D.shape[2]:
        return {}
    mn = np.lib.stride_tricks.sliding_window_view(D, nz, axis=2).min(axis=-1)
    return {k0: mn[:, :, k0] >= radius for k0 in range(mn.shape[2])}


def _triangle(points, min_dist):
    """A triple of points pairwise at least min_dist apart, or None; with several, the triple found is arbitrary (see `_best_triangle`)."""
    n = len(points)
    if n < 3:
        return None
    d = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    A = (d >= min_dist).astype(np.float32)
    C = (A @ A) * A
    if C.max() <= 0:
        return None
    return A


def _best_triangle(points, A, axis_xy):
    """Among the triples in the adjacency matrix A of `points`, the one whose centroid is nearest the trunk axis (xy)."""
    n = len(points)
    best, bd = None, np.inf
    for i in range(n):
        ni = np.flatnonzero(A[i, i + 1:]) + i + 1
        for j in ni:
            ks = ni[ni > j]
            ks = ks[A[j, ks] > 0]
            if not len(ks):
                continue
            cx = (points[i] + points[j])[None, :] + points[ks]
            dd = np.linalg.norm(cx / 3.0 - axis_xy[None, :], axis=1)
            q = int(np.argmin(dd))
            if dd[q] < bd:
                bd, best = float(dd[q]), (i, int(j), int(ks[q]))
    return best, bd


def search(seg: field.Segment, module: dict, clearance_mm: float, axis_xy, margin_start=None) -> dict:
    """The best arrangement of module["count"] (three) vertical modules in the body: the largest skin margin at which three fit, the height, the centres (segment frame) and the centroid's offset
    from the trunk axis `axis_xy` (the model's trunk axis in the segment frame). Returns {"feasible_at": m, ...} or {"none": True} when not even a margin of 0 admits them."""
    if module["count"] != 3:
        raise StopAndAsk("the placement search handles three modules (the reservation file's count)")
    R, L, h = module["diameter_mm"] / 2.0, module["length_mm"], seg.h
    min_dist = module["diameter_mm"] + clearance_mm

    def at(margin):
        D, zs = _layers(seg, margin)
        maps = _feasible_centres(D, zs, h, R, L)
        X = seg.centres(0)[::GRID_STRIDE]
        Y = seg.centres(1)[::GRID_STRIDE]
        found = []
        for k0 in sorted(maps)[::max(1, int(round(Z_STRIDE_MM / h)))]:
            m = maps[k0][::GRID_STRIDE, ::GRID_STRIDE]
            ii, jj = np.nonzero(m)
            if len(ii) < 3:
                continue
            P = np.column_stack([X[ii], Y[jj]])
            A = _triangle(P, min_dist)
            if A is not None:
                found.append((k0, P, A))
        return found, zs

    best_m, best = None, None
    m = 0.0
    last = None
    while m <= MAX_MARGIN_MM + 1e-9:
        found, zs = at(m)
        if not found:
            break
        best_m, best, last = m, found, zs
        m += MARGIN_STEP_MM
    if best is None:
        return {"none": True, "reason": "no three modules fit even with a skin margin of 0"}
    nz = int(math.ceil(L / h))
    cand = []
    for k0, P, A in best:
        tri, d = _best_triangle(P, A, np.asarray(axis_xy, float)) if len(P) <= 400 else _best_triangle(P[::2], A[::2, ::2], np.asarray(axis_xy, float))
        if tri is not None:
            cand.append((d, k0, P if len(P) <= 400 else P[::2], tri))
    d, k0, P, tri = min(cand, key=lambda c: c[0])
    zc = float(last[k0 + nz // 2])                          # the centre height of the module's length
    centres = [[float(P[i][0]), float(P[i][1]), zc] for i in tri]
    return {"none": False, "max_skin_margin_mm": best_m, "centres_mm": centres, "centroid_offset_from_trunk_axis_mm": d, "module_centre_height_mm": zc,
            "station_of_centre_mm": float(seg.z_top - zc), "heights_tried": len(best), "margin_step_mm": MARGIN_STEP_MM}


def registry_doc(body: str, search_result: dict, module: dict, clearance_mm: float, offset_mm, src="reservations.yaml spine_v2") -> dict | None:
    """The components/1 document of the three reserved modules in the model body frame of `body`: the segment-frame centres less the model-to-segment offset."""
    if search_result.get("none"):
        return None
    comps = []
    for i, c in enumerate(search_result["centres_mm"]):
        comps.append({"id": f"part.spine.m{i + 1}", "name": f"spine_module_{i + 1}", "status": "reserved", "owner": body,
                      "primitive": {"type": "cylinder", "diameter": module["diameter_mm"], "length": module["length_mm"]},
                      "pose": {"tx": round(c[0] - offset_mm[0], 3), "ty": round(c[1] - offset_mm[1], 3), "tz": round(c[2] - offset_mm[2], 3), "rx": 0, "ry": 0, "rz": 0},
                      "clearance_mm": clearance_mm, "mass_kg": module["mass_kg"], "source": src})
    return {"schema": registry.SCHEMA, "segment": body, "components": comps}


def free_numbers(seg, regs, required_mm, body_mass_kg, module_mass_total_kg) -> dict:
    """Free volume left (skin margin >= required, the modules dilated by their clearance removed), the largest free sphere, the occupied volume, and the mass impact."""
    virt, rep = occupancy.free_field([(seg, np.zeros(3))], regs, required_mm, 0.0)
    free = rep["free_volume_l"]
    skin_inner = rep["skin_volume_l"]
    return {"required_skin_margin_mm": required_mm, "inner_volume_l": skin_inner, "free_volume_l": free, "occupied_volume_l": rep["occupied_volume_l"], "largest_free_sphere_mm": rep["largest_free_sphere"]["diameter_mm"],
            "largest_free_sphere_centre_mm": rep["largest_free_sphere"]["centre_mm"], "sheet_mass_kg": body_mass_kg, "module_mass_kg": module_mass_total_kg,
            "module_mass_fraction_of_sheet_mass": module_mass_total_kg / body_mass_kg,
            "remaining_mass_if_inside_budget_kg": body_mass_kg - module_mass_total_kg,
            "density_remaining_inside_budget_kg_per_l": (body_mass_kg - module_mass_total_kg) / free if free > 0 else None,
            "density_remaining_modules_additional_kg_per_l": body_mass_kg / free if free > 0 else None,
            "density_without_modules_kg_per_l": body_mass_kg / skin_inner}
