"""Features read off the MakeHuman mesh (sheet frame, mm): sole plane, leg breadth profile and knee level, crotch apex, section centroids."""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import field

GAP_CLOSED_MM = 5.0          # legs count as joined where the gap between the inner thigh surfaces is below this
KNEE_BAND_MM = 50.0          # half-width of the knee search band around the ANSUR estimate
KNEE_PROMINENCE_MM = 3.0     # a breadth peak must stand this far above the band's lowest breadth to count as a feature
LEG_Y_MM = (-260.0, -30.0)   # right-leg strip used for the breadth profile (the arms are well outside it below the crotch)
GRID_MM = 2.0                # whole-body raster used for the section centroids


class Cuts:
    """Horizontal cuts of the surface: the points where mesh edges cross a plane."""

    def __init__(self, V, F):
        E = np.unique(np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1), axis=0)
        self.a, self.b = V[E[:, 0]], V[E[:, 1]]

    def points(self, z):
        m = (self.a[:, 2] - z) * (self.b[:, 2] - z) < 0
        t = (z - self.a[m, 2]) / (self.b[m, 2] - self.a[m, 2])
        return self.a[m] + (self.b[m] - self.a[m]) * t[:, None]


def sole_plane(V) -> dict:
    """The sole plane is the lowest vertex; flatness is the height difference between the lowest vertices of the two feet and the number of
    vertices within 1 mm / 3 mm of it."""
    z0 = float(V[:, 2].min())
    low = V[V[:, 2] < z0 + 10.0]
    r, l = low[low[:, 1] < 0], low[low[:, 1] >= 0]
    return {"z_mm": z0, "right_foot_lowest_mm": float(r[:, 2].min() - z0), "left_foot_lowest_mm": float(l[:, 2].min() - z0),
            "vertices_within_1mm": int((V[:, 2] < z0 + 1.0).sum()), "vertices_within_3mm": int((V[:, 2] < z0 + 3.0).sum())}


def midline_y(V, z_floor) -> float:
    """The mesh's sagittal plane: centred on the feet's lateral extent (the MakeHuman base mesh is left-right symmetric)."""
    f = V[V[:, 2] < z_floor + 10.0]
    return float((f[:, 1].min() + f[:, 1].max()) / 2)


def crotch_apex(cuts: Cuts, y_mid, z_lo, z_hi, step=0.5):
    """Lowest height at which the two legs are joined (scanning up from an open start): the gap between the right-most point of the left half and the left-most of the right
    half, at or below GAP_CLOSED_MM. Returns (height, gap profile as arrays)."""
    zs = np.arange(z_lo, z_hi, step)
    gaps = []
    for z in zs:
        P = cuts.points(z)
        P = P[np.abs(P[:, 1] - y_mid) < 200.0]
        r, l = P[P[:, 1] < y_mid, 1], P[P[:, 1] >= y_mid, 1]
        gaps.append(l.min() - r.max() if len(r) and len(l) else 0.0)
    gaps = np.array(gaps)
    closed = gaps < GAP_CLOSED_MM
    if closed[0]:
        raise ValueError("the legs are already joined at the bottom of the search range")
    k = int(np.argmax(closed))          # the first closed level above the open region that starts at the bottom
    if not closed.any():
        raise ValueError("legs are open over the whole search range")
    return float(zs[min(k, len(zs) - 1)]), zs, gaps


def breadth_profile(cuts: Cuts, y_mid, z_lo, z_hi, step=2.0):
    """Mediolateral breadth (mm) of the right leg's section at each height, from the surface crossings in the leg strip."""
    zs = np.arange(z_lo, z_hi, step)
    br = []
    for z in zs:
        P = cuts.points(z)
        P = P[(P[:, 1] - y_mid > LEG_Y_MM[0]) & (P[:, 1] - y_mid < LEG_Y_MM[1])]
        br.append(np.ptp(P[:, 1]) if len(P) else 0.0)
    return zs, np.array(br)


def knee_level(zs, br, centre, band=KNEE_BAND_MM) -> dict:
    """Height of the maximum breadth inside centre +- band, with how much it stands out (max minus min over the band) and whether the maximum
    sits on a band edge. A feature only if prominence >= KNEE_PROMINENCE_MM and the maximum is interior."""
    m = (zs >= centre - band) & (zs <= centre + band)
    zz, bb = zs[m], br[m]
    sm = ndimage.uniform_filter1d(bb, 5, mode="nearest")
    k = int(np.argmax(sm))
    prominence = float(sm.max() - sm.min())
    on_edge = k <= 1 or k >= len(zz) - 2
    return {"z_mm": float(zz[k]), "breadth_mm": float(sm[k]), "prominence_mm": prominence, "on_band_edge": bool(on_edge),
            "is_feature": bool(prominence >= KNEE_PROMINENCE_MM and not on_edge)}


class BodyRaster:
    """Inside/outside raster of the body below `z_hi` (heights above the sole), for section centroids."""

    def __init__(self, V, F, z_hi, h=GRID_MM, margin=6.0):
        x0, x1 = V[:, 0].min() - margin, V[:, 0].max() + margin
        y0, y1 = V[:, 1].min() - margin, V[:, 1].max() + margin
        self.h = h
        self.o = np.array([x0, y0, -margin])
        shape = (int(np.ceil((x1 - x0) / h)), int(np.ceil((y1 - y0) / h)), int(np.ceil((z_hi + margin) / h)))
        self.inside, self.odd = field.parity_inside(V, F, self.o, h, shape)

    def layer(self, z):
        return self.inside[:, :, int(np.clip(np.floor((z - self.o[2]) / self.h), 0, self.inside.shape[2] - 1))]

    def right_section(self, z, y_mid):
        """(area mm2, centroid (x, y), mask) of the largest connected piece of the section right of the midline at height z."""
        L = self.layer(z)
        yc = self.o[1] + self.h * (np.arange(L.shape[1]) + 0.5)
        right = L & (yc[None, :] < y_mid)
        lab, n = ndimage.label(right)
        if n == 0:
            return 0.0, (float("nan"), float("nan")), right
        areas = ndimage.sum(right, lab, range(1, n + 1))
        m = lab == (1 + int(np.argmax(areas)))
        ii, jj = np.nonzero(m)
        return float(areas.max() * self.h ** 2), (float(self.o[0] + self.h * (ii.mean() + 0.5)), float(self.o[1] + self.h * (jj.mean() + 0.5))), m
