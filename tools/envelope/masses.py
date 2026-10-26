"""The mass base: whole-body mesh volume, body density (Siri), expected segment masses and the densities they imply for the envelope's skin volumes.

BODY_FAT_FRACTION and V_LUNG_L (value and source) are Joe's inputs, in `data/envelope/body_density.json`. Until they are supplied the report gives the
bracket f = 0.15 and 0.35 and says so; nothing here picks a value. The reference densities are Joe's transcription of Winter's Table 4.1
(`data/envelope/reference_densities.json`) and the mass-cut landmarks are Dumas 2015 Table 1 (`data/envelope/dumas2015_table1_female.json`).

The primary share number is the raw ratio: the sheet's mass share over the sculpt's volume share. Dumas 2015 (p.116) expresses the reference segment masses
under a uniform density of 1 g/cm3, so the sheet's shares are volume shares of the reference women and 1.00 means the same distribution (lung gas is in both).
The Dempster-normalised ratio (raw ratio over reference density / mean mesh density) is secondary.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .sheet import StopAndAsk

PATH = "data/envelope/body_density.json"
BRACKET = (0.15, 0.35)                    # the brief's sensitivity bracket for the body fat fraction
BLENDER_TOLERANCE = 0.005                 # the brief: the computed volume must match Joe's Blender volume within 0.5%
DENSITIES_PATH = "data/envelope/reference_densities.json"
DUMAS_TABLE1_PATH = "data/envelope/dumas2015_table1_female.json"


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


def load_densities(root: Path) -> dict:
    """segment name -> reference density (kg/l) as `use` in the densities file maps it onto Winter's rows: thigh, shank, foot, abdomen, pelvis, abdomen_and_pelvis."""
    p = root / DENSITIES_PATH
    if not p.exists():
        raise StopAndAsk(f"{DENSITIES_PATH} is missing (Winter, Table 4.1 densities, transcribed by Joe)")
    d = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for seg, row in d["use"].items():
        if seg == "use_note":
            continue
        rho = d["rows"][row]["density_kg_per_l"]
        if rho is None:
            raise StopAndAsk(f"{DENSITIES_PATH}: row {row!r} has no density, needed for {seg!r}")
        out[seg] = float(rho)
    return out


def load_dumas_table1(root: Path) -> dict:
    p = root / DUMAS_TABLE1_PATH
    if not p.exists():
        raise StopAndAsk(f"{DUMAS_TABLE1_PATH} is missing (Dumas 2015 Table 1, female)")
    return json.loads(p.read_text(encoding="utf-8"))


def blender_volume_m3(constants: dict, mesh_label: str | None):
    """Joe's Blender volume for the mesh being measured: `blender_volume_m3` is the v1 mesh's (the original key), `blender_volume_v2_m3` the v2 mesh's;
    None when the mesh has no entry."""
    key = "blender_volume_v2_m3" if mesh_label and "body-v2" in mesh_label else "blender_volume_m3"
    return constants.get(key)


