"""Where a body mesh's volume sits, by anatomical region: feet, shanks, thighs, abdomen and pelvis, trunk above the tenth rib, head, arms.

The region split is for comparing meshes of the same topology (v1 posed, v1 at rest, v2) volume by volume (volume-extractor brief 4, item 2); it is not the
conformed segment of the envelope. Two steps.

Which vertices are arms is decided once, on the mesh where the arms hang free (the rest-pose v2), by `vertex_regions`: the mesh is rasterised (the parity
raster of `features.BodyRaster`), every horizontal layer is split into its connected pieces, and below the crotch apex a piece is a leg when its centroid is
within LEG_Y_MM_MAX of the midline and otherwise an arm, while from the apex up the largest piece is the core and the others are arms. The label belongs to
the vertex, so it carries to a posed mesh of the same topology, where the arms touch the body and no layer separates them.

Then each mesh's own raster cells are given to the arm label or to the rest by the nearest labelled vertex, and the rest is cut by horizontal planes: the AJC
and KJC planes make feet, shanks and thighs, the crotch apex to the tenth rib (Dumas MSR10) is "abdomen and pelvis", the tenth rib to the neck is the trunk
above the rib, the neck up is the head. A layer that straddles a plane is split by overlap, so a plane that falls between two layers moves no volume. Every
region sum equals the raster's total, which differs from the exact mesh volume by the raster's discretisation (reported by the caller).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

LEG_Y_MM_MAX = 300.0      # below the crotch apex a piece with its centroid this far from the midline is an arm, not a leg (thigh centroids are within ~130 mm; hands hang at 400+)
NECK_WINDOW = (0.80, 0.90)  # the neck is the narrowest core section between these fractions of the stature
REGIONS = ("feet", "shanks", "thighs", "abdomen_pelvis", "trunk_above_rib", "head", "arms")


def _layer_pieces(layer, h):
    """[(area mm2, centroid y, is the largest piece)] for the connected pieces of one boolean layer; y is the second grid axis offset by the caller."""
    lab, n = ndimage.label(layer)
    if n == 0:
        return [], lab
    idx = range(1, n + 1)
    area = np.asarray(ndimage.sum(layer, lab, idx)) * h * h
    cy = np.asarray(ndimage.mean(np.broadcast_to(np.arange(layer.shape[1])[None, :], layer.shape), lab, idx))
    big = int(np.argmax(area))
    return [(float(area[i]), float(cy[i]), i == big) for i in range(n)], lab


def profile(raster) -> dict:
    """Per layer of the raster: its start height, and the pieces as (area mm2, centroid y mm, is largest). Heights are in the raster's frame (mm above the sole)."""
    inside, h, o = raster.inside, raster.h, raster.o
    layers = []
    for k in range(inside.shape[2]):
        pieces, _ = _layer_pieces(inside[:, :, k], h)
        layers.append([(a, o[1] + h * (c + 0.5), big) for a, c, big in pieces])
    return {"h": float(h), "z0": o[2] + h * np.arange(inside.shape[2]), "layers": layers}


def total_volume(prof) -> float:
    """mm3, the raster's volume of the whole body."""
    return float(sum(a for L in prof["layers"] for a, _, _ in L) * prof["h"])


def _class_areas(prof, apex) -> dict:
    """Per-layer area (mm2) by class. A layer straddling the apex contributes to the below-apex classes by its overlap below and to the above-apex classes by the rest."""
    n, h = len(prof["layers"]), prof["h"]
    out = {c: np.zeros(n) for c in ("leg", "arm", "core")}
    for k, pieces in enumerate(prof["layers"]):
        f = float(np.clip((apex - prof["z0"][k]) / h, 0.0, 1.0))        # share of the layer below the apex
        for area, cy, big in pieces:
            if f > 0.0:
                out["leg" if abs(cy) <= LEG_Y_MM_MAX else "arm"][k] += area * f
            if f < 1.0:
                out["core" if big else "arm"][k] += area * (1.0 - f)
    return out


def _overlap(prof, lo, hi) -> np.ndarray:
    z0 = prof["z0"]
    return np.clip(np.minimum(z0 + prof["h"], hi) - np.maximum(z0, lo), 0.0, None)


def band(prof, cls, lo, hi, apex=0.0) -> float:
    """mm3 of class `cls` ('core', 'leg' or 'arm') between heights lo and hi (mm above the sole). `apex` is the crotch-apex height that separates the leg class
    (below) from the core (above); the default 0 puts everything above it."""
    return float((_class_areas(prof, apex)[cls] * _overlap(prof, lo, hi)).sum())


