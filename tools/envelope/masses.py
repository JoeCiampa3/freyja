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


def report(inp, results: dict, constants: dict) -> dict:
    """results: segment name -> SegResult for thigh, shank, foot. Returns the mass-base tables (plain data)."""
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
                        "density_formula": "BODY_DENSITY = 4.950 / (BODY_FAT_FRACTION + 4.500), Siri 1956, UCRL-3349 eq. (10)"}
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
        out["cases"][label] = {"body_fat_fraction": f, "body_density_kg_per_l": D, "mesh_mass_kg": M, "sculpt_bmi_kg_per_m2": M / stature_m ** 2,
                               "sheet_total_mass_kg": total, "sheet_total_over_mesh_mass": total / M, "robot_required_average_density_kg_per_l": total / (V_mesh - vl)}
    segs = {}
    for name, r in results.items():
        seg = r.seg
        frac = r.mass_kg / total
        row = {"sheet_mass_kg": r.mass_kg, "sheet_mass_fraction": frac, "skin_volume_l": seg.volume(0.0) / 1e6,
               "inner_volume_l": {f"t{t:g}": seg.volume(t) / 1e6 for t in (3.0, 5.0, 8.0, 10.0)}, "reference_density_kg_per_l": REFERENCE_DENSITY[name], "cases": {}}
        for label, f in cases.items():
            M = out["cases"][label]["mesh_mass_kg"]
            row["cases"][label] = {"expected_mass_kg": frac * M, "implied_density_kg_per_l": frac * M / row["skin_volume_l"]}
        if name == "thigh":
            from .trial import HIP_ZONE_MM
            v_ex = seg.volume(0.0, HIP_ZONE_MM, None) / 1e6
            row["skin_volume_excluding_hip_zone_l"] = v_ex
            row["hip_zone_mm"] = HIP_ZONE_MM
            row["cases_excluding_hip_zone"] = {label: {"implied_density_kg_per_l": frac * out["cases"][label]["mesh_mass_kg"] / v_ex} for label in cases}
        segs[name] = row
    out["segments"] = segs
    out["stature_mesh_m"] = stature_m
    return out
