"""Occupancy of a segment's envelope (volume-extractor brief 6, items 3 and 4): the margin of posed candidate shapes to the registry's components, the free field once the
components (dilated by their clearance, swept over their poses) are removed, and the exact distance between two meshes.

Distances are signed distances between surfaces, never to a cut plane. A component's solid has an analytic signed distance (cylinder, capsule, box, a capsule chain) or, for a mesh, the
voxel field of `field.build_segment` at MESH_VOXEL_MM. The margin of a candidate to a component is the smaller of (the component's signed distance at the candidate's surface samples)
and (the candidate's signed distance at the component's surface samples), minus the component's clearance: positive when separate, negative when they overlap, and the overlap case
is caught whichever solid is inside the other.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from . import field, oracle, registry

MESH_VOXEL_MM = 1.0           # the voxel size of a mesh component's signed-distance field (the accuracy of a mesh margin; the exact distance of the binding pair replaces it)
ROUND_SEGMENTS = 96           # facets around a cylinder or capsule when a candidate is turned into triangles for the exact distance (the inscribed polygon is 0.05% of the radius short)
PAIR_CHUNK = 200_000


def _R(rpy) -> np.ndarray:
    return Rotation.from_euler("xyz", np.asarray(rpy, float), degrees=True).as_matrix()


# ---- analytic signed distances (positive outside) ----------------------------------------------------------------------------------------

def shape_sdf(shape: dict, pose=(0.0,) * 6):
    """Signed distance function (positive outside, mm) of one oracle shape placed at `pose`: the shape's own `rpy_deg` and `offset` first, then the pose, as `oracle.sample_shape` and
    `oracle.pose_points` do."""
    pose = np.asarray(pose, float)
    Rp, t = _R(pose[3:]), pose[:3]
    Rs, off = _R(shape.get("rpy_deg", (0, 0, 0))), np.asarray(shape.get("offset", (0, 0, 0)), float)
    kind = shape["type"]

    def sd(P):
        q = ((np.atleast_2d(P) - t) @ Rp - off) @ Rs
        if kind in ("cylinder", "capsule"):
            r = float(shape["radius"]) if "radius" in shape else float(shape["diameter"]) / 2
            half = float(shape["length"]) / 2
            rho = np.hypot(q[:, 0], q[:, 1])
            if kind == "capsule":
                return np.hypot(rho, q[:, 2] - np.clip(q[:, 2], -half, half)) - r
            d1, d2 = rho - r, np.abs(q[:, 2]) - half
            return np.minimum(np.maximum(d1, d2), 0.0) + np.hypot(np.maximum(d1, 0.0), np.maximum(d2, 0.0))
        half = np.asarray(shape["half"], float)
        d = np.abs(q) - half
        return np.linalg.norm(np.maximum(d, 0.0), axis=1) + np.minimum(d.max(axis=1), 0.0)
    return sd


def _segment_distance(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-300), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def chain_sdf(polyline, radius: float, pose=(0.0,) * 6):
    """Signed distance (positive outside) of a chain of capsules of one radius along `polyline` (component frame), placed at `pose`."""
    pl = np.asarray(polyline, float)
    pose = np.asarray(pose, float)
    Rp, t = _R(pose[3:]), pose[:3]

    def sd(P):
        q = (np.atleast_2d(P) - t) @ Rp
        return np.min([_segment_distance(q, pl[i], pl[i + 1]) for i in range(len(pl) - 1)], axis=0) - radius
    return sd


def min_bend_radius(polyline) -> float:
    """Smallest circumradius of three consecutive polyline points (mm): the radius a cable follows at that vertex. Straight runs are infinite."""
    pl = np.asarray(polyline, float)
    best = np.inf
    for a, b, c in zip(pl[:-2], pl[1:-1], pl[2:]):
        ab, bc, ca = np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)
        area2 = np.linalg.norm(np.cross(b - a, c - a))
        if area2 > 1e-12 and min(ab, bc) > 0:
            best = min(best, ab * bc * ca / (2.0 * area2))
    return float(best)


def _capsule_chain_samples(polyline, radius):
    pl = np.asarray(polyline, float)
    parts = []
    for a, b in zip(pl[:-1], pl[1:]):
        d = b - a
        L = float(np.linalg.norm(d))
        if L < 1e-9:
            continue
        u = d / L
        z = np.array([0.0, 0.0, 1.0])
        v = np.cross(z, u)
        s, c = float(np.linalg.norm(v)), float(z @ u)
        if s < 1e-12:
            R = np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
        else:
            K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
            R = np.eye(3) + K + K @ K * ((1 - c) / s ** 2)
        pts = oracle.sample_shape({"type": "capsule", "radius": radius, "length": L})
        parts.append(pts @ R.T + (a + b) / 2)
    return np.vstack(parts)


# ---- a component's geometry --------------------------------------------------------------------------------------------------------------

class Body:
    """One registry component's solid in its own frame: surface samples and a signed-distance function; `placed(pose)` puts both in the segment frame."""

    def __init__(self, comp: registry.Component, reg: registry.Registry):
        self.comp = comp
        self.mesh_vf = None
        if comp.kind == "flexible":
            self._sd = chain_sdf(comp.polyline, comp.radius_mm)
            pts = _capsule_chain_samples(comp.polyline, comp.radius_mm)
            self.samples = pts[self._sd(pts) > -1e-6]                          # drop the samples buried where two capsules overlap: what is left is the chain's own surface
        elif comp.mesh:
            v, f = registry.read_stl(Path(reg.base) / comp.mesh)
            self.mesh_vf = (v, f)
            self.samples = field.sample_surface(v, f, oracle.SAMPLE_MM)
            seg = field.build_segment(v, f, length=float(np.ptp(v[:, 2])), voxel=MESH_VOXEL_MM, z_top=float(v[:, 2].max()), margin=10.0)
            self._sd = lambda P, seg=seg: -seg.signed_distance(P)
        else:
            self.samples = oracle.sample_shape(comp.primitive)
            self._sd = shape_sdf(comp.primitive)

    def placed(self, pose):
        pose = np.asarray(pose, float)
        Rp, t = _R(pose[3:]), pose[:3]
        return self.samples @ Rp.T + t, (lambda P: self._sd((np.atleast_2d(P) - t) @ Rp))

    def triangles(self, pose):
        """(vertices, faces) of the solid in the segment frame, for the exact distance; None when the component is not a mesh (an analytic solid has no triangles to be exact about)."""
        if self.mesh_vf is None:
            return None
        v, f = self.mesh_vf
        pose = np.asarray(pose, float)
        return v @ _R(pose[3:]).T + pose[:3], f


