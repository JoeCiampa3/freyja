"""The voxel field of a segment: inside/outside by x-ray parity, signed distance (positive inside) to the skin, regions, sections.

Distances are to the skin of the *extended* solid (the whole mesh handed in, margin included); the slab only masks the result, so cut
planes never shrink the inscribed radius near the ends. The frame is the segment frame: z up, the slab is z in [z_top - length, z_top],
x anterior, y left; station s is the distance below z_top.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

SAMPLE_MM = 1.0            # skin sampling spacing: sets the distance error (< ~0.4 mm RMS)
BAND_MM = 10.0             # within this distance of the skin sd is a nearest-sample query; deeper, it is carried inward from the band's inner edge
JITTER = (0.00731, 0.00419)   # fraction of a voxel by which the parity columns are moved off the grid, so no ray runs along an edge or vertex
SECTION_MM = 0.5           # raster of the 2-D sections


def watertight(faces, subset=None) -> dict:
    """Edge statistics of a triangle index mesh: boundary edges (one face) and non-manifold edges (more than two). With `subset` (a bool mask
    or index array of faces), only the edges of those faces are reported, counted against the whole mesh."""
    f = np.asarray(faces)
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    uniq, inv, counts = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    if subset is not None:
        sel = np.asarray(subset)
        if sel.dtype != bool:
            sel = np.isin(np.arange(len(f)), sel)
        used = np.zeros(len(uniq), bool)
        used[inv.ravel()[np.tile(sel, 3)]] = True
        counts = counts[used]
    return {"boundary_edges": int((counts == 1).sum()), "nonmanifold_edges": int((counts > 2).sum()), "edges": int(len(counts))}


def contains(v, f, p) -> bool:
    """Whether point p is inside the closed mesh (odd crossings of the +x ray, slightly off-axis so it avoids edges and vertices)."""
    p = np.asarray(p, float) + np.array([0.0, 1.3e-3, 0.9e-3])
    T = v[f]
    y, z = p[1], p[2]
    ok = (T[:, :, 1].min(1) <= y) & (T[:, :, 1].max(1) >= y) & (T[:, :, 2].min(1) <= z) & (T[:, :, 2].max(1) >= z)
    n = 0
    for P in T[ok]:
        (y0, z0), (y1, z1), (y2, z2) = P[:, 1:]
        den = (y1 - y0) * (z2 - z0) - (y2 - y0) * (z1 - z0)
        if den == 0:
            continue
        l1 = ((y - y0) * (z2 - z0) - (y2 - y0) * (z - z0)) / den
        l2 = ((y1 - y0) * (z - z0) - (y - y0) * (z1 - z0)) / den
        if l1 >= 0 and l2 >= 0 and l1 + l2 <= 1 and P[0, 0] + l1 * (P[1, 0] - P[0, 0]) + l2 * (P[2, 0] - P[0, 0]) > p[0]:
            n += 1
    return n % 2 == 1


def sample_surface(v, f, spacing=SAMPLE_MM):
    """Points on the triangles such that every surface point is within `spacing` of one: triangles are halved across their longest edge
    until that edge is at most 2 x `spacing` (long slivers cost one split per spacing, not a full lattice), and the corners are returned."""
    T = v[f]                                   # (n, 3, 3)
    out = [v]
    while len(T):
        e = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1), np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], axis=1)
        k = e.argmax(axis=1)
        big = e[np.arange(len(T)), k] > 2 * spacing
        if not big.any():
            break
        Tb, kb = T[big], k[big]
        # rotate so that the longest edge is corners (0, 1): corner order (k, k+1, k+2)
        idx = (kb[:, None] + np.arange(3)[None, :]) % 3
        P = np.take_along_axis(Tb, idx[:, :, None], axis=1)
        mid = (P[:, 0] + P[:, 1]) / 2
        out.append(mid)
        T = np.concatenate([np.stack([P[:, 0], mid, P[:, 2]], axis=1), np.stack([mid, P[:, 1], P[:, 2]], axis=1)])
    return np.vstack(out)


def parity_inside(v, f, o, h, shape):
    """(inside, odd): boolean grid of the cell centres o + h*(i + .5) with an odd number of crossings of the +x ray, and the count of
    columns whose total crossing count is odd (a closed mesh has none; those columns are filled up to the grid end)."""
    nx, ny, nz = shape
    ys = o[1] + h * (np.arange(ny) + 0.5) + JITTER[0] * h
    zs = o[2] + h * (np.arange(nz) + 0.5) + JITTER[1] * h
    cols, xs = [], []
    for tri in f:
        P = v[tri]
        j0, j1 = np.searchsorted(ys, P[:, 1].min()), np.searchsorted(ys, P[:, 1].max(), side="right")
        k0, k1 = np.searchsorted(zs, P[:, 2].min()), np.searchsorted(zs, P[:, 2].max(), side="right")
        if j0 >= j1 or k0 >= k1:
            continue
        (y0, z0), (y1, z1), (y2, z2) = P[:, 1:]
        den = (y1 - y0) * (z2 - z0) - (y2 - y0) * (z1 - z0)
        if den == 0:
            continue
        J, K = np.meshgrid(np.arange(j0, j1), np.arange(k0, k1), indexing="ij")
        Y, Z = ys[J], zs[K]
        l1 = ((Y - y0) * (z2 - z0) - (y2 - y0) * (Z - z0)) / den
        l2 = ((y1 - y0) * (Z - z0) - (Y - y0) * (z1 - z0)) / den
        ok = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        if not ok.any():
            continue
        cols.append(J[ok] * nz + K[ok])
        xs.append(P[0, 0] + l1[ok] * (P[1, 0] - P[0, 0]) + l2[ok] * (P[2, 0] - P[0, 0]))
    flat = np.zeros((nx, ny * nz), bool)
    if not cols:
        return flat.reshape(shape), 0
    cols, xs = np.concatenate(cols), np.concatenate(xs)
    order = np.lexsort((xs, cols))
    cols, xs = cols[order], xs[order]
    xc = o[0] + h * (np.arange(nx) + 0.5)
    odd = 0
    starts = np.r_[0, np.flatnonzero(np.diff(cols)) + 1, len(cols)]
    for s0, s1 in zip(starts[:-1], starts[1:]):
        x = xs[s0:s1]
        if len(x) % 2:
            odd += 1
            x = np.r_[x, np.inf]
        for a, b in zip(x[0::2], x[1::2]):
            flat[(xc >= a) & (xc < b), cols[s0]] = True
    return flat.reshape(shape), odd


def signed_distance_grid(inside, ff, v, centres, h):
    """Signed distance (positive inside) of the grid cell centres (n, 3) to the skin of the triangles ff.

    Voxel EDT gives a first value (about +-h/2 off); within BAND_MM of the skin the distance is then a nearest-sample query against the
    skin sampled at SAMPLE_MM, and deeper cells take min over the band's inner-edge cells of (distance to the cell + its own sd), which is
    exact up to the lateral spacing of those cells. A direct query for every cell is not used: along the medial axis the nearest skin is
    equidistant from thousands of samples and the k-d tree degenerates (minutes for a thigh)."""
    ins = inside.ravel()
    edt_in = ndimage.distance_transform_edt(inside, sampling=h).ravel()
    edt_out = ndimage.distance_transform_edt(~inside, sampling=h).ravel()
    coarse = np.where(ins, edt_in - h / 2, -(edt_out - h / 2))
    band = np.abs(coarse) < BAND_MM
    tree = cKDTree(sample_surface(v, ff))
    d, _ = tree.query(centres[band], distance_upper_bound=2 * BAND_MM, workers=-1)
    d = np.where(np.isfinite(d), d, 2 * BAND_MM)
    sd = coarse.copy()
    sd[band] = np.where(ins[band], d, -d)
    for sign in (1, -1):                       # deep inside, then far outside
        deep = (sign * coarse) >= BAND_MM
        if not deep.any():
            continue
        edge = band & ((sign * sd) > BAND_MM - 2 * h) & ((sign * sd) <= BAND_MM)
        if not edge.any():
            continue
        et = cKDTree(centres[edge])
        k = min(6, int(edge.sum()))
        dd, ii = et.query(centres[deep], k=k, workers=-1)
        dd = dd.reshape(len(dd), -1)
        ii = ii.reshape(len(ii), -1)
        sd[deep] = sign * (dd + np.abs(sd[edge][ii])).min(axis=1)
    return sd


@dataclass
class Segment:
    o: np.ndarray                 # grid origin (corner of cell 0), mm, segment frame
    h: float                      # voxel size, mm
    sd: np.ndarray                # signed distance to the skin at the cell centres, positive inside
    region: np.ndarray            # bool: the segment (slab, side, connected component)
    length: float                 # slab length, mm
    z_top: float
    zweight: np.ndarray           # per z layer: fraction inside the slab
    odd_columns: int = 0
    meta: dict = dc_field(default_factory=dict)

    def signed_distance(self, points) -> np.ndarray:
        """sd at points (n, 3) in the segment frame, trilinear. Outside the grid: the nearest grid value minus the distance to the grid."""
        p = np.atleast_2d(np.asarray(points, float))
        g = (p - self.o) / self.h - 0.5
        gc = np.clip(g, 0, np.array(self.sd.shape) - 1)
        val = ndimage.map_coordinates(self.sd, gc.T, order=1, mode="nearest")
        return val - np.linalg.norm((g - gc) * self.h, axis=1)

    def centres(self, axis):
        return self.o[axis] + self.h * (np.arange(self.sd.shape[axis]) + 0.5)

    def _fraction(self, t):
        """Per-voxel inside fraction of {sd >= t}: a linear ramp one voxel wide, which removes the staircase bias of a hard threshold."""
        return np.clip(0.5 + (self.sd - t) / self.h, 0.0, 1.0)

    def volume(self, t=0.0, s0=0.0, s1=None) -> float:
        """Volume (mm3) of {sd >= t} inside the segment between stations s0 and s1 (default the whole slab; stations are distances below z_top)."""
        s1 = self.length if s1 is None else s1
        zl = self.centres(2)
        w = np.clip((zl - (self.z_top - s1)) / self.h + 0.5, 0, 1) * np.clip((self.z_top - s0 - zl) / self.h + 0.5, 0, 1) * self.zweight
        return float((self._fraction(t) * self.region * w[None, None, :]).sum() * self.h ** 3)

    def sd_max(self) -> float:
        return float(self.sd[self.region].max())

    def save(self, path):
        np.savez_compressed(path, o=self.o, h=self.h, sd=self.sd, region=self.region, length=self.length, z_top=self.z_top,
                            zweight=self.zweight, odd=self.odd_columns, meta=json.dumps(self.meta, sort_keys=True))

    @classmethod
    def load(cls, path):
        z = np.load(path, allow_pickle=False)
        return cls(o=z["o"], h=float(z["h"]), sd=z["sd"], region=z["region"], length=float(z["length"]), z_top=float(z["z_top"]),
                   zweight=z["zweight"], odd_columns=int(z["odd"]), meta=json.loads(str(z["meta"])))

    def in_region(self, points) -> np.ndarray:
        """Whether points (n, 3) lie in the segment region (slab, side, connected component); trilinear, threshold one half."""
        g = np.clip((np.atleast_2d(points) - self.o) / self.h - 0.5, 0, np.array(self.sd.shape) - 1)
        return ndimage.map_coordinates(self.region.astype(np.float32), g.T, order=1, mode="nearest") >= 0.49

    def section(self, s, extent=None):
        return Section(self, float(s), extent)


class Section:
    """The segment's cross-section at station s (distance below z_top): a 2-D raster at SECTION_MM of the field there."""

    def __init__(self, seg: Segment, s: float, extent=None):
        self.seg, self.s = seg, s
        z = seg.z_top - s
        lo = seg.o
        hi = seg.o + seg.h * np.array(seg.sd.shape)
        ext = extent or (lo[0], hi[0], lo[1], hi[1])
        self.x = np.arange(ext[0] + SECTION_MM / 2, ext[1], SECTION_MM)
        self.y = np.arange(ext[2] + SECTION_MM / 2, ext[3], SECTION_MM)
        X, Y = np.meshgrid(self.x, self.y, indexing="ij")
        pts = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, z)])
        self.sd = seg.signed_distance(pts).reshape(X.shape)
        g = np.clip((pts - seg.o) / seg.h - 0.5, 0, np.array(seg.sd.shape) - 1)
        reg = ndimage.map_coordinates(seg.region.astype(np.float32), g.T, order=1, mode="nearest")
        self.region = reg.reshape(X.shape) >= 0.49      # a station on the slab's end face sits exactly half way between a cell in and one out

    def mask(self, t=0.0):
        return (self.sd >= t) & self.region

    def area(self, t=0.0) -> float:
        return float(np.clip(0.5 + (self.sd - t) / SECTION_MM, 0, 1)[self.region].sum() * SECTION_MM ** 2)

    def perimeter(self, t=0.0) -> float:
        """Length (mm) of the contour {sd = t} inside the segment region: the skin's true section perimeter. Where the region's side clip (the
        midplane) cuts the section, the cut line is not part of it; contour pieces outside the region are dropped."""
        from contourpy import contour_generator
        gen = contour_generator(self.x, self.y, self.sd.T.astype(float))        # z[j, i] at (x_i, y_j)
        total = 0.0
        for line in gen.lines(t):
            xs, ys = line[:, 0], line[:, 1]
            mid = np.column_stack([(xs[:-1] + xs[1:]) / 2, (ys[:-1] + ys[1:]) / 2, np.full(len(xs) - 1, self.seg.z_top - self.s)])
            keep = self.seg.in_region(mid)
            total += float((np.hypot(np.diff(xs), np.diff(ys)) * keep).sum())
        return total

    def chebyshev(self, t=0.0):
        """(cx, cy, r) of the largest circle inside the section of {sd >= t}, mm, segment frame."""
        m = self.mask(t)
        if not m.any():
            return (float("nan"), float("nan"), 0.0)
        d = ndimage.distance_transform_edt(m, sampling=SECTION_MM)
        i, j = np.unravel_index(np.argmax(d), d.shape)
        return (float(self.x[i]), float(self.y[j]), float(d[i, j] - SECTION_MM / 2))

    def ray(self, origin, angle_deg, t=0.0, step=0.25, reach=300.0) -> float:
        """Distance from `origin` (x, y) to where {sd >= t} is left, along the direction `angle_deg` from +x towards +y; 0 when the origin
        is not inside, `reach` when it never leaves."""
        a = np.radians(angle_deg)
        r = np.arange(0.0, reach, step)
        pts = np.column_stack([origin[0] + r * np.cos(a), origin[1] + r * np.sin(a), np.full(len(r), self.seg.z_top - self.s)])
        inside = (self.seg.signed_distance(pts) >= t) & self.seg.in_region(pts)
        if not inside[0]:
            return 0.0
        if inside.all():
            return reach
        k = int(np.argmin(inside))
        sd = self.seg.signed_distance(pts[k - 1:k + 1]) - t
        if sd[1] >= 0 or sd[0] < 0:          # left the region (the midplane) rather than the skin: no crossing to interpolate
            return float(r[k - 1])
        return float(r[k - 1] + step * sd[0] / (sd[0] - sd[1]))