def report(inp, results: dict, constants: dict, cuts: dict | None = None, densities: dict | None = None, mesh_label: str | None = None) -> dict:
    """results: segment name -> SegResult for thigh, shank, foot. cuts: the output of cuts.thigh_and_pelvis (adds the thigh variants, the pelvis and the
    lumped thigh+pelvis rows). Returns the mass-base tables (plain data).

    Mass share is the sheet's segment mass over the sheet total; volume share is the segment's skin volume over the whole mesh volume (lung gas
    included); their ratio is what a tissue of the segment's density over the mean mesh density would give, so ratio / expected tissue ratio, with
    expected = reference density / (M_mesh / V_mesh), is 1 when the sculpt's share matches the sheet's."""
    if densities is None:
        densities = load_densities(Path(__file__).resolve().parents[2])
    V_mesh = mesh_volume_l(inp.V, inp.F)
    blender = blender_volume_m3(constants, mesh_label)
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
        row = {"volume_l": volume_l, "mass_kg_sheet": mass_kg, "sheet_mass_per_skin_volume_kg_per_l": mass_kg / volume_l, "mass_share": share_m, "volume_share": share_v, "ratio": share_m / share_v, "reference_density_kg_per_l": ref, "cases": {}}
        for label in cases:
            c = out["cases"][label]
            expected = ref / c["mean_mesh_density_kg_per_l"]
            M = share_m * c["mesh_mass_kg"]
            row["cases"][label] = {"expected_tissue_ratio": expected, "normalised_ratio": row["ratio"] / expected, "expected_mass_kg": M, "implied_density_kg_per_l": M / volume_l}
        rows[name] = row

    for name, r in results.items():
        add(name, r.seg.volume(0.0) / 1e6, mass[name], densities[name])
        rows[name]["inner_volume_l"] = {f"t{t:g}": r.seg.volume(t) / 1e6 for t in (3.0, 5.0, 8.0, 10.0)}
    if cuts:
        v = cuts["volumes_mm3"]
        m_tp = 2 * mass["thigh"] + mass["pelvis"]
        ref_tp = (2 * mass["thigh"] * densities["thigh"] + mass["pelvis"] * densities["pelvis"]) / m_tp
        m_lump = sh.abdomen_mass_kg + mass["pelvis"] + 2 * mass["thigh"]
        # the abdomen-plus-pelvis part takes Winter's combined density directly; the thighs their own
        ref_lump = ((sh.abdomen_mass_kg + mass["pelvis"]) * densities["abdomen_and_pelvis"] + 2 * mass["thigh"] * densities["thigh"]) / m_lump
        for k in ("in", "out", "crotch"):
            add(f"thigh_{k}", v[f"thigh_{k}"] / 1e6, mass["thigh"], densities["thigh"])
        thigh_of = {"hjc": "in", "crotch": "crotch"}
        # pelvis variants by top: the lumbosacral plane (frame cut, ''), the ANSUR iliocristale (mean, -1 SD, +1 SD) and the Dumas RI (mean, +-10 mm)
        for suffix in ("", "_ilio", "_ilio_lo", "_ilio_hi", "_ri", "_ri_p10", "_ri_m10"):
            for k, th in thigh_of.items():
                key = f"pelvis_{k}{suffix}"
                if key not in v:
                    continue
                add(key, v[key] / 1e6, mass["pelvis"], densities["pelvis"])
                add(f"thigh_pelvis_{k}{suffix}", (2 * v[f"thigh_{th}"] + v[key]) / 1e6, m_tp, ref_tp)
        # the abdomen slab (Dumas MSR10 to RI, its variants) and the lumped region (abdomen + pelvis + both thighs, top to the KJC planes)
        for key in sorted(k for k in v if k.startswith("abdomen")):
            add(key, v[key] / 1e6, sh.abdomen_mass_kg, densities["abdomen"])
        for key in ("lumped", "lumped_lo", "lumped_hi") + tuple(sorted(k for k in v if k.startswith("lumped_msr10") or k == "lumped_rr10")):
            if key in v:
                add(key, v[key] / 1e6, m_lump, ref_lump)
        if "abdomen" in v:
            out["cut_diagnostics_per_10mm_l"] = {
                "label": "diagnostic",
                "abdomen_ri": (v["abdomen_ri_p10"] - v["abdomen_ri_m10"]) / 2.0 / 1e6,
                "abdomen_msr10": (v["abdomen_msr10_p10"] - v["abdomen_msr10_m10"]) / 2.0 / 1e6,
                "note": "volume change of the abdomen slab per 10 mm of the named cut moving up (central difference of the +-10 mm rows, litres); a diagnostic, not a result"}
        out["cut_stations"] = {"crotch_below_hip_centre_mm": cuts["s_crotch_mm"], "hip_zone_mm": 40.0, "ljc_mesh_mm": cuts["ljc_mesh_mm"]}
        out["dempster_lumped_check"] = dempster_lumped_check(sh, mass, densities)
    out["rows"] = rows
    out["stature_mesh_m"] = stature_m
    return out


def dempster_lumped_check(sh, mass: dict, densities: dict | None = None) -> dict:
    """Winter's Table 4.1 lumped share (abdomen and pelvis 0.281 + two thighs 0.100 each) against the sheet's mass share of abdomen + pelvis + two thighs."""
    root = Path(__file__).resolve().parents[2]
    rows = json.loads((root / DENSITIES_PATH).read_text(encoding="utf-8"))["rows"]
    d = rows["abdomen_and_pelvis"]["mass_fraction"] + 2 * rows["thigh"]["mass_fraction"]
    m = sh.abdomen_mass_kg + mass["pelvis"] + 2 * mass["thigh"]
    return {"dempster_share": d, "sheet_share": m / sh.total_mass_kg, "sheet_minus_dempster": m / sh.total_mass_kg - d, "sheet_mass_kg": m,
            "source": "Winter Table 4.1 (after Dempster 1955): abdomen and pelvis 0.281 + 2 x thigh 0.100"}