# ---- margin to the components -------------------------------------------------------------------------------------------------------------

def component_margins(shapes, poses, reg: registry.Registry, z_top: float = 0.0) -> list:
    """For every placed component of `reg`, the least margin over all candidate poses, shapes and the component's sweep poses (signed distance between the surfaces minus the
    component's clearance, mm). Each entry: name, id, status, clearance_mm, distance_mm (before the clearance), margin_mm, pose_index (candidate), component_pose_index, shape, point_mm
    (where the surfaces are closest, segment frame), station_mm, bend (flexible components) and `_binding`, the objects the exact distance needs."""
    poses = np.atleast_2d(np.asarray(poses, float))
    if poses.shape[1] == 3:
        poses = np.hstack([poses, np.zeros((len(poses), 3))])
    cand = [(s.get("name", f"shape{i}"), s, oracle.sample_shape(s)) for i, s in enumerate(shapes)]
    out = []
    for comp in reg.placed():
        body = Body(comp, reg)
        cposes = reg.poses(comp)
        best = None
        for pi, pose in enumerate(poses):
            for name, shape, pts in cand:
                P = oracle.pose_points(pts, pose)
                f_shape = shape_sdf(shape, pose)
                for ci, cp in enumerate(cposes):
                    Q, f_comp = body.placed(cp)
                    d1, d2 = f_comp(P), f_shape(Q)
                    j1, j2 = int(np.argmin(d1)), int(np.argmin(d2))
                    d, pt = (float(d1[j1]), P[j1]) if d1[j1] <= d2[j2] else (float(d2[j2]), Q[j2])
                    if best is None or d < best["distance_mm"]:
                        best = {"distance_mm": d, "pose_index": pi, "component_pose_index": ci, "shape": name, "point_mm": [float(x) for x in pt]}
        best.update({"name": comp.name, "id": comp.id, "status": comp.status, "clearance_mm": comp.clearance_mm, "margin_mm": best["distance_mm"] - comp.clearance_mm,
                     "station_mm": z_top - best["point_mm"][2], "sweep_poses": len(cposes)})
        if comp.kind == "flexible":
            br = min_bend_radius(comp.polyline)
            best["bend"] = {"min_radius_mm": br if np.isfinite(br) else None, "required_mm": comp.bend_radius_mm, "ok": bool(br >= comp.bend_radius_mm)}
        sh = next(s for n, s, _ in cand if n == best["shape"])
        best["_binding"] = (body, cposes[best["component_pose_index"]], sh, poses[best["pose_index"]])
        out.append(best)
    return out


