"""Where the thigh ends and the pelvis begins: the thigh's cut variants and a pelvis slab, so a thigh+pelvis total does not depend on the cut.

Variants of the thigh (right side, conformed): `in` (the slab from the hip-centre plane, hip zone included), `out` (stations beyond the 40 mm hip
zone) and `crotch` (the slab below the crotch-apex plane). The pelvis is the whole-width body slab between a lower plane and the lumbosacral-joint
plane (the pelvis body's origin in the snapshot), arms excluded as the connected body: for the `in` variant its lower plane is the hip-centre
plane, for the `crotch` variant the crotch apex. The axial stretch applies below the hip-centre node and the slope is 1 above it.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import features

PROFILE_STEP_MM = 2.0
RASTER_PAD_MM = 40.0        # the pelvis raster reaches this far above the lumbosacral plane


def core_area_profile(raster: features.BodyRaster, z_lo, z_hi, step=PROFILE_STEP_MM):
    """(z, area mm2) of the largest connected piece of the body's horizontal section (arms are separate pieces and so are left out)."""
    zs = np.arange(z_lo, z_hi + 1e-9, step)
    a = []
    for z in zs:
        lab, n = ndimage.label(raster.layer(z))
        a.append(float(ndimage.sum(raster.layer(z), lab, range(1, n + 1)).max() * raster.h ** 2) if n else 0.0)
    return zs, np.array(a)


def stretched_volume(z, area, lo, hi, reg):
    """Conformed volume (mm3) of the whole-width slab between mesh heights lo and hi: the area profile integrated with the registration's height map,
    which is the thigh stretch below the hip-centre node and slope 1 above it."""
    zz = np.linspace(lo, hi, max(2, int((hi - lo) / 1.0)))
    f = reg.axial.forward(zz)
    return float(np.trapezoid(np.interp(zz, z, area), f))


def landmark_heights(ansur, stature_mesh, names=("iliocristale", "tenth_rib")) -> dict:
    """Mesh heights (mm above the sole) of ANSUR II landmarks: ratio mean x the mesh stature, with the one-SD band (lo, hi) and the SD in mm."""
    out = {}
    for n in names:
        r = ansur["landmarks"][n]["ratio"]
        m, sd = r["mean"] * stature_mesh, r["sd"] * stature_mesh
        out[n] = {"mean": m, "lo": m - sd, "hi": m + sd, "sd": sd}
    return out


def dumas_cut_heights(table: dict, abdomen_length_mm: float, ljc_mesh_mm: float) -> dict:
    """Mesh heights (mm above the sole) of the Dumas 2015 Table 1 abdomen landmarks. The table's Y (up) axis runs along the abdomen from TJC (0) down to LJC
    (-121 for the reference women, Table 2); a landmark at Y sits (Y - Y_LJC) x s above the LJC plane, with s = the sheet's abdomen length over the reference
    length. Only the height is used: each cut is a horizontal plane. `ljc_mesh_mm` is the lumbosacral plane in the mesh frame."""
    seg = table["segments"]["abdomen"]["landmarks"]
    ref = float(table["reference_length_mm"]["abdomen"])
    y_ljc = seg["LJC"][1]
    s = abdomen_length_mm / ref
    out = {"scale": s, "LJC": ljc_mesh_mm, "TJC": ljc_mesh_mm + abdomen_length_mm}
    for name in ("MSR10", "RR10", "RI", "RASIS"):
        out[name] = ljc_mesh_mm + (seg[name][1] - y_ljc) * s
    return out


def lumped_volume(z, area, apex_m, top_m, reg, thigh_below_apex_mm3):
    """Conformed volume (mm3) of the region from the KJC planes up to mesh height `top_m`: the connected-body slab from the crotch apex, plus both thighs
    below the apex (each leg is a separate piece there, the right one doubled). No pelvis/thigh or pelvis/abdomen cut enters."""
    return stretched_volume(z, area, apex_m, top_m, reg) + 2.0 * thigh_below_apex_mm3


