"""The mass base: whole-body mesh volume, body density (Siri), expected segment masses and the densities they imply for the envelope's skin volumes.

BODY_FAT_FRACTION and V_LUNG_L (value and source) are Joe's inputs, in `data/envelope/body_density.json`. Until they are supplied the report gives the
bracket f = 0.15 and 0.35 and says so; nothing here picks a value.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .sheet import StopAndAsk

PATH = "data/envelope/body_density.json"
BRACKET = (0.15, 0.35)                    # the brief's sensitivity bracket for the body fat fraction
BLENDER_TOLERANCE = 0.005                 # the brief: the computed volume must match Joe's Blender volume within 0.5%
REFERENCE_DENSITY = {"thigh": 1.05, "shank": 1.09, "foot": 1.10}   # kg/l, Dempster-type values quoted in the brief; eyeballing only
PELVIS_REFERENCE_DENSITY = 1.01   # kg/l, Dempster's abdomen-pelvis value as I recall it from Winter's tables; the brief gives none for the pelvis (a question for Joe)


def body_density(f: float) -> float:
    """kg/l from the body fat fraction: Siri 1956, UCRL-3349, equation (10): D = 4.950 / (f + 4.500)."""
    return 4.950 / (f + 4.500)


def mesh_volume_l(V, F) -> float:
    """Signed volume of the closed triangle mesh (V in mm), in litres."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0 / 1e6)


def load_constants(root: Path) -> dict:
    p = root / PATH
    if not p.exists():
        raise StopAndAsk(f"{PATH} is missing (BODY_FAT_FRACTION, V_LUNG_L with sources, and Joe's Blender volume)")
    return json.loads(p.read_text(encoding="utf-8"))


def report(inp, results: dict, constants: dict, cuts: dict | None = None) -> dict:
    """results: segment name -> SegResult for thigh, shank, foot. cuts: the output of cuts.thigh_and_pelvis (adds the thigh variants, the pelvis and the
    lumped thigh+pelvis rows). Returns the mass-base tables (plain data).

    Mass share is the sheet's segment mass over the sheet total; volume share is the segment's skin volume over the whole mesh volume (lung gas
    included); their ratio is what a tissue of the segment's density over the mean mesh density would give, so ratio / expected tissue ratio, with
    expected = reference density / (M_mesh / V_mesh), is 1 when the sculpt's share matches the sheet's."""
    V_mesh = mesh_volume_l(inp.V, inp.F)
    blender = constants.get("blender_volume_m3")
    blender_l = blender * 1000.0 if blender else None
    out = {"mesh_volume_l": V_mesh, "blender_volume_l": blender_l,
           "blender_relative_difference": (V_mesh - blender_l) / blender_l if blender_l else None,
           "blender_within_tolerance": bool(abs(V_mesh - blender_l) / blender_l <= BLENDER_TOLERANCE) if blender_l else None}
    f_nom = constants.get("body_fat_fraction")
    v_lung = constants.get("v_lung_l")
    out["constants"] = {"body_fat_fraction": f_nom, "body_fat_source": constants.get("body_fat_source"), "v_lung_l": v_lung, "v_lung_source": constants.get("v_lung_source"),
                        "v_lung_supplied": v_lung is not None, "body_fat_supplied": f_nom is not None,
                        "density_formula": "BODY_DENSITY = 4.950 / (BODY_FAT_FRACTION + 4.500), Siri 1956, UCRL-3349 eq. (10); M_mesh = BODY_DENSITY x (V_mesh - V_LUNG)"}
    vl = v_lung or 0.0
    cases = {f"f={f:g}": f for f in BRACKET}
    if f_nom is not None:
        cases = {"nominal": f_nom, **cases}
    out["cases"] = {}
    stature_m = inp.stature_mesh / 1000.0
    total = inp.sheet.total_mass_kg
    for label, f in cases.items():
        D = body_density(f)
        M = D * (V_mesh - vl)
        out["cases"][label] = {"body_fat_fraction": f, "body_density_kg_per_l": D, "mesh_mass_kg": M, "mean_mesh_density_kg_per_l": M / V_mesh,
                               "sculpt_bmi_kg_per_m2": M / stature_m ** 2, "sheet_total_mass_kg": total, "sheet_total_over_mesh_mass": total / M,
                               "robot_required_average_density_kg_per_l": total / (V_mesh - vl)}
    sh = inp.sheet
    mass = {"thigh": sh.thigh_mass_kg, "shank": sh.shank_mass_kg, "foot": sh.foot_mass_kg, "pelvis": sh.pelvis_mass_kg}
    rows = {}

    def add(name, volume_l, mass_kg, ref, mass_label=None):
        share_m = mass_kg / total
        share_v = volume_l / V_mesh
        row = {"volume_l": volume_l, "mass_kg_sheet": mass_kg, "mass_share": share_m, "volume_share": share_v, "ratio": share_m / share_v, "reference_density_kg_per_l": ref, "cases": {}}
        for label in cases:
            c = out["cases"][label]
            expected = ref / c["mean_mesh_density_kg_per_l"]
            M = share_m * c["mesh_mass_kg"]
            row["cases"][label] = {"expected_tissue_ratio": expected, "normalised_ratio": row["ratio"] / expected, "expected_mass_kg": M, "implied_density_kg_per_l": M / volume_l}
        rows[name] = row

    for name, r in results.items():
        add(name, r.seg.volume(0.0) / 1e6, mass[name], REFERENCE_DENSITY[name])
        rows[name]["inner_volume_l"] = {f"t{t:g}": r.seg.volume(t) / 1e6 for t in (3.0, 5.0, 8.0, 10.0)}
    if cuts:
        v = cuts["volumes_mm3"]
        for k in ("in", "out", "crotch"):
            add(f"thigh_{k}", v[f"thigh_{k}"] / 1e6, mass["thigh"], REFERENCE_DENSITY["thigh"])
        for k in ("hjc", "crotch"):
            add(f"pelvis_{k}", v[f"pelvis_{k}"] / 1e6, mass["pelvis"], PELVIS_REFERENCE_DENSITY)
        for k, th in (("hjc", "in"), ("crotch", "crotch")):
            # both thighs (the mesh is left-right symmetric to under 0.5%) and the pelvis; the reference density is the mass-weighted mean of the parts'
            vol = 2 * v[f"thigh_{th}"] / 1e6 + v[f"pelvis_{k}"] / 1e6
            m = 2 * mass["thigh"] + mass["pelvis"]
            ref = (2 * mass["thigh"] * REFERENCE_DENSITY["thigh"] + mass["pelvis"] * PELVIS_REFERENCE_DENSITY) / m
            add(f"thigh_pelvis_{k}", vol, m, ref)
        out["cut_stations"] = {"crotch_below_hip_centre_mm": cuts["s_crotch_mm"], "hip_zone_mm": 40.0, "ljc_mesh_mm": cuts["ljc_mesh_mm"]}
    out["rows"] = rows
    out["stature_mesh_m"] = stature_m
    return out