def component_skin_margins(skin_sd, reg: registry.Registry) -> dict:
    """For every placed component, the least signed distance (mm, positive inside) from its surface samples to the skin over all its poses: a negative value is a component sticking
    out of the skin, a registry fault worth a warning, not a property of any candidate. `skin_sd` maps points (n, 3) to the skin's signed distance."""
    out = {}
    for comp in reg.placed():
        body = Body(comp, reg)
        out[comp.name] = float(min(skin_sd(body.placed(p)[0]).min() for p in reg.poses(comp)))
    return out


# ---- exact distance between two triangle meshes ---------------------------------------------------------------------------------------------

def _point_segment(P, A, B):
    AB = B - A
    t = np.clip(((P - A) * AB).sum(1) / np.maximum((AB * AB).sum(1), 1e-300), 0.0, 1.0)
    return np.linalg.norm(P - (A + t[:, None] * AB), axis=1)


def _point_triangle(P, A, B, C):
    """Distance from points to triangles, row by row: the plane distance when the foot of the perpendicular is inside, else the least distance to the three edges."""
    ab, ac = B - A, C - A
    n = np.cross(ab, ac)
    nn = np.linalg.norm(n, axis=1)
    ok = nn > 1e-12
    nh = n / np.where(ok, nn, 1.0)[:, None]
    t = ((P - A) * nh).sum(1)
    F = P - t[:, None] * nh
    side = lambda U, V, W: (np.cross(V - U, W - U) * nh).sum(1) >= 0          # W is on the inner side of the edge U-V
    inside = ok & side(A, B, F) & side(B, C, F) & side(C, A, F)
    edges = np.minimum(np.minimum(_point_segment(P, A, B), _point_segment(P, B, C)), _point_segment(P, C, A))
    return np.where(inside, np.abs(t), edges)


def _segment_segment(P1, Q1, P2, Q2):
    """Least distance between segments P1Q1 and P2Q2, row by row (Ericson, Real-Time Collision Detection 5.1.9)."""
    d1, d2, r = Q1 - P1, Q2 - P2, P1 - P2
    a, e, f = (d1 * d1).sum(1), (d2 * d2).sum(1), (d2 * r).sum(1)
    c, b = (d1 * r).sum(1), (d1 * d2).sum(1)
    den = a * e - b * b
    eps = 1e-12
    s = np.where(den > eps * np.maximum(a * e, eps), np.clip((b * f - c * e) / np.where(den > eps, den, 1.0), 0.0, 1.0), 0.0)
    t = (b * s + f) / np.maximum(e, eps)
    s = np.where(t < 0, np.clip(-c / np.maximum(a, eps), 0, 1), np.where(t > 1, np.clip((b - c) / np.maximum(a, eps), 0, 1), s))
    t = np.clip(t, 0.0, 1.0)
    s = np.where((a <= eps), 0.0, s)
    t = np.where((e <= eps), 0.0, t)
    return np.linalg.norm((P1 + s[:, None] * d1) - (P2 + t[:, None] * d2), axis=1)