def thigh_and_pelvis(inp, feats, reg, thigh_result, table=None, raster_z_hi=None):
    """Volumes (mm3) of the thigh variants (one side), the pelvis slabs, the abdomen slab and the lumped region, plus the stations they are cut at. The frame
    cuts are unchanged: the pelvis with its top at the lumbosacral plane (`pelvis_hjc`, `pelvis_crotch`). Beside them, with the Dumas 2015 Table 1 landmarks
    (`table`, the primary cuts): the pelvis topped at RI (`pelvis_*_ri`, and `_ri_p10`/`_ri_m10` for RI moved 10 mm up/down), the abdomen from MSR10 down to RI
    (`abdomen`, its `_ri_*` and `_msr10_*` +-10 mm variants, and `abdomen_rr10` with RR10 as the top), the lumped region from MSR10 down to the KJC planes
    (`lumped_msr10`, `_p10`/`_m10`, and `lumped_rr10`). The ANSUR iliocristale (mean, -1 SD `_lo`, +1 SD `_hi`) and tenth-rib heights remain as cross-checks:
    `pelvis_*_ilio*` and `lumped`, `lumped_lo`, `lumped_hi`."""
    sh = inp.sheet
    hjc_m = reg.mesh_nodes["hjc"]
    ljc_m = hjc_m + (sh.ljc - sh.hjc)                       # slope 1 above the hip-centre node
    apex_m = feats["crotch_apex_mm"]
    s_crotch = float(sh.hjc - reg.axial.forward(apex_m))     # station of the crotch-apex plane below the hip-centre plane, sheet frame
    seg = thigh_result.seg
    lm = landmark_heights(inp.ansur, inp.stature_mesh)
    dh = dumas_cut_heights(table, sh.abdomen_length_mm, ljc_m) if table else None
    top_m = max(ljc_m, lm["tenth_rib"]["hi"], lm["iliocristale"]["hi"], *( [dh["MSR10"] + 10.0] if dh else [] ))
    raster = features.BodyRaster(inp.V, inp.F, top_m + 20.0)
    z, a = core_area_profile(raster, apex_m - 10.0, top_m)
    vols = {
        "thigh_in": seg.volume(0.0),
        "thigh_out": seg.volume(0.0, 40.0, None),
        "thigh_crotch": seg.volume(0.0, s_crotch, None),
        "pelvis_hjc": stretched_volume(z, a, hjc_m, ljc_m, reg),
        "pelvis_crotch": stretched_volume(z, a, apex_m, ljc_m, reg),
    }
    for suffix, key in (("", "mean"), ("_lo", "lo"), ("_hi", "hi")):
        vols[f"pelvis_hjc_ilio{suffix}"] = stretched_volume(z, a, hjc_m, lm["iliocristale"][key], reg)
        vols[f"pelvis_crotch_ilio{suffix}"] = stretched_volume(z, a, apex_m, lm["iliocristale"][key], reg)
        vols[f"lumped{suffix}" if suffix else "lumped"] = lumped_volume(z, a, apex_m, lm["tenth_rib"][key], reg, vols["thigh_crotch"])
    if dh:
        sv = lambda lo, hi: stretched_volume(z, a, lo, hi, reg)
        ri, msr, rr = dh["RI"], dh["MSR10"], dh["RR10"]
        vols["abdomen"] = sv(ri, msr)
        vols["abdomen_rr10"] = sv(ri, rr)
        for tag, d in (("p10", 10.0), ("m10", -10.0)):
            vols[f"abdomen_ri_{tag}"] = sv(ri + d, msr)
            vols[f"abdomen_msr10_{tag}"] = sv(ri, msr + d)
        for k, lo in (("hjc", hjc_m), ("crotch", apex_m)):
            vols[f"pelvis_{k}_ri"] = sv(lo, ri)
            vols[f"pelvis_{k}_ri_p10"] = sv(lo, ri + 10.0)
            vols[f"pelvis_{k}_ri_m10"] = sv(lo, ri - 10.0)
        vols["lumped_msr10"] = lumped_volume(z, a, apex_m, msr, reg, vols["thigh_crotch"])
        vols["lumped_msr10_p10"] = lumped_volume(z, a, apex_m, msr + 10.0, reg, vols["thigh_crotch"])
        vols["lumped_msr10_m10"] = lumped_volume(z, a, apex_m, msr - 10.0, reg, vols["thigh_crotch"])
        vols["lumped_rr10"] = lumped_volume(z, a, apex_m, rr, reg, vols["thigh_crotch"])
    # the profile is the largest connected piece: a jump between neighbouring layers would mean an arm has merged with the trunk
    step = np.abs(np.diff(a)) / np.maximum(a[:-1], 1.0)
    return {"volumes_mm3": vols, "s_crotch_mm": s_crotch, "ljc_mesh_mm": ljc_m, "hjc_mesh_mm": hjc_m, "crotch_apex_mesh_mm": apex_m,
            "dumas_cut_heights_mesh_mm": dh,
            "pelvis_core_area_mm2": {"z": z.tolist()[::10], "area": a.tolist()[::10]}, "raster_odd_columns": int(raster.odd),
            "landmark_heights_mesh_mm": lm, "core_profile_top_mesh_mm": top_m, "core_profile_max_layer_step_fraction": float(step.max())}
