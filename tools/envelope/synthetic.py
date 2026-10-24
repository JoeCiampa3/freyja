"""Closed triangle meshes with analytic answers, for testing the envelope field and the oracle (segment frame, mm, z up)."""
import numpy as np


def frustum(r0, r1, z0, z1, n=240):
    """Closed frustum (cylinder when r0 == r1): radius r0 at z0, r1 at z1, caps included."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = lambda r, z: np.column_stack([r * np.cos(a), r * np.sin(a), np.full(n, z)])
    v = np.vstack([ring(r0, z0), ring(r1, z1), [[0, 0, z0]], [[0, 0, z1]]])
    c0, c1 = 2 * n, 2 * n + 1
    f = []
    for i in range(n):
        j = (i + 1) % n
        f += [(i, j, n + j), (i, n + j, n + i), (c0, j, i), (c1, n + i, n + j)]
    return v, np.array(f)


def box(hx, hy, hz, center=(0, 0, 0)):
    c = np.array([[sx * hx, sy * hy, sz * hz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float) + center
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    f = []
    for a, b, c_, d in quads:
        f += [(a, b, c_), (a, c_, d)]
    return c, np.array(f)


def frustum_volume(r0, r1, h):
    return np.pi * h / 3 * (r0 * r0 + r0 * r1 + r1 * r1)


def report(voxel=2.0):
    """Errors of the field against the analytic solids, each expressed as a surface displacement in mm: |dV| / surface area, |dA| / perimeter,
    |dr|. Three solids: a cylinder, a box and a tapered cone, each 300 mm long in a slab with 40 mm extension beyond both ends."""
    from . import field
    H = 300.0
    out = {}

    def seg_of(v, f):
        return field.build_segment(v, f, length=H, voxel=voxel, z_top=0.0, margin=40.0)

    R = 45.0
    s = seg_of(*frustum(R, R, 80, -H - 80))
    sec = s.section(150.0)
    out["cylinder"] = {"volume": abs(s.volume() - np.pi * R * R * H) / (2 * np.pi * R * H), "section_area": abs(sec.area() - np.pi * R * R) / (2 * np.pi * R),
                       "inscribed_radius": abs(sec.chebyshev()[2] - R)}
    hx, hy = 40.0, 25.0
    s = seg_of(*box(hx, hy, (H + 160) / 2, center=(0, 0, -H / 2)))
    sec = s.section(100.0)
    surf = 2 * (2 * hx * 2 * hy) + 2 * (2 * hx + 2 * hy) * H
    out["box"] = {"volume": abs(s.volume() - 4 * hx * hy * H) / surf, "section_area": abs(sec.area() - 4 * hx * hy) / (4 * (hx + hy)),
                  "inscribed_radius": abs(sec.chebyshev()[2] - hy)}
    r0, r1 = 60.0, 30.0
    slope = (r0 - r1) / H
    s = seg_of(*frustum(r0 + slope * 80, r1 - slope * 80, 80, -H - 80))
    surf = np.pi * (r0 + r1) * np.hypot(H, r0 - r1) + np.pi * (r0 ** 2 + r1 ** 2)
    e = {"volume": abs(s.volume() - frustum_volume(r0, r1, H)) / surf, "section_area": 0.0, "inscribed_radius": 0.0}
    for st in (20.0, 150.0, 280.0):
        r = r0 + (r1 - r0) * st / H
        sec = s.section(st)
        e["section_area"] = max(e["section_area"], abs(sec.area() - np.pi * r * r) / (2 * np.pi * r))
        e["inscribed_radius"] = max(e["inscribed_radius"], abs(sec.chebyshev()[2] - r))
    out["cone"] = e
    return out


def tube(r, z0, z1, rings, n=120):
    """Closed cylinder with `rings` rings between z0 and z1 (so a height-dependent transform bends it smoothly), caps included."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    zs = np.linspace(z0, z1, rings)
    v = [np.column_stack([r * np.cos(a), r * np.sin(a), np.full(n, z)]) for z in zs]
    v = np.vstack(v + [[[0, 0, z0]], [[0, 0, z1]]])
    c0, c1 = n * rings, n * rings + 1
    f = []
    for k in range(rings - 1):
        for i in range(n):
            j = (i + 1) % n
            f += [(k * n + i, k * n + j, (k + 1) * n + j), (k * n + i, (k + 1) * n + j, (k + 1) * n + i)]
    for i in range(n):
        j = (i + 1) % n
        f += [(c0, j, i), (c1, (rings - 1) * n + i, (rings - 1) * n + j)]
    return v, np.array(f)