def triangle_distance(TA, TB):
    """Least distance between triangle pairs, row by row: TA, TB are (n, 3, 3). Exact for triangles that do not intersect (the distance of intersecting triangles is 0 and is
    returned as the least of the vertex and edge distances, which is not 0: callers use the sign of the margin for overlap)."""
    d = np.full(len(TA), np.inf)
    for i in range(3):
        d = np.minimum(d, _point_triangle(TA[:, i], TB[:, 0], TB[:, 1], TB[:, 2]))
        d = np.minimum(d, _point_triangle(TB[:, i], TA[:, 0], TA[:, 1], TA[:, 2]))
    for i in range(3):
        for j in range(3):
            d = np.minimum(d, _segment_segment(TA[:, i], TA[:, (i + 1) % 3], TB[:, j], TB[:, (j + 1) % 3]))
    return d


def mesh_distance(VA, FA, VB, FB) -> float:
    """Exact least distance (mm) between two triangle meshes that do not intersect. A sampled upper bound picks the triangle pairs that can hold the closest points, and the
    triangle distance is exact on those."""
    VA, VB = np.asarray(VA, float), np.asarray(VB, float)
    SA, SB = field.sample_surface(VA, FA, 2.0), field.sample_surface(VB, FB, 2.0)
    d0 = float(cKDTree(SB).query(SA, workers=-1)[0].min())
    TA, TB = VA[FA], VB[FB]
    cA, cB = TA.mean(axis=1), TB.mean(axis=1)
    rA, rB = np.linalg.norm(TA - cA[:, None], axis=2).max(axis=1), np.linalg.norm(TB - cB[:, None], axis=2).max(axis=1)
    reach = d0 + rA.max() + rB.max() + 1e-6
    pairs = cKDTree(cA).query_ball_tree(cKDTree(cB), reach)
    ia = np.repeat(np.arange(len(TA)), [len(p) for p in pairs])
    ib = np.concatenate([np.asarray(p, int) for p in pairs]) if len(ia) else np.zeros(0, int)
    keep = np.linalg.norm(cA[ia] - cB[ib], axis=1) <= d0 + rA[ia] + rB[ib]
    ia, ib = ia[keep], ib[keep]
    best = d0
    for s in range(0, len(ia), PAIR_CHUNK):
        best = min(best, float(triangle_distance(TA[ia[s:s + PAIR_CHUNK]], TB[ib[s:s + PAIR_CHUNK]]).min()))
    return best