def build_segment(v, f, length, voxel, z_top=0.0, margin=40.0, xy=None, region_fn=None, seed_point=None):
    """Voxelise the extended solid (v, f) in the segment frame and return a Segment.

    xy: optional (xmin, xmax, ymin, ymax) of the grid; default the mesh extent. The grid spans z_top + margin down to z_top - length - margin
    (cell edges aligned to z_top). region_fn(X, Y, Z) gives a bool mask of the cell centres for the side clip; the slab is applied here.
    seed_point: a point inside the segment; when given, only the connected inside component of the region that holds it is kept.
    """
    v = np.asarray(v, float)
    f = np.asarray(f)
    h = float(voxel)
    ncell_top = int(np.ceil(margin / h))
    nz = ncell_top + int(np.ceil((length + margin) / h))
    x0, x1, y0, y1 = xy if xy else (v[:, 0].min() - 2 * h, v[:, 0].max() + 2 * h, v[:, 1].min() - 2 * h, v[:, 1].max() + 2 * h)
    o = np.array([x0, y0, z_top + ncell_top * h - nz * h])
    shape = (int(np.ceil((x1 - x0) / h)), int(np.ceil((y1 - y0) / h)), nz)
    box_lo, box_hi = o - 2 * BAND_MM, o + np.array(shape) * h + 2 * BAND_MM
    tri_lo, tri_hi = v[f].min(axis=1), v[f].max(axis=1)
    ff = f[np.all(tri_hi >= box_lo, axis=1) & np.all(tri_lo <= box_hi, axis=1)]
    inside, odd = parity_inside(v, ff, o, h, shape)
    C = [o[i] + h * (np.arange(shape[i]) + 0.5) for i in range(3)]
    X, Y, Z = np.meshgrid(*C, indexing="ij")
    sd = signed_distance_grid(inside, ff, v, np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]), h).reshape(shape)
    zl = C[2]
    zweight = np.clip((zl - (z_top - length)) / h + 0.5, 0, 1) * np.clip((z_top - zl) / h + 0.5, 0, 1)
    region = np.broadcast_to((zweight > 0)[None, None, :], shape) & (region_fn(X, Y, Z) if region_fn else True)
    if seed_point is not None:
        lab, _ = ndimage.label(region & inside)
        gi = np.floor((np.asarray(seed_point, float) - o) / h).astype(int)
        if not (np.all(gi >= 0) and np.all(gi < shape)) or lab[tuple(gi)] == 0:
            raise ValueError("seed point is not inside the segment region")
        # one voxel of dilation keeps the partially covered boundary cells (centre just outside) that the volume ramp counts
        region &= ndimage.binary_dilation(lab == lab[tuple(gi)])
    return Segment(o=o, h=h, sd=sd, region=region, length=float(length), z_top=float(z_top), zweight=zweight, odd_columns=odd)
