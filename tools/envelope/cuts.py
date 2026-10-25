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


def thigh_and_pelvis(inp, feats, reg, thigh_result, raster_z_hi=None):
    """Volumes (mm3) of the thigh variants (one side) and the pelvis slabs, plus the stations they are cut at."""
    sh = inp.sheet
    hjc_m = reg.mesh_nodes["hjc"]
    ljc_m = hjc_m + (sh.ljc - sh.hjc)                       # slope 1 above the hip-centre node
    apex_m = feats["crotch_apex_mm"]
    s_crotch = float(sh.hjc - reg.axial.forward(apex_m))     # station of the crotch-apex plane below the hip-centre plane, sheet frame
    seg = thigh_result.seg
    raster = features.BodyRaster(inp.V, inp.F, ljc_m + 20.0)
    z, a = core_area_profile(raster, apex_m - 10.0, ljc_m)
    vols = {
        "thigh_in": seg.volume(0.0),
        "thigh_out": seg.volume(0.0, 40.0, None),
        "thigh_crotch": seg.volume(0.0, s_crotch, None),
        "pelvis_hjc": stretched_volume(z, a, hjc_m, ljc_m, reg),
        "pelvis_crotch": stretched_volume(z, a, apex_m, ljc_m, reg),
    }
    return {"volumes_mm3": vols, "s_crotch_mm": s_crotch, "ljc_mesh_mm": ljc_m, "hjc_mesh_mm": hjc_m, "crotch_apex_mesh_mm": apex_m,
            "pelvis_core_area_mm2": {"z": z.tolist()[::10], "area": a.tolist()[::10]}, "raster_odd_columns": int(raster.odd)}