def neck_height(prof, stature_mm) -> float:
    """Height of the narrowest core section between 80% and 90% of the stature (the layer centre)."""
    area = _class_areas(prof, 0.0)["core"]
    zc = prof["z0"] + prof["h"] / 2
    m = (zc >= NECK_WINDOW[0] * stature_mm) & (zc <= NECK_WINDOW[1] * stature_mm) & (area > 0)
    k = np.flatnonzero(m)[int(np.argmin(area[m]))]
    return float(zc[k])


def labelled_profile(raster, V, arm_mask) -> dict:
    """Per layer of the raster, the area (mm2) of cells nearest to an arm-labelled vertex and of the rest. V are the mesh's vertices in the raster's frame,
    arm_mask the arm labels from `vertex_regions` on the reference mesh."""
    from scipy.spatial import cKDTree
    arm_mask = np.asarray(arm_mask, bool)
    h, o = raster.h, raster.o
    ii, jj, kk = np.nonzero(raster.inside)
    P = np.column_stack([o[0] + h * (ii + 0.5), o[1] + h * (jj + 0.5), o[2] + h * (kk + 0.5)])
    d_arm = cKDTree(V[arm_mask]).query(P, workers=-1)[0] if arm_mask.any() else np.full(len(P), np.inf)
    d_rest = cKDTree(V[~arm_mask]).query(P, workers=-1)[0]
    is_arm = d_arm < d_rest
    n = raster.inside.shape[2]
    return {"h": float(h), "z0": o[2] + h * np.arange(n), "arm": np.bincount(kk[is_arm], minlength=n) * h * h, "rest": np.bincount(kk[~is_arm], minlength=n) * h * h}


def region_volumes(lprof, planes) -> dict:
    """mm3 by region from a labelled profile. planes: ajc, kjc, apex, msr10, neck (and optionally top, default +inf), all mesh heights above the sole."""
    top = planes.get("top", np.inf)
    v = lambda cls, lo, hi: float((lprof[cls] * _overlap(lprof, lo, hi)).sum())
    return {
        "feet": v("rest", -np.inf, planes["ajc"]),
        "shanks": v("rest", planes["ajc"], planes["kjc"]),
        "thighs": v("rest", planes["kjc"], planes["apex"]),
        "abdomen_pelvis": v("rest", planes["apex"], planes["msr10"]),
        "trunk_above_rib": v("rest", planes["msr10"], planes["neck"]),
        "head": v("rest", planes["neck"], top),
        "arms": v("arm", -np.inf, np.inf),
    }


def vertex_regions(V, raster, planes) -> list:
    """'legs', 'torso', 'arms' or 'head' for every vertex (V in the raster's frame): the class of the piece the vertex sits on in its layer, found from the
    nearest inside cell when the vertex lies on the surface. Legs are the below-apex leg pieces, torso the core up to the neck plane, head the core above it."""
    h, o, inside = raster.h, raster.o, raster.inside
    apex, neck = planes["apex"], planes["neck"]
    out = [None] * len(V)
    cache = {}

    def layer_info(k):
        if k not in cache:
            L = inside[:, :, k]
            if not L.any():
                cache[k] = None
            else:
                pieces, lab = _layer_pieces(L, h)
                dist, near = ndimage.distance_transform_edt(~L, return_distances=True, return_indices=True)
                cache[k] = (lab, pieces, near, dist * h)
        return cache[k]

    nz = inside.shape[2]
    for n, p in enumerate(V):
        k0 = int(np.clip(np.floor((p[2] - o[2]) / h), 0, nz - 1))
        i = int(np.clip(np.floor((p[0] - o[0]) / h), 0, inside.shape[0] - 1))
        j = int(np.clip(np.floor((p[1] - o[1]) / h), 0, inside.shape[1] - 1))
        best = None
        for k in (k0 - 1, k0, k0 + 1):       # a vertex on a horizontal face sits on the boundary of two layers: take the nearest layer that holds the body there
            info = layer_info(k) if 0 <= k < nz else None
            if info is None:
                continue
            dz = max(o[2] + h * k - p[2], p[2] - (o[2] + h * (k + 1)), 0.0)
            d = float(np.hypot(info[3][i, j], dz))
            if best is None or d < best[0] - 1e-9:
                best = (d, info, o[2] + h * (k + 0.5))
        if best is None:
            out[n] = "torso"
            continue
        lab, pieces, near, _ = best[1]
        zl = best[2]                         # classify by the height of the layer the vertex was matched to, not its own: a vertex on a plane belongs to the layer it touches
        ni, nj = near[0][i, j], near[1][i, j]
        area, cy, big = pieces[int(lab[ni, nj]) - 1]
        cy_mm = o[1] + h * (cy + 0.5)
        if zl < apex:
            out[n] = "legs" if abs(cy_mm) <= LEG_Y_MM_MAX else "arms"
        elif not big:
            out[n] = "arms"
        else:
            out[n] = "head" if zl > neck else "torso"
    return out