def shape_mesh(shape: dict, pose=(0.0,) * 6):
    """Triangles (vertices, faces) of an oracle shape placed at `pose`: a box is 12 triangles, a cylinder or capsule a surface of revolution of ROUND_SEGMENTS facets."""
    kind = shape["type"]
    if kind == "box":
        hx, hy, hz = (float(x) for x in shape["half"])
        V = np.array([[sx * hx, sy * hy, sz * hz] for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)])
        F = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    else:
        r = float(shape["radius"]) if "radius" in shape else float(shape["diameter"]) / 2
        half = float(shape["length"]) / 2
        if kind == "cylinder":
            prof = [(0.0, -half), (r, -half), (r, half), (0.0, half)]
        else:
            k = max(4, ROUND_SEGMENTS // 4)
            ang = np.linspace(0, np.pi / 2, k + 1)
            prof = [(r * np.cos(a), -half - r * np.sin(a)) for a in ang[::-1]] + [(r * np.cos(a), half + r * np.sin(a)) for a in ang]
        n = ROUND_SEGMENTS
        th = np.linspace(0, 2 * np.pi, n, endpoint=False)
        V = np.array([[rr * np.cos(t), rr * np.sin(t), z] for rr, z in prof for t in th])
        F = []
        for i in range(len(prof) - 1):
            for j in range(n):
                a, b = i * n + j, i * n + (j + 1) % n
                c, d = (i + 1) * n + j, (i + 1) * n + (j + 1) % n
                F += [[a, b, c], [b, d, c]]
        F = np.array(F)
    if "rpy_deg" in shape:
        V = V @ _R(shape["rpy_deg"]).T
    if "offset" in shape:
        V = V + np.asarray(shape["offset"], float)
    pose = np.asarray(pose, float)
    return V @ _R(pose[3:]).T + pose[:3], F


def exact_binding_distance(entry: dict):
    """The exact mesh-to-mesh distance (mm, before the clearance) for the pair a margin entry binds on, or None when the component is not a mesh. `interpenetrating` is true when the
    sampled signed distance is negative: the meshes then overlap and the exact distance of separate meshes is not defined."""
    body, cpose, shape, pose = entry["_binding"]
    tri = body.triangles(cpose)
    if tri is None:
        return None
    if entry["distance_mm"] < 0:
        return {"exact_mm": None, "interpenetrating": True}
    VB, FB = shape_mesh(shape, pose)
    return {"exact_mm": mesh_distance(tri[0], tri[1], VB, FB), "interpenetrating": False}


# ---- the free field ---------------------------------------------------------------------------------------------------------------------

def _stack_parts(parts):
    """Lattice and slab of the union of segments: `parts` is a list of (segment, offset of its frame origin in the first part's frame). Returns the virtual Segment's grid origin, shape
    and the (top, length) of the slab. The lattice is the first segment's, extended."""
    s0 = parts[0][0]
    lo = np.min([seg.o + np.asarray(off, float) for seg, off in parts], axis=0)
    hi = np.max([seg.o + np.asarray(off, float) + seg.h * np.array(seg.sd.shape) for seg, off in parts], axis=0)
    o = s0.o + s0.h * np.floor((lo - s0.o) / s0.h + 1e-9)
    shape = tuple(int(x) for x in np.ceil((hi - o) / s0.h - 1e-9))
    top = max(seg.z_top + off[2] for seg, off in parts)
    bottom = min(seg.z_top - seg.length + off[2] for seg, off in parts)
    return o, shape, float(top), float(top - bottom)


def skin_field(parts, required: float):
    """The skin field {sd >= required} as a Segment-like grid: (o, h, sd, region, length, z_top, zweight). One part: the part's own arrays. Several: the union query of brief 5 on the
    first part's lattice: a cell in some part's slab takes the larger of the signed distances of the parts that hold it; a cell in none takes the nearest part's value (masked out by
    the region)."""
    s0 = parts[0][0]
    if len(parts) == 1:
        return field.Segment(o=s0.o, h=s0.h, sd=s0.sd, region=s0.region, length=s0.length, z_top=s0.z_top, zweight=s0.zweight, meta=dict(s0.meta))
    o, shape, top, length = _stack_parts(parts)
    h = s0.h
    C = [o[i] + h * (np.arange(shape[i]) + 0.5) for i in range(3)]
    X, Y, Z = np.meshgrid(*C, indexing="ij")
    P = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    sd = np.full(len(P), -np.inf)
    region = np.zeros(len(P), bool)
    gap = np.full(len(P), np.inf)
    nearest = np.zeros(len(P))
    for seg, off in parts:
        local = P - np.asarray(off, float)
        inr = seg.in_region(local) & (local[:, 2] <= seg.z_top + h / 2) & (local[:, 2] >= seg.z_top - seg.length - h / 2)
        v = seg.signed_distance(local)
        d = np.maximum(np.maximum(local[:, 2] - seg.z_top, seg.z_top - seg.length - local[:, 2]), 0.0)
        sd = np.where(inr, np.maximum(sd, v), sd)
        region |= inr
        closer = d < gap
        nearest = np.where(closer, v, nearest)
        gap = np.where(closer, d, gap)
    sd = np.where(region, sd, nearest).reshape(shape)
    zl = C[2]
    zweight = np.clip((zl - (top - length)) / h + 0.5, 0, 1) * np.clip((top - zl) / h + 0.5, 0, 1)
    return field.Segment(o=o, h=h, sd=sd, region=region.reshape(shape) & (zweight > 0)[None, None, :], length=length, z_top=top, zweight=zweight, meta=dict(s0.meta))


def free_field(parts, regs, required: float = 0.0, sphere_from_station_mm: float = 0.0):
    """The free field of a segment (or of the union of adjacent bodies): {skin sd >= required} minus every placed component dilated by its clearance and swept over its poses.
    `parts` is [(segment, offset)], `regs` [(registry, offset)] (the offset moves a registry's components into the first part's frame; the frames are parallel). Returns a Segment whose
    sd is min(skin sd - required, least component sd - clearance), so `sd >= 0` is the free field and the sd itself is the distance to the skin and the components (the radius of the
    largest sphere that fits), plus a report dict. The largest sphere is searched from station `sphere_from_station_mm` down: the thigh's hip zone, where the extended skin runs on into
    the pelvis and the other thigh, is left out of it as it is of the ledger's inscribed-radius minimum."""
    skin = skin_field(parts, required)
    h = skin.h
    sd_skin = skin.sd - required
    occ = np.full(skin.sd.shape, np.inf)
    C = [skin.o[i] + h * (np.arange(skin.sd.shape[i]) + 0.5) for i in range(3)]
    idx = np.flatnonzero((sd_skin > 0).ravel())
    ii, jj, kk = np.unravel_index(idx, skin.sd.shape)
    pts = np.column_stack([C[0][ii], C[1][jj], C[2][kk]])
    used = []
    flat = occ.ravel()
    for reg, off in regs:
        for comp in reg.placed():
            body = Body(comp, reg)
            poses = reg.poses(comp)
            poses = poses + np.r_[np.asarray(off, float), 0.0, 0.0, 0.0]
            for pose in poses:
                _, f = body.placed(pose)
                flat[idx] = np.minimum(flat[idx], f(pts) - comp.clearance_mm)
            used.append({"name": comp.name, "id": comp.id, "status": comp.status, "owner": comp.owner, "clearance_mm": comp.clearance_mm, "poses": int(len(poses))})
    free_sd = np.minimum(sd_skin, flat.reshape(skin.sd.shape))
    virt = field.Segment(o=skin.o, h=h, sd=free_sd, region=skin.region, length=skin.length, z_top=skin.z_top, zweight=skin.zweight, meta=dict(skin.meta))
    skin_t = field.Segment(o=skin.o, h=h, sd=sd_skin, region=skin.region, length=skin.length, z_top=skin.z_top, zweight=skin.zweight)
    v_skin, v_free = skin_t.volume(0.0) / 1e6, virt.volume(0.0) / 1e6
    masked = np.where(virt.region & ((skin.z_top - C[2]) >= sphere_from_station_mm - 1e-9)[None, None, :], free_sd, -np.inf)
    k = np.unravel_index(int(np.argmax(masked)), masked.shape)
    r = float(masked[k])
    centre = [float(C[0][k[0]]), float(C[1][k[1]]), float(C[2][k[2]])]
    rep = {"components": used, "skin_volume_l": v_skin, "free_volume_l": v_free, "occupied_volume_l": v_skin - v_free,
           "largest_free_sphere": {"diameter_mm": 2 * r if r > 0 else 0.0, "centre_mm": centre, "station_mm": skin.z_top - centre[2], "searched_from_station_mm": sphere_from_station_mm}, "voxel_mm": h}
    return virt, rep


def inputs_hash(parts_meta, regs, required: float, union_names) -> str:
    """Twelve hex over everything a free ledger depends on: the segments' input hashes, each registry with its pose and mesh files, the required margin and the union."""
    h = hashlib.sha256()
    h.update(json.dumps({"segments": parts_meta, "required": required, "union": list(union_names)}, sort_keys=True).encode())
    for reg, off in regs:
        h.update(json.dumps(reg.to_dict(), sort_keys=True).encode() + json.dumps([float(x) for x in off]).encode())
        for c in reg.components:
            for f in (c.poses_file, c.mesh):
                if f:
                    h.update((Path(reg.base) / f).read_bytes())
    return h.hexdigest()[:12]
